"""
process.py
Transforms raw DB data into analytics-ready DataFrames.

Key fix: every function handles empty DataFrames
so dashboard never crashes before data is loaded.
"""

import pandas as pd
from db import get_connection


def load_dataframes() -> dict:
    """
    Loads all tables into Pandas DataFrames.
    Opens connection, reads, closes immediately.
    """
    conn = get_connection()

    dfs = {
        "repos":     pd.read_sql("SELECT * FROM repos", conn),
        "commits":   pd.read_sql("SELECT * FROM commits", conn),
        "prs":       pd.read_sql("SELECT * FROM pull_requests", conn),
        "languages": pd.read_sql("SELECT * FROM languages", conn)
    }

    conn.close()

    # Parse dates — coerce errors so bad values become NaT not exceptions
    if not dfs["commits"].empty:
        dfs["commits"]["date"] = pd.to_datetime(
            dfs["commits"]["date"], utc=True, errors="coerce"
        )

    if not dfs["prs"].empty:
        dfs["prs"]["created_at"] = pd.to_datetime(
            dfs["prs"]["created_at"], utc=True, errors="coerce"
        )
        dfs["prs"]["merged_at"] = pd.to_datetime(
            dfs["prs"]["merged_at"], utc=True, errors="coerce"
        )

    if not dfs["repos"].empty:
        dfs["repos"]["pushed_at"] = pd.to_datetime(
            dfs["repos"]["pushed_at"], utc=True, errors="coerce"
        )

    return dfs


def get_kpis(dfs: dict) -> dict:
    """KPI numbers for the top cards."""
    df_commits = dfs["commits"]
    df_prs = dfs["prs"]
    df_repos = dfs["repos"]

    total_prs = len(df_prs)
    merged_prs = df_prs["merged_at"].notna().sum() if not df_prs.empty else 0

    top_lang = "N/A"
    if not df_repos.empty and not df_repos["language"].isna().all():
        top_lang = df_repos["language"].value_counts().idxmax()

    return {
        "total_repos":   len(df_repos),
        "total_commits": len(df_commits),
        "total_prs":     total_prs,
        "pr_merge_rate": round(merged_prs / total_prs * 100, 1) if total_prs > 0 else 0,
        "top_language":  top_lang,
        "total_stars":   int(df_repos["stars"].sum()) if not df_repos.empty else 0,
    }


def commit_activity_by_month(dfs: dict) -> pd.DataFrame:
    """Commits grouped by calendar month."""
    df = dfs["commits"].copy()

    if df.empty:
        return pd.DataFrame(columns=["month", "commit_count"])

    df["month"] = df["date"].dt.to_period("M")
    result = df.groupby("month").size().reset_index(name="commit_count")
    result["month"] = result["month"].astype(str)
    return result


def commit_activity_by_weekday(dfs: dict) -> pd.DataFrame:
    """Commits grouped by day of week, in correct order."""
    df = dfs["commits"].copy()

    if df.empty:
        return pd.DataFrame(columns=["weekday", "count"])

    order = ["Monday", "Tuesday", "Wednesday",
             "Thursday", "Friday", "Saturday", "Sunday"]
    df["weekday"] = df["date"].dt.day_name()
    result = df.groupby("weekday").size().reset_index(name="count")
    result["weekday"] = pd.Categorical(
        result["weekday"], categories=order, ordered=True)
    result = result.sort_values("weekday").reset_index(drop=True)
    return result


def language_distribution(dfs: dict) -> pd.DataFrame:
    """Top 6 languages by byte count, rest grouped as Other."""
    df = dfs["languages"].copy()

    if df.empty:
        return pd.DataFrame(columns=["language", "bytes"])

    lang_totals = df.groupby("language")["bytes"].sum().reset_index()
    lang_totals = lang_totals.sort_values("bytes", ascending=False)

    top = lang_totals.head(6).copy()
    other_bytes = lang_totals.iloc[6:]["bytes"].sum()

    if other_bytes > 0:
        top = pd.concat(
            [top, pd.DataFrame([{"language": "Other", "bytes": other_bytes}])],
            ignore_index=True
        )

    return top


def pr_merge_timeline(dfs: dict) -> pd.DataFrame:
    """Monthly PR count + merge rate."""
    df = dfs["prs"].copy()

    if df.empty:
        return pd.DataFrame(columns=["month", "total_prs", "merged_prs", "merge_rate"])

    df["month"] = df["created_at"].dt.to_period("M").astype(str)

    monthly = df.groupby("month").agg(
        total_prs=("id", "count"),
        merged_prs=("merged_at", lambda x: x.notna().sum())
    ).reset_index()

    monthly["merge_rate"] = (
        monthly["merged_prs"] / monthly["total_prs"] * 100
    ).round(1)

    return monthly


def commit_streak(dfs: dict) -> tuple[int, int]:
    """
    Returns (longest_streak, current_streak) in days.
    Algorithm: sort active days, count consecutive day diffs == 1.
    """
    df = dfs["commits"].copy()

    if df.empty:
        return 0, 0

    active_days = sorted(df["date"].dt.date.unique())

    if len(active_days) == 0:
        return 0, 0

    max_streak = 1
    current_streak = 1

    for i in range(1, len(active_days)):
        diff = (active_days[i] - active_days[i - 1]).days
        if diff == 1:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 1

    return max_streak, current_streak


def top_repos_by_commits(dfs: dict, top_n: int = 10) -> pd.DataFrame:
    """Repos ranked by commit count."""
    df = dfs["commits"].copy()

    if df.empty:
        return pd.DataFrame(columns=["repo_name", "commit_count"])

    result = df.groupby("repo_name").size().reset_index(name="commit_count")
    return result.sort_values("commit_count", ascending=False).head(top_n)


def calculate_productivity_score(dfs: dict) -> dict:
    """
    Proprietary 5-dimension developer productivity score (0-100).
    Each dimension scored 0-20.

    1. Consistency  — how regularly they commit
    2. Volume       — commits per active day
    3. Collaboration — PR merge rate
    4. Diversity    — number of languages used
    5. Impact       — stars + forks
    """
    df_commits = dfs["commits"]
    df_prs = dfs["prs"]
    df_repos = dfs["repos"]

    # --- Consistency (0-20) ---
    if df_commits.empty:
        consistency = 0
    else:
        date_range = (df_commits["date"].max() -
                      df_commits["date"].min()).days or 1
        active_days = df_commits["date"].dt.date.nunique()
        consistency = min((active_days / date_range) * 20, 20)

    # --- Volume (0-20) ---
    active_days_count = df_commits["date"].dt.date.nunique(
    ) if not df_commits.empty else 1
    avg_per_day = len(df_commits) / max(active_days_count, 1)
    volume = min(avg_per_day * 4, 20)

    # --- Collaboration (0-20) ---
    total_prs = len(df_prs)
    merged = df_prs["merged_at"].notna().sum() if not df_prs.empty else 0
    merge_rate = merged / max(total_prs, 1)
    collab = min(merge_rate * 20, 20)

    # --- Diversity (0-20) ---
    lang_count = df_repos["language"].nunique() if not df_repos.empty else 0
    diversity = min(lang_count * 3, 20)

    # --- Impact (0-20) ---
    total_stars = df_repos["stars"].sum() if not df_repos.empty else 0
    total_forks = df_repos["forks"].sum() if not df_repos.empty else 0
    impact = min((total_stars * 0.5 + total_forks * 1.5) / 10, 20)

    total = consistency + volume + collab + diversity + impact

    grade = (
        "S" if total >= 85 else
        "A" if total >= 70 else
        "B" if total >= 55 else
        "C" if total >= 40 else "D"
    )

    return {
        "total":         round(total, 1),
        "consistency":   round(consistency, 1),
        "volume":        round(volume, 1),
        "collaboration": round(collab, 1),
        "diversity":     round(diversity, 1),
        "impact":        round(impact, 1),
        "grade":         grade
    }
