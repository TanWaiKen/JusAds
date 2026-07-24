from datetime import date

from jusads_trends import daily_idea


def _inputs(*, events=None, signals=None, trends=None):
    return {
        "events": events or [],
        "signals": signals or [],
        "trends": trends or [],
    }


def test_event_fallback_uses_verified_date_and_name():
    idea = daily_idea._fallback_idea(
        _inputs(
            events=[
                {
                    "name": "Verified Market Day",
                    "start_date": "2026-07-27",
                }
            ]
        ),
        today=date(2026, 7, 24),
        market="malaysia",
    )

    assert idea["event_name"] == "Verified Market Day"
    assert "3 days" in idea["why_today"]
    assert idea["confidence"] == "event-backed"


def test_malformed_event_date_falls_through_to_signal():
    idea = daily_idea._fallback_idea(
        _inputs(
            events=[{"name": "Bad Date Event", "start_date": "soon"}],
            signals=[
                {
                    "title": "Fast reveal",
                    "why_trending": "Supported by saved evidence.",
                    "suggested_adaptation": "Reveal the product after a visual interruption.",
                    "how_it_works": "Interrupt, pivot, demonstrate.",
                    "confidence": "medium",
                }
            ],
        ),
        today=date(2026, 7, 24),
        market="malaysia",
    )

    assert idea["title"] == "Fast reveal"
    assert idea["event_name"] is None


def test_local_cache_round_trip(tmp_path, monkeypatch):
    cache_path = tmp_path / "daily-ideas.json"
    monkeypatch.setattr(daily_idea, "_CACHE_PATH", cache_path)
    payload = {"idea_date": "2026-07-24", "title": "Stable idea"}

    daily_idea._write_local_cache("2026-07-24:malaysia", payload)

    assert daily_idea._read_local_cache("2026-07-24:malaysia") == payload


def test_out_of_season_aidilfitri_event_is_rejected():
    assert not daily_idea._event_date_is_plausible(
        {
            "name": "Hari Raya Aidilfitri Festive Bazars",
            "start_date": "2026-07-27",
        },
        "malaysia",
    )


def test_out_of_season_cached_aidilfitri_idea_is_rejected():
    assert not daily_idea._cached_payload_is_plausible(
        {
            "title": "Hari Raya Aidilfitri Festive Bazars: preparation moment",
            "event_name": "Hari Raya Aidilfitri Festive Bazars",
        },
        "2026-07-24",
        "malaysia",
    )
