import requests
import sqlite3
import os
import time
from dotenv import load_dotenv
from db import get_connection

load_dotenv()  # loads .env file

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
BASE_URL = "https://api.github.com"

# All API calls go through this function
# It handles auth headers + rate limit retries automatically


def api_get(endpoint, params=None):
    """
    Makes a GET request to GitHub API.
    Automatically retries if rate limited (429 or 403).

    GitHub allows 5000 requests/hour with token.
    Without token: only 60/hour — useless for this project.
    """
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"{BASE_URL}{endpoint}"

    while True:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return response.json()

        elif response.status_code == 403:
            # Rate limit hit — GitHub tells you when it resets
            reset_time = int(response.headers.get(
                "X-RateLimit-Reset", time.time() + 60))
            wait = max(reset_time - int(time.time()), 1)
            print(f"Rate limited. Waiting {wait}s...")
            time.sleep(wait)

        elif response.status_code == 404:
            print(f"Not found: {url}")
            return None

        else:
            print(f"Error {response.status_code} for {url}")
            return None


def fetch_repos(username):
    """
    Fetches all public repos for a GitHub user.
    Handles pagination — GitHub returns max 100 per page.
    """
    repos = []
    page = 1

    while True:
        data = api_get(f"/users/{username}/repos", params={
            "per_page": 100,
            "page": page,
            "sort": "updated"
        })

        if not data:  # empty page = no more repos
            break

        repos.extend(data)
        page += 1

        # GitHub paginates — if less than 100 returned, we're on last page
        if len(data) < 100:
            break

    return repos


def fetch_commits(username, repo_name, max_pages=5):
    """
    Fetches commits for a single repo.
    max_pages=5 means max 500 commits per repo.
    Increase for very active repos.
    """
    commits = []
    page = 1

    while page <= max_pages:
        data = api_get(f"/repos/{username}/{repo_name}/commits", params={
            "per_page": 100,
            "page": page,
            "author": username  # only this user's commits
        })

        if not data:
            break

        commits.extend(data)
        page += 1

        if len(data) < 100:
            break

    return commits


def fetch_pull_requests(username, repo_name):
    """
    Fetches ALL PRs (open + closed) for a repo.
    state=all is important — we want merge rate calculation.
    """
    prs = []
    page = 1

    while True:
        data = api_get(f"/repos/{username}/{repo_name}/pulls", params={
            "state": "all",
            "per_page": 100,
            "page": page
        })

        if not data:
            break

        prs.extend(data)
        page += 1

        if len(data) < 100:
            break

    return prs


def fetch_languages(username, repo_name):
    """
    Returns language byte breakdown for a repo.
    Example: {"Python": 15420, "HTML": 3200}
    """
    return api_get(f"/repos/{username}/{repo_name}/languages") or {}


def store_all_data(username):
    """
    Master function — fetches everything and stores in DB.
    Call this from scheduler or manually.
    """
    conn = get_connection()
    cursor = conn.cursor()

    print(f"Fetching repos for {username}...")
    repos = fetch_repos(username)

    for repo in repos:
        repo_name = repo["name"]
        print(f"  Processing: {repo_name}")

        # --- Store repo ---
        cursor.execute("""
            INSERT OR REPLACE INTO repos 
            (id, name, full_name, language, stars, forks, open_issues, 
             created_at, updated_at, pushed_at, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            repo["id"],
            repo["name"],
            repo["full_name"],
            repo.get("language"),       # can be None
            repo["stargazers_count"],
            repo["forks_count"],
            repo["open_issues_count"],
            repo["created_at"],
            repo["updated_at"],
            repo["pushed_at"],
            repo.get("description")
        ))

        # --- Store commits ---
        commits = fetch_commits(username, repo_name)
        for c in commits:
            # Nested structure: commit.author.date
            author = c.get("author") or {}
            commit_data = c.get("commit", {})
            commit_author = commit_data.get("author", {})

            cursor.execute("""
                INSERT OR IGNORE INTO commits (sha, repo_name, author, date, message)
                VALUES (?, ?, ?, ?, ?)
            """, (
                c["sha"],
                repo_name,
                author.get("login", commit_author.get("name", "unknown")),
                commit_author.get("date"),
                commit_data.get("message", "")[:500]  # cap at 500 chars
            ))

        # --- Store PRs ---
        prs = fetch_pull_requests(username, repo_name)
        for pr in prs:
            cursor.execute("""
                INSERT OR REPLACE INTO pull_requests 
                (id, repo_name, title, state, created_at, merged_at, additions, deletions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pr["id"],
                repo_name,
                pr["title"][:300],
                pr["state"],
                pr["created_at"],
                pr.get("merged_at"),    # None if not merged
                pr.get("additions", 0),
                pr.get("deletions", 0)
            ))

        # --- Store languages ---
        languages = fetch_languages(username, repo_name)
        for lang, byte_count in languages.items():
            cursor.execute("""
                INSERT OR REPLACE INTO languages (repo_name, language, bytes)
                VALUES (?, ?, ?)
            """, (repo_name, lang, byte_count))

        conn.commit()  # commit after each repo — don't lose progress

    conn.close()
    print(f"Done. Stored {len(repos)} repos for {username}.")
