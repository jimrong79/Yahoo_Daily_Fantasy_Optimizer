from dataclasses import dataclass

import pandas as pd
from pulp import LpMaximize, LpProblem, LpStatus, LpVariable, lpSum

from dfs_core import normalize_positions

SITE_RULES = {
    "yahoo": {
        "salary_cap": 200,
        "roster_slots": ["PG", "SG", "G", "SF", "PF", "F", "C", "UTIL"],
    },
    "dk": {
        "salary_cap": 50000,
        "roster_slots": ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"],
    },
}

FANTASY_POINTS_WEIGHTS = {
    "PTS": 1.0,
    "TRB": 1.2,
    "AST": 1.5,
    "STL": 3.0,
    "BLK": 3.0,
    "TOV": -1.0,
}


@dataclass
class LineupResult:
    lineup: pd.DataFrame
    total_salary: float
    projected_points: float
    solver_status: str


def calculate_fantasy_points(players: pd.DataFrame, dvp_data: dict[str, pd.DataFrame], apply_dvp: bool = True) -> pd.DataFrame:
    projected_players = players.copy()

    for stat in FANTASY_POINTS_WEIGHTS:
        projected_players[stat] = pd.to_numeric(projected_players[stat], errors="coerce").fillna(0.0)

    if apply_dvp:
        for index, player in projected_players.iterrows():
            positions = normalize_positions(player.get("Positions"))
            opponent = player.get("Opponent")
            position = _pick_dvp_position(positions, dvp_data)

            if not position or position not in dvp_data or opponent not in dvp_data[position].index:
                continue

            dvp_row = dvp_data[position].loc[opponent]
            adjustments = {
                "PTS": _percent_to_multiplier(dvp_row.get("p%")),
                "TRB": _percent_to_multiplier(dvp_row.get("r%")),
                "AST": _percent_to_multiplier(dvp_row.get("a%")),
                "STL": _percent_to_multiplier(dvp_row.get("s%")),
                "BLK": _percent_to_multiplier(dvp_row.get("b%")),
                "TOV": _percent_to_multiplier(dvp_row.get("to%")),
            }

            for stat, multiplier in adjustments.items():
                projected_players.at[index, stat] = round(projected_players.at[index, stat] * multiplier, 2)

    projected_players["FP"] = sum(
        projected_players[stat] * weight for stat, weight in FANTASY_POINTS_WEIGHTS.items()
    )

    return projected_players


def build_lineup(
    players: pd.DataFrame,
    site: str = "yahoo",
    lineup_name: str | None = None,
    selected_players: list[str] | None = None,
    excluded_players: list[str] | None = None,
) -> LineupResult:
    selected_players = selected_players or []
    excluded_players = set(excluded_players or [])

    rules = SITE_RULES[site]
    roster_slots = rules["roster_slots"]
    salary_cap = rules["salary_cap"]

    player_pool = players.copy().reset_index(drop=True)
    player_pool["Salary"] = pd.to_numeric(player_pool["Salary"], errors="coerce").fillna(0.0)
    player_pool["FP"] = pd.to_numeric(player_pool["FP"], errors="coerce").fillna(0.0)
    player_pool["Positions"] = player_pool["Positions"].apply(normalize_positions)
    player_pool["EligibleSlots"] = player_pool["Positions"].apply(lambda positions: _eligible_slots(site, positions))

    model = LpProblem(f"{site.upper()}_DFS_Lineup", LpMaximize)

    assignment_vars = {}
    for player_index, player in player_pool.iterrows():
        for slot in player["EligibleSlots"]:
            assignment_vars[(player_index, slot)] = LpVariable(f"player_{player_index}_{slot}", cat="Binary")

    model += lpSum(
        player_pool.at[player_index, "FP"] * variable
        for (player_index, _slot), variable in assignment_vars.items()
    )

    for slot in roster_slots:
        model += lpSum(
            variable for (player_index, candidate_slot), variable in assignment_vars.items() if candidate_slot == slot
        ) == 1, f"Fill_{slot}"

    for player_index, player in player_pool.iterrows():
        player_variables = [
            variable for (candidate_index, _slot), variable in assignment_vars.items() if candidate_index == player_index
        ]
        if not player_variables:
            continue

        model += lpSum(player_variables) <= 1, f"Use_Player_{player_index}"

        player_name = player["Player"]
        if player.get("Ineligible", False) or player_name in excluded_players:
            model += lpSum(player_variables) == 0, f"Exclude_Player_{player_index}"
        elif player_name in selected_players:
            model += lpSum(player_variables) == 1, f"Lock_Player_{player_index}"

    model += lpSum(
        player_pool.at[player_index, "Salary"] * variable
        for (player_index, _slot), variable in assignment_vars.items()
    ) <= salary_cap, "Salary_Cap"

    model.solve()
    solver_status = LpStatus.get(model.status, str(model.status))
    if solver_status != "Optimal":
        raise ValueError(f"Lineup solver did not find an optimal lineup. Status: {solver_status}")

    lineup_rows = []
    for (player_index, slot), variable in assignment_vars.items():
        if variable.varValue == 1.0:
            lineup_rows.append(
                {
                    "RosterSlot": slot,
                    "Player": player_pool.at[player_index, "Player"],
                    "Positions": "/".join(player_pool.at[player_index, "Positions"]),
                    "Tm": player_pool.at[player_index, "Tm"],
                    "Salary": player_pool.at[player_index, "Salary"],
                    "FP": round(player_pool.at[player_index, "FP"], 2),
                }
            )

    lineup = pd.DataFrame(lineup_rows)
    lineup["RosterSlot"] = pd.Categorical(lineup["RosterSlot"], roster_slots, ordered=True)
    lineup = lineup.sort_values("RosterSlot").reset_index(drop=True)

    return LineupResult(
        lineup=lineup,
        total_salary=float(lineup["Salary"].sum()),
        projected_points=round(float(lineup["FP"].sum()), 2),
        solver_status=solver_status,
    )


def _eligible_slots(site: str, positions: list[str]) -> list[str]:
    slots = []
    normalized_positions = normalize_positions(positions)

    for position in normalized_positions:
        if position in {"PG", "SG", "SF", "PF", "C"} and position not in slots:
            slots.append(position)

    if any(position in {"PG", "SG"} for position in normalized_positions):
        slots.append("G")

    if any(position in {"SF", "PF"} for position in normalized_positions):
        slots.append("F")

    if site in {"yahoo", "dk"}:
        slots.append("UTIL")

    return list(dict.fromkeys(slot for slot in slots if slot in SITE_RULES[site]["roster_slots"]))


def _percent_to_multiplier(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 1.0

    text = str(value).strip().replace("%", "")
    if not text:
        return 1.0

    return (float(text) / 100.0) + 1.0


def _pick_dvp_position(positions: list[str], dvp_data: dict[str, pd.DataFrame]) -> str | None:
    for position in positions:
        if position in dvp_data:
            return position

    if "G" in positions:
        for fallback in ["PG", "SG"]:
            if fallback in dvp_data:
                return fallback

    if "F" in positions:
        for fallback in ["SF", "PF"]:
            if fallback in dvp_data:
                return fallback

    return None
