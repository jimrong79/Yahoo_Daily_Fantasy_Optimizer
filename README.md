# Yahoo NBA Daily Fantasy Lineup Optimizer

Personal project to generate Yahoo fantasy lineups.

## PREREQUISITES

- Python 3.7+
- ChromeDriver installed and placed in a location on your system’s PATH  
  [Download ChromeDriver](https://chromedriver.chromium.org/downloads)

## INSTALLING

Use the `requirements.txt` file provided to install all necessary packages:

pip install -r requirements.txt

## How to use

Run the optimizer script:

python yahoo_dfs_optimizer.py

## Introduction

Following are the steps taken by the optimizer:

READ IN CONTEST DATA:
Imports Yahoo DFS contest data and normalizes team names. Also identifies injured or out players, and records salaries, teams, and positions for each player.

GET DEFENSE VERSUS POSITION DATA:
Uses Selenium to scrape defensive rankings from Basketball Monster, giving insight into favorable or tough matchups.

GET PLAYER STATS:
Fetches recent (last 15 days) per-game stats from FantasyPros, focusing on current form rather than season-long averages.

CALCULATE FANTASY POINTS:
Adjusts player stats based on DVP and calculates fantasy points following Yahoo DFS scoring:

PTS: 1.0
TRB: 1.2
AST: 1.5
STL: 3.0
BLK: 3.0
TOV: -1.0
INITIALIZE PULP MODEL:
Sets up the PuLP linear programming model to maximize total fantasy points under salary and positional constraints.

SETUP LPVARIABLES FOR PLAYERS:
Each player is represented by a binary variable indicating whether they are selected.

INPUT OBJECTIVE FUNCTIONS AND COST CONSTRAINTS:
Ensures the total cost (salary) stays within the Yahoo DFS limit (e.g., 200).

INPUT PLAYER POSITION CONSTRAINTS:
Meets daily fantasy contest roster requirements (minimum and maximum players per position).

SOLVE THE PROBLEM AND DISPLAY OUTPUT:
The LP solver finds an optimal lineup. The script then prints the selected players, total used salary, and projected points.

## OUTCOME

After running the model, you get an optimized lineup based on current player performance and matchups. While not a guaranteed win, it provides a solid starting point for DFS strategy.

![](/images/winning.jpg)
