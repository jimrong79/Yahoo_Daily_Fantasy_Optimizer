import argparse
import time
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_SCHEDULE_URL = "https://www.basketball-reference.com/leagues/{}_games-{}.html"
DEFAULT_MONTHS = ["october", "november", "december", "january", "february", "march", "april"]


def scrape_season_game_data(
    season_year: str,
    months: list[str] | None = None,
    request_delay: float = 3.0,
    max_games: int | None = None,
) -> pd.DataFrame:
    months = months or DEFAULT_MONTHS
    all_game_data = []
    games_processed = 0

    for month in months:
        schedule_url = BASE_SCHEDULE_URL.format(season_year, month)
        print(f"Processing schedule page: {schedule_url}")
        response = requests.get(schedule_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        if response.status_code != 200:
            print(f"Could not retrieve {schedule_url}")
            continue

        schedule_soup = BeautifulSoup(response.content, "html.parser")
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
            time.sleep(request_delay)

            game_data = scrape_single_game(game_url)
            if not game_data:
                continue

            all_game_data.extend(game_data)
            games_processed += 1
            print(f"Processed game: {game_url}")

            if max_games is not None and games_processed >= max_games:
                return pd.DataFrame(all_game_data)

    return pd.DataFrame(all_game_data)


def scrape_single_game(game_url: str) -> list[dict]:
    response = requests.get(game_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    if response.status_code != 200:
        print(f"Failed to get box score for {game_url}")
        return []

    game_soup = BeautifulSoup(response.content, "html.parser")
    scorebox = game_soup.find("div", class_="scorebox")
    if not scorebox:
        return []

    meta = scorebox.find("div", class_="scorebox_meta")
    game_date = _parse_game_date(meta)

    score_elems = scorebox.find_all("div", class_="score")
    if len(score_elems) < 2:
        return []

    try:
        team_score1 = int(score_elems[0].get_text().strip())
        team_score2 = int(score_elems[1].get_text().strip())
    except ValueError:
        return []

    basic_tables = game_soup.find_all("table", id=lambda table_id: table_id and table_id.endswith("-game-basic"))
    advanced_tables = game_soup.find_all(
        "table", id=lambda table_id: table_id and table_id.endswith("-game-advanced")
    )

    team_basic = _extract_team_tables(basic_tables)
    team_advanced_usage = _extract_advanced_usage(advanced_tables)
    if len(team_basic) != 2:
        return []

    team_abbrs = list(team_basic.keys())
    all_game_data = []

    for index, team_abbr in enumerate(team_abbrs):
        opponent_abbr = team_abbrs[1 - index]
        team_score = team_score1 if index == 0 else team_score2
        opponent_score = team_score2 if index == 0 else team_score1

        all_game_data.extend(
            _extract_team_player_rows(
                table=team_basic[team_abbr],
                team_abbr=team_abbr,
                opponent_abbr=opponent_abbr,
                team_score=team_score,
                opponent_score=opponent_score,
                game_date=game_date,
                game_url=game_url,
                team_advanced_usage=team_advanced_usage,
            )
        )

    return all_game_data


def _extract_team_tables(tables) -> dict[str, object]:
    team_tables = {}
    for table in tables:
        table_id = table.get("id")
        try:
            team_abbr = table_id.split("-")[1]
        except (AttributeError, IndexError):
            continue
        team_tables[team_abbr] = table
    return team_tables


def _extract_advanced_usage(advanced_tables) -> dict[str, dict[str, str]]:
    team_advanced_usage = {}
    for table in advanced_tables:
        table_id = table.get("id")
        try:
            team_abbr = table_id.split("-")[1]
        except (AttributeError, IndexError):
            continue

        usage_dict = {}
        tbody_adv = table.find("tbody")
        if not tbody_adv:
            continue

        for row in tbody_adv.find_all("tr"):
            if row.get("class") and "thead" in row.get("class"):
                continue

            player_cell = row.find("th", {"data-stat": "player"})
            usg_cell = row.find("td", {"data-stat": "usg_pct"})
            if player_cell and usg_cell:
                usage_dict[player_cell.get_text().strip()] = usg_cell.get_text().strip()

        team_advanced_usage[team_abbr] = usage_dict

    return team_advanced_usage


def _extract_team_player_rows(
    table,
    team_abbr: str,
    opponent_abbr: str,
    team_score: int,
    opponent_score: int,
    game_date: str | None,
    game_url: str,
    team_advanced_usage: dict[str, dict[str, str]],
) -> list[dict]:
    tbody = table.find("tbody")
    if not tbody:
        return []

    rows = []
    for row in tbody.find_all("tr"):
        if row.get("class") and "thead" in row.get("class"):
            continue

        player_cell = row.find("th", {"data-stat": "player"})
        cells = row.find_all("td")
        if not player_cell or not cells:
            continue

        stat = {
            "Player": player_cell.get_text().strip(),
            "TEAM": team_abbr,
            "OPP_TEAM": opponent_abbr,
            "team_final_score": team_score,
            "opp_final_score": opponent_score,
            "GAME_DATE": game_date,
            "GAME_URL": game_url,
        }

        stat_mapping = {
            "mp": "MIN",
            "pts": "PTS",
            "fg3": "3PM",
            "trb": "TRB",
            "ast": "AST",
            "stl": "STL",
            "blk": "BLK",
            "tov": "TOV",
        }

        for cell in cells:
            data_stat = cell.get("data-stat")
            if data_stat in stat_mapping:
                stat[stat_mapping[data_stat]] = cell.get_text().strip()

        usage_value = team_advanced_usage.get(team_abbr, {}).get(stat["Player"])
        if usage_value is not None:
            stat["USG"] = usage_value

        rows.append(stat)

    return rows


def _parse_game_date(meta) -> str | None:
    if meta is None:
        return None

    meta_lines = meta.get_text(separator="\n").strip().split("\n")
    if not meta_lines:
        return None

    try:
        date_obj = datetime.strptime(meta_lines[0].strip(), "%I:%M %p, %B %d, %Y")
    except ValueError:
        return None

    return date_obj.strftime("%m/%d/%Y")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Basketball Reference NBA game logs into CSV")
    parser.add_argument("--season", default="NBA_2025", help="Basketball Reference season id, for example NBA_2025")
    parser.add_argument("--output", default="nba_season_game_stats.csv", help="Output CSV path")
    parser.add_argument("--max-games", type=int, default=None, help="Optional limit for testing")
    args = parser.parse_args()

    data = scrape_season_game_data(args.season, max_games=args.max_games)
    data.to_csv(args.output, index=False)
    print(f"Saved {len(data)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
