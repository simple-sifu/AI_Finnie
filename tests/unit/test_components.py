"""Web UI helpers (Story 7.5 / chat rendering)."""

from src.web_app.components import escape_markdown_dollars


def test_escape_markdown_dollars_preserves_compound_interest_example():
    text = (
        "For example, if you invest $1,000 at a 7% annual return, after one year you'll have $1,070. "
        "In the second year, you earn interest on the new total ($1,070), which would be about $1,145."
    )
    escaped = escape_markdown_dollars(text)
    assert escaped.count("\\$") == 4
    assert "invest \\$1,000" in escaped
