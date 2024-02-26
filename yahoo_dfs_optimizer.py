import pandas as pd
import requests
import sys
from bs4 import BeautifulSoup
from dataclasses import dataclass
from pulp import LpMaximize, LpAffineExpression, LpVariable, LpProblem
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from unidecode import unidecode
import time

@dataclass
class ContestData:
    contest_id: int
    team_opp: dict
    inactive_players: dict
    salaries: dict
    player_team: dict
    player_pos: dict

def getting_dvp_by_pos(driver):
    """
        Returns a dictionary contains defense versus position dataframe of each NBA team
        
        Parameters:
            None
        
        Return:
            dict: a dictionary with dvp dataframe for 5 different position (PG, SG, SF, PF, C)
    """
    
    dvp_dict = {}
    url = "https://basketballmonster.com/easerankings.aspx"
    option_dict = {"3": "C", "4": "PG", "5": "SG", "6": "SF", "7": "PF"}
    driver.get(url)

    position_dropdown_xpath = "//select[@name='ctl00$ContentPlaceHolder1$PositionDropDownList']/option[@value='{}']"

    for option, pos in option_dict.items():
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, position_dropdown_xpath.format(option)))
        )
        element.click()
        WebDriverWait(driver, 10).until(
            EC.text_to_be_present_in_element((By.XPATH, position_dropdown_xpath.format(option)), pos)
        )
        time.sleep(0.1)

        page = driver.page_source
        soup = BeautifulSoup(page, 'html.parser')
        
        whole_table = soup.findAll('tr')
        headers = [th.getText() for th in whole_table[0]]
        rows = soup.findAll('tr')[1:]
        dvp_stats = [[td.getText() for td in rows[i].findAll('td')] for i in range(len(rows))]

        for i in range(len(dvp_stats)):
            dvp_stats[i][0] = dvp_stats[i][0].replace("vs", "")
            dvp_stats[i][0] = dvp_stats[i][0].strip()
            dvp_stats[i][0] = dvp_stats[i][0].replace("NOR", "NOP").replace("CHA", "CHO")

        dvp_stats_df = pd.DataFrame(dvp_stats, columns = headers)
        dvp_stats_df = dvp_stats_df.drop(columns = ['Value', 'pV', 'rV', 'aV', 'sV', 'bV', 'toV'],  axis = 1)
        dvp_stats_df.set_index("vs Team", inplace = True)
        dvp_dict[pos] = dvp_stats_df

    driver.quit()

    return dvp_dict

def get_per_game_stats(contest_data):
    """
        Gets season per game stats and adjusts the dataframe based on Yahoo contest data
        
        Parameters:
            team_opp: dict
                information of which 2 teams play agaisnt each other
            
            inactive_players: dict
                information of which players are not playing tonight
            
            salaries: dict
                players' yahoo daily fantasy contest salary
                        
        Return:
            DataFrame: Season per game stats dataframe        
       
    """
    
    
    per_game_list = pd.read_html("https://www.basketball-reference.com/leagues/NBA_2024_per_game.html")
    per_game = per_game_list[0]
    #per_game.sort_values(by = "Tm", inplace = True)

    #dealing name difference between bball reference and fantasypros
    per_game = per_game.replace({"Tm":"BRK"}, {"Tm":"BKN"})

    per_game["Salary"] = 0.0
    
    # Adding opponent column
    per_game['Opponent'] = per_game['Tm'].map(contest_data.team_opp)
    per_game['Injured'] = per_game['Player'].map(contest_data.inactive_players)
    per_game['Player'] = per_game["Player"].apply(lambda x: formalize_name(x))
    per_game["Pos"] = per_game["Player"].map(contest_data.player_pos)
    per_game["Salary"] = per_game["Player"].replace(contest_data.salaries)

    # Dropping players not playing today
    per_game = per_game[per_game.Injured.isnull()]
    per_game = per_game[per_game.Opponent.notnull()]

    per_game = per_game[pd.to_numeric(per_game['Salary'], errors = "coerce").notnull()]
    per_game = per_game.drop(columns = ['Injured'],  axis = 1)

    return per_game



def get_last_x_days_per_game(contest_data, days):
    
    """
        Gets last 15 days per game stats and adjusts the dataframe based on Yahoo contest data
        
        Parameters:
            team_opp: dict
                information of which 2 teams play agaisnt each other
            
            inactive_players: dict
                information of which players are not playing tonight
            
            salaries: dict
                players' yahoo daily fantasy contest salary
                
            player_team: dict
                information of player's current team
            
            player_pos: dict
                information of player's position based on yahoo contest
        
        Return:
            DataFrame: Last 15 days per game stats dataframe        
       
    """
    
    last_x_days = pd.read_html("https://www.fantasypros.com/nba/stats/avg-overall.php?days={}".format(days))
    last_x_days = last_x_days[0]

    last_x_days['Tm'] = ''
    last_x_days['Pos'] = ''
    
    # Damian Lillard (POR - PG)  get rid of (POR - PG) part
    for i, player in last_x_days.iterrows():
        if "(" in last_x_days.at[i, "Player"]:
            last_x_days.at[i, "Player"] = player.Player[:player.Player.index('(')]    

    last_x_days['Player'] = last_x_days["Player"].apply(lambda x: formalize_name(x))
    last_x_days['Tm'] = last_x_days["Player"].map(contest_data.player_team)
    last_x_days['Pos'] = last_x_days["Player"].map(contest_data.player_pos)
    last_x_days["Salary"] = last_x_days["Player"].map(contest_data.salaries)
    last_x_days['Injured'] = last_x_days["Player"].map(contest_data.inactive_players)
    last_x_days['Opponent'] = last_x_days['Tm'].map(contest_data.team_opp)
    
    # Take out inactive players and players who are not playing today
    last_x_days = last_x_days[last_x_days.Injured.isnull()]
    last_x_days = last_x_days[last_x_days.Opponent.notnull()]


    last_x_days = last_x_days[pd.to_numeric(last_x_days['Salary'], errors = "coerce").notnull()]
    last_x_days = last_x_days.drop(columns = ['Injured'],  axis = 1)
    last_x_days = last_x_days.rename(columns = {"REB": "TRB", "TO": "TOV"})

    return last_x_days
   


def formalize_name(name):
    """
    Gets and returns player name according to Yahoo Fantasy format
    
    Parameters:
        name: str
            Player's name
    
    Returns:
        str: Player's name after uniform formatting
    """
    corrections = {
        "Jakob Poltl": "Jakob Poeltl",
        "Taurean Waller-Prince": "Taurean Prince",
        "Mo Bamba": "Mohamed Bamba",
        "Bojan Bogdanović": "Bojan Bogdanovic",
        # Add more corrections as needed
    }

    # Apply corrections
    corrected_name = name
    for original, corrected in corrections.items():
        corrected_name = corrected_name.replace(original, corrected)

    # Remove extra characters (e.g., Jr, III)
    corrected_name = unidecode(corrected_name).replace(".", "").strip()

    return corrected_name


def calculate_fantasy_points(players, dvp_dict, apply_dvp = True):
    """
        Adjust players stats based on defens vs postion with the team they play against. 
        After that calculate fantasy points based on yahoo scoring rule
        
        Parameters:
            playeres: dataframe
                dataframe which conatins stats of all players who are playing tonight
            
            dvp_dict: dict
                defense versus position information
                
        Returns:
            DataFrame: players stats after adjustment
    
    """
    

    fan_pts_dict = {'PTS':1.0, 'TRB':1.2, 'AST':1.5, 'STL':3.0, 'BLK':3.0, 'TOV':-1.0}

    players['FP'] = 0.0

    for i, player in players.iterrows():
        player_pos = player.get("Pos")
        
        # Special case for Trey Burke on basketball reference
        if player_pos == 'G':
            player_pos = 'PG'

        opponent = player.get("Opponent")
        if apply_dvp:
            pts_mod = float(dvp_dict[player_pos].loc[[opponent], ['p%']].values[0][0].strip('%')) / 100 + 1
            reb_mod = float(dvp_dict[player_pos].loc[[opponent], ['r%']].values[0][0].strip('%')) / 100 + 1
            ast_mod = float(dvp_dict[player_pos].loc[[opponent], ['a%']].values[0][0].strip('%')) / 100 + 1
            stl_mod = float(dvp_dict[player_pos].loc[[opponent], ['s%']].values[0][0].strip('%')) / 100 + 1
            blk_mod = float(dvp_dict[player_pos].loc[[opponent], ['b%']].values[0][0].strip('%')) / 100 + 1
            tov_mod = float(dvp_dict[player_pos].loc[[opponent], ['to%']].values[0][0].strip('%')) / 100 + 1
        else:
            pts_mod = 1
            reb_mod = 1
            ast_mod = 1
            stl_mod = 1
            blk_mod = 1
            tov_mod = 1

        
        players.at[i, 'PTS'] = round(pts_mod * float(players.at[i, 'PTS']), 1) 
        players.at[i, 'TRB'] = round(reb_mod * float(players.at[i, 'TRB']), 1) 
        players.at[i, 'AST'] = round(ast_mod * float(players.at[i, 'AST']), 1) 
        players.at[i, 'STL'] = round(stl_mod * float(players.at[i, 'STL']), 1) 
        players.at[i, 'BLK'] = round(blk_mod * float(players.at[i, 'BLK']), 1) 
        players.at[i, 'TOV'] = round(tov_mod * float(players.at[i, 'TOV']), 1) 

        players.at[i, 'FP'] = players.at[i, 'PTS'] * fan_pts_dict['PTS'] + players.at[i, 'TRB'] * fan_pts_dict['TRB'] \
                            + players.at[i, 'AST'] * fan_pts_dict['AST'] + players.at[i, 'STL'] * fan_pts_dict['STL'] \
                            + players.at[i, 'BLK'] * fan_pts_dict['BLK'] + players.at[i, 'TOV'] * fan_pts_dict['TOV']

    # adjustment based on inactive players
    teams = set(players['Tm'].tolist())
    for team in teams:
        team_total = players.loc[players['Tm'] == team, 'FP'].sum()        
        print ("{} FP total is : {}".format(team, team_total))

    return players

def build_lineup(players, lineup_name = None):
    """
        Build optimal lineup based on players salary and projected fantasy point

        Paramenters:
            players: DataFrame
                players salary and fantasy point information

        Returns:
            None

    """

    players = players.reindex()
    
    players["PG"] = (players["Pos"] == 'PG').astype(float)
    players["SG"] = (players["Pos"] == 'SG').astype(float)
    players["SF"] = (players["Pos"] == 'SF').astype(float)
    players["PF"] = (players["Pos"] == 'PF').astype(float)
    players["C"] = (players["Pos"] == 'C').astype(float)
    players["G"] = (players["Pos"] == 'PG').astype(float)
    players["F"] = (players["Pos"] == 'SF').astype(float)
    players["Salary"] = players["Salary"].astype(float)


    players.loc[players['SG'] == 1, ['G']] = 1
    players.loc[players['PF'] == 1, ['F']] = 1

    model = LpProblem("Yahoo", LpMaximize)
    total_points = {}
    cost = {}
    PGs = {}
    SGs = {}
    SFs = {}
    PFs = {}
    Gs = {}
    Fs = {}
    Cs = {}
    number_of_players = {}
    
    # i = row index, player = player attributes
    for i, player in players.iterrows():

        var_name = 'x' + str(i) # Create variable name
        decision_var = LpVariable(var_name, cat='Binary') # Initialize Variables

        total_points[decision_var] = player["FP"] # Create PPG Dictionary
        cost[decision_var] = player["Salary"] # Create Cost Dictionary
        
        # Create Dictionary for Player Types
        PGs[decision_var] = player["PG"]
        SGs[decision_var] = player["SG"]
        SFs[decision_var] = player["SF"]
        PFs[decision_var] = player["PF"]
        Cs[decision_var] = player["C"]
        Gs[decision_var] = player["PG"] or player["SG"]
        Fs[decision_var] = player["SF"] or player["PF"]
        number_of_players[decision_var] = 1.0
        
    # Define ojective function and add it to the model
    objective_function = LpAffineExpression(total_points)
    model += objective_function

    #Define cost constraint and add it to the model
    total_cost = LpAffineExpression(cost)
    model += (total_cost <= 200)

    # Add player type constraints
    PG_constraint = LpAffineExpression(PGs)
    SG_constraint = LpAffineExpression(SGs)
    SF_constraint = LpAffineExpression(SFs)
    PF_constraint = LpAffineExpression(PFs)
    C_constraint = LpAffineExpression(Cs)
    G_constraint = LpAffineExpression(Gs)
    F_constraint = LpAffineExpression(Fs)
    total_players = LpAffineExpression(number_of_players)

    model += (PG_constraint <= 3)
    model += (PG_constraint >= 1)
    model += (SG_constraint <= 3)
    model += (SG_constraint >= 1)
    model += (SF_constraint <= 3)
    model += (SF_constraint >= 1)
    model += (PF_constraint <= 3)
    model += (PF_constraint >= 1)
    model += (C_constraint <= 2)
    model += (C_constraint >= 1)
    model += (G_constraint >= 3)
    model += (F_constraint >= 3)
    model += (total_players <= 8)

    model.status
    model.solve()

    players["is_drafted"] = 0.0

    for var in model.variables():
        # Set is drafted to the value determined by the LP
        # print ('{}, {}'.format(var.name[1:], var.varValue))

        players.loc[int(var.name[1:]), "is_drafted"] = var.varValue # column 20 = is_drafted

    my_team = players[players["is_drafted"] == 1.0]
    my_team = my_team[["Player", "Pos","Tm","Salary","FP"]]
    
    print ("Line up build by {} stats".format(lineup_name))
    print (my_team)
    print ("Total used amount of salary cap: {}".format(my_team["Salary"].sum()))
    print ("Projected points for tonight: {}".format(my_team["FP"].sum().round(1)))

def find_first_contest():
    static_url = "https://sports.yahoo.com/dailyfantasy/nba"
    response = requests.get(static_url)
    soup = BeautifulSoup(response.text, "html.parser")
    first_contest = soup.find("a", class_="contestCard")
    
    if first_contest:
        first_contest_link = first_contest["href"]
        # Assuming the link format is consistent (e.g., /contest/<contest_id>/setlineup)
        contest_id = first_contest_link.split("/contest/")[-1].split("/setlineup")[0]
        print(f"First contest ID: {contest_id}")
        return contest_id
    else:
        print("No contests found.")
        return None

def import_contest_data(contest_data: ContestData) -> pd.DataFrame:
    """
        Returns: DataFrame
            yahoo contest dataframe 
    """
    players = pd.read_csv(f"https://dfyql-ro.sports.yahoo.com/v2/export/contestPlayers?contestId={contest_data.contest_id}")

    # Convert team names from Yahoo format to match with basketball reference
    team_name_transfer_dict_yahoo = {"NY": "NYK", "GS": "GSW", "NO": "NOP", "SA": "SAS", "CHA": "CHO"}
    players = players.replace({"Team": team_name_transfer_dict_yahoo})
    players = players.replace({"Opponent": team_name_transfer_dict_yahoo})

    for i, player in players.iterrows():
        player_name = player.get("First Name") + ' ' + player.get("Last Name")
        player_name = formalize_name(player_name)
        if player.get("Injury Status") in {"INJ", "O"}:
            contest_data.inactive_players[player_name] = 1
        if player.get("Team") not in contest_data.team_opp:
            contest_data.team_opp[player.get("Team")] = player.get("Opponent")
        contest_data.salaries[player_name] = int(player.get("Salary"))
        contest_data.player_team[player_name] = player.get("Team")
        contest_data.player_pos[player_name] = player.get("Position")

    return players
    
def main():
    contest_id = find_first_contest()
    contest_data_instance = ContestData(
        contest_id=contest_id,
        team_opp={},
        inactive_players={},
        salaries={},
        player_team={},
        player_pos={}
    )
    driver = webdriver.Chrome()

    exclude_players = [""]

    import_contest_data(contest_data_instance)
    dvp_dict = getting_dvp_by_pos(driver)

    #exluding players that you don't want to pick
    for name in exclude_players:
        contest_data_instance.inactive_players[name] = 1

    players_last_15 = get_last_x_days_per_game(contest_data_instance, 15)
    
    players_last_15 = calculate_fantasy_points(players_last_15, dvp_dict)
    
    build_lineup(players_last_15, "Last 15 Days")

if __name__ == "__main__":
    sys.exit(main())  

