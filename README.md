# Yahoo NBA Daily Fantasy Lineup Optimizer

This project builds NBA daily fantasy lineups for Yahoo and DraftKings using recent player stats, salary data, matchup adjustments, and linear optimization.

It is designed as a personal research tool for generating a strongest-projected lineup from a given slate. The optimizer can pull contest data, gather recent player averages, optionally apply defense-versus-position adjustments, and return a salary-cap-valid lineup.

## Features

- supports both Yahoo and DraftKings slates
- builds lineups under each site's salary and roster rules
- uses recent FantasyPros player averages
- supports pluggable DVP sources
- can lock players into a lineup
- can exclude players from the player pool
- includes a separate script for scraping historical NBA game logs from Basketball Reference

## Project Files

- `yahoo_dfs_optimizer.py`: main command-line entry point
- `data_providers.py`: contest import, recent stats, and DVP data loading
- `lineup_optimizer.py`: fantasy point calculations and lineup optimization
- `dfs_core.py`: shared normalization and contest data helpers
- `season_data.py`: historical game-log scraper
- `requirements.txt`: Python dependencies

## Requirements

- Python 3.10+
- Google Chrome and ChromeDriver only if using `--dvp-source basketballmonster`

Install dependencies:

```bash
pip install -r requirements.txt
```

If you use Conda, activate your environment first and then run the same install command.

## How It Works

The optimizer follows this general flow:

1. Load the contest player pool from Yahoo or from a DraftKings salary CSV.
2. Normalize player names, teams, opponents, salaries, and positions.
3. Pull recent player averages from FantasyPros.
4. Optionally apply defense-versus-position matchup adjustments.
5. Solve for the highest projected lineup that satisfies salary cap and roster-slot rules.

## Usage

### Yahoo

Build a Yahoo lineup using Hashtag Basketball DVP data:

```bash
python yahoo_dfs_optimizer.py --site yahoo --dvp-source hashtag
```

Build a Yahoo lineup without DVP adjustments:

```bash
python yahoo_dfs_optimizer.py --site yahoo --dvp-source none
```

### DraftKings

Build a DraftKings lineup from a local salary CSV:

```bash
python yahoo_dfs_optimizer.py --site dk --csv DKSalaries.csv --dvp-source none
```

### Locking And Excluding Players

Lock players into the lineup:

```bash
python yahoo_dfs_optimizer.py --site yahoo --select "Nikola Jokic" "Jalen Brunson"
```

Exclude players from the player pool:

```bash
python yahoo_dfs_optimizer.py --site yahoo --exclude "Player Name"
```

Adjust the recent-stat sample window:

```bash
python yahoo_dfs_optimizer.py --site yahoo --days 7
```

## DVP Sources

The optimizer supports these options:

- `hashtag`: free/public DVP source from Hashtag Basketball
- `basketballmonster`: Selenium-based Basketball Monster scrape
- `none`: disables DVP matchup adjustments

Example:

```bash
python yahoo_dfs_optimizer.py --site yahoo --dvp-source hashtag
```

## Historical Data Scraper

The project also includes a Basketball Reference scraper for collecting game-level season data.

Example:

```bash
python season_data.py --season NBA_2025 --output nba_season_game_stats.csv
```

Optional test run with a limit:

```bash
python season_data.py --season NBA_2025 --max-games 5
```

## Notes

- Yahoo contest data is pulled from Yahoo's contest export endpoint.
- DraftKings input currently comes from a local salary CSV.
- External sites can change their markup or access rules over time, which may require updates to scraping logic.
- This project is best treated as a lineup research tool, not a guarantee of DFS results.
