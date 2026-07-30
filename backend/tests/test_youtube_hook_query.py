from jusads_trends.youtube_hook_cache import normalise_hook_query


def test_query_requires_a_product_category_term() -> None:
    assert normalise_hook_query("Malaysia viral hooks", "Skincare products") is None


def test_query_accepts_a_short_category_led_query() -> None:
    assert normalise_hook_query("Skincare Malaysia hook", "Skincare products") == "Skincare Malaysia hook"


def test_query_rejects_overlong_llm_output() -> None:
    assert normalise_hook_query("Skincare Malaysia viral beauty product hook", "Skincare") is None
