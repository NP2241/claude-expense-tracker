# expense-cli

A minimal command-line expense tracker written in Python. Expenses are stored in
`expenses.json` in whatever directory you run the script from.

## Requirements

Python 3.8+ — no third-party packages needed.

## Usage

```bash
python -m expense_cli <command> [options]
```

### `add` — record a new expense

```bash
python -m expense_cli add <amount> <category> <note>

# Examples
python -m expense_cli add 12.50 food "Lunch at the deli"
python -m expense_cli add 3.00 transport "Bus fare"
python -m expense_cli add 89.99 utilities "Electric bill"
```

### `list` — show all expenses

```bash
python -m expense_cli list

# Filter by category (case-insensitive)
python -m expense_cli list --category food
python -m expense_cli list -c transport
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
python -m expense_cli summary

# Restrict to a specific month
python -m expense_cli summary --month 2026-06
python -m expense_cli summary -m 2026-06
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

### `export-csv` — export expenses to CSV

Writes all expenses to **stdout** as CSV with columns
`id,date,amount,category,note`. Always emits the header row, even when the
store is empty, so the output is valid CSV in all cases.

```bash
python -m expense_cli export-csv

# Redirect to a file
python -m expense_cli export-csv > expenses.csv
```

Sample output:

```
id,date,amount,category,note
1,2026-06-20,12.5,food,Lunch at the deli
2,2026-06-20,3.0,transport,Bus fare
3,2026-06-20,89.99,utilities,Electric bill
```

### `import-csv` — import expenses from a CSV file

Reads a CSV file produced by `export-csv` (or any CSV with the same columns)
and appends the rows to the current store. IDs in the source file are ignored
and re-assigned sequentially so they never conflict with existing expenses.

```bash
python -m expense_cli import-csv expenses.csv
```

The CSV must contain these columns (order does not matter):
`id`, `date`, `amount`, `category`, `note`

**Round-trip example:**

```bash
# Export from one store
python -m expense_cli export-csv > backup.csv

# Import into another directory
cd /other/project
python -m expense_cli import-csv /path/to/backup.csv
# Imported 3 expense(s).
```

## Data file

Expenses are saved to `expenses.json` in the current working directory:

```json
[
  {
    "id": 1,
    "date": "2026-06-20",
    "amount": 12.5,
    "category": "food",
    "note": "Lunch at the deli"
  }
]
```
