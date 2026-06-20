"""Command handlers and argparse wiring for expense-cli."""

import argparse
import csv
import os
import sys

from expense_cli import storage
from expense_cli.models import create_expense

# Canonical column order used by both export and import.
CSV_FIELDS = ["id", "date", "amount", "category", "note"]


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_add(args):
    """Append a new expense entry."""
    expenses = storage.load()
    try:
        entry = create_expense(args.amount, args.category, args.note, expenses)
    except ValueError as exc:
        sys.exit(f"Error: {exc}")
    expenses.append(entry)
    storage.save(expenses)
    print(
        f"Added expense #{entry['id']}: "
        f"${entry['amount']:.2f} [{entry['category']}] - {entry['note']}"
    )


def cmd_list(args):
    """Print all expenses in a formatted table."""
    expenses = storage.load()
    if not expenses:
        print("No expenses recorded yet.")
        return

    # Optional category filter.
    # NOTE: expenses with an empty category string are always included when a
    # filter is active — this is a known bug left in place intentionally.
    if args.category:
        expenses = [
            e for e in expenses
            if not e["category"]
            or e["category"].lower() == args.category.lower()
        ]
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
    expenses = storage.load()
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
        totals[e["category"]] = round(
            totals.get(e["category"], 0.0) + e["amount"], 2
        )

    grand_total = sum(totals.values())
    width = max(len(c) for c in totals)

    title = f"Summary{f' for {args.month}' if args.month else ''}"
    print(f"\n{title}")
    print("=" * (width + 14))
    for category, total in sorted(totals.items(), key=lambda x: x[1],
                                  reverse=True):
        bar = "X" * min(int(total / grand_total * 20), 20)
        print(f"  {category:<{width}}  ${total:>8.2f}  {bar}")
    print("=" * (width + 14))
    print(f"  {'TOTAL':<{width}}  ${grand_total:>8.2f}")
    print()


def cmd_export_csv(args):
    """Write all expenses to stdout as CSV (header + one row per expense)."""
    expenses = storage.load()
    # lineterminator='\n' keeps output clean on all platforms and avoids \r
    # characters when stdout is captured or redirected.
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(CSV_FIELDS)
    for e in expenses:
        writer.writerow([e["id"], e["date"], e["amount"], e["category"], e["note"]])


def cmd_import_csv(args):
    """Import expenses from a CSV file, appending them to the store."""
    if not os.path.exists(args.path):
        sys.exit(f"Error: file not found: {args.path}")

    with open(args.path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = set(reader.fieldnames or [])
        missing = set(CSV_FIELDS) - fieldnames
        if missing:
            sys.exit(
                f"Error: CSV is missing required columns: "
                f"{', '.join(sorted(missing))}"
            )

        rows = []
        for i, row in enumerate(reader, start=1):
            try:
                amount = float(row["amount"])
            except ValueError:
                sys.exit(
                    f"Error: invalid amount on row {i}: {row['amount']!r}"
                )
            rows.append({
                "date":     row["date"].strip(),
                "amount":   round(amount, 2),
                "category": row["category"].strip(),
                "note":     row["note"].strip(),
            })

    if not rows:
        print("No expenses to import.")
        return

    expenses = storage.load()
    next_id = (expenses[-1]["id"] + 1) if expenses else 1
    for row in rows:
        row["id"] = next_id
        next_id += 1
        expenses.append(row)

    storage.save(expenses)
    print(f"Imported {len(rows)} expense(s).")


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="expense-cli",
        description="Track your expenses from the command line.",
    )
    parser.add_argument(
        "--version", action="version", version="expense-cli 0.1.0",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # --- add ---
    p_add = sub.add_parser("add", help="Record a new expense")
    p_add.add_argument("amount", type=float,
                       help="Expense amount (e.g. 12.50)")
    p_add.add_argument("category",
                       help="Category label (e.g. food, travel)")
    p_add.add_argument("note",
                       help="Short description of the expense")
    p_add.set_defaults(func=cmd_add)

    # --- list ---
    p_list = sub.add_parser("list", help="List all recorded expenses")
    p_list.add_argument(
        "--category", "-c", default=None,
        help="Filter by category (case-insensitive)",
    )
    p_list.set_defaults(func=cmd_list)

    # --- summary ---
    p_summary = sub.add_parser("summary",
                               help="Show spending totals by category")
    p_summary.add_argument(
        "--month", "-m", default=None, metavar="YYYY-MM",
        help="Restrict summary to a specific month (e.g. 2026-06)",
    )
    p_summary.set_defaults(func=cmd_summary)

    # --- export-csv ---
    p_export = sub.add_parser(
        "export-csv",
        help="Export all expenses to stdout as CSV",
    )
    p_export.set_defaults(func=cmd_export_csv)

    # --- import-csv ---
    p_import = sub.add_parser(
        "import-csv",
        help="Import expenses from a CSV file",
    )
    p_import.add_argument("path", help="Path to the CSV file to import")
    p_import.set_defaults(func=cmd_import_csv)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
