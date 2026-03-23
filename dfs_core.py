from dataclasses import dataclass, field

TEAM_NAME_CORRECTIONS = {
    "NY": "NYK",
    "GS": "GSW",
    "NO": "NOP",
    "SA": "SAS",
    "CHA": "CHO",
    "NOR": "NOP",
}

NAME_CORRECTIONS = {
    "Jakob Poltl": "Jakob Poeltl",
    "Taurean Waller-Prince": "Taurean Prince",
    "Mo Bamba": "Mohamed Bamba",
    "Bojan BogdanoviÄ‡": "Bojan Bogdanovic",
    "Bobby Portis Jr.": "Bobby Portis",
}


@dataclass
class ContestData:
    site: str
    contest_id: int | None = None
    csv: str | None = None
    team_opponents: dict = field(default_factory=dict)
    inactive_players: dict = field(default_factory=dict)
    salaries: dict = field(default_factory=dict)
    player_teams: dict = field(default_factory=dict)
    player_positions: dict = field(default_factory=dict)


def normalize_team_abbreviation(team: str | None) -> str | None:
    if team is None:
        return None
    return TEAM_NAME_CORRECTIONS.get(str(team).strip(), str(team).strip())


def formalize_name(name: str | None) -> str:
    if name is None:
        return ""

    corrected_name = NAME_CORRECTIONS.get(str(name).strip(), str(name).strip())

    try:
        from unidecode import unidecode
    except ImportError:
        return corrected_name.replace(".", "").strip()

    return unidecode(corrected_name).replace(".", "").strip()


def normalize_positions(position_value) -> list[str]:
    if position_value is None:
        return []

    if isinstance(position_value, list):
        raw_positions = position_value
    else:
        raw_positions = str(position_value).split("/")

    normalized = []
    for position in raw_positions:
        clean_position = str(position).strip().upper()
        if clean_position and clean_position not in normalized:
            normalized.append(clean_position)
    return normalized
