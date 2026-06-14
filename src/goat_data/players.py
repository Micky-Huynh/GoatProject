from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from goat_data.config import GoatPaths, load_yaml, normalize_name


@dataclass(frozen=True)
class Allowlist:
    player_ids: list[str]
    display_names: dict[str, str]
    pre_three_point_line_players: set[str]


def load_career_info(paths: GoatPaths) -> pd.DataFrame:
    frame = pd.read_csv(paths.raw_data / "Player Career Info.csv")
    frame["norm_name"] = frame["player"].map(normalize_name)
    return frame


def resolve_allowlist(paths: GoatPaths) -> Allowlist:
    cfg = load_yaml(paths.allowlist)
    career = load_career_info(paths)
    lookup = career.drop_duplicates("norm_name").set_index("norm_name")

    player_ids: list[str] = []
    display_names: dict[str, str] = {}
    unresolved: list[str] = []

    for entry in cfg["players"]:
        norm = normalize_name(entry["name"])
        if norm not in lookup.index:
            unresolved.append(entry["name"])
            continue
        row = lookup.loc[norm]
        player_id = row["player_id"]
        player_ids.append(player_id)
        display_names[player_id] = row["player"]

    if unresolved:
        raise ValueError(f"Allowlist names not found in Career Info: {unresolved}")
    if len(player_ids) != cfg["player_count"]:
        raise ValueError(f"Expected {cfg['player_count']} players, resolved {len(player_ids)}")

    pre_three = {normalize_name(name) for name in cfg.get("pre_three_point_line_players", [])}
    pre_three_ids = {
        lookup.loc[norm, "player_id"]
        for norm in pre_three
        if norm in lookup.index
    }

    return Allowlist(
        player_ids=player_ids,
        display_names=display_names,
        pre_three_point_line_players=pre_three_ids,
    )
