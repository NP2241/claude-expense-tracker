"""Expense entry construction and validation."""

from datetime import date


def create_expense(amount: float, category: str, note: str) -> dict:
    """Build a new expense dict ready for storage.

    Handles date stamping, cent rounding, and whitespace stripping.
    Raises ``ValueError`` if *amount* is not positive.

    The ``id`` field is intentionally absent — the storage layer assigns
    it via SQLite AUTOINCREMENT on insert.
    """
    if amount <= 0:
        raise ValueError("amount must be a positive number")

    return {
        "date":     str(date.today()),
        "amount":   round(amount, 2),
        "category": category.strip(),
        "note":     note.strip(),
    }
