import math
import threading
import unicodedata
from pathlib import Path
from queue import Empty, Queue

import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import numpy as np
import pandas as pd
import soccerdata as sd

SEASONS = ["17-18","18-19","19-20", "20-21", "21-22", "22-23", "23-24", "24-25", "25-26"]
DURATA_PARTITA = 90
PARQUET_PATH = Path("Fanta_Stats.parquet")
MAX_CRONOLOGIA = 30
POS_COL = ("standard", "pos", "")
MAX_COLONNE_GRAFICI = 5


# --------------------------------------------------------------------------
# Data layer
# --------------------------------------------------------------------------

def normalize(s):
    """Minuscolo e senza accenti, per confronti tolleranti"""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def load(fbref, stat_type):
    d = fbref.read_player_season_stats(stat_type=stat_type)
    d.columns = pd.MultiIndex.from_tuples([(stat_type, *c) for c in d.columns])
    return d


def fbref_scraping(leagues="Big 5 European Leagues Combined", season=""):
    """Recupera i dati dal sito ufficiale FBref.com"""
    if not season:
        raise ValueError("No season specified")

    fbref = sd.FBref(leagues=leagues, seasons=season)

    # Recupero i dati di tutti i giocatori delle principali competizioni europee
    df = pd.concat([load(fbref, t) for t in ["standard", "keeper"]], axis=1)

    # Salvo il dataframe ottenuto
    df.to_parquet(PARQUET_PATH)

    return df


def create_player_season_stats(df):
    """Crea un DataFrame con statistiche aggregate su tutti i giocatori per stagione"""
    if df.empty:
        raise ValueError("No DataFrame to edit")

    player_season_rules = {
        ("standard", "pos", ""): moda,
        ("standard", "Playing Time", "Min"): "sum",
        ("standard", "Performance", "Gls"): "sum",
        ("standard", "Performance", "Ast"): "sum",
        ("standard", "Performance", "PK"): "sum",
        ("standard", "Performance", "PKatt"): "sum",
        ("standard", "Performance", "CrdY"): "sum",
        ("standard", "Performance", "CrdR"): "sum",
        ("keeper", "Performance", "GA"): "sum",
        ("keeper", "Performance", "Saves"): "sum",
    }

    out = df.groupby(["player", "season"]).agg(player_season_rules)
    out[("standard", "Playing Time", "N_Partite")] = (
        out[("standard", "Playing Time", "Min")] / DURATA_PARTITA
    )
    return out


def find_players(df, query):
    """Restituisce i nomi completi che contengono tutte le parole cercate"""
    if not query or not query.strip():
        raise ValueError("No player name specified")

    names = df.index.get_level_values("player").unique()
    words = normalize(query).split()

    return sorted(n for n in names if all(w in normalize(n) for w in words))


def get_player_season_stats(df, player_name):
    """Recupera le statistiche su più stagioni di un giocatore"""
    if df.empty:
        raise ValueError("No DataFrame to edit")
    if not player_name:
        raise ValueError("No player name specified")
    try:
        return df.xs(player_name, level="player")
    except KeyError:
        raise KeyError(f"No player found: {player_name}")


def get_player_stats(season_stats):
    """Media di carriera a partire dalle righe stagionali di un giocatore"""
    if season_stats.empty:
        raise ValueError("No DataFrame to edit")

    numeric = season_stats.drop(columns=[POS_COL]).mean()
    numeric[POS_COL] = moda(season_stats[POS_COL])
    return numeric[season_stats.columns]


# --------------------------------------------------------------------------
# Helper di presentazione
# --------------------------------------------------------------------------

def moda(s):
    """Valore più frequente, o NaN se la serie non ha valori validi"""
    m = s.mode()
    return m.iat[0] if not m.empty else np.nan

def column_label(col):
    """('standard', 'Playing Time', 'Min') -> 'Min'"""
    parts = [p for p in col if p]
    return parts[-1] if parts else ""


def format_value(v):
    if pd.isna(v):
        return ""
    if isinstance(v, float):
        return f"{v:.2f}" if v % 1 else f"{v:.0f}"
    return str(v)


def fill_tree(tree, df, index_title):
    """Riempie una Treeview con un DataFrame, usando l'indice come prima colonna"""
    tree.delete(*tree.get_children())

    labels, seen = [], {}
    for col in df.columns:
        label = column_label(col)
        if label in seen:
            seen[label] += 1
            label = f"{label}_{seen[label]}"
        else:
            seen[label] = 0
        labels.append(label)

    tree["columns"] = labels
    tree.heading("#0", text=index_title)
    tree.column("#0", width=110, minwidth=90, anchor="w", stretch=False)
    for label in labels:
        tree.heading(label, text=label)
        tree.column(label, width=78, minwidth=60, anchor="center", stretch=False)

    for idx, row in df.iterrows():
        tree.insert("", "end", text=str(idx), values=[format_value(v) for v in row])


# --------------------------------------------------------------------------
# Interfaccia
# --------------------------------------------------------------------------

class FantaApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)
        self.grid(row=0, column=0, sticky="nsew")
        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)

        self.season_stats = None      # DataFrame aggregato per giocatore/stagione
        self.matches = []             # Nomi trovati dall'ultima ricerca
        self.queue = Queue()          # Comunicazione dal thread di caricamento
        self.plot_data = None         # (nome, DataFrame stagionale) in attesa di essere disegnato
        self.plot_dirty = False       # I grafici mostrano dati vecchi

        self._build_widgets()
        self._start_loading()

    # -- costruzione UI ----------------------------------------------------

    def _build_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Riga di ricerca
        search = ttk.Frame(self)
        search.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        search.columnconfigure(1, weight=1)

        ttk.Label(search, text="Giocatore").grid(row=0, column=0, padx=(0, 8))

        self.query_var = tk.StringVar()
        self.entry = ttk.Entry(search, textvariable=self.query_var)
        self.entry.grid(row=0, column=1, sticky="ew")
        self.entry.bind("<Return>", lambda _e: self.on_search())

        self.search_btn = ttk.Button(search, text="Cerca", command=self.on_search)
        self.search_btn.grid(row=0, column=2, padx=(8, 0))

        # Corpo: elenco risultati a sinistra, tabelle a destra
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.grid(row=1, column=0, sticky="nsew")

        left = ttk.PanedWindow(paned, orient="vertical")

        self.results = self._make_name_tree(left, "Risultati")
        self.results.bind("<<TreeviewSelect>>", self.on_result_select)
        left.add(self.results.master, weight=3)

        self.history = self._make_name_tree(left, "Cercati di recente")
        self.history.bind("<<TreeviewSelect>>", self.on_history_select)
        ttk.Button(self.history.master, text="Svuota", width=8,
                   command=self.clear_history).grid(row=1, column=0, sticky="w", pady=(6, 0))
        left.add(self.history.master, weight=2)

        paned.add(left, weight=1)

        right = ttk.Frame(paned)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self.player_label = ttk.Label(right, text="Nessun giocatore selezionato",
                                      font=("TkDefaultFont", 13, "bold"))
        self.player_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.notebook = ttk.Notebook(right)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.notebook.bind("<<NotebookTabChanged>>", lambda _e: self._aggiorna_grafici())

        # Scheda "Stagioni": tabella sopra, grafici sotto
        season_tab = ttk.PanedWindow(self.notebook, orient="vertical")
        self.season_tree = self._make_tree(season_tab)
        season_tab.add(self.season_tree.master, weight=1)

        plot_frame = ttk.Frame(season_tab, padding=(6, 0, 6, 6))
        self.figure = Figure(figsize=(9, 3.4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        season_tab.add(plot_frame, weight=2)

        self.describe_tree = self._make_tree(self.notebook)
        self.career_tree = self._make_tree(self.notebook)

        self.notebook.add(season_tab, text="Stagioni")
        self.notebook.add(self.describe_tree.master, text="Riepilogo")
        self.notebook.add(self.career_tree.master, text="Media carriera")

        paned.add(right, weight=4)

        # Barra di stato
        status = ttk.Frame(self)
        status.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        status.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Caricamento dei dati…")
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

        self.progress = ttk.Progressbar(status, mode="indeterminate", length=140)
        self.progress.grid(row=0, column=1, sticky="e")
        self.progress.start(12)

        self.set_enabled(False)

    def _make_name_tree(self, parent, heading):
        """Treeview a colonna singola per un elenco di nomi"""
        frame = ttk.Frame(parent, padding=(0, 0, 8, 6))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        tree = ttk.Treeview(frame, show="tree headings", selectmode="browse", height=6)
        tree.heading("#0", text=heading)
        tree.column("#0", anchor="w", stretch=True)
        tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=vsb.set)

        return tree

    def _make_tree(self, parent):
        """Treeview con scrollbar orizzontale e verticale, dentro un Frame"""
        frame = ttk.Frame(parent, padding=6)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        tree = ttk.Treeview(frame, show="tree headings", selectmode="none")
        tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        return tree

    def set_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self.entry.configure(state=state)
        self.search_btn.configure(state=state)

    # -- caricamento dati in background -----------------------------------

    def _start_loading(self):
        threading.Thread(target=self._load_worker, daemon=True).start()
        self.after(100, self._poll_queue)

    def _load_worker(self):
        try:
            if PARQUET_PATH.is_file():
                df = pd.read_parquet(PARQUET_PATH)
            else:
                df = fbref_scraping(season=SEASONS)
            self.queue.put(("ok", create_player_season_stats(df)))
        except Exception as exc:  # il thread non deve morire in silenzio
            self.queue.put(("error", exc))

    def _poll_queue(self):
        try:
            kind, payload = self.queue.get_nowait()
        except Empty:
            self.after(100, self._poll_queue)
            return

        self.progress.stop()
        self.progress.grid_remove()

        if kind == "error":
            self.status_var.set("Caricamento non riuscito.")
            messagebox.showerror("Errore di caricamento", str(payload))
            return

        self.season_stats = payload
        n = self.season_stats.index.get_level_values("player").nunique()
        self.status_var.set(f"{n} giocatori disponibili.")
        self.set_enabled(True)
        self.entry.focus_set()

    # -- azioni ------------------------------------------------------------

    def on_search(self):
        if self.season_stats is None:
            return

        query = self.query_var.get()
        self.results.delete(*self.results.get_children())
        self.matches = []

        if not query.strip():
            self.status_var.set("Scrivi un nome per avviare la ricerca.")
            return

        self.matches = find_players(self.season_stats, query)

        if not self.matches:
            self.status_var.set(f"Nessun giocatore corrisponde a «{query}».")
            self._clear_stats()
            return

        for name in self.matches:
            self.results.insert("", "end", iid=name, text=name)

        if len(self.matches) == 1:
            self.results.selection_set(self.matches[0])
        else:
            self.status_var.set(f"{len(self.matches)} giocatori trovati. Scegline uno.")

    def on_result_select(self, _event):
        selection = self.results.selection()
        if selection:
            self.show_player(self.results.item(selection[0], "text"))

    def on_history_select(self, _event):
        selection = self.history.selection()
        if selection:
            self.show_player(self.history.item(selection[0], "text"))

    def show_player(self, player_name):
        season_stats = get_player_season_stats(self.season_stats, player_name).sort_index()
        career = get_player_stats(season_stats).to_frame().T
        career.index = ["media"]

        self.player_label.configure(text=player_name)
        fill_tree(self.season_tree, season_stats, "Stagione")
        fill_tree(self.describe_tree, season_stats.describe(), "Statistica")
        fill_tree(self.career_tree, career, "")
        self.status_var.set(f"{player_name} — {len(season_stats)} stagioni.")
        self._ricorda(player_name)

        self.plot_data = (player_name, season_stats)
        self.plot_dirty = True
        self._aggiorna_grafici()

    # -- grafici -----------------------------------------------------------

    def _aggiorna_grafici(self):
        """Ridisegna solo se la scheda Stagioni è quella visibile"""
        if not self.plot_dirty or self.notebook.index("current") != 0:
            return
        self._disegna_grafici()
        self.plot_dirty = False

    def _disegna_grafici(self):
        self.figure.clear()

        if self.plot_data is None:
            self.canvas.draw_idle()
            return

        player_name, stats = self.plot_data
        colonne = [c for c in stats.columns if c != POS_COL and stats[c].notna().any()]

        if not colonne:
            self.canvas.draw_idle()
            return

        n_colonne = min(MAX_COLONNE_GRAFICI, len(colonne))
        n_righe = math.ceil(len(colonne) / n_colonne)
        axes = self.figure.subplots(n_righe, n_colonne, squeeze=False)

        stagioni = [str(s) for s in stats.index]
        x = np.arange(len(stagioni))

        for ax, col in zip(axes.flat, colonne):
            valori = stats[col].astype(float).to_numpy()
            validi = ~np.isnan(valori)

            ax.plot(x, valori, marker="o", markersize=4, linewidth=1.4,
                    color="#4c72b0", label="valore")

            if validi.sum() >= 2:
                pendenza, intercetta = np.polyfit(x[validi], valori[validi], 1)
                ax.plot(x, pendenza * x + intercetta, linestyle="--", linewidth=1.2,
                        color="#c44e52", label="tendenza")

            ax.set_title(column_label(col), fontsize=9)
            ax.set_xticks(list(x))
            ax.set_xticklabels(stagioni, rotation=60, fontsize=7)
            ax.tick_params(axis="y", labelsize=7)
            ax.margins(x=0.08)

        for ax in axes.flat[len(colonne):]:
            ax.set_visible(False)

        self.figure.suptitle(player_name, fontsize=11)
        self.figure.legend(*axes.flat[0].get_legend_handles_labels(),
                           loc="upper right", fontsize=8, frameon=False)
        self.figure.tight_layout(rect=(0, 0, 1, 0.92))
        self.canvas.draw_idle()

    def _ricorda(self, player_name):
        """Aggiunge il giocatore in cima alla cronologia, se non è già presente"""
        if self.history.exists(player_name):
            return

        self.history.insert("", 0, iid=player_name, text=player_name)
        for eccedenza in self.history.get_children()[MAX_CRONOLOGIA:]:
            self.history.delete(eccedenza)

    def clear_history(self):
        self.history.delete(*self.history.get_children())

    def _clear_stats(self):
        self.player_label.configure(text="Nessun giocatore selezionato")
        for tree in (self.season_tree, self.describe_tree, self.career_tree):
            tree.delete(*tree.get_children())

        self.plot_data = None
        self.plot_dirty = True
        self._aggiorna_grafici()


def main():
    root = tk.Tk()
    root.title("Fantacalciooooo Analytics")
    root.geometry("1300x620")
    root.minsize(820, 460)
    FantaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()