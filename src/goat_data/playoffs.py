from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from goat_data.config import GoatPaths, load_yaml


@dataclass(frozen=True)
class TeamPcaResult:
    components: np.ndarray
    explained_variance_ratio: np.ndarray
    mean: np.ndarray
    feature_columns: list[str]
    strength_metric: str


@dataclass(frozen=True)
class PlayoffBuildResult:
    player_context: pd.DataFrame
    team_snapshots: pd.DataFrame
    team_pca: TeamPcaResult


def load_finals_results(paths: GoatPaths) -> pd.DataFrame:
    playoffs_cfg = load_yaml(paths.root / "config" / "playoffs.yaml")
    filename = playoffs_cfg.get("finals_results_file", "finals_results.csv")
    finals_path = paths.raw_data / filename
    if not finals_path.exists():
        finals_path = paths.root / "data" / filename
    frame = pd.read_csv(finals_path)
    frame["season"] = frame["season"].astype(int)
    return frame


def _normalize_abbrev(value: str) -> str:
    text = str(value).strip().upper()
    aliases = {
        "PHX": "PHO",
        "PHO": "PHO",
        "NJN": "NJN",
        "BRK": "NJN",
        "CHO": "CHA",
        "CHH": "CHA",
        "CHA": "CHA",
        "NOH": "NOP",
        "NOP": "NOP",
        "NO": "NOP",
        "GS": "GSW",
        "SAN": "SAS",
        "NYN": "NYK",
        "WSB": "WSB",
        "WAS": "WSB",
    }
    return aliases.get(text, text)


def _max_consecutive_seasons(seasons: list[int]) -> int:
    if not seasons:
        return 0
    ordered = sorted(set(int(s) for s in seasons))
    best = current = 1
    for idx in range(1, len(ordered)):
        if ordered[idx] == ordered[idx - 1] + 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def _repeat_titles_score(ring_seasons: list[int], cfg: dict[str, Any]) -> tuple[int, float]:
    """Score rings with extra credit for back-to-back and dynasty runs."""
    if not ring_seasons:
        return 0, 0.0
    ordered = sorted(set(int(s) for s in ring_seasons))
    max_consecutive = _max_consecutive_seasons(ordered)
    bonus_per = float(cfg.get("consecutive_bonus_per_ring", 0.75))
    dynasty_threshold = int(cfg.get("dynasty_threshold", 3))
    dynasty_bonus = float(cfg.get("dynasty_bonus", 1.5))

    score = float(len(ordered))
    streak = 1
    for idx in range(1, len(ordered)):
        if ordered[idx] == ordered[idx - 1] + 1:
            streak += 1
        else:
            if streak > 1:
                score += (streak - 1) * bonus_per
            streak = 1
    if streak > 1:
        score += (streak - 1) * bonus_per
    if max_consecutive >= dynasty_threshold:
        score += dynasty_bonus
    return max_consecutive, score


def build_team_season_snapshots(paths: GoatPaths) -> tuple[pd.DataFrame, list[str]]:
    playoffs_cfg = load_yaml(paths.root / "config" / "playoffs.yaml")
    snap_cfg = playoffs_cfg["team_snapshot"]
    summary_features = list(snap_cfg["summary_features"])
    per_game_features = list(snap_cfg["per_game_features"])

    summaries = pd.read_csv(paths.raw_data / "Team Summaries.csv")
    summaries = summaries[summaries["playoffs"] == True].copy()
    summaries["abbreviation"] = summaries["abbreviation"].map(_normalize_abbrev)
    summaries["season"] = summaries["season"].astype(int)

    per_game = pd.read_csv(paths.raw_data / "Team Stats Per Game.csv")
    per_game = per_game[per_game["playoffs"] == True].copy()
    per_game["abbreviation"] = per_game["abbreviation"].map(_normalize_abbrev)
    per_game["season"] = per_game["season"].astype(int)

    merged = summaries.merge(
        per_game[["season", "abbreviation", *per_game_features]],
        on=["season", "abbreviation"],
        how="inner",
        suffixes=("_summary", "_pg"),
    )
    feature_cols = summary_features + per_game_features
    for col in feature_cols:
        merged[col] = pd.to_numeric(merged[col], errors="coerce")
    merged = merged.dropna(subset=feature_cols, how="all")
    return merged, feature_cols


def fit_team_pca(snapshots: pd.DataFrame, feature_cols: list[str], cfg: dict[str, Any]) -> TeamPcaResult:
    values = snapshots[feature_cols].astype(float).to_numpy()
    values = np.nan_to_num(values, nan=0.0)
    mean = values.mean(axis=0, keepdims=True)
    centered = values - mean
    _, singular_values, vt = np.linalg.svd(centered, full_matrices=False)
    explained = (singular_values ** 2) / max(centered.shape[0] - 1, 1)
    total = explained.sum()
    ratio = explained / total if total > 0 else explained
    cumulative = np.cumsum(ratio)
    threshold = float(cfg.get("cumulative_variance_threshold", 0.90))
    k = int(np.searchsorted(cumulative, threshold) + 1)
    k = max(1, min(k, len(ratio)))
    return TeamPcaResult(
        components=vt[:k],
        explained_variance_ratio=ratio[:k],
        mean=mean,
        feature_columns=feature_cols,
        strength_metric=str(cfg.get("strength_metric", "l2_norm")),
    )


def _project_team_strength(snapshots: pd.DataFrame, feature_cols: list[str], team_pca: TeamPcaResult) -> pd.Series:
    values = np.nan_to_num(snapshots[feature_cols].astype(float).to_numpy(), nan=0.0)
    centered = values - team_pca.mean
    projected = centered @ team_pca.components.T
    if team_pca.strength_metric == "pc1":
        return pd.Series(projected[:, 0], index=snapshots.index)
    return pd.Series(np.linalg.norm(projected, axis=1), index=snapshots.index)


def build_player_season_teams(paths: GoatPaths) -> pd.DataFrame:
    advanced = pd.read_csv(paths.raw_data / "Advanced.csv")
    advanced["season"] = advanced["season"].astype(int)
    advanced["team"] = advanced["team"].astype(str).str.strip().str.upper()

    def pick_row(group: pd.DataFrame) -> pd.Series:
        totals = group[group["team"].str.endswith("TM", na=False)]
        if not totals.empty:
            return totals.sort_values("mp", ascending=False).iloc[0]
        return group.sort_values("mp", ascending=False).iloc[0]

    rows = [pick_row(group) for _, group in advanced.groupby(["player_id", "season"], sort=False)]
    frame = pd.DataFrame(rows).reset_index(drop=True)
    frame["team_abbrev"] = frame["team"].str.replace("TM", "", regex=False).map(_normalize_abbrev)
    return frame[["player_id", "player", "season", "team_abbrev", "mp"]]


def build_playoff_context(
    paths: GoatPaths,
    allowlist_player_ids: set[str] | list[str],
    display_names: dict[str, str],
) -> PlayoffBuildResult:
    allowlist_player_ids = set(allowlist_player_ids)
    playoffs_cfg = load_yaml(paths.root / "config" / "playoffs.yaml")
    snapshots, feature_cols = build_team_season_snapshots(paths)
    team_pca = fit_team_pca(snapshots, feature_cols, playoffs_cfg["team_snapshot"]["pca"])
    snapshots = snapshots.copy()
    snapshots["team_strength_raw"] = _project_team_strength(snapshots, feature_cols, team_pca)

    strength_median = float(snapshots["team_strength_raw"].median())
    snapshots["team_strength_index"] = snapshots["team_strength_raw"] - strength_median

    strength_lookup = snapshots.set_index(["season", "abbreviation"])["team_strength_index"].to_dict()
    playoff_teams = set(zip(snapshots["season"].tolist(), snapshots["abbreviation"].tolist()))

    finals = load_finals_results(paths)
    finals["champion_abbrev"] = finals["champion_abbrev"].map(_normalize_abbrev)
    finals["runner_up_abbrev"] = finals["runner_up_abbrev"].map(_normalize_abbrev)
    champ_by_season = finals.set_index("season")["champion_abbrev"].to_dict()
    runner_by_season = finals.set_index("season")["runner_up_abbrev"].to_dict()

    player_seasons = build_player_season_teams(paths)
    player_seasons = player_seasons[player_seasons["player_id"].isin(allowlist_player_ids)].copy()

    perf_cfg = playoffs_cfg.get("playoff_performance", {})
    ring_depth = float(perf_cfg.get("ring_depth", 3.0))
    finals_depth = float(perf_cfg.get("finals_depth", 2.0))
    playoff_depth = float(perf_cfg.get("playoff_depth", 1.0))
    underdog_depth_bonus = float(perf_cfg.get("underdog_depth_bonus", 0.15))

    champ_cfg = playoffs_cfg["championship"]
    ring_base = float(champ_cfg["ring_base_credit"])
    loss_base = float(champ_cfg["finals_loss_base"])
    underdog_w = float(champ_cfg["underdog_weight"])
    favorite_w = float(champ_cfg["favorite_penalty"])

    season_rows: list[dict[str, Any]] = []
    for row in player_seasons.itertuples(index=False):
        key = (int(row.season), str(row.team_abbrev))
        if key not in playoff_teams:
            continue
        strength = float(strength_lookup.get(key, 0.0))
        season = int(row.season)
        team = str(row.team_abbrev)
        ring = int(champ_by_season.get(season) == team)
        finals_loss = int(runner_by_season.get(season) == team)
        finals_app = int(ring or finals_loss)
        underdog_bonus = max(0.0, -strength) * underdog_w
        favorite_penalty = max(0.0, strength) * favorite_w
        ring_credit = ring * (ring_base + underdog_bonus)
        loss_debit = finals_loss * (loss_base + favorite_penalty)
        if ring:
            depth = ring_depth
        elif finals_loss:
            depth = finals_depth
        else:
            depth = playoff_depth
        depth *= 1.0 + max(0.0, -strength) * underdog_depth_bonus
        season_rows.append(
            {
                "player_id": row.player_id,
                "season": season,
                "team_abbrev": team,
                "playoff_team_strength": strength,
                "championship_won": ring,
                "finals_loss": finals_loss,
                "finals_appearance": finals_app,
                "ring_credit": ring_credit,
                "finals_loss_debit": loss_debit,
                "depth_score": depth,
            }
        )

    season_frame = pd.DataFrame(season_rows)
    if season_frame.empty:
        empty = pd.DataFrame(
            {
                "player_id": list(allowlist_player_ids),
                "display_name": [display_names.get(pid, pid) for pid in allowlist_player_ids],
                "championships": 0,
                "finals_losses": 0,
                "finals_appearances": 0,
                "playoff_seasons": 0,
                "team_strength_index": 0.0,
                "championship_credit": 0.0,
                "finals_loss_debit": 0.0,
                "championship_net": 0.0,
                "playoff_performance": 0.0,
                "max_consecutive_championships": 0,
                "repeat_titles_score": 0.0,
            }
        )
        return PlayoffBuildResult(player_context=empty, team_snapshots=snapshots, team_pca=team_pca)

    grouped = season_frame.groupby("player_id", as_index=False).agg(
        championships=("championship_won", "sum"),
        finals_losses=("finals_loss", "sum"),
        finals_appearances=("finals_appearance", "sum"),
        playoff_seasons=("season", "count"),
        team_strength_index=("playoff_team_strength", "mean"),
        championship_credit=("ring_credit", "sum"),
        finals_loss_debit=("finals_loss_debit", "sum"),
        playoff_depth_total=("depth_score", "sum"),
    )
    grouped["playoff_performance"] = grouped["playoff_depth_total"] / grouped["playoff_seasons"].clip(lower=1)
    grouped["championship_net"] = grouped["championship_credit"] - grouped["finals_loss_debit"]

    repeat_cfg = playoffs_cfg.get("repeat_titles", {})
    repeat_rows: list[dict[str, Any]] = []
    ring_frame = season_frame[season_frame["championship_won"] == 1]
    for player_id, sub in ring_frame.groupby("player_id"):
        seasons = sub["season"].astype(int).tolist()
        max_consecutive, repeat_score = _repeat_titles_score(seasons, repeat_cfg)
        repeat_rows.append(
            {
                "player_id": player_id,
                "max_consecutive_championships": max_consecutive,
                "repeat_titles_score": repeat_score,
            }
        )
    if repeat_rows:
        grouped = grouped.merge(pd.DataFrame(repeat_rows), on="player_id", how="left")
    grouped["max_consecutive_championships"] = grouped.get(
        "max_consecutive_championships", pd.Series(0, index=grouped.index)
    ).fillna(0).astype(int)
    grouped["repeat_titles_score"] = grouped.get(
        "repeat_titles_score", pd.Series(0.0, index=grouped.index)
    ).fillna(0.0).astype(float)
    grouped["display_name"] = grouped["player_id"].map(display_names)

    missing = allowlist_player_ids - set(grouped["player_id"])
    if missing:
        filler = pd.DataFrame({"player_id": list(missing)})
        for col, val in [
            ("championships", 0),
            ("finals_losses", 0),
            ("finals_appearances", 0),
            ("playoff_seasons", 0),
            ("team_strength_index", 0.0),
            ("championship_credit", 0.0),
            ("finals_loss_debit", 0.0),
            ("championship_net", 0.0),
            ("playoff_performance", 0.0),
            ("playoff_depth_total", 0.0),
            ("max_consecutive_championships", 0),
            ("repeat_titles_score", 0.0),
        ]:
            filler[col] = val
        filler["display_name"] = filler["player_id"].map(display_names)
        grouped = pd.concat([grouped, filler], ignore_index=True)

    grouped = grouped.sort_values("player_id").reset_index(drop=True)
    return PlayoffBuildResult(player_context=grouped, team_snapshots=snapshots, team_pca=team_pca)
