"""Tests for expense_cli — add, list, and summary commands."""

import argparse
import json

import pytest

import expense_cli


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
    monkeypatch.setattr(expense_cli, "EXPENSES_FILE", str(path))
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ns(**kwargs):
    """Build an argparse.Namespace for direct handler calls.

    Mirrors the attributes argparse would populate; only supply what the
    command under test actually reads.
    """
    defaults = {"amount": None, "category": None, "note": None, "month": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def seed(path, expenses):
    """Write a list of expense dicts directly to the JSON file."""
    path.write_text(json.dumps(expenses), encoding="utf-8")


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

class TestAdd:

    def test_creates_file(self, expense_file):
        expense_cli.cmd_add(ns(amount=10.0, category="food", note="lunch"))
        assert expense_file.exists()

    def test_correct_fields_stored(self, expense_file):
        expense_cli.cmd_add(ns(amount=9.99, category="transport", note="bus"))
        data = json.loads(expense_file.read_text())
        assert len(data) == 1
        entry = data[0]
        assert entry["id"] == 1
        assert entry["amount"] == 9.99
        assert entry["category"] == "transport"
        assert entry["note"] == "bus"
        assert "date" in entry

    def test_id_auto_increments(self, expense_file):
        expense_cli.cmd_add(ns(amount=5.00, category="food",      note="coffee"))
        expense_cli.cmd_add(ns(amount=20.00, category="food",     note="dinner"))
        expense_cli.cmd_add(ns(amount=3.00, category="transport", note="bus"))
        ids = [e["id"] for e in json.loads(expense_file.read_text())]
        assert ids == [1, 2, 3]

    def test_amount_rounded_to_cents(self, expense_file):
        expense_cli.cmd_add(ns(amount=1.999, category="misc", note="test"))
        assert json.loads(expense_file.read_text())[0]["amount"] == 2.0

    def test_whitespace_stripped_from_category_and_note(self, expense_file):
        expense_cli.cmd_add(ns(amount=5.0, category="  food  ", note="  lunch  "))
        entry = json.loads(expense_file.read_text())[0]
        assert entry["category"] == "food"
        assert entry["note"] == "lunch"

    def test_prints_confirmation(self, capsys):
        expense_cli.cmd_add(ns(amount=12.50, category="food", note="lunch"))
        out = capsys.readouterr().out
        assert "#1" in out
        assert "$12.50" in out
        assert "food" in out
        assert "lunch" in out

    def test_negative_amount_exits(self):
        with pytest.raises(SystemExit):
            expense_cli.cmd_add(ns(amount=-5.0, category="food", note="bad"))

    def test_zero_amount_exits(self):
        with pytest.raises(SystemExit):
            expense_cli.cmd_add(ns(amount=0.0, category="food", note="bad"))


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

class TestList:

    def test_empty_store(self, capsys):
        expense_cli.cmd_list(ns(category=None))
        assert "No expenses recorded yet." in capsys.readouterr().out

    def test_shows_all_expenses(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 12.50, "category": "food",      "note": "lunch"},
            {"id": 2, "date": "2026-06-02", "amount":  3.00, "category": "transport", "note": "bus"},
        ])
        expense_cli.cmd_list(ns(category=None))
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
        expense_cli.cmd_list(ns(category=None))
        assert "15.00" in capsys.readouterr().out

    def test_filter_by_category_excludes_others(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 12.50, "category": "food",      "note": "lunch"},
            {"id": 2, "date": "2026-06-01", "amount":  3.00, "category": "transport", "note": "bus"},
        ])
        expense_cli.cmd_list(ns(category="food"))
        out = capsys.readouterr().out
        assert "food"      in out
        assert "transport" not in out

    def test_filter_is_case_insensitive(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 12.50, "category": "Food", "note": "lunch"},
        ])
        expense_cli.cmd_list(ns(category="food"))   # lowercase query
        assert "12.50" in capsys.readouterr().out

    def test_filter_no_match_message(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 5.0, "category": "food", "note": "snack"},
        ])
        expense_cli.cmd_list(ns(category="travel"))
        assert "No expenses found" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

class TestSummary:

    def test_empty_store(self, capsys):
        expense_cli.cmd_summary(ns(month=None))
        assert "No expenses recorded yet." in capsys.readouterr().out

    def test_groups_by_category_and_sums(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 10.0, "category": "food",      "note": "a"},
            {"id": 2, "date": "2026-06-01", "amount":  5.0, "category": "food",      "note": "b"},
            {"id": 3, "date": "2026-06-01", "amount": 20.0, "category": "transport", "note": "c"},
        ])
        expense_cli.cmd_summary(ns(month=None))
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
        expense_cli.cmd_summary(ns(month=None))
        out = capsys.readouterr().out
        assert "TOTAL" in out
        assert "42.00" in out

    def test_month_filter_includes_matching(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-01-15", "amount": 10.0, "category": "food", "note": "jan"},
            {"id": 2, "date": "2026-06-01", "amount": 99.0, "category": "food", "note": "jun"},
        ])
        expense_cli.cmd_summary(ns(month="2026-01"))
        out = capsys.readouterr().out
        assert "10.00" in out
        assert "99.00" not in out

    def test_month_filter_appears_in_title(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-01-15", "amount": 10.0, "category": "food", "note": "a"},
        ])
        expense_cli.cmd_summary(ns(month="2026-01"))
        assert "2026-01" in capsys.readouterr().out

    def test_month_filter_no_match_message(self, expense_file, capsys):
        seed(expense_file, [
            {"id": 1, "date": "2026-06-01", "amount": 10.0, "category": "food", "note": "a"},
        ])
        expense_cli.cmd_summary(ns(month="2020-01"))
        assert "No expenses found" in capsys.readouterr().out
