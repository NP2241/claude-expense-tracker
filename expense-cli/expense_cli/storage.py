"""Expense persistence — SQLite backend (expenses.db)."""

import os
import sqlite3

DB_FILE = os.path.join(os.getcwd(), "expenses.db")

_CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS expenses (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        date     TEXT    NOT NULL,
        amount   REAL    NOT NULL,
        category TEXT    NOT NULL,
        note     TEXT    NOT NULL
    )
"""


def _connect() -> sqlite3.Connection:
    """Open the database, enable WAL mode, and ensure the schema exists."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_CREATE_TABLE)
    conn.commit()
    return conn


def add(entry: dict) -> int:
    """Insert one expense and return the auto-assigned id."""
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO expenses (date, amount, category, note) VALUES (?, ?, ?, ?)",
        (entry["date"], entry["amount"], entry["category"], entry["note"]),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def add_many(entries: list) -> int:
    """Insert multiple expenses in one transaction; return the count inserted."""
    conn = _connect()
    conn.executemany(
        "INSERT INTO expenses (date, amount, category, note) VALUES (?, ?, ?, ?)",
        [(e["date"], e["amount"], e["category"], e["note"]) for e in entries],
    )
    conn.commit()
    conn.close()
    return len(entries)


def load() -> list:
    """Return all expenses ordered by id as a list of plain dicts."""
    conn = _connect()
    rows = conn.execute(
        "SELECT id, date, amount, category, note FROM expenses ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
