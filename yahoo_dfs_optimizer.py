import sys
import time
from dataclasses import dataclass

import pandas as pd
import requests
from bs4 import BeautifulSoup
from pulp import LpMaximize, LpAffineExpression, LpVariable, LpProblem
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from unidecode import unidecode


@dataclass
class ContestData:
    contest_id: int
    team_opponents: dict
    inactive_players: dict
    salaries: dict
    player_teams: dict
    player_positions: dict


def get_dvp_by_position(driver):
    """
    Fetches Defense Versus Position (DVP) data for each NBA team and position.

    Parameters:
        driver: Selenium WebDriver instance.

    Returns:
        dict: A dictionary where keys are positions (PG, SG, SF, PF, C) and values are DataFrames containing DVP stats.
    """
    dvp_data = {}
    url = "https://basketballmonster.com/easerankings.aspx"
    position_options = {"3": "C", "4": "PG", "5": "SG", "6": "SF", "7": "PF"}
    driver.get(url)

    date_filter_xpath = "//select[@name='DateFilterControl']/option[@value='{}']"
    position_dropdown_xpath = "//select[@name='ctl00$ContentPlaceHolder1$PositionDropDownList']/option[@value='{}']"

    # Set date filter to 'Past 2 Weeks'
    try:
        date_option = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, date_filter_xpath.format("LastTwoWeeks")))
        )
        date_option.click()
        WebDriverWait(driver, 10).until(
            EC.text_to_be_present_in_element(
                (By.XPATH, date_filter_xpath.format("LastTwoWeeks")), "Past 2 Weeks"
            )
        )
    except Exception as e:
        print(f"Error setting date filter: {e}")
        driver.quit()
        return {}

    for option_value, position in position_options.items():
        try:
            # Select position from dropdown
            position_option = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, position_dropdown_xpath.format(option_value)))
            )
            position_option.click()
            WebDriverWait(driver, 10).until(
                EC.text_to_be_present_in_element(
                    (By.XPATH, position_dropdown_xpath.format(option_value)), position
                )
            )

            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            table_rows = soup.find_all('tr')
            headers = [th.get_text() for th in table_rows[0].find_all('th')]
            data_rows = table_rows[1:]

            dvp_stats = []
            for row in data_rows:
                cols = row.find_all('td')
                dvp_stats.append([col.get_text() for col in cols])

            # Process team names and corrections
            for stats in dvp_stats:
                team_name = stats[0].replace("vs", "").strip()
                team_name = team_name.replace("NOR", "NOP").replace("CHA", "CHO")
                stats[0] = team_name

            dvp_df = pd.DataFrame(dvp_stats, columns=headers)
            dvp_df.drop(columns=['Value', 'pV', 'rV', 'aV', 'sV', 'bV', 'toV'], inplace=True)
            dvp_df.set_index("vs Team", inplace=True)
            dvp_data[position] = dvp_df

        except Exception as e:
            print(f"Error processing position {position}: {e}")
            continue

    driver.quit()
    return dvp_data


def formalize_name(name):
    """
    Formats player names to a consistent format used in Yahoo Fantasy.

    Parameters:
        name (str): Player's name.

    Returns:
        str: Player's name after uniform formatting.
    """
    corrections = {
        "Jakob Poltl": "Jakob Poeltl",
        "Taurean Waller-Prince": "Taurean Prince",
        "Mo Bamba": "Mohamed Bamba",
        "Bojan Bogdanović": "Bojan Bogdanovic",
        # Add more corrections as needed
    }

    # Apply corrections
    corrected_name = corrections.get(name, name)

    # Remove diacritics and extra characters
    corrected_name = unidecode(corrected_name).replace(".", "").strip()

    return corrected_name


def get_last_x_days_per_game(contest_data, days=15):
    """
    Fetches and adjusts per-game stats over the last X days, based on contest data.

    Parameters:
        contest_data (ContestData): The contest data containing team and player info.
        days (int): Number of days to consider for stats.

    Returns:
        DataFrame: Adjusted per-game stats DataFrame.
    """
    try:
        stats_url = f"https://www.fantasypros.com/nba/stats/avg-overall.php?days={days}"
        last_x_days = pd.read_html(stats_url)[0]
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return pd.DataFrame()

    # Clean player names
    last_x_days['Player'] = last_x_days['Player'].str.split('(').str[0].str.strip()
    last_x_days['Player'] = last_x_days['Player'].apply(formalize_name)

    # Map additional data from contest data
    last_x_days['Tm'] = last_x_days['Player'].map(contest_data.player_teams)
    last_x_days['Pos'] = last_x_days['Player'].map(contest_data.player_positions)
    last_x_days['Salary'] = last_x_days['Player'].map(contest_data.salaries)
    last_x_days['Injured'] = last_x_days['Player'].map(contest_data.inactive_players)
    last_x_days['Opponent'] = last_x_days['Tm'].map(contest_data.team_opponents)

    # Filter out inactive players and those not playing today
    last_x_days = last_x_days[last_x_days['Injured'].isnull()]
    last_x_days = last_x_days[last_x_days['Opponent'].notnull()]

    # Ensure Salary is numeric
    last_x_days = last_x_days[pd.to_numeric(last_x_days['Salary'], errors='coerce').notnull()]
    last_x_days.drop(columns=['Injured'], inplace=True)

    # Rename columns to match expected format
    last_x_days.rename(columns={"REB": "TRB", "TO": "TOV"}, inplace=True)

    # Filter out players with 0 minutes or less than 2 games played
    last_x_days = last_x_days[last_x_days['MIN'] > 0]
    last_x_days = last_x_days[last_x_days['GP'] > 2]

    return last_x_days


def calculate_fantasy_points(players, dvp_data, apply_dvp=True):
    """
    Adjusts player stats based on defense versus position and calculates fantasy points.

    Parameters:
        players (DataFrame): Player stats DataFrame.
        dvp_data (dict): Defense versus position data.
        apply_dvp (bool): Whether to adjust stats based on DVP.

    Returns:
        DataFrame: Players DataFrame with calculated fantasy points.
    """
    fantasy_points_weights = {'PTS': 1.0, 'TRB': 1.2, 'AST': 1.5, 'STL': 3.0, 'BLK': 3.0, 'TOV': -1.0}
    players['FP'] = 0.0

    for idx, player in players.iterrows():
        player_pos = player.get('Pos', '')
        opponent = player.get('Opponent', '')
        if not opponent:
            continue

        # Handle special cases
        if player_pos == 'G':
            player_pos = 'PG'

        # Apply DVP adjustments if applicable
        if apply_dvp and player_pos in dvp_data:
            dvp_stats = dvp_data[player_pos]
            if opponent in dvp_stats.index:
                adjustments = {}
                for stat in ['p%', 'r%', 'a%', 's%', 'b%', 'to%']:
                    adj_value = dvp_stats.loc[opponent, stat]
                    adjustments[stat] = float(adj_value.strip('%')) / 100 + 1

                players.at[idx, 'PTS'] = round(adjustments['p%'] * float(players.at[idx, 'PTS']), 1)
                players.at[idx, 'TRB'] = round(adjustments['r%'] * float(players.at[idx, 'TRB']), 1)
                players.at[idx, 'AST'] = round(adjustments['a%'] * float(players.at[idx, 'AST']), 1)
                players.at[idx, 'STL'] = round(adjustments['s%'] * float(players.at[idx, 'STL']), 1)
                players.at[idx, 'BLK'] = round(adjustments['b%'] * float(players.at[idx, 'BLK']), 1)
                players.at[idx, 'TOV'] = round(adjustments['to%'] * float(players.at[idx, 'TOV']), 1)
        else:
            # No adjustments
            pass

        # Calculate fantasy points
        fp = (
            players.at[idx, 'PTS'] * fantasy_points_weights['PTS']
            + players.at[idx, 'TRB'] * fantasy_points_weights['TRB']
            + players.at[idx, 'AST'] * fantasy_points_weights['AST']
            + players.at[idx, 'STL'] * fantasy_points_weights['STL']
            + players.at[idx, 'BLK'] * fantasy_points_weights['BLK']
            + players.at[idx, 'TOV'] * fantasy_points_weights['TOV']
        )
        players.at[idx, 'FP'] = fp

    # Optionally, print team total fantasy points
    # teams = players['Tm'].unique()
    # for team in teams:
    #     team_total_fp = players[players['Tm'] == team]['FP'].sum()
    #     print(f"{team} total fantasy points: {team_total_fp}")

    return players


def build_lineup(players, lineup_name=None, selected_players=[]):
    """
    Builds the optimal lineup based on player salaries and projected fantasy points.

    Parameters:
        players (DataFrame): Players DataFrame with salary and fantasy point information.
        lineup_name (str): Name of the lineup for display purposes.

    Returns:
        None
    """
    players.reset_index(drop=True, inplace=True)

    # Position flags
    positions = ['PG', 'SG', 'SF', 'PF', 'C']
    for pos in positions:
        players[pos] = (players['Pos'] == pos).astype(float)

    players['G'] = players['PG'] + players['SG']
    players['F'] = players['SF'] + players['PF']
    players['Salary'] = players['Salary'].astype(float)

    model = LpProblem("Yahoo_DFS_Lineup", LpMaximize)

    # Decision variables
    decision_vars = [LpVariable(f'x{i}', cat='Binary') for i in players.index]

    # Objective function
    total_points = {var: players.at[i, 'FP'] for i, var in enumerate(decision_vars)}
    model += LpAffineExpression(total_points), "Total Fantasy Points"

    salary_cap = 200
    total_players_count = 8  # Total number of players in the lineup

    # Position constraints
    position_constraints = {
        'PG': (1, 3),
        'SG': (1, 3),
        'SF': (1, 3),
        'PF': (1, 3),
        'C': (1, 2),
        'G': (3, None),
        'F': (3, None),
    }

    # Handle pre-selected players
    for name in selected_players:
        player = players[players["Player"] == name]

        if player.empty:
            print(f"Player '{name}' not found in the player pool. Skipping...")
            continue

        # Adjust salary cap
        salary = player["Salary"].iloc[0]
        salary_cap -= salary

        if salary_cap < 0:
            print(f"Error: Selecting {name} exceeds the salary cap.")
            return

        # Adjust total players
        total_players_count -= 1
        if total_players_count < 0:
            print(f"Error: Too many pre-selected players. Exceeds total player limit.")
            return

        # Adjust positional constraints
        position = player["Pos"].iloc[0]
        if position in position_constraints:
            min_pos, max_pos = position_constraints[position]
            if max_pos is not None:
                position_constraints[position] = (min_pos - 1, max_pos - 1)
            else:
                position_constraints[position] = (min_pos - 1, None)

        # Handle grouped positions (e.g., G and F)
        if position in ["PG", "SG"]:
            g_min, g_max = position_constraints["G"]
            if g_max is not None:
                position_constraints["G"] = (g_min - 1, g_max - 1)
            else:
                position_constraints["G"] = (g_min - 1, None)

        if position in ["SF", "PF"]:
            f_min, f_max = position_constraints["F"]
            if f_max is not None:
                position_constraints["F"] = (f_min - 1, f_max - 1)
            else:
                position_constraints["F"] = (f_min - 1, None)

        print(f"Pre-selected {name}: Salary = {salary}, Position = {position}")

    for pos, (min_count, max_count) in position_constraints.items():
        pos_vars = {var: players.at[i, pos] for i, var in enumerate(decision_vars)}
        if max_count is not None:
            model += LpAffineExpression(pos_vars) <= max_count, f"Max {pos}"
        model += LpAffineExpression(pos_vars) >= min_count, f"Min {pos}"

    # Constraints
    total_cost = {var: players.at[i, 'Salary'] for i, var in enumerate(decision_vars)}
    model += LpAffineExpression(total_cost) <= salary_cap, "Total Salary Cap"

    # Total players constraint
    total_players = {var: 1.0 for var in decision_vars}
    model += LpAffineExpression(total_players) == total_players_count, "Total Players"

    # Solve the model
    model.solve()

    # Extract the lineup
    players['is_drafted'] = [var.varValue for var in decision_vars]
    drafted_players = players[players['is_drafted'] == 1.0]
    lineup = drafted_players[['Player', 'Pos', 'Tm', 'Salary', 'FP']]

    print(f"Lineup built using {lineup_name} stats:")
    print(lineup)
    print(f"Total Salary Used: {lineup['Salary'].sum()}")
    print(f"Projected Fantasy Points: {lineup['FP'].sum().round(1)}\n")


def find_first_contest():
    """
    Finds the first available contest ID from Yahoo DFS NBA page.

    Returns:
        str: The contest ID if found, otherwise None.
    """
    url = "https://sports.yahoo.com/dailyfantasy/nba"
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        first_contest = soup.find("a", class_="contestCard")
        if first_contest:
            first_contest_link = first_contest["href"]
            contest_id = first_contest_link.split("/contest/")[-1].split("/setlineup")[0]
            print(f"First contest ID: {contest_id}")
            return contest_id
        else:
            print("No contests found.")
            return None
    except Exception as e:
        print(f"Error finding first contest: {e}")
        return None


def import_contest_data(contest_data: ContestData) -> pd.DataFrame:
    """
    Imports contest data and populates ContestData attributes.

    Parameters:
        contest_data (ContestData): The ContestData instance to populate.

    Returns:
        DataFrame: DataFrame of players from the contest.
    """
    try:
        players_url = f"https://dfyql-ro.sports.yahoo.com/v2/export/contestPlayers?contestId={contest_data.contest_id}"
        players = pd.read_csv(players_url)
    except Exception as e:
        print(f"Error importing contest data: {e}")
        return pd.DataFrame()

    # Team name corrections
    team_name_corrections = {"NY": "NYK", "GS": "GSW", "NO": "NOP", "SA": "SAS", "CHA": "CHO"}
    players.replace({"Team": team_name_corrections, "Opponent": team_name_corrections}, inplace=True)

    # Populate ContestData attributes
    for _, player in players.iterrows():
        player_name = formalize_name(f"{player['First Name']} {player['Last Name']}")
        if player.get("Injury Status") in {"INJ", "O"}:
            contest_data.inactive_players[player_name] = 1
        if player["Team"] not in contest_data.team_opponents:
            contest_data.team_opponents[player["Team"]] = player["Opponent"]
        contest_data.salaries[player_name] = int(player["Salary"])
        contest_data.player_teams[player_name] = player["Team"]
        contest_data.player_positions[player_name] = player["Position"]

    return players


def main():
    contest_id = find_first_contest()
    if not contest_id:
        print("Exiting due to missing contest ID.")
        return

    contest_data = ContestData(
        contest_id=contest_id,
        team_opponents={},
        inactive_players={},
        salaries={},
        player_teams={},
        player_positions={},
    )

    # Initialize Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)

    # Exclude specific players if needed
    exclude_players = []
    selected_players = []

    import_contest_data(contest_data)
    for name in exclude_players:
        contest_data.inactive_players[name] = 1

    dvp_data = get_dvp_by_position(driver)
    players_stats = get_last_x_days_per_game(contest_data, days=15)
    if players_stats.empty:
        print("No player stats available.")
        return

    players_stats = calculate_fantasy_points(players_stats, dvp_data)
    build_lineup(players_stats, lineup_name="Last 15 Days", selected_players=selected_players)


if __name__ == "__main__":
    sys.exit(main())
