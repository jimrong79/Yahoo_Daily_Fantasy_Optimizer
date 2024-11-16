import pandas as pd

def get_team_averages():
    url = "https://www.basketball-reference.com/leagues/NBA_2025.html"
    team_abbreviations = {
        "Indiana Pacers": "IND",
        "Milwaukee Bucks": "MIL",
        "Oklahoma City Thunder": "OKC",
        "Atlanta Hawks": "ATL",
        "Boston Celtics": "BOS",
        "Golden State Warriors": "GSW",
        "Dallas Mavericks": "DAL",
        "Sacramento Kings": "SAC",
        "Utah Jazz": "UTA",
        "Los Angeles Clippers": "LAC",
        "Phoenix Suns": "PHX",
        "Philadelphia 76ers": "PHI",
        "Los Angeles Lakers": "LAL",
        "New Orleans Pelicans": "NOP",
        "Denver Nuggets": "DEN",
        "Toronto Raptors": "TOR",
        "Washington Wizards": "WAS",
        "Cleveland Cavaliers": "CLE",
        "New York Knicks": "NYK",
        "Minnesota Timberwolves": "MIN",
        "Houston Rockets": "HOU",
        "Detroit Pistons": "DET",
        "Brooklyn Nets": "BKN",
        "San Antonio Spurs": "SAS",
        "Chicago Bulls": "CHI",
        "Orlando Magic": "ORL",
        "Miami Heat": "MIA",
        "Charlotte Hornets": "CHA",
        "Portland Trail Blazers": "POR",
        "Memphis Grizzlies": "MEM"
    }

    team_stats_tables = pd.read_html(url, match="Per Game Stats", flavor="lxml")
    selected_columns = ["Team", "PTS", "TRB", "AST", "STL", "BLK", "TOV"]
    desired_data = team_stats_tables[0][selected_columns]
    desired_data["Team"] = desired_data["Team"].map(team_abbreviations, na_action='ignore')

    return desired_data

if __name__ == "__main__":
    team_averages = get_team_averages()
    if team_averages is not None:
        print("NBA Team Averages (2023-24 Season):\n")
        print(team_averages)
    else:
        print("Unable to retrieve data. Please try again.")
