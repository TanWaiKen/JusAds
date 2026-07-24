from jusads_generation.agents.video_v3_grid import (
    _build_expressive_voiceover_text,
    _build_music_tags,
    _build_sfx_prompt,
    _grid_dimensions,
    _group_scenes_for_omni,
    _reference_role_label,
    _resolve_scene_count,
    _scene_durations,
)


def test_v3_voiceover_adds_hook_and_cta_delivery_tags():
    text = _build_expressive_voiceover_text([
        {"voiceover": "Wait—what just happened?"},
        {"voiceover": "Fresh chee cheong fun, made to order."},
        {"voiceover": "Come try it tonight."},
    ])

    assert text.startswith("[energetic] [fast]")
    assert "[excited]" in text
    assert "[warmly] [confident]" in text


def test_existing_audio_tags_are_preserved():
    text = _build_expressive_voiceover_text([
        {"voiceover": "[whispers] Look closer."},
    ])

    assert text == "[whispers] Look closer."


def test_action_direction_creates_high_energy_music_tags():
    tags = _build_music_tags([
        {"sound_direction": "fast fight whooshes, then a shock impact"},
    ])

    assert "high-energy" in tags
    assert "percussive" in tags


def test_sfx_prompt_excludes_music_and_requests_reveal_impact():
    prompt = _build_sfx_prompt({
        "description": "A rapid mock fight match-cuts to sauce poured over chee cheong fun.",
        "sound_direction": "glove whoosh, shock hit, plate and sauce Foley",
    })

    assert "no music" in prompt.lower()
    assert "shock-impact" in prompt
    assert "product action" in prompt


def test_reference_filenames_preserve_shop_product_and_character_roles():
    assert _reference_role_label("Shop.png").startswith("SHOP / LOCATION")
    assert _reference_role_label("Product.jpg").startswith("PRODUCT")
    assert _reference_role_label("鸡哥.jpg").startswith("CHARACTER")


def test_fifteen_second_storyboard_uses_complete_two_by_two_grid():
    scene_count = _resolve_scene_count(15)
    durations = _scene_durations(15, scene_count)
    segments = _group_scenes_for_omni([
        {"duration": duration} for duration in durations
    ])

    assert scene_count == 4
    assert _grid_dimensions(scene_count) == (2, 2)
    assert durations == [5, 5, 3, 2]
    assert [sum(scene["duration"] for scene in segment) for segment in segments] == [10, 5]


def test_short_storyboard_uses_minimum_one_by_two_grid():
    scene_count = _resolve_scene_count(5)

    assert scene_count == 2
    assert _grid_dimensions(scene_count) == (2, 1)
    assert _scene_durations(5, scene_count) == [3, 2]
