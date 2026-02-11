from app.resolver import resolve


def test_exact_normalized_match():
    r = resolve("  Ravi   Kumar ", "RAVI KUMAR")
    assert r.decision == "auto_accept"
    assert "exact_normalized_match" in r.reasons


def test_initials_compatible():
    r = resolve("RAVI KUMAR", "RAVI K")
    assert r.decision == "auto_accept"


def test_token_subset_containment():
    r = resolve("RAHUL KUMAR", "RAHUL KUMAR SINGH")
    assert r.decision == "auto_accept"


def test_company_suffix_normalization():
    r = resolve("XYZ PVT LTD", "XYZ PRIVATE LIMITED", entity_type="company")
    assert r.decision == "auto_accept"


def test_insufficient_tokens_goes_to_ops():
    r = resolve("A", "A", ml_score=0.7)
    assert r.decision == "send_to_ops"
