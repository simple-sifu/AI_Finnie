"""Parse an uploaded holdings CSV (Story 3.3, D-29).

Format: columns `ticker`, `shares` and an optional `expense_ratio`, written as a
percentage (0.03 means 0.03%). Column names are case-insensitive; other columns
are ignored. Rows are numbered as a spreadsheet shows them: the header is row 1,
so the first holding is row 2.

Any problem means no analysis: every problem is listed so the user can fix the
file in one go (front-end spec §4.2).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from src.core.market_data import normalize_ticker

MAX_EXPENSE_RATIO = 3.0  # percent; anything higher is almost certainly a typo or a fraction


@dataclass(frozen=True)
class Holding:
    ticker: str
    shares: float
    expense_ratio: float | None  # percent, from the file; None if blank


@dataclass(frozen=True)
class ParseResult:
    holdings: list[Holding]
    problems: list[str]
    notes: list[str]

    @property
    def ok(self) -> bool:
        return not self.problems and bool(self.holdings)


def _number(text: str) -> float | None:
    try:
        value = float(text.replace(",", "").replace("$", "").replace("%", "").strip())
    except ValueError:
        return None
    return value if value == value and value not in (float("inf"), float("-inf")) else None


def parse_holdings(data: bytes | str, max_rows: int = 200, max_file_mb: float = 1.0) -> ParseResult:
    raw = data.encode() if isinstance(data, str) else data
    if len(raw) > max_file_mb * 1024 * 1024:
        return ParseResult([], [f"This file is larger than {max_file_mb:g} MB. Please upload a smaller file."], [])
    try:
        text = raw.decode("utf-8-sig")  # handles the byte-order mark Excel adds
    except UnicodeDecodeError:
        return ParseResult([], ["This file isn't a readable CSV text file. Please save it as CSV (UTF-8)."], [])

    # Old Mac spreadsheets end lines with a bare carriage return, which Python's csv module rejects.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    try:
        return _parse(csv.reader(io.StringIO(text)), max_rows)
    except csv.Error:  # e.g. a single field longer than the csv module allows
        return ParseResult([], ["This file doesn't look like a valid CSV. Please check it and save it as CSV (UTF-8)."], [])


def _parse(reader, max_rows: int) -> ParseResult:
    header = next(reader, None)
    columns = [c.strip().lower() for c in header] if header else []
    missing = [name for name in ("ticker", "shares") if name not in columns]
    if missing:
        return ParseResult([], [f"The file needs a {' and a '.join(repr(m) for m in missing)} column. "
                                "Columns should be: ticker, shares, expense_ratio (optional)."], [])
    t_col, s_col = columns.index("ticker"), columns.index("shares")
    e_col = columns.index("expense_ratio") if "expense_ratio" in columns else None

    rows = [(number, row) for number, row in enumerate(reader, start=2) if any(cell.strip() for cell in row)]
    if len(rows) > max_rows:
        return ParseResult([], [f"This file has {len(rows)} holdings; the limit is {max_rows}. Please upload a smaller file."], [])

    problems: list[str] = []
    combined: dict[str, Holding] = {}
    notes: list[str] = []
    for number, row in rows:
        cell = lambda i: row[i].strip() if i is not None and i < len(row) else ""  # noqa: E731
        raw_ticker, raw_shares, raw_er = cell(t_col), cell(s_col), cell(e_col)

        ticker = normalize_ticker(raw_ticker)
        if not raw_ticker:
            problems.append(f"Row {number}: the ticker is missing.")
        elif ticker is None:
            problems.append(f"Row {number}: {raw_ticker!r} isn't a valid US ticker symbol.")

        shares = _number(raw_shares)
        if not raw_shares:
            problems.append(f"Row {number}: shares is missing.")
        elif shares is None:
            problems.append(f"Row {number}: shares is not a number ({raw_shares!r}).")
        elif shares <= 0:
            problems.append(f"Row {number}: shares must be more than 0.")

        expense_ratio = None
        if raw_er:
            expense_ratio = _number(raw_er)
            if expense_ratio is None:
                problems.append(f"Row {number}: expense_ratio is not a number ({raw_er!r}).")
            elif not 0 <= expense_ratio < MAX_EXPENSE_RATIO:
                problems.append(f"Row {number}: expense_ratio {raw_er} looks wrong. Write it as a percentage, e.g. 0.03 for 0.03%.")

        if ticker and shares and shares > 0 and (not raw_er or expense_ratio is not None):
            if ticker in combined:
                previous = combined[ticker]
                notes.append(f"{ticker} appears more than once, so its shares were added together.")
                combined[ticker] = Holding(ticker, previous.shares + shares, previous.expense_ratio or expense_ratio)
            else:
                combined[ticker] = Holding(ticker, shares, expense_ratio)

    if not rows:
        problems.append("The file has no holdings. Add one row per investment under the header.")
    if problems:
        return ParseResult([], problems, [])
    return ParseResult(list(combined.values()), [], sorted(set(notes)))
