"""Built-in fund table and expense-ratio lookup (Story 2.5, D-27, D-36).

Expense ratios are percentages: 0.03 means 0.03%.

Lookup order for a holding:
1. An expense ratio in the uploaded file always wins.
2. Otherwise, the built-in fund table.
3. Otherwise, a US mutual fund ticker (five letters ending in X) is a fund
   whose expense ratio is unknown, reported as "unknown", never 0.
4. Otherwise, the ticker is treated as an individual stock (D-36), which has
   no expense ratio. This is an assumption, so it is flagged for the UI.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from functools import lru_cache
from pathlib import Path

FUND_TABLE_PATH = Path(__file__).resolve().parents[1] / "data" / "fund_table.csv"
ASSET_TYPES = ("cash", "bond_fund", "balanced_fund", "stock_fund", "individual_stock")
FUND_TABLE_COLUMNS = ("ticker", "name", "asset_type", "expense_ratio", "as_of", "source")
MUTUAL_FUND_TICKER = re.compile(r"^[A-Z]{4}X$")


class FundTableError(Exception):
    """Raised when the built-in fund table is missing or invalid."""


class ExpenseSource(str, Enum):
    FILE = "file"  # from the user's upload
    TABLE = "table"  # from the built-in fund table
    NOT_APPLICABLE = "not_applicable"  # individual stocks have no expense ratio
    UNKNOWN = "unknown"  # a fund with no expense ratio anywhere


@dataclass(frozen=True)
class FundInfo:
    ticker: str
    name: str
    asset_type: str
    expense_ratio: float
    as_of: date
    source: str


@dataclass(frozen=True)
class ExpenseLookup:
    ticker: str
    expense_ratio: float | None  # percent; None when not applicable or unknown
    source: ExpenseSource
    asset_type: str | None  # None when the holding is a fund of unknown type
    assumed_stock: bool = False  # True when we guessed "individual stock"


def load_fund_table(path: Path = FUND_TABLE_PATH) -> dict[str, FundInfo]:
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if tuple(reader.fieldnames or ()) != FUND_TABLE_COLUMNS:
                raise FundTableError(f"{path.name}: columns must be {', '.join(FUND_TABLE_COLUMNS)}")
            rows = list(reader)
    except OSError as exc:
        raise FundTableError(f"{path.name}: cannot be read") from exc

    table: dict[str, FundInfo] = {}
    for line, row in enumerate(rows, start=2):
        where = f"{path.name} line {line}"
        ticker = (row["ticker"] or "").strip().upper()
        if not ticker or ticker in table:
            raise FundTableError(f"{where}: missing or duplicate ticker")
        if row["asset_type"] not in ASSET_TYPES or row["asset_type"] == "individual_stock":
            raise FundTableError(f"{where}: invalid asset_type {row['asset_type']!r}")
        try:
            ratio = float(row["expense_ratio"])
            as_of = date.fromisoformat(row["as_of"])
        except (TypeError, ValueError) as exc:
            raise FundTableError(f"{where}: expense_ratio must be a number and as_of a date") from exc
        if not 0 <= ratio < 3:
            raise FundTableError(f"{where}: expense_ratio must be a percentage, e.g. 0.03")
        if not row["source"]:
            raise FundTableError(f"{where}: missing source")
        table[ticker] = FundInfo(ticker, row["name"], row["asset_type"], ratio, as_of, row["source"])
    return table


@lru_cache(maxsize=1)
def fund_table() -> dict[str, FundInfo]:
    """The built-in table, loaded once."""
    return load_fund_table()


def lookup_expense_ratio(
    ticker: str, file_value: float | None = None, table: dict[str, FundInfo] | None = None
) -> ExpenseLookup:
    table = fund_table() if table is None else table
    ticker = ticker.strip().upper()
    fund = table.get(ticker)

    if file_value is not None:
        return ExpenseLookup(ticker, file_value, ExpenseSource.FILE, fund.asset_type if fund else None)
    if fund:
        return ExpenseLookup(ticker, fund.expense_ratio, ExpenseSource.TABLE, fund.asset_type)
    if MUTUAL_FUND_TICKER.match(ticker):
        return ExpenseLookup(ticker, None, ExpenseSource.UNKNOWN, None)
    return ExpenseLookup(ticker, None, ExpenseSource.NOT_APPLICABLE, "individual_stock", assumed_stock=True)
