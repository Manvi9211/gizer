"""
fetch_github.py
Fetches data from GitHub REST API and stores in SQLite.

Key fix: store_all_data() opens + closes connection
after EACH repo so SQLite never stays locked.
"""

from __future__ import annotations

import os
import time
import requests
from dotenv import load_dotenv
from db import get_connection

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
BASE_URL = "https://api.github.com"
REQUEST_TIMEOUT = 30

HEADERS = {
    "Accept": "application/vnd.github+json",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


# ---------------------------------------------------------
# Core Request Function
# ---------------------------------------------------------

def github_get(endpoint: str, params: dict | None = None):
    """
    GET request to GitHub API.
    Handles rate limiting with automatic retry.
    Raises RuntimeError on failure.
    """
    url = f"{BASE_URL}{endpoint}"

    while True:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            return response.json()

        if response.status_code == 403:
            # Rate limit — wait until reset
            reset_time = int(response.headers.get(
                "X-RateLimit-Reset", time.time() + 60))
            wait = max(reset_time - int(time.time()), 1)
            print(f"Rate limited. Waiting {wait}s...")
            time.sleep(wait)
            continue

        if response.status_code == 404:
            raise RuntimeError(f"Not found: {url}")

        raise RuntimeError(
            f"GitHub API Error {response.status_code}: {response.text[:200]}"
        )


# ---------------------------------------------------------
# Fetch Functions — API only, no DB
# ---------------------------------------------------------

def fetch_repos(username: str) -> list:
    print(f"Fetching repos for {username}...")
    repos = []
    page = 1

    while True:
        data = github_get(f"/users/{username}/repos", params={
            "per_page": 100,
            "page": page,
            "sort": "updated"
        })
        if not data:
            break
        repos.extend(data)
        page += 1
        if len(data) < 100:
            break

    print(f"  Found {len(repos)} repos.")
    return repos


def fetch_commits(username: str, repo_name: str) -> list:
    print(f"  Fetching commits -> {repo_name}")
    try:
        return github_get(
            f"/repos/{username}/{repo_name}/commits",
            params={"per_page": 100, "author": username}
        )
    except Exception as e:
        print(f"  Skipping commits for {repo_name}: {e}")
        return []


def fetch_pull_requests(username: str, repo_name: str) -> list:
    print(f"  Fetching PRs -> {repo_name}")
    try:
        prs = github_get(
            f"/repos/{username}/{repo_name}/pulls",
            params={"state": "all", "per_page": 100}
        )
        detailed = []
        for pr in prs:
            try:
                detail = github_get(
                    f"/repos/{username}/{repo_name}/pulls/{pr['number']}"
                )
                detailed.append(detail)
            except Exception:
                detailed.append(pr)
        return detailed
    except Exception as e:
        print(f"  Skipping PRs for {repo_name}: {e}")
        return []


def fetch_languages(username: str, repo_name: str) -> dict:
    print(f"  Fetching languages -> {repo_name}")
    try:
        return github_get(f"/repos/{username}/{repo_name}/languages") or {}
    except Exception as e:
        print(f"  Skipping languages for {repo_name}: {e}")
        return {}


# ---------------------------------------------------------
# Store Functions — DB only, no API
# ---------------------------------------------------------

def store_repo(cursor, repo: dict):
    cursor.execute("""
        INSERT OR REPLACE INTO repos
        (id, name, full_name, language, stars, forks,
         open_issues, created_at, updated_at, pushed_at, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        repo["id"],
        repo["name"],
        repo["full_name"],
        repo.get("language"),
        repo.get("stargazers_count", 0),
        repo.get("forks_count", 0),
        repo.get("open_issues_count", 0),
        repo.get("created_at"),
        repo.get("updated_at"),
        repo.get("pushed_at"),
        repo.get("description", "")[:500] if repo.get("description") else None
    ))


def store_commits(cursor, repo_name: str, commits: list):
    for c in commits:
        try:
            commit_data = c.get("commit", {})
            commit_author = commit_data.get("author", {})
            github_author = c.get("author") or {}

            author_login = (
                github_author.get("login")
                or commit_author.get("name")
                or "unknown"
            )

            cursor.execute("""
                INSERT OR IGNORE INTO commits
                (sha, repo_name, author, date, message)
                VALUES (?, ?, ?, ?, ?)
            """, (
                c["sha"],
                repo_name,
                author_login,
                commit_author.get("date"),
                commit_data.get("message", "")[:500]
            ))
        except Exception as e:
            print(f"    Skipping commit: {e}")


def store_pull_requests(cursor, repo_name: str, prs: list):
    for pr in prs:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO pull_requests
                (id, repo_name, title, state, created_at, merged_at, additions, deletions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pr["id"],
                repo_name,
                pr.get("title", "")[:300],
                pr.get("state"),
                pr.get("created_at"),
                pr.get("merged_at"),
                pr.get("additions", 0),
                pr.get("deletions", 0)
            ))
        except Exception as e:
            print(f"    Skipping PR: {e}")


def store_languages(cursor, repo_name: str, languages: dict):
    for lang, byte_count in languages.items():
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO languages (repo_name, language, bytes)
                VALUES (?, ?, ?)
            """, (repo_name, lang, byte_count))
        except Exception as e:
            print(f"    Skipping language {lang}: {e}")


# ---------------------------------------------------------
# Master Function — called from app.py
# ---------------------------------------------------------

def store_all_data(username: str):
    """
    Fetches all GitHub data for a user and stores in SQLite.

    KEY DESIGN:
    - Opens a NEW connection per repo
    - Commits + closes after each repo
    - This prevents SQLite from staying locked
      while Dash is also trying to read

    This is the function app.py calls.
    """
    repos = fetch_repos(username)

    if not repos:
        raise RuntimeError(f"No public repos found for '{username}'")

    for repo in repos:
        repo_name = repo["name"]
        print(f"\nProcessing: {repo_name}")

        # Fetch from API (no DB connection open yet)
        commits = fetch_commits(username, repo_name)
        prs = fetch_pull_requests(username, repo_name)
        languages = fetch_languages(username, repo_name)

        # Open connection, write everything, close immediately
        conn = get_connection()
        cursor = conn.cursor()

        try:
            store_repo(cursor, repo)
            store_commits(cursor, repo_name, commits)
            store_pull_requests(cursor, repo_name, prs)
            store_languages(cursor, repo_name, languages)
            conn.commit()
            print(f"  Saved: {len(commits)} commits, {len(prs)} PRs")
        except Exception as e:
            conn.rollback()
            print(f"  DB error for {repo_name}: {e}")
        finally:
            conn.close()  # ALWAYS close — prevents lock

    print(f"\nDone. Processed {len(repos)} repos for {username}.")
