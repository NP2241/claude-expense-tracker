#!/usr/bin/env python3
"""expense-cli: A minimal command-line expense tracker."""

import argparse
import json
import os
import sys
from datetime import date

EXPENSES_FILE = os.path.join(os.getcwd(), "expenses.json")


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _load() -> list:
    """Load expenses from disk, returning an empty list if the file is missing."""
    if not os.path.exists(EXPENSES_FILE):
        return []
    with open(EXPENSES_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save(expenses: list) -> None:
    """Persist expenses to disk."""
    with open(EXPENSES_FILE, "w", encoding="utf-8") as fh:
        json.dump(expenses, fh, indent=2)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_add(args):
    """Append a new expense entry."""
    if args.amount <= 0:
        sys.exit("Error: amount must be a positive number.")

    expenses = _load()
    entry = {
        "id": (expenses[-1]["id"] + 1) if expenses else 1,
        "date": str(date.today()),
        "amount": round(args.amount, 2),
        "category": args.category.strip(),
        "note": args.note.strip(),
    }
    expenses.append(entry)
    _save(expenses)
    print(f"Added expense #{entry['id']}: ${entry['amount']:.2f} [{entry['category']}] - {entry['note']}")


def cmd_list(args):
    """Print all expenses in a formatted table."""
    expenses = _load()
    if not expenses:
        print("No expenses recorded yet.")
        return

    # Optional category filter
    if args.category:
        expenses = [e for e in expenses if e["category"].lower() == args.category.lower()]
        if not expenses:
            print(f"No expenses found for category '{args.category}'.")
            return

    col = {"id": 4, "date": 10, "amount": 9, "category": 12, "note": 30}
    header = (
        f"{'ID':<{col['id']}}  "
        f"{'Date':<{col['date']}}  "
        f"{'Amount':>{col['amount']}}  "
        f"{'Category':<{col['category']}}  "
        f"{'Note':<{col['note']}}"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)
    for e in expenses:
        print(
            f"{e['id']:<{col['id']}}  "
            f"{e['date']:<{col['date']}}  "
            f"${e['amount']:>{col['amount'] - 1}.2f}  "
            f"{e['category']:<{col['category']}}  "
            f"{e['note']:<{col['note']}}"
        )
    print(sep)
    total = sum(e["amount"] for e in expenses)
    print(f"{'Total':<{col['id'] + col['date'] + 4}}  ${total:>{col['amount'] - 1}.2f}")


def cmd_summary(args):
    """Print spending totals grouped by category."""
    expenses = _load()
    if not expenses:
        print("No expenses recorded yet.")
        return

    # Optional month filter (YYYY-MM)
    if args.month:
        expenses = [e for e in expenses if e["date"].startswith(args.month)]
        if not expenses:
            print(f"No expenses found for {args.month}.")
            return

    totals = {}
    for e in expenses:
        totals[e["category"]] = round(totals.get(e["category"], 0.0) + e["amount"], 2)

    grand_total = sum(totals.values())
    width = max(len(c) for c in totals)

    title = f"Summary{f' for {args.month}' if args.month else ''}"
    print(f"\n{title}")
    print("=" * (width + 14))
    for category, total in sorted(totals.items(), key=lambda x: x[1], reverse=True):
        bar = "X" * min(int(total / grand_total * 20), 20)
        print(f"  {category:<{width}}  ${total:>8.2f}  {bar}")
    print("=" * (width + 14))
    print(f"  {'TOTAL':<{width}}  ${grand_total:>8.2f}")
    print()


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="expense-cli",
        description="Track your expenses from the command line.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # --- add ---
    p_add = sub.add_parser("add", help="Record a new expense")
    p_add.add_argument("amount", type=float, help="Expense amount (e.g. 12.50)")
    p_add.add_argument("category", help="Category label (e.g. food, travel)")
    p_add.add_argument("note", help="Short description of the expense")
    p_add.set_defaults(func=cmd_add)

    # --- list ---
    p_list = sub.add_parser("list", help="List all recorded expenses")
    p_list.add_argument(
        "--category", "-c", default=None,
        help="Filter by category (case-insensitive)",
    )
    p_list.set_defaults(func=cmd_list)

    # --- summary ---
    p_summary = sub.add_parser("summary", help="Show spending totals by category")
    p_summary.add_argument(
        "--month", "-m", default=None, metavar="YYYY-MM",
        help="Restrict summary to a specific month (e.g. 2026-06)",
    )
    p_summary.set_defaults(func=cmd_summary)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
