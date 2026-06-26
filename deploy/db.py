import sqlite3
import os

DB_PATH = "github_data.db"


def get_connection():
    """
    Returns a SQLite connection.
    In production (Azure), swap this with PostgreSQL using SQLAlchemy.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn


def initialize_db():
    """
    Creates all tables if they don't exist.
    Run this once at startup.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        -- Stores one row per repository
        CREATE TABLE IF NOT EXISTS repos (
            id          INTEGER PRIMARY KEY,
            name        TEXT,
            full_name   TEXT,
            language    TEXT,       -- primary language
            stars       INTEGER,
            forks       INTEGER,
            open_issues INTEGER,
            created_at  TEXT,
            updated_at  TEXT,
            pushed_at   TEXT,       -- last commit push time
            description TEXT,
            username     TEXT,
            PRIMARY KEY (id, username)         
        );

        -- Stores one row per commit across all repos
        CREATE TABLE IF NOT EXISTS commits (
            sha         TEXT PRIMARY KEY,  -- unique commit hash
            username    TEXT,             
            repo_name   TEXT,
            author      TEXT,              -- GitHub username
            date        TEXT,              -- ISO 8601 format
            message     TEXT,
            PRIMARY KEY (sha, username)
        );

        -- Stores one row per pull request
        CREATE TABLE IF NOT EXISTS pull_requests (
            id          INTEGER PRIMARY KEY,
            repo_name   TEXT,
            title       TEXT,
            state       TEXT,       -- open / closed
            created_at  TEXT,
            merged_at   TEXT,       -- NULL if not merged
            additions   INTEGER,    -- lines added
            deletions   INTEGER     -- lines removed
        );

        -- Stores language byte counts per repo
        -- GitHub returns {"Python": 12400, "JavaScript": 3200}
        CREATE TABLE IF NOT EXISTS languages (
            repo_name   TEXT,
            language    TEXT,
            bytes       INTEGER,
            PRIMARY KEY (repo_name, language)
        );
    """)

    conn.commit()
    conn.close()
    print("DB initialized successfully.")
