from pydoc import describe

import soccerdata as sd
import pandas as pd
from pathlib import Path

pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
SEASONS = ["19-20","20-21","21-22","22-23", "23-24", "24-25", "25-26"]
DURATA_PARTITA = 90

import unicodedata

def normalize(s):
    """Minuscolo e senza accenti, per confronti tolleranti"""
    s = unicodedata.normalize('NFKD', str(s))
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()

def find_players(df, query):
    """Restituisce i nomi completi che contengono tutte le parole cercate"""
    if not query or not query.strip():
        raise ValueError("No player name specified")

    names = df.index.get_level_values('player').unique()
    words = normalize(query).split()

    return sorted(n for n in names if all(w in normalize(n) for w in words))

def load(fbref,stat_type):
    d = fbref.read_player_season_stats(stat_type=stat_type)
    d.columns = pd.MultiIndex.from_tuples([(stat_type, *c) for c in d.columns])
    return d

def fbref_scraping(leagues = 'Big 5 European Leagues Combined', season = ''):
    """Recupera i dati dal sito ufficiale FBref.com"""

    if not season:
        raise ValueError("No season specified")

    fbref = sd.FBref(leagues=leagues, seasons=season)

    # Rcupero i dati di tutti i giocatori delle principali competizioni europee
    df = pd.concat([load(fbref,t) for t in ["standard", "keeper"]], axis=1)

    #Salvo dataframe ottenuto
    df.to_parquet('Fanta_Stats.parquet')

    return df

def create_player_season_stats(df):
    """Crea un DataFrame con statistiche aggregate su tutti i giocatori per stagione"""
    if df.empty:
        raise ValueError("No DataFrame to edit")

    player_season_rules = {
        ('standard','pos', ''): lambda s: s.mode().iat[0],
        ('standard','Playing Time', 'Min'): "sum",
        ('standard','Performance', 'Gls'): 'sum',
        ('standard','Performance', 'Ast'): 'sum',
        ('standard','Performance', 'PK'): 'sum',
        ('standard','Performance', 'PKatt'): 'sum',
        ('standard','Performance', 'CrdY'): 'sum',
        ('standard','Performance', 'CrdR'): 'sum',
        ('keeper','Performance', 'GA'): 'sum',
        ('keeper', 'Performance', 'Saves'): 'sum'
    }

    player_season_summary_stats = df.groupby(['player', 'season']).agg(player_season_rules)
    player_season_summary_stats['standard','Playing Time', 'N_Partite'] = player_season_summary_stats[('standard','Playing Time', 'Min')] / DURATA_PARTITA

    return player_season_summary_stats

def get_player_season_stats(df,player_name):
    """Recupera le statistiche su più stagioni di un giocatore"""

    if df.empty:
        raise ValueError("No DataFrame to edit")
    if not player_name:
        raise ValueError("No player name specified")
    try:
        return df.xs(player_name, level='player')
    except KeyError:
        raise KeyError(f"No player player: {player_name} found")


def get_player_stats(df,player_name):
    """Recupera le statistiche aggregate di un singolo giocatore"""

    if df.empty:
        raise ValueError("No DataFrame to edit")
    if not player_name:
        raise ValueError("No player name specified")

    player_rules = {
        ('standard', 'pos', ''): lambda s: s.mode().iat[0],
        ('standard', 'Playing Time', 'Min'): "mean",
        ('standard', 'Performance', 'Gls'): 'mean',
        ('standard', 'Performance', 'Ast'): 'mean',
        ('standard', 'Performance', 'PK'): 'mean',
        ('standard', 'Performance', 'PKatt'): 'mean',
        ('standard', 'Performance', 'CrdY'): 'mean',
        ('standard', 'Performance', 'CrdR'): 'mean',
        ('keeper', 'Performance', 'GA'): 'mean',
        ('keeper', 'Performance', 'Saves'): 'mean'
    }
    try:
        player_summary_stats = df.groupby('player').agg(player_rules)
        return player_summary_stats.loc[player_name]

    except KeyError:
        raise KeyError(f"No player player: {player_name} found")

def select_player(df, query):
    matches = find_players(df, query)

    if not matches:
        raise KeyError(f"No player found: {query}")
    if len(matches) == 1:
        return matches[0]

    print(f"\nTrovati {len(matches)} giocatori:")
    for i, name in enumerate(matches, 1):
        print(f"  {i}. {name}")

    while True:
        scelta = input("Numero del giocatore: ").strip()
        if scelta.isdigit() and 1 <= int(scelta) <= len(matches):
            return matches[int(scelta) - 1]
        print("Scelta non valida.")

def main():
    file_path = Path('Fanta_Stats.parquet')
    if not file_path.is_file():
        df= fbref_scraping(season=SEASONS)
    else:
        df = pd.read_parquet(file_path)

    df_player_season_stats = create_player_season_stats(df)

    query = input("Inserisci nome del player: ")
    player_name = select_player(df_player_season_stats, query)

    player_season_stats = get_player_season_stats(df_player_season_stats,player_name)

    #player_stats = get_player_stats(df_player_season_stats, player_name)

    print(player_season_stats)
    print()
    print(player_season_stats.describe())


if __name__ == "__main__":
    main()



