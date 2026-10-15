"""UAT-LIMIT-01: API limit behavior (docs/uat-script.md §7)."""


def test_uat_limit_alpha_vantage_daily_cap_uses_sample_data(stack):
    stack.alpha.limit_after = 0
    response = stack.ask("How is VTI doing?")
    assert response.answer == "VTI closed at $377.00."
    assert [label.text for label in response.labels] == ["Sample data · not real prices"]
    requests = len(stack.alpha.calls)
    stack.ask("How is SPY doing?")
    assert len(stack.alpha.calls) == requests


def test_uat_limit_serpapi_out_of_searches_uses_sample_headlines(stack):
    stack.serp.out_of_searches = True
    response = stack.ask("What's in the financial news today?")
    assert response.answer.startswith("According to Finnie sample data, Sample:")
    assert [label.text for label in response.labels] == ["Sample data · not real headlines"]
