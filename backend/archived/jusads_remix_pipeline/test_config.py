"""Tests for jusads_remix_pipeline.config module."""

import pytest

from jusads_remix_pipeline.config import (
    CULTURAL_RULES,
    DEFAULT_LANGUAGE,
    ETHNICITY_LANGUAGE_MAP,
    VOICE_MAPPING,
    CulturalRules,
    get_cultural_prompt,
    get_cultural_rules,
    get_language_for_ethnicity,
    get_voice_id,
)


# ─── Voice Mapping Tests ─────────────────────────────────────────────────────


class TestGetVoiceId:
    """Tests for get_voice_id function."""

    def test_malaysia_malay_male(self):
        voice_id = get_voice_id("Malaysia", "Malay", "male")
        assert voice_id != ""
        assert isinstance(voice_id, str)

    def test_malaysia_malay_female(self):
        voice_id = get_voice_id("Malaysia", "Malay", "female")
        assert voice_id != ""
        assert isinstance(voice_id, str)

    def test_malaysia_chinese_male(self):
        voice_id = get_voice_id("Malaysia", "Chinese", "male")
        assert voice_id != ""

    def test_malaysia_chinese_female(self):
        voice_id = get_voice_id("Malaysia", "Chinese", "female")
        assert voice_id != ""

    def test_malaysia_indian_male(self):
        voice_id = get_voice_id("Malaysia", "Indian", "male")
        assert voice_id != ""

    def test_malaysia_indian_female(self):
        voice_id = get_voice_id("Malaysia", "Indian", "female")
        assert voice_id != ""

    def test_singapore_chinese_male(self):
        voice_id = get_voice_id("Singapore", "Chinese", "male")
        assert voice_id != ""

    def test_singapore_chinese_female(self):
        voice_id = get_voice_id("Singapore", "Chinese", "female")
        assert voice_id != ""

    def test_unknown_combination_returns_default(self):
        voice_id = get_voice_id("Thailand", "Thai", "male")
        assert voice_id != ""
        # Should fall back to default

    def test_all_mapping_entries_are_non_empty(self):
        for key, voice_id in VOICE_MAPPING.items():
            assert voice_id != "", f"Empty voice ID for {key}"
            assert isinstance(voice_id, str)


# ─── Cultural Rules Tests ─────────────────────────────────────────────────────


class TestCulturalRules:
    """Tests for cultural rules definitions and functions."""

    def test_malay_rules_exist(self):
        rules = get_cultural_rules("Malay")
        assert rules is not None
        assert rules.ethnicity == "Malay"

    def test_malay_rules_model_ethnicity(self):
        rules = get_cultural_rules("Malay")
        assert rules.model_ethnicity == "Malay"

    def test_malay_rules_hijab_required(self):
        rules = get_cultural_rules("Malay")
        assert rules.hijab_required_for_females is True

    def test_malay_rules_modest_dress(self):
        rules = get_cultural_rules("Malay")
        assert rules.modest_dress_required is True
        assert "elbow" in rules.modest_dress_description.lower()
        assert "knee" in rules.modest_dress_description.lower()

    def test_chinese_rules_exist(self):
        rules = get_cultural_rules("Chinese")
        assert rules is not None
        assert rules.ethnicity == "Chinese"

    def test_chinese_rules_model_ethnicity(self):
        rules = get_cultural_rules("Chinese")
        assert rules.model_ethnicity == "Chinese"

    def test_chinese_rules_no_hijab(self):
        rules = get_cultural_rules("Chinese")
        assert rules.hijab_required_for_females is False

    def test_unknown_ethnicity_returns_none(self):
        rules = get_cultural_rules("Unknown")
        assert rules is None

    def test_malay_prompt_contains_key_elements(self):
        prompt = get_cultural_prompt("Malay")
        assert "Malay" in prompt
        assert "hijab" in prompt.lower()
        assert "elbow" in prompt.lower()
        assert "knee" in prompt.lower()

    def test_chinese_prompt_contains_chinese_models(self):
        prompt = get_cultural_prompt("Chinese")
        assert "Chinese" in prompt

    def test_unknown_ethnicity_prompt_is_empty(self):
        prompt = get_cultural_prompt("Unknown")
        assert prompt == ""


# ─── Ethnicity-to-Language Mapping Tests ──────────────────────────────────────


class TestLanguageMapping:
    """Tests for ethnicity-to-language mapping."""

    def test_chinese_maps_to_mandarin(self):
        assert get_language_for_ethnicity("Chinese") == "Mandarin"

    def test_malay_maps_to_bahasa_malaysia(self):
        assert get_language_for_ethnicity("Malay") == "Bahasa Malaysia"

    def test_none_defaults_to_english(self):
        assert get_language_for_ethnicity(None) == "English"

    def test_unknown_ethnicity_defaults_to_english(self):
        assert get_language_for_ethnicity("Indian") == "English"
        assert get_language_for_ethnicity("Thai") == "English"
        assert get_language_for_ethnicity("") == "English"

    def test_default_language_is_english(self):
        assert DEFAULT_LANGUAGE == "English"
