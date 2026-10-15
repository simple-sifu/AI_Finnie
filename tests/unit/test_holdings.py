"""Story 3.3: parsing the holdings CSV."""

from pathlib import Path

import pytest

from src.core.holdings import Holding, parse_holdings

SAMPLES = Path(__file__).resolve().parents[2] / "src" / "data" / "samples"


def test_valid_samples_parse():
    result = parse_holdings((SAMPLES / "diversified.csv").read_bytes())
    assert result.ok and result.problems == []
    assert result.holdings[0] == Holding("VTI", 40.0, 0.03)
    assert result.holdings[-1] == Holding("AAPL", 5.0, None)


def test_malformed_values_list_every_problem_by_spreadsheet_row():
    result = parse_holdings((SAMPLES / "malformed_bad_values.csv").read_bytes())
    assert not result.ok and result.holdings == []
    assert result.problems == [
        "Row 2: shares is not a number ('forty').",
        "Row 3: the ticker is missing.",
        "Row 4: shares must be more than 0.",
        "Row 5: expense_ratio is not a number ('abc').",
    ]


def test_missing_column_is_explained():
    result = parse_holdings((SAMPLES / "malformed_missing_column.csv").read_bytes())
    assert result.problems == ["The file needs a 'shares' column. Columns should be: ticker, shares, expense_ratio (optional)."]


def test_header_is_case_insensitive_extra_columns_ignored_and_excel_bom_handled():
    data = "﻿Ticker,Name,SHARES,Expense_Ratio\nvti,Total Market,10,0.03\n".encode()
    assert parse_holdings(data).holdings == [Holding("VTI", 10.0, 0.03)]


def test_expense_ratio_column_is_optional_and_numbers_can_have_commas():
    assert parse_holdings("ticker,shares\nVOO,\"1,250\"\n").holdings == [Holding("VOO", 1250.0, None)]


def test_duplicate_tickers_are_combined_with_a_note():
    result = parse_holdings("ticker,shares,expense_ratio\nVTI,10,\nVTI,5,0.03\n")
    assert result.holdings == [Holding("VTI", 15.0, 0.03)]
    assert result.notes == ["VTI appears more than once, so its shares were added together."]


def test_blank_lines_are_skipped():
    assert len(parse_holdings("ticker,shares\nVTI,1\n\n,\nBND,2\n").holdings) == 2


@pytest.mark.parametrize(
    "row, problem",
    [
        ("VTI,10,5", "looks wrong. Write it as a percentage"),
        ("VTI,10,-0.1", "looks wrong"),
        ("12ABC,10,", "isn't a valid US ticker"),
        ("VTI,,", "shares is missing"),
        ("VTI,nan,", "shares is not a number"),
    ],
)
def test_bad_rows(row, problem):
    result = parse_holdings(f"ticker,shares,expense_ratio\n{row}\n")
    assert not result.ok and problem in result.problems[0]


def test_empty_file_and_header_only():
    assert "needs a 'ticker' and a 'shares' column" in parse_holdings("").problems[0]
    assert parse_holdings("ticker,shares\n").problems == ["The file has no holdings. Add one row per investment under the header."]


def test_row_limit():
    data = "ticker,shares\n" + "VTI,1\n" * 201
    assert "has 201 holdings; the limit is 200" in parse_holdings(data).problems[0]


def test_size_limit():
    data = b"ticker,shares\n" + b"VTI,1\n" * 200_000
    assert "larger than 1 MB" in parse_holdings(data).problems[0]


def test_non_text_file():
    assert "isn't a readable CSV" in parse_holdings(b"\xff\xfe\x00\x81binary").problems[0]
