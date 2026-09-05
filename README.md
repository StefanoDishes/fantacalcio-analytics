# ⚽ Fantacalcio Analytics

Un'app desktop in Python per non farsi fregare all'asta del fantacalcio.

Cerchi un giocatore, e in due secondi ti trovi davanti gol, assist, minuti, cartellini e parate
di **9 stagioni**, stagione per stagione, con tanto di grafici e linea di tendenza.
Così quando il tuo amico ti dice "eh ma lui l'anno scorso ha spaccato", tu apri l'app e gli fai
notare che sono tre anni che cala. 📉

I dati arrivano da [FBref](https://fbref.com) (tramite [soccerdata](https://github.com/probberechts/soccerdata))
e coprono i **Big 5 campionati europei** — Serie A, Premier League, Liga, Bundesliga e Ligue 1 —
dalla stagione 2017-18 alla 2025-26. In tutto circa **7.700 giocatori** e **25.000 righe** di statistiche.

---

## 🚀 Come si parte

Ti serve Python 3.10 o superiore. Poi:

```bash
git clone https://github.com/StefanoDishes/fantacalcio-analytics.git
cd fantacalcio-analytics
python3 -m venv .venv
source .venv/bin/activate        # su Windows: .venv\Scripts\activate
pip install -r requirements.txt
python fantacalcio_tkinter.py
```

E via, si apre la finestra.

> **Nota bella:** nel repo trovi già `Fanta_Stats.parquet`, cioè il database bello e pronto.
> Quindi al primo avvio **non devi scaricare niente**, parte subito.
> Se invece cancelli quel file, l'app si mette a scaricare tutto da FBref da sola —
> **bisogna avere Google Chrome installato**.

---

## 🖱️ Come si usa

1. **Scrivi un nome** nella casella in alto e premi Invio (o clicca *Cerca*).
   La ricerca è tollerante: niente accenti, niente maiuscole, e puoi scrivere anche solo pezzi
   di nome. `"lauta mar"` ti trova comunque Lautaro Martínez.
2. **Se salta fuori più di un giocatore**, li vedi nell'elenco a sinistra: clicchi quello giusto.
   Se ce n'è uno solo, viene selezionato in automatico.
3. **Guardi i numeri** nelle tre schede a destra:

   | Scheda | Cosa ci trovi |
   |---|---|
   | **Stagioni** | La tabella anno per anno + i grafici dell'andamento |
   | **Riepilogo** | Media, mediana, minimo, massimo, deviazione standard… il classico `describe()` |
   | **Media carriera** | Una riga sola con la media di tutte le stagioni: comoda per farsi un'idea al volo |

4. **I giocatori che hai già guardato** finiscono nella lista *Cercati di recente* in basso a sinistra
   (ne tiene 30). Durante l'asta è la cosa più utile che c'è: ci clicchi sopra e ritorni sul giocatore
   senza riscrivere niente. C'è anche il tasto *Svuota* se vuoi ripulire.

### 📊 I grafici

Nella scheda **Stagioni**, sotto la tabella, ogni statistica ha il suo grafichino:

- la **linea blu** è il valore reale stagione per stagione;
- la **tratteggiata rossa** è la retta di tendenza (regressione lineare).

Se la rossa punta in su il giocatore sta crescendo, se punta in giù… beh, magari lascialo prendere
a qualcun altro. 🙃

I grafici vengono ridisegnati solo quando guardi davvero la scheda Stagioni, così l'app resta reattiva.

---

## 📈 Quali statistiche vedi

Tutte aggregate per giocatore e stagione (somma delle presenze in campionato e coppe):

| Colonna | Significato |
|---|---|
| `pos` | Ruolo più frequente (DF, MF, FW, GK) |
| `Min` | Minuti giocati |
| `N_Partite` | Partite equivalenti, cioè minuti ÷ 90 |
| `Gls` | Gol |
| `Ast` | Assist |
| `PK` / `PKatt` | Rigori segnati / rigori calciati |
| `CrdY` / `CrdR` | Cartellini gialli / rossi |
| `GA` | Gol subiti (portieri) |
| `Saves` | Parate (portieri) |

`N_Partite` è il numero più sottovalutato di tutti: un attaccante da 10 gol in 15 partite equivalenti
vale molto più di uno da 12 gol in 35. Guardala sempre. 😉

---

## 🗂️ Cosa c'è nel repo

```
fantacalcio_tkinter.py   # l'app vera e propria, quella con l'interfaccia
Fanta_Stats.parquet      # il database pronto (Big 5, 2017-18 → 2025-26)
requirements.txt         # le librerie che servono
```

### Come funziona dentro, in breve

- All'avvio l'app carica il parquet **in un thread separato**, così la finestra non si blocca:
  vedi la barra di caricamento che gira e appena è pronto la casella di ricerca si sblocca.
  Il thread comunica col resto tramite una `Queue`, che è il modo pulito di farlo con Tkinter.
- I dati grezzi vengono raggruppati con `groupby(["player", "season"])`: le statistiche si sommano,
  il ruolo si prende con la moda (il valore più frequente).
- Le colonne sono un `MultiIndex` di pandas (roba tipo `("standard", "Performance", "Gls")`),
  ma nelle tabelle vedi solo l'ultimo pezzo, quello leggibile.
- L'interfaccia è tutta `tkinter` + `ttk`, i grafici sono `matplotlib` col backend `TkAgg`
  incastrato dentro la finestra.

---

## 🔄 Aggiornare i dati

Il parquet nel repo è una fotografia. Per rifarla da zero con i dati freschi:

```bash
rm Fanta_Stats.parquet
python fantacalcio_tkinter.py
```

Al riavvio l'app se ne accorge e riscarica tutto da FBref. Ci mette un po', quindi fallo quando
hai da fare altro. Le stagioni scaricate sono quelle nella lista `SEASONS` in cima al file:
se ne vuoi di più o di meno, modifichi lì.

---

## 🧯 Se qualcosa non va

**`ModuleNotFoundError: No module named 'tkinter'`**
Tkinter non è incluso in alcune installazioni di Python. Su macOS con Homebrew: `brew install python-tk`.
Su Debian/Ubuntu: `sudo apt install python3-tk`. Su Windows di solito c'è già.

**Il download da FBref si pianta o dà errore**
FBref limita le richieste. Aspetta qualche minuto e riprova, oppure tieni il parquet che trovi qui
e non pensarci più.

**La finestra è troppo piccola / i grafici sono schiacciati**
Allargala pure, si adatta. Il minimo è 820×460, ma dallo schermo intero si vede molto meglio.

---

Buona asta 🏆
