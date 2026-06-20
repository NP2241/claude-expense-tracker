"""Expense persistence — read/write expenses.json."""

import json
import os

EXPENSES_FILE = os.path.join(os.getcwd(), "expenses.json")


def load() -> list:
    """Load expenses from disk, returning an empty list if the file is missing."""
    if not os.path.exists(EXPENSES_FILE):
        return []
    with open(EXPENSES_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save(expenses: list) -> None:
    """Persist expenses to disk."""
    with open(EXPENSES_FILE, "w", encoding="utf-8") as fh:
        json.dump(expenses, fh, indent=2)
