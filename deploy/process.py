import pandas as pd
import sqlite3
from db import get_connection


def load_dataframes():
    """
    Loads all tables into Pandas DataFrames.
    Returns a dict — easy to pass around.
    """
    conn = get_connection()

    dfs = {
        "repos": pd.read_sql("SELECT * FROM repos", conn),
        "commits": pd.read_sql("SELECT * FROM commits", conn),
        "prs": pd.read_sql("SELECT * FROM pull_requests", conn),
        "languages": pd.read_sql("SELECT * FROM languages", conn)
    }

    conn.close()

    # Parse dates immediately — every time series analysis needs this
    dfs["commits"]["date"] = pd.to_datetime(dfs["commits"]["date"], utc=True)
    dfs["prs"]["created_at"] = pd.to_datetime(
        dfs["prs"]["created_at"], utc=True)
    dfs["prs"]["merged_at"] = pd.to_datetime(dfs["prs"]["merged_at"], utc=True)
    dfs["repos"]["pushed_at"] = pd.to_datetime(
        dfs["repos"]["pushed_at"], utc=True)

    return dfs


def get_kpis(dfs):
    """
    Top-level numbers for the KPI cards in dashboard.
    """
    df_commits = dfs["commits"]
    df_prs = dfs["prs"]
    df_repos = dfs["repos"]

    total_prs = len(df_prs)
    merged_prs = df_prs["merged_at"].notna().sum()

    return {
        "total_repos": len(df_repos),
        "total_commits": len(df_commits),
        "total_prs": total_prs,
        # Avoid division by zero
        "pr_merge_rate": round((merged_prs / total_prs * 100), 1) if total_prs > 0 else 0,
        "top_language": df_repos["language"].value_counts().idxmax()
        if not df_repos["language"].isna().all() else "N/A",
        "total_stars": int(df_repos["stars"].sum()),
    }


def commit_activity_by_month(dfs):
    """
    How many commits per month — shows consistency over time.
    Returns DataFrame with columns: month (period), commit_count
    """
    df = dfs["commits"].copy()
    df["month"] = df["date"].dt.to_period("M")
    result = df.groupby("month").size().reset_index(name="commit_count")
    result["month"] = result["month"].astype(
        str)  # Plotly can't handle Period type
    return result


def commit_activity_by_weekday(dfs):
    """
    Which days of the week are most active.
    Useful insight: serious devs commit Mon-Fri, hobbyists on weekends.
    """
    df = dfs["commits"].copy()

    # dt.day_name() returns Monday, Tuesday etc.
    df["weekday"] = df["date"].dt.day_name()

    # Enforce correct order — not alphabetical
    order = ["Monday", "Tuesday", "Wednesday",
             "Thursday", "Friday", "Saturday", "Sunday"]
    result = df.groupby("weekday").size().reset_index(name="count")
    result["weekday"] = pd.Categorical(
        result["weekday"], categories=order, ordered=True)
    result = result.sort_values("weekday")

    return result


def language_distribution(dfs):
    """
    Language usage by bytes (more accurate than repo count).
    Groups small languages into "Other" to keep chart clean.
    """
    df = dfs["languages"].copy()
    lang_totals = df.groupby("language")["bytes"].sum().reset_index()
    lang_totals = lang_totals.sort_values("bytes", ascending=False)

    # Keep top 6, group rest as "Other"
    top_langs = lang_totals.head(6)
    other_bytes = lang_totals.iloc[6:]["bytes"].sum()

    if other_bytes > 0:
        other_row = pd.DataFrame([{"language": "Other", "bytes": other_bytes}])
        top_langs = pd.concat([top_langs, other_row], ignore_index=True)

    return top_langs


def pr_merge_timeline(dfs):
    """
    PR creation vs merge rate over time.
    Shows: are PRs getting merged or accumulating?
    """
    df = dfs["prs"].copy()
    df["month"] = df["created_at"].dt.to_period("M").astype(str)

    monthly = df.groupby("month").agg(
        total_prs=("id", "count"),
        merged_prs=("merged_at", lambda x: x.notna().sum())
    ).reset_index()

    monthly["merge_rate"] = (monthly["merged_prs"] /
                             monthly["total_prs"] * 100).round(1)
    return monthly


def commit_streak(dfs):
    """
    Calculates longest consecutive active days streak.
    This is a good talking point in interviews — shows algorithm thinking.
    """
    df = dfs["commits"].copy()
    active_days = sorted(df["date"].dt.date.unique())

    if not active_days:
        return 0, 0

    max_streak = 1
    current_streak = 1

    for i in range(1, len(active_days)):
        diff = (active_days[i] - active_days[i-1]).days
        if diff == 1:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 1

    # Current streak = streak ending today or most recent day
    return max_streak, current_streak


def top_repos_by_commits(dfs, top_n=10):
    """
    Which repos got the most commits — signals project depth.
    """
    df = dfs["commits"].copy()
    result = df.groupby("repo_name").size().reset_index(name="commit_count")
    return result.sort_values("commit_count", ascending=False).head(top_n)
# process.py — add this function


def calculate_productivity_score(dfs):
    """
    Weighted scoring algorithm across 5 dimensions.
    This is YOUR intellectual contribution — not a GitHub metric.
    """
    scores = {}

    df_commits = dfs["commits"]
    df_prs = dfs["prs"]
    df_repos = dfs["repos"]

    # 1. Consistency Score (0-20)
    # How regularly do they commit? Streaks + active days
    total_days = (df_commits["date"].max() -
                  df_commits["date"].min()).days or 1
    active_days = df_commits["date"].dt.date.nunique()
    consistency = min((active_days / total_days) * 20, 20)

    # 2. Volume Score (0-20)
    # Commits per active day — not raw commits (avoids "100 commits in one day" gaming)
    avg_commits_per_day = len(df_commits) / max(active_days, 1)
    volume = min(avg_commits_per_day * 4, 20)

    # 3. Collaboration Score (0-20)
    # PR merge rate × PR frequency
    total_prs = len(df_prs)
    merged = df_prs["merged_at"].notna().sum()
    merge_rate = merged / max(total_prs, 1)
    collab = min(merge_rate * 20, 20)

    # 4. Diversity Score (0-20)
    # Language diversity across repos — not a one-trick pony
    lang_count = df_repos["language"].nunique()
    diversity = min(lang_count * 3, 20)

    # 5. Impact Score (0-20)
    # Stars + forks normalized
    total_stars = df_repos["stars"].sum()
    total_forks = df_repos["forks"].sum()
    impact = min((total_stars * 0.5 + total_forks * 1.5) / 10, 20)

    total = consistency + volume + collab + diversity + impact

    return {
        "total": round(total, 1),
        "consistency": round(consistency, 1),
        "volume": round(volume, 1),
        "collaboration": round(collab, 1),
        "diversity": round(diversity, 1),
        "impact": round(impact, 1),
        "grade": "S" if total >= 85 else "A" if total >= 70 else
                 "B" if total >= 55 else "C" if total >= 40 else "D"
    }
