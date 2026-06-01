"""Unit tests for audio_remediator.select_voice().

Tests voice selection logic including supported market/ethnicity/gender
combinations, case-insensitive lookup, default gender, and fallback behavior.

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""

import pytest

from backend.jusads_video_compliance.audio_remediator import (
    LANGUAGE_CODE_MAP,
    VOICE_MAP,
    select_voice,
)


class TestSelectVoiceMalaysiaMarket:
    """Test voice selection for Malaysia market (Req 4.1)."""

    def test_malaysia_malay_male(self):
        vc = select_voice("malaysia", "malay", "all_ages", "ms", "male")
        assert vc.voice_id != ""
        assert vc.language_code == "ms"
        assert vc.market == "malaysia"
        assert vc.ethnicity == "malay"
        assert vc.gender == "male"

    def test_malaysia_malay_female(self):
        vc = select_voice("malaysia", "malay", "all_ages", "ms", "female")
        assert vc.voice_id != ""
        assert vc.language_code == "ms"
        assert vc.gender == "female"

    def test_malaysia_chinese_male(self):
        vc = select_voice("malaysia", "chinese", "all_ages", "zh", "male")
        assert vc.voice_id != ""
        assert vc.language_code == "zh"
        assert vc.ethnicity == "chinese"

    def test_malaysia_chinese_female(self):
        vc = select_voice("malaysia", "chinese", "all_ages", "zh", "female")
        assert vc.voice_id != ""
        assert vc.language_code == "zh"

    def test_malaysia_indian_male(self):
        vc = select_voice("malaysia", "indian", "all_ages", "en", "male")
        assert vc.voice_id != ""
        assert vc.language_code == "en"
        assert vc.ethnicity == "indian"

    def test_malaysia_indian_female(self):
        vc = select_voice("malaysia", "indian", "all_ages", "en", "female")
        assert vc.voice_id != ""
        assert vc.language_code == "en"


class TestSelectVoiceSingaporeMarket:
    """Test voice selection for Singapore market (Req 4.2)."""

    def test_singapore_english_male(self):
        vc = select_voice("singapore", "english", "all_ages", "en", "male")
        assert vc.voice_id != ""
        assert vc.language_code == "en"
        assert vc.market == "singapore"
        assert vc.ethnicity == "english"
        assert vc.gender == "male"

    def test_singapore_english_female(self):
        vc = select_voice("singapore", "english", "all_ages", "en", "female")
        assert vc.voice_id != ""
        assert vc.language_code == "en"

    def test_singapore_chinese_male(self):
        vc = select_voice("singapore", "chinese", "all_ages", "zh", "male")
        assert vc.voice_id != ""
        assert vc.language_code == "zh"

    def test_singapore_chinese_female(self):
        vc = select_voice("singapore", "chinese", "all_ages", "zh", "female")
        assert vc.voice_id != ""
        assert vc.language_code == "zh"


class TestSelectVoiceLanguageCodes:
    """Test correct language code mapping (Req 4.4)."""

    def test_malaysia_malay_maps_to_ms(self):
        vc = select_voice("malaysia", "malay", "all_ages", "ms", "female")
        assert vc.language_code == "ms"

    def test_malaysia_chinese_maps_to_zh(self):
        vc = select_voice("malaysia", "chinese", "all_ages", "zh", "female")
        assert vc.language_code == "zh"

    def test_malaysia_indian_maps_to_en(self):
        vc = select_voice("malaysia", "indian", "all_ages", "en", "female")
        assert vc.language_code == "en"

    def test_singapore_english_maps_to_en(self):
        vc = select_voice("singapore", "english", "all_ages", "en", "female")
        assert vc.language_code == "en"

    def test_singapore_chinese_maps_to_zh(self):
        vc = select_voice("singapore", "chinese", "all_ages", "zh", "female")
        assert vc.language_code == "zh"


class TestSelectVoiceCaseInsensitive:
    """Test case-insensitive lookup (Req 4.7)."""

    def test_uppercase_market(self):
        vc = select_voice("MALAYSIA", "malay", "all_ages", "ms", "female")
        assert vc.voice_id != ""
        assert vc.market == "malaysia"

    def test_uppercase_ethnicity(self):
        vc = select_voice("malaysia", "MALAY", "all_ages", "ms", "female")
        assert vc.voice_id != ""
        assert vc.ethnicity == "malay"

    def test_uppercase_gender(self):
        vc = select_voice("malaysia", "malay", "all_ages", "ms", "MALE")
        assert vc.voice_id != ""
        assert vc.gender == "male"

    def test_mixed_case(self):
        vc = select_voice("Singapore", "Chinese", "all_ages", "zh", "Male")
        assert vc.voice_id != ""
        assert vc.market == "singapore"
        assert vc.ethnicity == "chinese"
        assert vc.gender == "male"

    def test_all_uppercase(self):
        vc = select_voice("SINGAPORE", "ENGLISH", "ALL_AGES", "EN", "FEMALE")
        assert vc.voice_id != ""
        assert vc.language_code == "en"


class TestSelectVoiceDefaultGender:
    """Test default gender behavior (Req 4.6)."""

    def test_default_gender_is_female(self):
        vc = select_voice("malaysia", "malay", "all_ages", "ms")
        assert vc.gender == "female"

    def test_explicit_female_same_as_default(self):
        vc_default = select_voice("malaysia", "malay", "all_ages", "ms")
        vc_explicit = select_voice("malaysia", "malay", "all_ages", "ms", "female")
        assert vc_default.voice_id == vc_explicit.voice_id


class TestSelectVoiceFallback:
    """Test fallback to default voice (Req 4.5)."""

    def test_unknown_market_falls_back(self):
        vc = select_voice("unknown", "malay", "all_ages", "ms", "female")
        assert vc.voice_id != ""
        assert vc.market == "malaysia"
        assert vc.ethnicity == "malay"
        assert vc.gender == "female"

    def test_unknown_ethnicity_falls_back(self):
        vc = select_voice("malaysia", "unknown", "all_ages", "ms", "female")
        assert vc.voice_id != ""
        assert vc.market == "malaysia"
        assert vc.ethnicity == "malay"

    def test_completely_invalid_falls_back(self):
        vc = select_voice("xyz", "abc", "all_ages", "xx", "other")
        assert vc.voice_id != ""
        assert vc.market == "malaysia"
        assert vc.ethnicity == "malay"
        assert vc.gender == "female"

    def test_fallback_returns_valid_voice_config(self):
        vc = select_voice("invalid", "invalid", "all_ages", "xx", "male")
        assert vc.voice_id != ""
        assert vc.language_code == "ms"


class TestVoiceMapCompleteness:
    """Test that VOICE_MAP and LANGUAGE_CODE_MAP are complete."""

    def test_voice_map_has_10_entries(self):
        assert len(VOICE_MAP) == 10

    def test_language_code_map_has_5_entries(self):
        assert len(LANGUAGE_CODE_MAP) == 5

    def test_all_voice_ids_are_non_empty(self):
        for key, voice_id in VOICE_MAP.items():
            assert voice_id != "", f"Empty voice_id for {key}"
