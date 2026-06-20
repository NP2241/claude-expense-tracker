"""Expense persistence — read/write expenses.json."""

import json
import os
import sys

EXPENSES_FILE = os.path.join(os.getcwd(), "expenses.json")


def load() -> list:
    """Load expenses from disk, returning an empty list if the file is missing.

    Strips surrounding whitespace before parsing so trailing blank lines in
    the file never cause a spurious JSONDecodeError.  Exits with a clear
    message when the file exists but cannot be parsed as JSON.
    """
    if not os.path.exists(EXPENSES_FILE):
        return []
    with open(EXPENSES_FILE, "r", encoding="utf-8") as fh:
        text = fh.read().strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        sys.exit(
            f"Error: {EXPENSES_FILE} contains invalid JSON "
            f"({exc.msg}, line {exc.lineno} col {exc.colno}). "
            f"Fix or delete the file and try again."
        )


def save(expenses: list) -> None:
    """Persist expenses to disk."""
    with open(EXPENSES_FILE, "w", encoding="utf-8") as fh:
        json.dump(expenses, fh, indent=2)
