"""
db.py
Database connection and schema initialization.
Uses SQLite with simple threading config — no WAL mode
to avoid locking issues with Dash's multi-threaded server.
"""

import sqlite3
import os

# Store DB in same directory as script
DB_PATH = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "github_data.db")


def get_connection():
    """
    Returns a fresh SQLite connection.
    Called per-operation — never shared across threads.
    This is the correct pattern for SQLite + multi-threaded apps.
    """
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    # Do NOT use WAL mode here — it causes locking with Dash threads
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialize_db():
    """
    Creates all tables if they don't exist.
    Safe to call multiple times.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS repos (
            id          INTEGER PRIMARY KEY,
            name        TEXT,
            full_name   TEXT,
            language    TEXT,
            stars       INTEGER,
            forks       INTEGER,
            open_issues INTEGER,
            created_at  TEXT,
            updated_at  TEXT,
            pushed_at   TEXT,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS commits (
            sha         TEXT PRIMARY KEY,
            repo_name   TEXT,
            author      TEXT,
            date        TEXT,
            message     TEXT
        );

        CREATE TABLE IF NOT EXISTS pull_requests (
            id          INTEGER PRIMARY KEY,
            repo_name   TEXT,
            title       TEXT,
            state       TEXT,
            created_at  TEXT,
            merged_at   TEXT,
            additions   INTEGER,
            deletions   INTEGER
        );

        CREATE TABLE IF NOT EXISTS languages (
            repo_name   TEXT,
            language    TEXT,
            bytes       INTEGER,
            PRIMARY KEY (repo_name, language)
        );
    """)

    conn.commit()
    conn.close()
    print("Database initialized.")
