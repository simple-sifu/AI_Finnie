"""Story 2.4: sample holdings files for testing and the demo.

Format (D-29): CSV with columns ticker, shares and an optional expense_ratio.
expense_ratio is a percentage, so 0.03 means 0.03%.
"""

import csv
import re
from pathlib import Path

import pytest

SAMPLES = Path(__file__).resolve().parents[2] / "src" / "data" / "samples"
VALID = ["diversified.csv", "concentrated.csv", "missing_expense_ratios.csv"]
MALFORMED = ["malformed_missing_column.csv", "malformed_bad_values.csv"]
TICKER = re.compile(r"^[A-Z]{1,5}$")  # US ticker symbols
FUNDS = {"VOO", "VTI", "VXUS", "BND", "VNQ", "QQQ", "SCHB"}  # funds used in the samples


def rows(name):
    with open(SAMPLES / name, newline="") as f:
        return list(csv.DictReader(f))


def problems(name):
    """A minimal checker for these fixtures; the real parser comes in Story 3.3."""
    with open(SAMPLES / name, newline="") as f:
        reader = csv.DictReader(f)
        if not {"ticker", "shares"} <= set(reader.fieldnames or []):
            return ["missing required column"]
        found = []
        for row in reader:
            if not TICKER.match(row["ticker"] or ""):
                found.append("bad ticker")
            try:
                if float(row["shares"]) <= 0:
                    found.append("shares not positive")
            except ValueError:
                found.append("shares not a number")
            if row.get("expense_ratio"):
                try:
                    float(row["expense_ratio"])
                except ValueError:
                    found.append("expense_ratio not a number")
        return found


@pytest.mark.parametrize("name", VALID)
def test_valid_samples_have_no_problems(name):
    assert rows(name), f"{name} is empty"
    assert problems(name) == []


@pytest.mark.parametrize("name", VALID)
def test_expense_ratios_are_percentages(name):
    for row in rows(name):
        if row["expense_ratio"]:
            assert 0 <= float(row["expense_ratio"]) < 3, "use percent, e.g. 0.03 for 0.03%"


def test_concentrated_sample_holds_two_stocks_and_one_fund():
    tickers = [row["ticker"] for row in rows("concentrated.csv")]
    stocks = [t for t in tickers if t not in FUNDS]
    assert len(stocks) == 2 and len(tickers) == 3


def test_missing_expense_ratio_sample_has_funds_without_one():
    missing = [r["ticker"] for r in rows("missing_expense_ratios.csv") if not r["expense_ratio"]]
    assert any(t in FUNDS for t in missing)


def test_malformed_missing_column():
    assert problems("malformed_missing_column.csv") == ["missing required column"]


def test_malformed_bad_values_covers_each_problem():
    found = problems("malformed_bad_values.csv")
    for problem in ["shares not a number", "bad ticker", "shares not positive", "expense_ratio not a number"]:
        assert problem in found


def test_samples_are_listed_in_readme():
    readme = (SAMPLES.parents[2] / "README.md").read_text()
    for name in VALID + MALFORMED:
        assert name in readme
