import io
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from dfs_core import ContestData, formalize_name, normalize_positions, normalize_team_abbreviation


def find_first_yahoo_contest() -> str | None:
    url = "https://sports.yahoo.com/dailyfantasy/nba"
    response = requests.get(url, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    first_contest = soup.find("a", class_="contestCard")
    if not first_contest:
        return None

    first_contest_link = first_contest.get("href", "")
    if "/contest/" not in first_contest_link:
        return None

    return first_contest_link.split("/contest/")[-1].split("/setlineup")[0]


def import_contest_data(contest_data: ContestData) -> pd.DataFrame:
    if contest_data.site == "dk" and contest_data.csv:
        players = pd.read_csv(contest_data.csv)
    else:
        players_url = (
            f"https://dfyql-ro.sports.yahoo.com/v2/export/contestPlayers?contestId={contest_data.contest_id}"
        )
        players = pd.read_csv(players_url)

    if contest_data.site == "dk":
        if "TeamAbbrev" in players.columns:
            players = players.rename(columns={"TeamAbbrev": "Team"})

        if "Game Info" in players.columns:
            players["Opponent"] = players.apply(_extract_dk_opponent, axis=1)

        if "Position" in players.columns:
            players["Position"] = players["Position"].apply(normalize_positions)

    players = players.replace(
        {
            "Team": {
                "NY": "NYK",
                "GS": "GSW",
                "NO": "NOP",
                "SA": "SAS",
                "CHA": "CHO",
            },
            "Opponent": {
                "NY": "NYK",
                "GS": "GSW",
                "NO": "NOP",
                "SA": "SAS",
                "CHA": "CHO",
            },
        }
    )

    for _, player in players.iterrows():
        raw_name = player.get("Name", f"{player.get('First Name', '')} {player.get('Last Name', '')}")
        player_name = formalize_name(raw_name)
        injury_status = str(player.get("Injury Status", "")).strip().upper()
        team = normalize_team_abbreviation(player.get("Team"))
        opponent = normalize_team_abbreviation(player.get("Opponent"))
        position_value = player.get("Position")
        positions = (
            position_value if isinstance(position_value, list) else normalize_positions(position_value)
        )

        if injury_status in {"INJ", "O", "D"}:
            contest_data.inactive_players[player_name] = 1

        if team and team not in contest_data.team_opponents and opponent:
            contest_data.team_opponents[team] = opponent

        salary_value = pd.to_numeric(player.get("Salary"), errors="coerce")
        if pd.notna(salary_value):
            contest_data.salaries[player_name] = int(salary_value)

        contest_data.player_teams[player_name] = team
        contest_data.player_positions[player_name] = positions

    return players


def get_recent_player_stats(contest_data: ContestData, days: int = 15) -> pd.DataFrame:
    stats_url = f"https://www.fantasypros.com/nba/stats/avg-overall.php?days={days}"
    recent_stats = pd.read_html(stats_url)[0]

    recent_stats["Player"] = recent_stats["Player"].str.split("(").str[0].str.strip()
    recent_stats["Player"] = recent_stats["Player"].apply(formalize_name)
    recent_stats["Tm"] = recent_stats["Player"].map(contest_data.player_teams)
    recent_stats["Positions"] = recent_stats["Player"].map(contest_data.player_positions)
    recent_stats["Salary"] = recent_stats["Player"].map(contest_data.salaries)
    recent_stats["Injured"] = recent_stats["Player"].map(contest_data.inactive_players)
    recent_stats["Opponent"] = recent_stats["Tm"].map(contest_data.team_opponents)

    recent_stats = recent_stats[recent_stats["Injured"].isnull()]
    recent_stats = recent_stats[recent_stats["Opponent"].notnull()]
    recent_stats = recent_stats[pd.to_numeric(recent_stats["Salary"], errors="coerce").notnull()]
    recent_stats = recent_stats.drop(columns=["Injured"])
    recent_stats = recent_stats.rename(columns={"REB": "TRB", "TO": "TOV"})

    stat_columns = ["MIN", "GP", "PTS", "TRB", "AST", "STL", "BLK", "TOV"]
    for column in stat_columns:
        recent_stats[column] = pd.to_numeric(recent_stats[column], errors="coerce").fillna(0)

    recent_stats["Positions"] = recent_stats["Positions"].apply(normalize_positions)
    recent_stats["PrimaryPos"] = recent_stats["Positions"].apply(lambda positions: positions[0] if positions else "")
    recent_stats["Ineligible"] = (recent_stats["MIN"] <= 0) | (recent_stats["GP"] <= 2)

    return recent_stats


def get_dvp_by_position(source: str, driver=None) -> dict[str, pd.DataFrame]:
    source_key = source.lower()
    if source_key == "none":
        return {}
    if source_key == "hashtag":
        return get_hashtag_dvp()
    if source_key == "basketballmonster":
        if driver is None:
            raise ValueError("Basketball Monster DVP requires a Selenium driver.")
        return get_basketballmonster_dvp(driver)
    raise ValueError(f"Unsupported DVP source: {source}")


def get_hashtag_dvp() -> dict[str, pd.DataFrame]:
    url = "https://hashtagbasketball.com/nba-defense-vs-position"
    response = requests.get(url, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    tables = pd.read_html(io.StringIO(response.text))
    position_table = None

    for table in tables:
        normalized_columns = [str(column).strip() for column in table.columns]
        required = {"Position", "Team", "PTS", "REB", "AST", "STL", "BLK"}
        if required.issubset(set(normalized_columns)):
            candidate = table.copy()
            candidate.columns = normalized_columns
            position_table = candidate
            break

    if position_table is None:
        fallback_data = _parse_hashtag_dvp_from_text(soup.get_text("\n"))
        if fallback_data:
            return fallback_data
        raise ValueError("Could not find a usable Hashtag Basketball DVP table.")

    position_table["Position"] = position_table["Position"].astype(str).str.strip().str.upper()
    position_table["Team"] = position_table["Team"].apply(normalize_team_abbreviation)

    stat_mapping = {
        "PTS": "p%",
        "REB": "r%",
        "AST": "a%",
        "STL": "s%",
        "BLK": "b%",
        "TO": "to%",
    }

    dvp_data = {}
    for position, frame in position_table.groupby("Position"):
        usable_columns = ["Team"] + [column for column in stat_mapping if column in frame.columns]
        stat_frame = frame[usable_columns].copy()

        for stat_column in usable_columns[1:]:
            stat_frame[stat_column] = pd.to_numeric(stat_frame[stat_column], errors="coerce")

        averages = stat_frame[usable_columns[1:]].mean(numeric_only=True)
        output = pd.DataFrame(index=stat_frame["Team"])

        for stat_column, output_column in stat_mapping.items():
            if stat_column not in stat_frame.columns or averages.get(stat_column, 0) == 0:
                continue
            delta = (stat_frame[stat_column] / averages[stat_column] - 1.0) * 100.0
            output[output_column] = delta.round(1).map(lambda value: f"{value:+.1f}%")

        dvp_data[position] = output

    return dvp_data


def _parse_hashtag_dvp_from_text(page_text: str) -> dict[str, pd.DataFrame]:
    stat_mapping = {
        "PTS": "p%",
        "REB": "r%",
        "AST": "a%",
        "STL": "s%",
        "BLK": "b%",
        "TO": "to%",
    }
    normalized_text = " ".join(page_text.split())
    pattern = re.compile(
        r"\b(PG|SG|SF|PF|C)\s+([A-Z]{2,3})\s+"
        r"\d+\s+([0-9.]+)\s+"       # overall rank, PTS
        r"\d+\s+[0-9.]+\s+"         # FG%
        r"\d+\s+[0-9.]+\s+"         # FT%
        r"\d+\s+[0-9.]+\s+"         # 3PM
        r"\d+\s+([0-9.]+)\s+"       # REB
        r"\d+\s+([0-9.]+)\s+"       # AST
        r"\d+\s+([0-9.]+)\s+"       # STL
        r"\d+\s+([0-9.]+)\s+"       # BLK
        r"\d+\s+([0-9.]+)\b"        # TO
    )
    records = []

    for match in pattern.finditer(normalized_text):
        try:
            record = {
                "Position": match.group(1),
                "Team": normalize_team_abbreviation(match.group(2)),
                "PTS": float(match.group(3)),
                "REB": float(match.group(4)),
                "AST": float(match.group(5)),
                "STL": float(match.group(6)),
                "BLK": float(match.group(7)),
                "TO": float(match.group(8)),
            }
        except ValueError:
            continue

        records.append(record)

    if not records:
        return {}

    position_table = pd.DataFrame(records).drop_duplicates(subset=["Position", "Team"], keep="last")
    dvp_data = {}

    for position, frame in position_table.groupby("Position"):
        output = pd.DataFrame(index=frame["Team"])
        averages = frame[list(stat_mapping.keys())].mean(numeric_only=True)

        for stat_name, output_name in stat_mapping.items():
            average = averages.get(stat_name, 0)
            if not average:
                continue
            delta = (frame[stat_name] / average - 1.0) * 100.0
            output[output_name] = delta.round(1).map(lambda value: f"{value:+.1f}%")

        dvp_data[position] = output

    return dvp_data


def get_basketballmonster_dvp(driver) -> dict[str, pd.DataFrame]:
    dvp_data = {}
    url = "https://basketballmonster.com/easerankings.aspx"
    position_options = {"3": "C", "4": "PG", "5": "SG", "6": "SF", "7": "PF"}
    driver.get(url)

    date_filter_xpath = "//select[@name='DateFilterControl']/option[@value='{}']"
    position_dropdown_xpath = "//select[@name='ctl00$ContentPlaceHolder1$PositionDropDownList']/option[@value='{}']"

    date_option = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, date_filter_xpath.format("LastTwoWeeks")))
    )
    date_option.click()

    for option_value, position in position_options.items():
        position_option = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, position_dropdown_xpath.format(option_value)))
        )
        position_option.click()

        tables = pd.read_html(driver.page_source)
        target_table = None
        for table in tables:
            if "vs Team" in table.columns:
                target_table = table.copy()
                break

        if target_table is None:
            continue

        target_table["vs Team"] = (
            target_table["vs Team"]
            .astype(str)
            .str.replace("vs", "", regex=False)
            .str.strip()
            .apply(normalize_team_abbreviation)
        )

        columns_to_drop = [column for column in ["Value", "pV", "rV", "aV", "sV", "bV", "toV"] if column in target_table]
        target_table = target_table.drop(columns=columns_to_drop).set_index("vs Team")
        dvp_data[position] = target_table

    return dvp_data


def _extract_dk_opponent(row) -> str | None:
    game_info = str(row.get("Game Info", ""))
    team = normalize_team_abbreviation(row.get("Team"))

    if "@" not in game_info:
        return None

    away_side, home_side = game_info.split("@", 1)
    away_team = normalize_team_abbreviation(away_side.split()[0])
    home_team = normalize_team_abbreviation(home_side.split()[0])

    if team == home_team:
        return away_team
    if team == away_team:
        return home_team
    return None
