"""Expense entry construction and validation."""

from datetime import date


def create_expense(amount: float, category: str, note: str,
                   existing: list) -> dict:
    """Build a new expense dict ready for storage.

    Handles id generation, date stamping, cent rounding, and whitespace
    stripping.  Raises ``ValueError`` if *amount* is not positive.
    """
    if amount <= 0:
        raise ValueError("amount must be a positive number")

    return {
        "id": (existing[-1]["id"] + 1) if existing else 1,
        "date": str(date.today()),
        "amount": round(amount, 2),
        "category": category.strip(),
        "note": note.strip(),
    }
