# Yahoo NBA Daily Fantasy Lineup Optimizer

Personal project to generate yahoo fantasy 


## Prerequisites

Python 3.7

## Installing

Download chrome driver to designated location

https://chromedriver.chromium.org/downloads


Packages installed:

pulp

pandas

bs4

selenium

unidecode

## How to use

Click on any yahoo daily fantasy contest. Select export players list. Download "Yahoo_DF_player_export.csv" to the same folder as yahoo_dfs_optimizer.py. 

https://sports.yahoo.com/dailyfantasy/nba

Then run yahoo_dfs_optimizer.py will generate a optimized lineup based on matchups and yahoo salary.

## Introduction

This optimizer will utilize BeautifulSoup and Selenium driver to scrape player's data online and then use the PuLP python package for Linear Programming to find the 
best lineup in <b>Yahoo Fantasy Sport's Daily Fantasy Contest</b>.


#### READ IN CONTEST DATA

First step for the optimization pipeline is reading the yahoo fantasy contest into Pandas DataFrame. There are several information that is crucial to our results, the opposite team, players who were hurt or out, players' DFS salary, players' team, players' position, which are stored in several dictionaries for future use. 

One small note is that the abbreviation of the teams is slightly different from site to site, so I made them all to the same format as basketball reference website to make sure everything can be working.

The reason I'm not taking the average fantasy points here from Yahoo's spreadsheet is that I believe season-long stats is not that helpful in daily fantasy sports compare to stats over the past week or so.

``` Python

def import_contest_data(team_opp, inactive_players, salaries, player_team, player_pos):
    """
        Import yahoo daily fantasy contest data and acquire information for building lineup

        Paramenters:
            team_opp: dict
                dictionary to contain information of which 2 teams play agaisnt each other 
            inactive_playeres: dict
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

```

#### GET DEFENSE VERSUS POSITION DATA
This part of code utilized data from Basketball Monster which analyze differnt teams defense against different positions. This could be useful for us to predict the potential outcome of a player's performance of the night based on his opponents.

The part I have to work around with is because of the .aspx page I need ASP.NET App "think" that I clicked the combobox to select differnt player positions to get the data. I used a webdriver to accomplish that and get the information I need.


``` Python

def getting_dvp_by_pos():

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
```

#### GET PLAYER STATS

Then I have to get players' stats. I think stats for the past 2 weeks serves the best for daily fantasy lineup based on experience. Need to verify if this is true.
I also dropped players who are not playing for the night


``` Python


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
   
```

#### CALCULATE FANTASY POINTS

Once I collect the data I need, I can combine the information together to generate fantasy points for all the players.

``` Python

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

```


## Future work

1. Getting more data from NBA.com. 
2. Handling high usg players sitting out / Injured
3. Explore possibility of ML
4. Start building up lineup records in Yahoo 1 dollar GPP and 50/50 contests
5. Adding factors of # of days rest 
