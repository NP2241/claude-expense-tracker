"""Tests for expense_cli — add, list, summary, export-csv, and import-csv."""

import argparse
import csv
import io

import pytest

from expense_cli import cli, storage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def db_file(tmp_path, monkeypatch):
    """Point DB_FILE at a fresh temp database for every test.

    autouse=True means every test gets an isolated, empty database
    automatically.  Returning the path lets individual tests assert that
    the file was created.
    """
    path = tmp_path / "expenses.db"
    monkeypatch.setattr(storage, "DB_FILE", str(path))
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ns(**kwargs):
    """Build an argparse.Namespace for direct handler calls.

    Mirrors the attributes argparse would populate; only supply what the
    command under test actually reads.
    """
    defaults = {"amount": None, "category": None, "note": None,
                "month": None, "path": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def seed(expenses):
    """Insert a list of expense dicts directly into the test database."""
    storage.add_many(expenses)


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------

class TestStorage:

    def test_empty_db_returns_empty_list(self):
        assert storage.load() == []

    def test_add_returns_auto_assigned_id(self):
        entry = {"date": "2026-01-01", "amount": 5.0,
                 "category": "food", "note": "test"}
        assert storage.add(entry) == 1

    def test_ids_assigned_sequentially(self):
        e = {"date": "2026-01-01", "amount": 5.0, "category": "food", "note": "x"}
        assert storage.add(e) == 1
        assert storage.add(e) == 2
        assert storage.add(e) == 3

    def test_load_returns_inserted_rows(self):
        storage.add({"date": "2026-01-01", "amount": 10.0,
                     "category": "food", "note": "a"})
        storage.add({"date": "2026-01-02", "amount":  5.0,
                     "category": "misc", "note": "b"})
        rows = storage.load()
        assert len(rows) == 2
        assert rows[0]["category"] == "food"
        assert rows[1]["category"] == "misc"

    def test_load_rows_ordered_by_id(self):
        for i in range(3):
            storage.add({"date": "2026-01-01", "amount": float(i + 1),
                         "category": "food", "note": str(i)})
        assert [r["id"] for r in storage.load()] == [1, 2, 3]


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

class TestAdd:

    def test_creates_db_file(self, db_file):
        cli.cmd_add(ns(amount=10.0, category="food", note="lunch"))
        assert db_file.exists()

    def test_correct_fields_stored(self):
        cli.cmd_add(ns(amount=9.99, category="transport", note="bus"))
        data = storage.load()
        assert len(data) == 1
        entry = data[0]
        assert entry["id"] == 1
        assert entry["amount"] == 9.99
        assert entry["category"] == "transport"
        assert entry["note"] == "bus"
        assert "date" in entry

    def test_id_auto_increments(self):
        cli.cmd_add(ns(amount=5.00,  category="food",      note="coffee"))
        cli.cmd_add(ns(amount=20.00, category="food",      note="dinner"))
        cli.cmd_add(ns(amount=3.00,  category="transport", note="bus"))
        assert [e["id"] for e in storage.load()] == [1, 2, 3]

    def test_amount_rounded_to_cents(self):
        cli.cmd_add(ns(amount=1.999, category="misc", note="test"))
        assert storage.load()[0]["amount"] == 2.0

    def test_whitespace_stripped_from_category_and_note(self):
        cli.cmd_add(ns(amount=5.0, category="  food  ", note="  lunch  "))
        entry = storage.load()[0]
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

    def test_shows_all_expenses(self, capsys):
        seed([
            {"date": "2026-06-01", "amount": 12.50, "category": "food",      "note": "lunch"},
            {"date": "2026-06-02", "amount":  3.00, "category": "transport", "note": "bus"},
        ])
        cli.cmd_list(ns(category=None))
        out = capsys.readouterr().out
        assert "12.50"     in out
        assert "food"      in out
        assert "3.00"      in out
        assert "transport" in out

    def test_total_row(self, capsys):
        seed([
            {"date": "2026-06-01", "amount": 10.00, "category": "food", "note": "a"},
            {"date": "2026-06-01", "amount":  5.00, "category": "food", "note": "b"},
        ])
        cli.cmd_list(ns(category=None))
        assert "15.00" in capsys.readouterr().out

    def test_filter_by_category_excludes_others(self, capsys):
        seed([
            {"date": "2026-06-01", "amount": 12.50, "category": "food",      "note": "lunch"},
            {"date": "2026-06-01", "amount":  3.00, "category": "transport", "note": "bus"},
        ])
        cli.cmd_list(ns(category="food"))
        out = capsys.readouterr().out
        assert "food"      in out
        assert "transport" not in out

    def test_filter_is_case_insensitive(self, capsys):
        seed([{"date": "2026-06-01", "amount": 12.50,
               "category": "Food", "note": "lunch"}])
        cli.cmd_list(ns(category="food"))   # lowercase query
        assert "12.50" in capsys.readouterr().out

    def test_filter_no_match_message(self, capsys):
        seed([{"date": "2026-06-01", "amount": 5.0,
               "category": "food", "note": "snack"}])
        cli.cmd_list(ns(category="travel"))
        assert "No expenses found" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

class TestSummary:

    def test_empty_store(self, capsys):
        cli.cmd_summary(ns(month=None))
        assert "No expenses recorded yet." in capsys.readouterr().out

    def test_groups_by_category_and_sums(self, capsys):
        seed([
            {"date": "2026-06-01", "amount": 10.0, "category": "food",      "note": "a"},
            {"date": "2026-06-01", "amount":  5.0, "category": "food",      "note": "b"},
            {"date": "2026-06-01", "amount": 20.0, "category": "transport", "note": "c"},
        ])
        cli.cmd_summary(ns(month=None))
        out = capsys.readouterr().out
        assert "food"      in out
        assert "transport" in out
        assert "15.00"     in out   # food subtotal
        assert "20.00"     in out   # transport subtotal
        assert "35.00"     in out   # grand total

    def test_grand_total_label(self, capsys):
        seed([{"date": "2026-06-01", "amount": 42.0,
               "category": "bills", "note": "rent"}])
        cli.cmd_summary(ns(month=None))
        out = capsys.readouterr().out
        assert "TOTAL" in out
        assert "42.00" in out

    def test_month_filter_includes_matching(self, capsys):
        seed([
            {"date": "2026-01-15", "amount": 10.0, "category": "food", "note": "jan"},
            {"date": "2026-06-01", "amount": 99.0, "category": "food", "note": "jun"},
        ])
        cli.cmd_summary(ns(month="2026-01"))
        out = capsys.readouterr().out
        assert "10.00" in out
        assert "99.00" not in out

    def test_month_filter_appears_in_title(self, capsys):
        seed([{"date": "2026-01-15", "amount": 10.0,
               "category": "food", "note": "a"}])
        cli.cmd_summary(ns(month="2026-01"))
        assert "2026-01" in capsys.readouterr().out

    def test_month_filter_no_match_message(self, capsys):
        seed([{"date": "2026-06-01", "amount": 10.0,
               "category": "food", "note": "a"}])
        cli.cmd_summary(ns(month="2020-01"))
        assert "No expenses found" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# export-csv
# ---------------------------------------------------------------------------

class TestExportCsv:

    def test_header_always_written_on_empty_store(self, capsys):
        cli.cmd_export_csv(ns())
        assert capsys.readouterr().out.startswith("id,date,amount,category,note")

    def test_exports_all_rows(self, capsys):
        seed([
            {"date": "2026-06-01", "amount": 12.5, "category": "food",      "note": "lunch"},
            {"date": "2026-06-02", "amount":  3.0, "category": "transport", "note": "bus"},
        ])
        cli.cmd_export_csv(ns())
        rows = list(csv.reader(io.StringIO(capsys.readouterr().out)))
        assert len(rows) == 3   # header + 2 data rows
        assert rows[1] == ["1", "2026-06-01", "12.5",  "food",      "lunch"]
        assert rows[2] == ["2", "2026-06-02",  "3.0",  "transport", "bus"]

    def test_amount_has_no_dollar_sign(self, capsys):
        seed([{"date": "2026-06-01", "amount": 9.99,
               "category": "misc", "note": "thing"}])
        cli.cmd_export_csv(ns())
        assert "$" not in capsys.readouterr().out

    def test_output_is_valid_csv(self, capsys):
        seed([{"date": "2026-06-01", "amount": 5.0,
               "category": "food", "note": 'a "quoted" note'}])
        cli.cmd_export_csv(ns())
        rows = list(csv.reader(io.StringIO(capsys.readouterr().out)))
        assert rows[0] == ["id", "date", "amount", "category", "note"]
        assert rows[1][4] == 'a "quoted" note'


# ---------------------------------------------------------------------------
# import-csv
# ---------------------------------------------------------------------------

class TestImportCsv:

    def _write_csv(self, tmp_path, rows, filename="import.csv"):
        """Write a well-formed CSV file and return its path."""
        p = tmp_path / filename
        with open(p, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=cli.CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return p

    def test_imports_expenses_from_csv(self, tmp_path):
        csv_path = self._write_csv(tmp_path, [
            {"id": 1, "date": "2026-01-10", "amount": 15.0, "category": "food",      "note": "lunch"},
            {"id": 2, "date": "2026-01-11", "amount":  4.5, "category": "transport", "note": "bus"},
        ])
        cli.cmd_import_csv(ns(path=str(csv_path)))
        data = storage.load()
        assert len(data) == 2
        assert data[0]["category"] == "food"
        assert data[1]["category"] == "transport"

    def test_ids_are_reassigned_from_one_on_empty_store(self, tmp_path):
        # IDs in the CSV are ignored; SQLite AUTOINCREMENT assigns fresh ones.
        csv_path = self._write_csv(tmp_path, [
            {"id": 99, "date": "2026-01-10", "amount": 10.0, "category": "food", "note": "a"},
            {"id": 42, "date": "2026-01-11", "amount": 20.0, "category": "food", "note": "b"},
        ])
        cli.cmd_import_csv(ns(path=str(csv_path)))
        assert [e["id"] for e in storage.load()] == [1, 2]

    def test_ids_continue_after_existing(self, tmp_path):
        seed([
            {"date": "2026-01-01", "amount": 5.0, "category": "food", "note": "existing"},
            {"date": "2026-01-02", "amount": 5.0, "category": "food", "note": "existing"},
        ])
        csv_path = self._write_csv(tmp_path, [
            {"id": 1, "date": "2026-02-01", "amount": 7.0, "category": "misc", "note": "imported"},
        ])
        cli.cmd_import_csv(ns(path=str(csv_path)))
        data = storage.load()
        assert len(data) == 3
        assert data[2]["id"] == 3   # AUTOINCREMENT continues from last used id

    def test_appends_to_existing_expenses(self, tmp_path):
        seed([{"date": "2026-01-01", "amount": 5.0,
               "category": "food", "note": "kept"}])
        csv_path = self._write_csv(tmp_path, [
            {"id": 99, "date": "2026-02-01", "amount": 8.0, "category": "misc", "note": "new"},
        ])
        cli.cmd_import_csv(ns(path=str(csv_path)))
        data = storage.load()
        assert data[0]["note"] == "kept"
        assert data[1]["note"] == "new"

    def test_empty_csv_reports_nothing_to_import(self, tmp_path, capsys):
        cli.cmd_import_csv(ns(path=str(self._write_csv(tmp_path, []))))
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
        p.write_text("id,date,category,note\n1,2026-01-01,food,lunch\n",
                     encoding="utf-8")
        with pytest.raises(SystemExit):
            cli.cmd_import_csv(ns(path=str(p)))
