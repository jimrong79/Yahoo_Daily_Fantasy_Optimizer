from pulp import *
import numpy as np
import pandas as pd
import statistics 
import sys
from collections import defaultdict
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
import time
import unidecode
from collections import defaultdict


from webdriver_manager.chrome import ChromeDriverManager
driver = webdriver.Chrome(ChromeDriverManager().install())

dvp_list = pd.read_html('https://basketballmonster.com/dfsdvp.aspx')
dvp = dvp_list[0]

def import_contest_data(team_opp, inactive_players, salaries, player_team, player_pos):
    """
        Import yahoo daily fantasy contest data and acquire information for building lineup

        Paramenters:
            team_opp: dict
                dictionary to contain information of which 2 teams play agaisnt each other 
            inactive_players: dict
                dictionary to contain information of players not playing tonight
            salaries: dict
                dictionary to contain information of players' dfs contest salary
            player_team: dict
                dictionary to contain information of players' current team
            player_pos: dict
                dictionary to contain information of players' position based on yahoo contest

        Returns: DataFrame
            yahoo contest dataframe
    
    """
    players = pd.read_csv("Yahoo_DF_player_export.csv")

    # convert team names from yahoo format to match with bball reference
    team_name_transfer_dict_yahoo = {"NY": "NYK", "GS": "GSW", "NO": "NOP", "SA": "SAS"}   
    players = players.replace({"Team": team_name_transfer_dict_yahoo})
    players = players.replace({"Opponent": team_name_transfer_dict_yahoo})

    for i, player in players.iterrows():
        player_name = player.get("First Name") + ' ' + player.get("Last Name")
        player_name = formalize_name(player_name)
        if player.get("Injury Status") == "INJ" or player.get("Injury Status") == "O":
            inactive_players[player_name] = 1
        if player.get("Team") not in team_opp:
            team_opp[player.get("Team")] = player.get("Opponent")
        salaries[player_name] = int(player.get("Salary"))
        player_team[player_name] = player.get("Team")
        player_pos[player_name] = player.get("Position")


    return players


def getting_dvp_by_pos():
    """
        Returns a dictionary contains defense versus position dataframe of each NBA team
        
        Parameters:
            None
        
        Return:
            dict: a dictionary with dvp dataframe for 5 different position (PG, SG, SF, PF, C)
    """
    
    dvp_dict = {}
    url = "https://basketballmonster.com/DailyEaseRankings.aspx"
    option_dict = {"3": "C", "4": "PG", "5": "SG", "6": "SF", "7": "PF"}
    driver.get(url)

    
    for option, pos in option_dict.items():
        
        element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//select[@name='ctl00$ContentPlaceHolder1$PositionDropDownList']/option[@value='" + option + "']"))
        )
        element.click()
        WebDriverWait(driver, 10).until(
            EC.text_to_be_present_in_element(
                (By.XPATH, "//select[@name='ctl00$ContentPlaceHolder1$PositionDropDownList']/option[@selected='selected']"),
                pos
            )
        )
        time.sleep(0.1)

        page = driver.page_source
        soup = BeautifulSoup(page, 'html.parser')
        whole_table = soup.findAll('tr', limit = 2)[1]
        headers = [th.getText() for th in whole_table.findAll('tr', limit = 1)[0].findAll('td')]
        rows = whole_table.findAll('tr')[1:]
        dvp_stats = [[td.getText() for td in rows[i].findAll('td')] for i in range(len(rows))]

        for i in range(len(dvp_stats)):
            dvp_stats[i][0] = dvp_stats[i][0].replace("vs", "")
            dvp_stats[i][0] = dvp_stats[i][0].strip()
            dvp_stats[i][0] = dvp_stats[i][0].replace("NOR", "NOP")

        dvp_stats_df = pd.DataFrame(dvp_stats, columns = headers)
        dvp_stats_df = dvp_stats_df.drop(columns = ['Value', 'pV', 'rV', 'aV', 'sV', 'bV', 'toV'],  axis = 1)
        dvp_stats_df.set_index("vs Team", inplace = True)
        dvp_dict[pos] = dvp_stats_df

    driver.quit()
    return dvp_dict

def get_per_game_stats(team_opp, inactive_players, salaries, player_pos):
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
    
    
    # per_game_list = pd.read_html("https://www.basketball-reference.com/leagues/NBA_2020_per_game.html")
    per_game_list = pd.read_html("https://www.basketball-reference.com/playoffs/2020-nba-eastern-conference-finals-heat-vs-celtics.html")
    
    #HEAT
    heat_per_game = per_game_list[9]
    drop_cols = [i for i in range(21, len(heat_per_game.columns))]
    heat_per_game.drop(heat_per_game.columns[drop_cols], axis = 1, inplace = True)
    heat_per_game.drop(heat_per_game.shape[0] - 1, axis = 0, inplace = True)
    heat_per_game.columns = heat_per_game.columns.droplevel()
    heat_per_game["TOV"] = heat_per_game["TOV"] / heat_per_game["G"]
    heat_per_game["PTS"] = heat_per_game["PTS"] / heat_per_game["G"]
    heat_per_game["AST"] = heat_per_game["AST"] / heat_per_game["G"]
    heat_per_game["TRB"] = heat_per_game["TRB"] / heat_per_game["G"]
    heat_per_game["STL"] = heat_per_game["STL"] / heat_per_game["G"]
    heat_per_game["BLK"] = heat_per_game["BLK"] / heat_per_game["G"]
    heat_per_game["Tm"] = "MIA"
    
    #CELTICS
    celtics_per_game = per_game_list[8]
    drop_cols = [i for i in range(21, len(celtics_per_game.columns))]
    celtics_per_game.drop(celtics_per_game.columns[drop_cols], axis = 1, inplace = True)
    celtics_per_game.drop(celtics_per_game.shape[0] - 1, axis = 0, inplace = True)
    celtics_per_game.columns = celtics_per_game.columns.droplevel()
    celtics_per_game["TOV"] = celtics_per_game["TOV"] / celtics_per_game["G"]
    celtics_per_game["PTS"] = celtics_per_game["PTS"] / celtics_per_game["G"]
    celtics_per_game["AST"] = celtics_per_game["AST"] / celtics_per_game["G"]
    celtics_per_game["TRB"] = celtics_per_game["TRB"] / celtics_per_game["G"]
    celtics_per_game["STL"] = celtics_per_game["STL"] / celtics_per_game["G"]
    celtics_per_game["BLK"] = celtics_per_game["BLK"] / celtics_per_game["G"]
    celtics_per_game["Tm"] = "BOS"
    
    
    
    per_game_list = pd.read_html("https://www.basketball-reference.com/playoffs/2020-nba-western-conference-finals-nuggets-vs-lakers.html")

    
    #LAKERS
    lakers_per_game = per_game_list[6]
    drop_cols = [i for i in range(21, len(lakers_per_game.columns))]
    lakers_per_game.drop(lakers_per_game.columns[drop_cols], axis = 1, inplace = True)
    lakers_per_game.drop(lakers_per_game.shape[0] - 1, axis = 0, inplace = True)
    lakers_per_game.columns = lakers_per_game.columns.droplevel()
    lakers_per_game["TOV"] = lakers_per_game["TOV"] / lakers_per_game["G"]
    lakers_per_game["PTS"] = lakers_per_game["PTS"] / lakers_per_game["G"]
    lakers_per_game["AST"] = lakers_per_game["AST"] / lakers_per_game["G"]
    lakers_per_game["TRB"] = lakers_per_game["TRB"] / lakers_per_game["G"]
    lakers_per_game["STL"] = lakers_per_game["STL"] / lakers_per_game["G"]
    lakers_per_game["BLK"] = lakers_per_game["BLK"] / lakers_per_game["G"]
    lakers_per_game["Tm"] = "LAL"
    
    #NUGGETS
    nuggets_per_game = per_game_list[7]
    drop_cols = [i for i in range(21, len(nuggets_per_game.columns))]
    nuggets_per_game.drop(nuggets_per_game.columns[drop_cols], axis = 1, inplace = True)
    nuggets_per_game.drop(nuggets_per_game.shape[0] - 1, axis = 0, inplace = True)
    nuggets_per_game.columns = nuggets_per_game.columns.droplevel()
    nuggets_per_game["TOV"] = nuggets_per_game["TOV"] / nuggets_per_game["G"]
    nuggets_per_game["PTS"] = nuggets_per_game["PTS"] / nuggets_per_game["G"]
    nuggets_per_game["AST"] = nuggets_per_game["AST"] / nuggets_per_game["G"]
    nuggets_per_game["TRB"] = nuggets_per_game["TRB"] / nuggets_per_game["G"]
    nuggets_per_game["STL"] = nuggets_per_game["STL"] / nuggets_per_game["G"]
    nuggets_per_game["BLK"] = nuggets_per_game["BLK"] / nuggets_per_game["G"]
    nuggets_per_game["Tm"] = "DEN"
    
    frames = [heat_per_game, celtics_per_game, nuggets_per_game, lakers_per_game]
    
    per_game = pd.concat(frames)
    
    #per_game.to_csv('per_game_stats.csv', index = False)
    
    #per_game.sort_values(by = "Tm", inplace = True)
    
    #dealing name difference between bball reference and fantasypros
    per_game = per_game.replace({"Tm":"BRK"}, {"Tm":"BKN"})

    per_game["Salary"] = 0.0
    
    # Adding opponent column    
    per_game['Player'] = per_game["Player"].apply(lambda x: formalize_name(x))
    per_game['Opponent'] = per_game['Tm'].map(team_opp)
    per_game['Injured'] = per_game['Player'].map(inactive_players)
    per_game["Pos"] = per_game["Player"].map(player_pos)
    per_game["Salary"] = per_game["Player"].replace(salaries)


    # per_game.to_csv("per_game_no_drop_salary.csv")
    # Dropping players not playing today
    per_game = per_game[per_game.Injured.isnull()]
    per_game = per_game[per_game.Opponent.notnull()]

    per_game.to_csv("per_game_no_drop_salary.csv")
    per_game = per_game[pd.to_numeric(per_game['Salary'], errors = "coerce").notnull()]
    per_game = per_game.drop(columns = ['Injured'],  axis = 1)
    per_game = per_game.reset_index()
    per_game.to_csv('per_game_stats.csv')

    return per_game



def get_last_x_days_per_game(team_opp, inactive_players, salaries, player_team, player_pos, days):
    
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
    last_x_days['Tm'] = last_x_days["Player"].map(player_team)
    last_x_days['Pos'] = last_x_days["Player"].map(player_pos)
    last_x_days["Salary"] = last_x_days["Player"].map(salaries)
    last_x_days['Injured'] = last_x_days["Player"].map(inactive_players)
    last_x_days['Opponent'] = last_x_days['Tm'].map(team_opp)
    
    # Take out inactive players and players who are not playing today
    last_x_days = last_x_days[last_x_days.Injured.isnull()]
    last_x_days = last_x_days[last_x_days.Opponent.notnull()]


    last_x_days = last_x_days[pd.to_numeric(last_x_days['Salary'], errors = "coerce").notnull()]
    last_x_days = last_x_days.drop(columns = ['Injured'],  axis = 1)
    last_x_days = last_x_days.rename(columns = {"REB": "TRB", "TO": "TOV"})

    
    last_x_days.to_csv("last_{}_days.csv".format(days))
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

    name = unidecode.unidecode(name)
    name = name.replace(".", "").replace(" Jr", "").replace(" III", "")
    name = name.replace("Jakob Poltl", "Jakob Poeltl").replace("Taurean Waller-Prince", "Taurean Prince").replace("Maurice Harkless", "Moe Harkless")
    name = name.replace("Mo Bamba", "Mohamed Bamba").replace("Wesley Iwundu", "Wes Iwundu").replace("JaKarr Sampson", "Jakarr Sampson").replace("Bojan Bogdanović", "Bojan Bogdanovic")
    name = name.strip()
    return name



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



    players.to_csv('mod_per_game.csv')

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

    model = pulp.LpProblem("Yahoo", pulp.LpMaximize)
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
        decision_var = pulp.LpVariable(var_name, cat='Binary') # Initialize Variables

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
    objective_function = pulp.LpAffineExpression(total_points)
    model += objective_function

    #Define cost constraint and add it to the model
    total_cost = pulp.LpAffineExpression(cost)
    model += (total_cost <= 200)

    # Add player type constraints
    PG_constraint = pulp.LpAffineExpression(PGs)
    SG_constraint = pulp.LpAffineExpression(SGs)
    SF_constraint = pulp.LpAffineExpression(SFs)
    PF_constraint = pulp.LpAffineExpression(PFs)
    C_constraint = pulp.LpAffineExpression(Cs)
    G_constraint = pulp.LpAffineExpression(Gs)
    F_constraint = pulp.LpAffineExpression(Fs)
    total_players = pulp.LpAffineExpression(number_of_players)

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

    #pulp.pulpTestAll()

    model.status
    model.solve()

    players["is_drafted"] = 0.0
    #players.to_csv('result.csv')

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

      
      
def main():
    
    team_opp = {}
    inactive_players = {}
    salaries = {}
    player_team = {}
    player_pos = {}

    exclude_list_last_name =  []
    exclude_players = [""]
    exclude_list_time = []
    late_game = False
    if late_game:
        exclude_list_time = ['7:00PM EDT', '7:30PM EDT']
    
    yahoo_contest = import_contest_data(team_opp, inactive_players, salaries, player_team, player_pos)
    #get_team_avg_stats()
    dvp_dict = getting_dvp_by_pos()
    
    #exluding players that you don't want to pick
    for name in exclude_players:
        inactive_players[name] = 1

    players_season = get_per_game_stats(team_opp, inactive_players, salaries, player_pos)
    # players_last_15 = get_last_x_days_per_game(team_opp, inactive_players, salaries, player_team, player_pos, 15)
    # players_last_7 = get_last_x_days_per_game(team_opp, inactive_players, salaries, player_team, player_pos, 7)
    
    players_season = calculate_fantasy_points(players_season, dvp_dict, False)
    # players_last_15 = calculate_fantasy_points(players_last_15, dvp_dict)
    # players_last_7 = calculate_fantasy_points(players_last_7, dvp_dict)
    
    build_lineup(players_season, "Per Game")
    # build_lineup(players_last_15, "Last 15 Days")
    # build_lineup(players_last_7, "Last 7 Days")


    #players = adjust_fppg_by_pace(players)
    #players = lock_unlock_players(players, exclude_players = exclude_list_last_name, exclude_time = exclude_list_time)



# Under development
def lock_unlock_players(players_df, **kwargs):

    for key, value in kwargs.items():
        if key == "exclude_players":
            for excluded_last_name in value:
                players_df.loc[players_df["Last Name"] == excluded_last_name, "FPPG"] = 0
        
        if key == "exclude_time":
            for exclude_time in value:
                players_df.loc[players["Time"] == exclude_time, 'FPPG'] = 0
        
    return players_df

# Under development
def get_team_avg_stats():
    team_avg_list = pd.read_html("https://www.espn.com/nba/stats/team")
    team_avg = pd.concat([team_avg_list[0], team_avg_list[1]], axis = 1, sort=False)

    team_avg['FP'] = team_avg["PTS"] + team_avg["REB"] * 1.2 + team_avg["AST"] * 1.5 + team_avg[""]
    # team_avg.at[i, 'FP'] = players.at[i, 'PTS'] * fan_pts_dict['PTS'] + players.at[i, 'TRB'] * fan_pts_dict['TRB'] \
    #                     + players.at[i, 'AST'] * fan_pts_dict['AST'] + players.at[i, 'STL'] * fan_pts_dict['STL'] \
    #                     + players.at[i, 'BLK'] * fan_pts_dict['BLK'] + players.at[i, 'TOV'] * fan_pts_dict['TOV']

    team_avg.to_csv("team_avg.csv")

# Not in use
def adjust_fppg_by_pace(players_df):
    """
        Not in use. Replaced by dvp stats
        
        Adjust fantasy points per game based on pace from both teams. Current method may be inaccurate. Will do some research and apply the best way
        
        
        Parameters:
            players_df: dataframe 
                imported from yahoo daily fantasy page
        
        Returns: 
            DataFrame: adjusted dataframe based on pace
            
    """

    # mapping team names to yahoo format
    team_name_transfer_dict_espn = {"LA Clippers" : "LAC", "San Antonio": "SAS", "Phoenix": "PHO", "Atlanta":"ATL", "Dallas":"DAL", "Portland":"POR", 
                                    "Minnesota":"MIN", "New Orleans":"NOP", "Detroit":"DET", "Brooklyn":"BKN", "Toronto":"TOR", "LA Lakers":"LAL", "Miami":"MIA", 
                                    "Houston":"HOU", "Milwaukee":"MIL", "Charlotte":"CHA", "Boston":"BOS", "Philadelphia":"PHI", "Indiana":"IND", "Denver":"DEN", 
                                    "Utah":"UTA", "Memphis":"MEM", "Washington":"WAS", "Golden State":"GSW", "Chicago":"CHI", "Cleveland":"CLE", "New York":"NYK", 
                                    "Oklahoma City":"OKC", "Orlando":"ORL", "Sacramento":"SAC"}

    team_stats_list = pd.read_html("http://www.espn.com/nba/hollinger/teamstats")
    team_stats = team_stats_list[0]
    team_stats.columns = team_stats.iloc[1]
    team_stats = team_stats.drop(team_stats.index[1])
    team_stats = team_stats.drop(team_stats.index[0])

    team_stats = team_stats.replace({"TEAM": team_name_transfer_dict_espn})
    team_stats["PACE"] = team_stats["PACE"].astype(float)
    team_stats.set_index("TEAM", inplace = True)

    #team_stats.to_csv("team_stats.csv")
    total_teams = team_stats.shape[0]
    pace_avg = round(team_stats["PACE"].mean(), 2)
    for i, row in players_df.iterrows():
        multiplier = (team_stats.at[row.at["Team"], "PACE"]) /  pace_avg * (team_stats.at[row.at["Opponent"], "PACE"]) /  pace_avg
        players_df.at[i, 'FPPG'] = round(multiplier * players_df.at[i, 'FPPG'], 1)
    
    return players_df


if __name__ == "__main__":
    sys.exit(main())  


