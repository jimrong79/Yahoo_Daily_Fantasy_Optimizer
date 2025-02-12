import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime


# --- CONFIGURATION ---
season_year = "NBA_2025"  # Change to your target season
months = ["october", "november", "december", "january", "february", "march", "april"]

# Base URL for schedule pages
BASE_SCHEDULE_URL = "https://www.basketball-reference.com/leagues/{}_games-{}.html"

# List to hold each player's game-level stats
all_game_data = []

# --- LOOP THROUGH SCHEDULE PAGES ---
for month in months:
    schedule_url = BASE_SCHEDULE_URL.format(season_year, month)
    print(f"Processing schedule page: {schedule_url}")
    resp = requests.get(schedule_url, headers={"User-Agent": "Mozilla/5.0"})
    if resp.status_code != 200:
        print(f"Could not retrieve {schedule_url}")
        continue
    schedule_soup = BeautifulSoup(resp.content, "html.parser")
    
    schedule_table = schedule_soup.find("table", id="schedule")
    if not schedule_table:
        print("No schedule table found.")
        continue

    rows = schedule_table.find("tbody").find_all("tr")
    for row in rows:
        if row.get("class") and "thead" in row.get("class"):
            continue
        box_link_tag = row.find("a", string="Box Score")
        if not box_link_tag:
            continue
        game_relative_url = box_link_tag.get("href")
        game_url = "https://www.basketball-reference.com" + game_relative_url

        # Pause 3 seconds per request (to stay under 30 pages/minute)
        time.sleep(3)

        # --- PROCESS INDIVIDUAL GAME BOX SCORE ---
        game_resp = requests.get(game_url, headers={"User-Agent": "Mozilla/5.0"})
        if game_resp.status_code != 200:
            print(f"Failed to get box score for {game_url}")
            continue
        game_soup = BeautifulSoup(game_resp.content, "html.parser")

        # Extract game date from the scorebox meta, if available
        scorebox = game_soup.find("div", class_="scorebox")
        if not scorebox:
            continue

        # Capture game date if present in a scorebox_meta div
        meta = scorebox.find("div", class_="scorebox_meta")
        if meta:
            meta_lines = meta.get_text(separator="\n").strip().split("\n")
            game_date_str = meta_lines[0].strip()  # often the first line is the date
        else:
            game_date_str = None

        # Extract team names from <strong> tags.
        team_tags = scorebox.find_all("strong")
        if len(team_tags) < 2:
            continue
        team1_full = team_tags[0].get_text().strip()
        team2_full = team_tags[1].get_text().strip()

        # Extract final scores from score elements.
        score_elems = scorebox.find_all("div", class_="score")
        if len(score_elems) < 2:
            print("Could not extract final scores.")
            continue
        try:
            team_score1 = int(score_elems[0].get_text().strip())
            team_score2 = int(score_elems[1].get_text().strip())
        except ValueError:
            print("Score conversion error.")
            continue

        # --- Extract Basic Box Score Data ---
        basic_tables = game_soup.find_all("table", id=lambda x: x and x.endswith("-game-basic"))
        if len(basic_tables) != 2:
            print("Unexpected number of basic box score tables.")
            continue
        team_basic = {}
        for table in basic_tables:
            table_id = table.get("id")
            try:
                team_abbr = table_id.split("-")[1]
            except IndexError:
                continue
            team_basic[team_abbr] = table

        if len(team_basic) != 2:
            continue
        team_abbrs = list(team_basic.keys())
        
        # --- Extract Advanced Box Score Data (for USG) ---
        advanced_tables = game_soup.find_all("table", id=lambda x: x and x.endswith("-game-advanced"))
        # Build a mapping: team abbreviation -> {player_name: usage}
        team_advanced_usage = {}
        if len(advanced_tables) == 2:
            for table in advanced_tables:
                table_id = table.get("id")
                try:
                    team_abbr = table_id.split("-")[1]
                except IndexError:
                    continue
                usage_dict = {}
                tbody_adv = table.find("tbody")
                if tbody_adv:
                    adv_rows = tbody_adv.find_all("tr")
                    for adv_row in adv_rows:
                        if adv_row.get("class") and "thead" in adv_row.get("class"):
                            continue
                        player_cell = adv_row.find("th", {"data-stat": "player"})
                        if not player_cell:
                            continue
                        player_name = player_cell.get_text().strip()
                        # USG is typically in a cell with data-stat "usg"
                        usg_cell = adv_row.find("td", {"data-stat": "usg_pct"})
                        if usg_cell:
                            usage_dict[player_name] = usg_cell.get_text().strip()
                team_advanced_usage[team_abbr] = usage_dict

        # For each team from the basic table, process the player rows.
        for i, team_abbr in enumerate(team_abbrs):
            opp_abbr = team_abbrs[1 - i]
            table = team_basic[team_abbr]
            tbody = table.find("tbody")
            if not tbody:
                continue
            player_rows = tbody.find_all("tr")
            for prow in player_rows:
                if prow.get("class") and "thead" in prow.get("class"):
                    continue
                cells = prow.find_all("td")
                if not cells:
                    continue
                stat = {}
                player_cell = prow.find("th", {"data-stat": "player"})
                if player_cell:
                    stat["Player"] = player_cell.get_text().strip()
                else:
                    continue
                # Extract basic stats from the basic table.
                for cell in cells:
                    data_stat = cell.get("data-stat")
                    text_val = cell.get_text().strip()
                    if data_stat == "mp":
                        stat["MIN"] = text_val
                    elif data_stat == "pts":
                        stat["PTS"] = text_val
                    elif data_stat == "fg3":
                        stat["3PM"] = text_val
                    elif data_stat == "trb":
                        stat["TRB"] = text_val
                    elif data_stat == "ast":
                        stat["AST"] = text_val
                    elif data_stat == "stl":
                        stat["STL"] = text_val
                    elif data_stat == "blk":
                        stat["BLK"] = text_val
                    elif data_stat == "tov":
                        stat["TOV"] = text_val
                # Look up USG from the advanced mapping (if available)
                usg_value = None
                if team_abbr in team_advanced_usage:
                    usg_value = team_advanced_usage[team_abbr].get(stat["Player"], None)
                if usg_value is not None:
                    stat["USG"] = usg_value

                # Add game context: team affiliation and final scores.
                stat["TEAM"] = team_abbr
                stat["OPP_TEAM"] = opp_abbr
                if i == 0:
                    team_score = team_score1
                    opp_score = team_score2
                else:
                    team_score = team_score2
                    opp_score = team_score1
                stat["team_final_score"] = team_score
                stat["opp_final_score"] = opp_score
                # Add game date if available.
                if game_date_str:
                    # Parse the string into a datetime object
                    date_obj = datetime.strptime(game_date_str, '%I:%M %p, %B %d, %Y')
                    # Format the datetime object to the desired string format
                    stat["GAME_DATE"] = date_obj.strftime('%m/%d/%Y')
                stat["GAME_URL"] = game_url

                all_game_data.append(stat)
                
        print(f"Processed game: {game_url}")
        # For testing purposes, you might break early (remove break in production)
        break  # Remove or comment out this break to process all games in each month

# --- CREATE DATAFRAME AND SAVE ---
df = pd.DataFrame(all_game_data)
print("Sample scraped data:")
print(df.head())

# Save the results to CSV
df.to_csv("nba_season_game_stats.csv", index=False)
