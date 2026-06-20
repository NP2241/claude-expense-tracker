# expense-cli

A minimal command-line expense tracker written in Python. Expenses are stored in
`expenses.json` in whatever directory you run the script from.

## Requirements

Python 3.8+ — no third-party packages needed.

## Usage

```bash
# Run directly
python expense_cli.py <command> [options]
```

### `add` — record a new expense

```bash
python expense_cli.py add <amount> <category> <note>

# Examples
python expense_cli.py add 12.50 food "Lunch at the deli"
python expense_cli.py add 3.00 transport "Bus fare"
python expense_cli.py add 89.99 utilities "Electric bill"
```

### `list` — show all expenses

```bash
python expense_cli.py list

# Filter by category (case-insensitive)
python expense_cli.py list --category food
python expense_cli.py list -c transport
```

Sample output:

```
ID    Date          Amount  Category      Note
--------------------------------------------------------------------
1     2026-06-20    $12.50  food          Lunch at the deli
2     2026-06-20     $3.00  transport     Bus fare
3     2026-06-20    $89.99  utilities     Electric bill
--------------------------------------------------------------------
Total                       $105.49
```

### `summary` — totals by category

```bash
python expense_cli.py summary

# Restrict to a specific month
python expense_cli.py summary --month 2026-06
python expense_cli.py summary -m 2026-06
```

Sample output:

```
Summary for 2026-06
=========================
  utilities  $   89.99  XXXXXXXXXXXXXXXXXX
  food       $   12.50  XX
  transport  $    3.00  
=========================
  TOTAL      $  105.49
```

## Data file

Expenses are saved to `expenses.json` in the current working directory:

```json
[
  {
    "id": 1,
    "date": "2026-06-20",
    "amount": 12.50,
    "category": "food",
    "note": "Lunch at the deli"
  }
]
```
