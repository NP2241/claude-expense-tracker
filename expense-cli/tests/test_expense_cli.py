"""Tests for expense_cli — add, list, summary, export-csv, and import-csv."""

import argparse
import csv
import io
import json

import pytest

from expense_cli import cli, storage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def expense_file(tmp_path, monkeypatch):
    """Redirect EXPENSES_FILE to a fresh temp file for every test.

    autouse=True means every test gets an isolated, empty store automatically.
    Returning the path lets individual tests seed it with known data.
    """
    path = tmp_path / "expenses.json"
    monkeypatch.setattr(storage, "EXPENSES_FILE", str(path))
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ns(**kwargs):
    """Build an argparse.Namespace for direct handler calls.

    Mirrors the attributes argparse would populate; only supply what the
    command under test actually reads.
    """
    defaults = {"amount": None, "category": None, "note": None, "month": None, "path": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def seed(path, expenses):
    """Write a list of expense dicts directly to the JSON file."""
    path.write_text(json.dumps(expenses), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI — top-level flags
# ---------------------------------------------------------------------------

class TestCLI:

    def test_version_flag_prints_version_and_exits(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cli.build_parser().parse_args(["--version"])
        assert exc_info.value.code == 0
        assert "expense-cli 0.1.0" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------

class TestStorage:

    def test_trailing_whitespace_and_blank_lines_load_successfully(self, expense_file):
        # Files written by external tools often have a trailing newline or
        # blank lines; they must not cause a parse error or alter the data.
        expense_file.write_text(
            '[{"id": 1, "date": "2026-01-01", "amount": 5.0, "category": "food", "note": "a"}]'
            "\n\n   \n",
            encoding="utf-8",
        )
        data = storage.load()
        assert len(data) == 1
        assert data[0]["id"] == 1

    def test_corrupt_json_exits_with_clear_message(self, expense_file):
        expense_file.write_text("[{broken json", encoding="utf-8")
        with pytest.raises(SystemExit, match="invalid JSON"):
            storage.load()


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

class TestAdd:

    def test_creates_file(self, expense_file):
        cli.cmd_add(ns(amount=10.0, category="food", note="lunch"))
        assert expense_file.exists()

    def test_correct_fields_stored(self, expense_file):
        cli.cmd_add(ns(amount=9.99, category="transport", note="bus"))
        data = json.loads(expense_file.read_text())
        assert len(data) == 1
        entry = data[0]
        assert entry["id"] == 1
        assert entry["amount"] == 9.99
        assert entry["category"] == "transport"
        assert entry["note"] == "bus"
        assert "date" in entry

    def test_id_auto_increments(self, expense_file):
        cli.cmd_add(ns(amount=5.00, category="food",      note="coffee"))
        cli.cmd_add(ns(amount=20.00, category="food",     note="dinner"))
        cli.cmd_add(ns(amount=3.00, category="transport", note="bus"))
        ids = [e["id"] for e in json.loads(expense_file.read_text())]
        assert ids == [1, 2, 3]

    def test_amount_rounded_to_cents(self, expense_file):
        cli.cmd_add(ns(amount=1.999, category="misc", note="test"))
        assert json.loads(expense_file.read_text())[0]["amount"] == 2.0

    def test_whitespace_stripped_from_category_and_note(self, expense_file):
        cli.cmd_add(ns(amount=5.0, category="  food  ", note="  lunch  "))
        entry = json.loads(expense_file.read_text())[0]
        assert entry["category"] == "food"
        assert entry["note"] == "lunch"

    def test_prints_confirmation(self, capsys):
        cli.cmd_add(ns(amount=12.50, category="food", note="lunch"))
        out = capsys.readouterr().out
        assert "#1" in out
        assert "$12.50" in out
        assert "food" in out
        assert "lunch" in out

    def test_negative_amount_exits(self):
        with pytest.raises(SystemExit):
            cli.cmd_add(ns(amount=-5.0, category="food", note="bad"))

    def test_zero_amount_exits(self):
        with pytest.raises(SystemExit):
            cli.cmd_add(ns(amount=0.0, category="food", note="bad"))


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

class TestList:

    def test_empty_store(self, capsys):
        cli.cmd_list(ns(category=None))
        assert "No expenses recorded yet." in capsys.readouterr().out

    def test_shows_all_expenses(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 12.50, "category": "food",      "note": "lunch"},
            {"id": 2, "date": "2026-06-02", "amount":  3.00, "category": "transport", "note": "bus"},
        ])
        cli.cmd_list(ns(category=None))
        out = capsys.readouterr().out
        assert "12.50"     in out
        assert "food"      in out
        assert "3.00"      in out
        assert "transport" in out

    def test_total_row(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 10.00, "category": "food", "note": "a"},
            {"id": 2, "date": "2026-06-01", "amount":  5.00, "category": "food", "note": "b"},
        ])
        cli.cmd_list(ns(category=None))
        assert "15.00" in capsys.readouterr().out

    def test_filter_by_category_excludes_others(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 12.50, "category": "food",      "note": "lunch"},
            {"id": 2, "date": "2026-06-01", "amount":  3.00, "category": "transport", "note": "bus"},
        ])
        cli.cmd_list(ns(category="food"))
        out = capsys.readouterr().out
        assert "food"      in out
        assert "transport" not in out

    def test_filter_is_case_insensitive(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 12.50, "category": "Food", "note": "lunch"},
        ])
        cli.cmd_list(ns(category="food"))   # lowercase query
        assert "12.50" in capsys.readouterr().out

    def test_filter_returns_all_matching_rows_with_correct_total(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 10.00, "category": "food", "note": "lunch"},
            {"id": 2, "date": "2026-06-01", "amount":  5.00, "category": "food", "note": "coffee"},
            {"id": 3, "date": "2026-06-01", "amount": 20.00, "category": "transport", "note": "taxi"},
        ])
        cli.cmd_list(ns(category="food"))
        out = capsys.readouterr().out
        assert "lunch"     in out
        assert "coffee"    in out
        assert "taxi"      not in out
        assert "15.00"     in out   # total for food only, not 35.00

    def test_filter_excludes_empty_category_rows(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 10.00, "category": "food", "note": "lunch"},
            {"id": 2, "date": "2026-06-01", "amount":  5.00, "category": "",     "note": "mystery"},
        ])
        cli.cmd_list(ns(category="food"))
        out = capsys.readouterr().out
        assert "lunch"   in out
        assert "mystery" not in out

    def test_filter_no_match_message(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 5.0, "category": "food", "note": "snack"},
        ])
        cli.cmd_list(ns(category="travel"))
        assert "No expenses found" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

class TestSummary:

    def test_empty_store(self, capsys):
        cli.cmd_summary(ns(month=None))
        assert "No expenses recorded yet." in capsys.readouterr().out

    def test_groups_by_category_and_sums(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 10.0, "category": "food",      "note": "a"},
            {"id": 2, "date": "2026-06-01", "amount":  5.0, "category": "food",      "note": "b"},
            {"id": 3, "date": "2026-06-01", "amount": 20.0, "category": "transport", "note": "c"},
        ])
        cli.cmd_summary(ns(month=None))
        out = capsys.readouterr().out
        assert "food"      in out
        assert "transport" in out
        assert "15.00"     in out   # food subtotal
        assert "20.00"     in out   # transport subtotal
        assert "35.00"     in out   # grand total

    def test_grand_total_label(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 42.0, "category": "bills", "note": "rent"},
        ])
        cli.cmd_summary(ns(month=None))
        out = capsys.readouterr().out
        assert "TOTAL" in out
        assert "42.00" in out

    def test_month_filter_includes_matching(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-01-15", "amount": 10.0, "category": "food", "note": "jan"},
            {"id": 2, "date": "2026-06-01", "amount": 99.0, "category": "food", "note": "jun"},
        ])
        cli.cmd_summary(ns(month="2026-01"))
        out = capsys.readouterr().out
        assert "10.00" in out
        assert "99.00" not in out

    def test_month_filter_appears_in_title(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-01-15", "amount": 10.0, "category": "food", "note": "a"},
        ])
        cli.cmd_summary(ns(month="2026-01"))
        assert "2026-01" in capsys.readouterr().out

    def test_month_filter_no_match_message(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 10.0, "category": "food", "note": "a"},
        ])
        cli.cmd_summary(ns(month="2020-01"))
        assert "No expenses found" in capsys.readouterr().out

    def test_category_filter_shows_only_matching_total(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 10.0, "category": "food",      "note": "a"},
            {"id": 2, "date": "2026-06-01", "amount":  5.0, "category": "food",      "note": "b"},
            {"id": 3, "date": "2026-06-01", "amount": 20.0, "category": "transport", "note": "c"},
        ])
        cli.cmd_summary(ns(category="food"))
        out = capsys.readouterr().out
        assert "food"      in out
        assert "transport" not in out
        assert "15.00"     in out   # food subtotal = grand total when filtered
        assert "20.00"     not in out

    def test_category_filter_no_match_message(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 10.0, "category": "food", "note": "a"},
        ])
        cli.cmd_summary(ns(category="travel"))
        assert "No expenses found" in capsys.readouterr().out

    def test_category_and_month_filter_combined(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-01-01", "amount": 10.0, "category": "food",      "note": "jan food"},
            {"id": 2, "date": "2026-01-01", "amount": 30.0, "category": "transport", "note": "jan transport"},
            {"id": 3, "date": "2026-06-01", "amount": 99.0, "category": "food",      "note": "jun food"},
        ])
        cli.cmd_summary(ns(month="2026-01", category="food"))
        out = capsys.readouterr().out
        assert "10.00"     in out    # only the jan food expense
        assert "30.00"     not in out
        assert "99.00"     not in out


# ---------------------------------------------------------------------------
# export-csv
# ---------------------------------------------------------------------------

class TestExportCsv:

    def test_header_always_written_on_empty_store(self, capsys):
        cli.cmd_export_csv(ns())
        out = capsys.readouterr().out
        assert out.startswith("id,date,amount,category,note")

    def test_exports_all_rows(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 12.5,  "category": "food",      "note": "lunch"},
            {"id": 2, "date": "2026-06-02", "amount":  3.0,  "category": "transport", "note": "bus"},
        ])
        cli.cmd_export_csv(ns())
        out = capsys.readouterr().out
        rows = list(csv.reader(io.StringIO(out)))
        # header + 2 data rows
        assert len(rows) == 3
        assert rows[1] == ["1", "2026-06-01", "12.5",  "food",      "lunch"]
        assert rows[2] == ["2", "2026-06-02",  "3.0",  "transport", "bus"]

    def test_amount_has_no_dollar_sign(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 9.99, "category": "misc", "note": "thing"},
        ])
        cli.cmd_export_csv(ns())
        out = capsys.readouterr().out
        # dollar signs must only appear in the human-readable commands, not CSV
        assert "$" not in out

    def test_output_is_valid_csv(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 5.0, "category": "food", "note": 'a "quoted" note'},
        ])
        cli.cmd_export_csv(ns())
        out = capsys.readouterr().out
        rows = list(csv.reader(io.StringIO(out)))
        assert rows[0] == ["id", "date", "amount", "category", "note"]
        assert rows[1][4] == 'a "quoted" note'


# ---------------------------------------------------------------------------
# import-csv
# ---------------------------------------------------------------------------

class TestImportCsv:

    # Helper: write a well-formed CSV file in tmp_path
    def _write_csv(self, tmp_path, rows, filename="import.csv"):
        p = tmp_path / filename
        with open(p, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=cli.CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return p

    def test_imports_expenses_from_csv(self, expense_file, tmp_path):
        csv_path = self._write_csv(tmp_path, [
            {"id": 1, "date": "2026-01-10", "amount": 15.0,  "category": "food",  "note": "lunch"},
            {"id": 2, "date": "2026-01-11", "amount":  4.5,  "category": "transport", "note": "bus"},
        ])
        cli.cmd_import_csv(ns(path=str(csv_path)))
        data = json.loads(expense_file.read_text())
        assert len(data) == 2
        assert data[0]["category"] == "food"
        assert data[1]["category"] == "transport"

    def test_ids_are_reassigned_from_one_on_empty_store(self, expense_file, tmp_path):
        # CSV may have arbitrary IDs; they should be ignored and reassigned
        csv_path = self._write_csv(tmp_path, [
            {"id": 99, "date": "2026-01-10", "amount": 10.0, "category": "food", "note": "a"},
            {"id": 42, "date": "2026-01-11", "amount": 20.0, "category": "food", "note": "b"},
        ])
        cli.cmd_import_csv(ns(path=str(csv_path)))
        data = json.loads(expense_file.read_text())
        assert [e["id"] for e in data] == [1, 2]

    def test_ids_continue_after_existing(self, expense_file, tmp_path):
        seed(expense_file, [
            {"id": 1, "date": "2026-01-01", "amount": 5.0, "category": "food", "note": "existing"},
            {"id": 2, "date": "2026-01-02", "amount": 5.0, "category": "food", "note": "existing"},
        ])
        csv_path = self._write_csv(tmp_path, [
            {"id": 1, "date": "2026-02-01", "amount": 7.0, "category": "misc", "note": "imported"},
        ])
        cli.cmd_import_csv(ns(path=str(csv_path)))
        data = json.loads(expense_file.read_text())
        assert len(data) == 3
        assert data[2]["id"] == 3   # continues from max existing id

    def test_appends_to_existing_expenses(self, expense_file, tmp_path):
        seed(expense_file, [
            {"id": 1, "date": "2026-01-01", "amount": 5.0, "category": "food", "note": "kept"},
        ])
        csv_path = self._write_csv(tmp_path, [
            {"id": 99, "date": "2026-02-01", "amount": 8.0, "category": "misc", "note": "new"},
        ])
        cli.cmd_import_csv(ns(path=str(csv_path)))
        data = json.loads(expense_file.read_text())
        # original row preserved
        assert data[0]["note"] == "kept"
        assert data[1]["note"] == "new"

    def test_empty_csv_reports_nothing_to_import(self, tmp_path, capsys):
        csv_path = self._write_csv(tmp_path, [])   # header only, no data rows
        cli.cmd_import_csv(ns(path=str(csv_path)))
        assert "No expenses to import." in capsys.readouterr().out

    def test_prints_imported_count(self, tmp_path, capsys):
        csv_path = self._write_csv(tmp_path, [
            {"id": 1, "date": "2026-01-10", "amount": 5.0, "category": "food", "note": "a"},
            {"id": 2, "date": "2026-01-11", "amount": 6.0, "category": "food", "note": "b"},
            {"id": 3, "date": "2026-01-12", "amount": 7.0, "category": "food", "note": "c"},
        ])
        cli.cmd_import_csv(ns(path=str(csv_path)))
        assert "3" in capsys.readouterr().out

    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            cli.cmd_import_csv(ns(path=str(tmp_path / "nonexistent.csv")))

    def test_invalid_amount_exits(self, tmp_path):
        p = tmp_path / "bad.csv"
        p.write_text("id,date,amount,category,note\n1,2026-01-01,not-a-number,food,lunch\n",
                     encoding="utf-8")
        with pytest.raises(SystemExit):
            cli.cmd_import_csv(ns(path=str(p)))

    def test_missing_column_exits(self, tmp_path):
        p = tmp_path / "bad.csv"
        # 'amount' column deliberately omitted
        p.write_text("id,date,category,note\n1,2026-01-01,food,lunch\n",
                     encoding="utf-8")
        with pytest.raises(SystemExit):
            cli.cmd_import_csv(ns(path=str(p)))
