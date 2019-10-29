from pulp import *
import numpy as np
import pandas as pd

players = pd.read_csv("Yahoo_DF_player_export.csv")

players["PG"] = (players["Position"] == 'PG').astype(float)
players["SG"] = (players["Position"] == 'SG').astype(float)
players["SF"] = (players["Position"] == 'SF').astype(float)
players["PF"] = (players["Position"] == 'PF').astype(float)
players["C"] = (players["Position"] == 'C').astype(float)
players["Salary"] = players["Salary"].astype(float)

players.loc[players["Injury Status"] == 'INJ', 'FPPG'] = 0
players.loc[players["Injury Status"] == 'O', 'FPPG'] = 0
players.loc[players["Time"] == '7:30PM EDT', 'FPPG'] = 0
players.loc[players["Time"] == '7:00PM EDT', 'FPPG'] = 0
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
##    Gs[decision_var] = player["PG"] or player["SG"]
##    Fs[decision_var] = player["SF"] or player["PF"]
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
##G_constraint = pulp.LpAffineExpression(Gs)
##F_constraint = pulp.LpAffineExpression(Fs)
total_players = pulp.LpAffineExpression(number_of_players)

model += (PG_constraint <= 2)
model += (SG_constraint <= 2)
model += (SF_constraint <= 2)
model += (PF_constraint <= 2)
model += (C_constraint <= 2)
##model += (G_constraint <= 1)
##model += (F_constraint <= 1)
model += (total_players <= 8)

#pulp.pulpTestAll()

model.status
model.solve()

players["is_drafted"] = 0.0

for var in model.variables():
    # Set is drafted to the value determined by the LP
    players.iloc[int(var.name[1:]),17] = var.varValue # column 11 = is_drafted

my_team = players[players["is_drafted"] == 1.0]
my_team = my_team[["First Name", "Last Name", "Position","Team","Salary","FPPG"]]

print (my_team)
print ("Total used amount of salary cap: {}".format(my_team["Salary"].sum()))
print ("Projected points for tonight: {}".format(my_team["FPPG"].sum().round(1)))

    
