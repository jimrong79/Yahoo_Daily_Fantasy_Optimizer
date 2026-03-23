import argparse
import sys

from selenium import webdriver

from data_providers import (
    find_first_yahoo_contest,
    get_dvp_by_position,
    get_recent_player_stats,
    import_contest_data,
)
from dfs_core import ContestData, formalize_name
from lineup_optimizer import build_lineup, calculate_fantasy_points


def main() -> int:
    parser = argparse.ArgumentParser(description="Yahoo & DraftKings NBA DFS Optimizer")
    parser.add_argument("--site", choices=["yahoo", "dk"], default="yahoo", help="Select DFS site")
    parser.add_argument("--csv", type=str, default="DKSalaries.csv", help="DraftKings salary CSV path")
    parser.add_argument(
        "--dvp-source",
        choices=["hashtag", "basketballmonster", "none"],
        default="hashtag",
        help="Choose the DVP provider",
    )
    parser.add_argument("--days", type=int, default=15, help="Number of recent days to use for player stats")
    parser.add_argument("--exclude", nargs="*", default=[], help="Player names to exclude")
    parser.add_argument("--select", nargs="*", default=[], help="Player names to lock into the lineup")
    args = parser.parse_args()
    excluded_players = [formalize_name(name) for name in args.exclude]
    selected_players = [formalize_name(name) for name in args.select]

    contest_id = None
    if args.site == "yahoo":
        try:
            contest_id = find_first_yahoo_contest()
        except Exception as exc:
            print(f"Error finding Yahoo contest: {exc}")
            return 1

        if not contest_id:
            print("No Yahoo contest found.")
            return 1

    contest_data = ContestData(site=args.site, contest_id=contest_id, csv=args.csv)

    try:
        import_contest_data(contest_data)
        for name in excluded_players:
            contest_data.inactive_players[name] = 1

        driver = None
        if args.dvp_source == "basketballmonster":
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            driver = webdriver.Chrome(options=options)

        try:
            dvp_data = get_dvp_by_position(args.dvp_source, driver=driver)
        finally:
            if driver is not None:
                driver.quit()

        player_stats = get_recent_player_stats(contest_data, days=args.days)
        if player_stats.empty:
            print("No player stats available.")
            return 1

        projected_players = calculate_fantasy_points(
            player_stats,
            dvp_data=dvp_data,
            apply_dvp=args.dvp_source != "none",
        )
        lineup_result = build_lineup(
            projected_players,
            site=args.site,
            lineup_name=f"Last {args.days} Days",
            selected_players=selected_players,
            excluded_players=excluded_players,
        )
    except Exception as exc:
        print(f"Optimizer failed: {exc}")
        return 1

    print(f"Lineup built using Last {args.days} Days stats:")
    print(lineup_result.lineup)
    print(f"Total Salary Used: {lineup_result.total_salary}")
    print(f"Projected Fantasy Points: {lineup_result.projected_points}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
