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



dvp_list = pd.read_html('https://basketballmonster.com/dfsdvp.aspx')
dvp = dvp_list[0]

def getting_dvp_by_pos():
    dvp_dict = {}
    
    #driver = webdriver.Chrome(r"C:\Users\jimro\AppData\Local\Programs\Python\Python37-32\Lib\site-packages\selenium\webdriver\chromedriver_win32\chromedriver.exe")
    driver = webdriver.Chrome(r"C:\Users\710453\AppData\Local\Programs\Python\Python36-32\Lib\site-packages\selenium\webdriver\chromedriver_win32\chromedriver.exe")
    url = "https://basketballmonster.com/DailyEaseRankings.aspx"
    
    option_dict = {"3": "C", "4": "PG", "5": "SG", "6": "SF", "7": "PF"}
    
    driver.get(url)
    
    for option, pos in option_dict.items():
        
        
        element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//select[@name='ctl00$ContentPlaceHolder1$PositionDropDownList']/option[@value='" + option + "']"))
        )
        element.click()
        WebDriverWait(driver, 3).until(
            EC.text_to_be_present_in_element(
                (By.XPATH, "//select[@name='ctl00$ContentPlaceHolder1$PositionDropDownList']/option[@selected='selected']"),
                pos
            )
        )

        page = driver.page_source
        soup = BeautifulSoup(page, 'html.parser')

        whole_table = soup.findAll('tr', limit = 2)[1]
        headers = [th.getText() for th in whole_table.findAll('tr', limit = 1)[0].findAll('td')]
        rows = whole_table.findAll('tr')[1:]
        dvp_stats = [[td.getText() for td in rows[i].findAll('td')] for i in range(len(rows))]

        for i in range(len(dvp_stats)):
            dvp_stats[i][0] = dvp_stats[i][0].replace("vs", "")
            dvp_stats[i][0] = dvp_stats[i][0].strip()

        dvp_stats_df = pd.DataFrame(dvp_stats, columns = headers)
        
        dvp_dict[pos] = dvp_stats_df

        print (dvp_stats_df.head(31))

    driver.quit()
    return dvp_dict


def get_per_game_stats(team_opp, inactive_players):
    
    per_game_list = pd.read_html("https://www.basketball-reference.com/leagues/NBA_2020_per_game.html")
    per_game = per_game_list[0]
    per_game.sort_values(by = "Tm", inplace = True)
    
    # Adding opponent column
    per_game['Opponent'] = per_game['Tm'].map(team_opp)
    per_game['Injured'] = per_game['Player'].map(inactive_players)

    # Dropping players not playing today
    per_game = per_game[per_game.Injured.isnull()]
    per_game = per_game[per_game.Opponent.notnull()]

    fan_pts_dict = {'PTS':1, 'TRB':1.2, 'AST':1.5, 'STL':3, 'BLK':3, 'TOV':-1}
          
    
    return per_game






def main():
    
    team_opp = {}
    inactive_players = {}
    
    exclude_list_last_name =  []
    exclude_list_time = []
    late_game = False
    if late_game:
        exclude_list_time = ['7:00PM EDT', '7:30PM EDT']
    yahoo_contest = import_contest_data(team_opp, inactive_players)
    players = get_per_game_stats(team_opp, inactive_players)
    dvp_dict = getting_dvp_by_pos()
    #players = adjust_fppg_by_pace(players)
    #players = lock_unlock_players(players, exclude_players = exclude_list_last_name, exclude_time = exclude_list_time)
    #build_lineup(players)






def adjust_fppg_by_pace(players_df):
    """
        Adjust fantasy points per game based on pace from both teams. Current method may be inaccurate. Will do some research and apply the best way
        
        
        Parameters:
            players_df: dataframe imported from yahoo daily fantasy page
        
        Returns: 
            adjusted dataframe based on pace
            
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

    team_stats.to_csv("team_stats.csv")
    total_teams = team_stats.shape[0]
    pace_avg = round(team_stats["PACE"].mean(), 2)
    for i, row in players_df.iterrows():
        multiplier = (team_stats.at[row.at["Team"], "PACE"]) /  pace_avg * (team_stats.at[row.at["Opponent"], "PACE"]) /  pace_avg
        players_df.at[i, 'FPPG'] = round(multiplier * players_df.at[i, 'FPPG'], 1)
    
    return players_df



def import_contest_data(team_opp, inactive_players):
    players = pd.read_csv("Yahoo_DF_player_export.csv")

    # convert team names from yahoo format to match with bball reference
    team_name_transfer_dict_yahoo = {"NY": "NYK", "GS": "GSW", "NO": "NOP", "SA": "SAS"}   
    players = players.replace({"Team": team_name_transfer_dict_yahoo})
    
    for i, player in players.iterrows():
        if player.get("Injury Status") == "INJ" or player.get("Injury Status") == "O":
            inactive_players[player.get("First Name") + ' ' + player.get("Last Name")] = 1
        if player.get("Team") not in team_opp:
            team_opp[player.get("Team")] = player.get("Opponent")
   
    return 
    

    players["PG"] = (players["Position"] == 'PG').astype(float)
    players["SG"] = (players["Position"] == 'SG').astype(float)
    players["SF"] = (players["Position"] == 'SF').astype(float)
    players["PF"] = (players["Position"] == 'PF').astype(float)
    players["C"] = (players["Position"] == 'C').astype(float)
    players["G"] = (players["Position"] == 'PG').astype(float)
    players["F"] = (players["Position"] == 'SF').astype(float)
    players["Salary"] = players["Salary"].astype(float)


    players.loc[players['SG'] == 1, ['G']] = 1
    players.loc[players['PF'] == 1, ['F']] = 1

    players.loc[players["Injury Status"] == 'INJ', 'FPPG'] = 0
    players.loc[players["Injury Status"] == 'O', 'FPPG'] = 0
    
    
    return players


def lock_unlock_players(players_df, **kwargs):

    
    for key, value in kwargs.items():
        if key == "exclude_players":
            for excluded_last_name in value:
                players_df.loc[players_df["Last Name"] == excluded_last_name, "FPPG"] = 0
        
        if key == "exclude_time":
            for exclude_time in value:
                players_df.loc[players["Time"] == exclude_time, 'FPPG'] = 0
        
    return players_df

def build_lineup(players):
    
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

        total_points[decision_var] = player["FPPG"] # Create PPG Dictionary
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
    is_drafted_idx = players.columns.get_loc("is_drafted")
    for var in model.variables():
        # Set is drafted to the value determined by the LP
        players.iloc[int(var.name[1:]),is_drafted_idx] = var.varValue # column 20 = is_drafted

    players.to_csv('result.csv')

    my_team = players[players["is_drafted"] == 1.0]
    my_team = my_team[["First Name", "Last Name", "Position","Team","Salary","FPPG"]]

    print (my_team)
    print ("Total used amount of salary cap: {}".format(my_team["Salary"].sum()))
    print ("Projected points for tonight: {}".format(my_team["FPPG"].sum().round(1)))

        



if __name__ == "__main__":
    sys.exit(main())  


