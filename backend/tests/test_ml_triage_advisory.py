from jusads_compliance.ml_triage_advisory import classify_text


def test_demo_triage_is_explainable_and_non_authoritative():
    result = classify_text("Guaranteed miracle cure with instant results")

    assert result.label == "higher_review_priority"
    assert result.risk_score > 0.5
    assert result.advisory_only is True
    assert result.synthetic_demo_model is True
    assert result.top_features[0]["feature"] in {"cure", "guaranteed", "miracle"}


def test_demo_triage_identifies_lower_priority_copy():
    result = classify_text("Read ingredients and terms before ordering")

    assert result.label == "lower_review_priority"
    assert result.risk_score < 0.5
    assert 0 <= result.confidence <= 1
