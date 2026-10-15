"""Story 2.5: built-in expense-ratio table and lookup."""

from datetime import date

import pytest

from src.core.funds import (
    ASSET_TYPES,
    ExpenseSource,
    FundTableError,
    fund_table,
    load_fund_table,
    lookup_expense_ratio,
)

HEADER = "ticker,name,asset_type,expense_ratio,as_of,source\n"


def table_file(tmp_path, *rows):
    path = tmp_path / "fund_table.csv"
    path.write_text(HEADER + "".join(rows))
    return path


def test_real_table_loads_with_required_fields():
    table = fund_table()
    assert len(table) >= 10
    for fund in table.values():
        assert fund.asset_type in ASSET_TYPES and fund.asset_type != "individual_stock"
        assert 0 <= fund.expense_ratio < 3
        assert isinstance(fund.as_of, date) and fund.source


def test_real_table_covers_every_fund_in_the_sample_portfolios():
    assert {"VTI", "VXUS", "BND", "VNQ", "VOO", "QQQ", "SCHB"} <= set(fund_table())


def test_file_value_takes_priority_over_table():
    result = lookup_expense_ratio("VTI", file_value=0.5)
    assert result.expense_ratio == 0.5 and result.source is ExpenseSource.FILE
    assert result.asset_type == "stock_fund"


def test_table_fills_in_a_missing_value():
    result = lookup_expense_ratio("qqq")
    assert result.ticker == "QQQ"
    assert result.expense_ratio == fund_table()["QQQ"].expense_ratio
    assert result.source is ExpenseSource.TABLE


def test_unlisted_ticker_is_treated_as_an_individual_stock():
    result = lookup_expense_ratio("AAPL")
    assert result.expense_ratio is None
    assert result.source is ExpenseSource.NOT_APPLICABLE
    assert result.asset_type == "individual_stock" and result.assumed_stock


def test_unlisted_mutual_fund_is_unknown_not_zero():
    result = lookup_expense_ratio("VTSAX")
    assert result.expense_ratio is None and result.expense_ratio != 0
    assert result.source is ExpenseSource.UNKNOWN and result.asset_type is None


def test_file_value_for_an_unlisted_fund_is_used():
    result = lookup_expense_ratio("FXAIX", file_value=0.015)
    assert result.expense_ratio == 0.015 and result.asset_type is None


def test_custom_table(tmp_path):
    path = table_file(tmp_path, "ABC,Test Fund,bond_fund,0.10,2026-01-02,Test source\n")
    table = load_fund_table(path)
    assert lookup_expense_ratio("ABC", table=table).expense_ratio == 0.10


@pytest.mark.parametrize(
    "row, message",
    [
        ("ABC,Fund,crypto_fund,0.1,2026-01-02,Src\n", "invalid asset_type"),
        ("ABC,Fund,individual_stock,0.1,2026-01-02,Src\n", "invalid asset_type"),
        ("ABC,Fund,bond_fund,abc,2026-01-02,Src\n", "must be a number"),
        ("ABC,Fund,bond_fund,0.1,not-a-date,Src\n", "must be a number"),
        ("ABC,Fund,bond_fund,0.0003,2026-01-02,Src\nABC,Fund,bond_fund,0.1,2026-01-02,Src\n", "duplicate"),
        ("ABC,Fund,bond_fund,5,2026-01-02,Src\n", "percentage"),
        ("ABC,Fund,bond_fund,0.1,2026-01-02,\n", "missing source"),
    ],
)
def test_bad_rows_fail(tmp_path, row, message):
    with pytest.raises(FundTableError, match=message):
        load_fund_table(table_file(tmp_path, row))


def test_wrong_columns_fail(tmp_path):
    path = tmp_path / "fund_table.csv"
    path.write_text("ticker,expense_ratio\nABC,0.1\n")
    with pytest.raises(FundTableError, match="columns must be"):
        load_fund_table(path)


def test_missing_file_fails(tmp_path):
    with pytest.raises(FundTableError, match="cannot be read"):
        load_fund_table(tmp_path / "nope.csv")
