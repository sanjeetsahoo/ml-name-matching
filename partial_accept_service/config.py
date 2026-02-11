from pydantic_settings import BaseSettings, SettingsConfigDict


class DecisionSettings(BaseSettings):
    """Runtime-tunable settings for partial-accept automation."""

    model_config = SettingsConfigDict(env_prefix="PA_", extra="ignore")

    auto_accept_threshold: float = 0.86
    auto_reject_threshold: float = 0.33
    max_ml_score_for_auto_reject: float = 0.56
    strong_model_accept_threshold: float = 0.91

    model_weight: float = 0.45
    token_sort_weight: float = 0.25
    jaccard_weight: float = 0.17
    containment_weight: float = 0.09
    initials_bonus: float = 0.06
    exact_bonus: float = 0.08
    hard_mismatch_penalty: float = 0.20
