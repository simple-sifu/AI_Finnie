"""The fixed list of knowledge-base categories (Story 2.2).

This is the single place categories are defined. Articles, the glossary and
retrieval filters (Story 6.5) all use these exact names.
"""

INVESTING_BASICS = "Investing Basics"
STOCKS = "Stocks"
BONDS = "Bonds"
ETFS_AND_MUTUAL_FUNDS = "ETFs & Mutual Funds"
RETIREMENT_AND_TAX_ACCOUNTS = "Retirement & Tax Accounts"
PORTFOLIO_AND_RISK = "Portfolio & Risk"
MARKETS = "Markets"
GOALS_AND_SAVING = "Goals & Saving"

CATEGORIES: tuple[str, ...] = (
    INVESTING_BASICS,
    STOCKS,
    BONDS,
    ETFS_AND_MUTUAL_FUNDS,
    RETIREMENT_AND_TAX_ACCOUNTS,
    PORTFOLIO_AND_RISK,
    MARKETS,
    GOALS_AND_SAVING,
)


def is_category(name: object) -> bool:
    return isinstance(name, str) and name in CATEGORIES
