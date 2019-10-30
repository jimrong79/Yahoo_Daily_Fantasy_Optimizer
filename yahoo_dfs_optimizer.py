from pulp import *
import numpy as np
import pandas as pd
import statistics 

dvp_list = pd.read_html('https://basketballmonster.com/dfsdvp.aspx')
dvp = dvp_list[0]

# mapping team names to yahoo format
team_name_transfer_dict_espn = {"LA Clippers" : "LAC", "San Antonio": "SA", "Phoenix": "PHO", "Atlanta":"ATL", "Dallas":"DAL", "Portland":"POR", 
                                "Minnesota":"MIN", "New Orleans":"NO", "Detroit":"DET", "Brooklyn":"BKN", "Toronto":"TOR", "LA Lakers":"LAL", "Miami":"MIA", 
                                "Houston":"HOU", "Milwaukee":"MIL", "Charlotte":"CHA", "Boston":"BOS", "Philadelphia":"PHI", "Indiana":"IND", "Denver":"DEN", 
                                "Utah":"UTA", "Memphis":"MEM", "Washington":"WAS", "Golden State":"GS", "Chicago":"CHI", "Cleveland":"CLE", "New York":"NY", 
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
#print (team_stats.loc[["LAL"], ["PACE"]].values[0][0])
#print (team_stats.get_value("ATL", "PACE"))
pace_avg = round(team_stats["PACE"].mean(), 2)

players = pd.read_csv("Yahoo_DF_player_export.csv")

players["PG"] = (players["Position"] == 'PG').astype(float)
players["SG"] = (players["Position"] == 'SG').astype(float)
players["SF"] = (players["Position"] == 'SF').astype(float)
players["PF"] = (players["Position"] == 'PF').astype(float)
players["C"] = (players["Position"] == 'C').astype(float)
players["G"] = (players["Position"] == 'PG').astype(float)
players["F"] = (players["Position"] == 'SF').astype(float)
players["Salary"] = players["Salary"].astype(float)

for i, row in players.iterrows():
    
    multiplier = (team_stats.at[row.at["Team"], "PACE"]) /  pace_avg * (team_stats.at[row.at["Opponent"], "PACE"]) /  pace_avg
    players.at[i, 'FPPG'] = round(multiplier * players.at[i, 'FPPG'], 1)
    print (multiplier)

players.loc[players['SG'] == 1, ['G']] = 1
players.loc[players['PF'] == 1, ['F']] = 1

players.loc[players["Injury Status"] == 'INJ', 'FPPG'] = 0
players.loc[players["Injury Status"] == 'O', 'FPPG'] = 0
##players.loc[players["Time"] == '7:30PM EDT', 'FPPG'] = 0
##players.loc[players["Time"] == '7:00PM EDT', 'FPPG'] = 0
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

pulp.pulpTestAll()

model.status
model.solve()

players["is_drafted"] = 0.0
for var in model.variables():
    # Set is drafted to the value determined by the LP
    players.iloc[int(var.name[1:]),19] = var.varValue # column 20 = is_drafted

players.to_csv('result.csv')

my_team = players[players["is_drafted"] == 1.0]
my_team = my_team[["First Name", "Last Name", "Position","Team","Salary","FPPG"]]

print (my_team)
print ("Total used amount of salary cap: {}".format(my_team["Salary"].sum()))
print ("Projected points for tonight: {}".format(my_team["FPPG"].sum().round(1)))
