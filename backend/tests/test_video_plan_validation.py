from jusads_generation.video_plan_validation import is_usable_v3_plan


def _plan(**overrides):
    plan = {
        "pipeline_version": "v3_grid",
        "scenes": [{}, {}],
        "grid_url": "https://cdn.example.com/grid.png",
        "frame_urls": [
            "https://cdn.example.com/frame-01.png",
            "https://cdn.example.com/frame-02.png",
        ],
    }
    plan.update(overrides)
    return plan


def test_accepts_plan_with_grid_and_one_frame_per_scene():
    assert is_usable_v3_plan(_plan())


def test_rejects_plan_without_scene_grid():
    assert not is_usable_v3_plan(_plan(grid_url=""))


def test_rejects_plan_with_missing_scene_frames():
    assert not is_usable_v3_plan(
        _plan(frame_urls=["https://cdn.example.com/frame-01.png"])
    )


def test_rejects_non_v3_or_empty_plan():
    assert not is_usable_v3_plan(None)
    assert not is_usable_v3_plan(_plan(pipeline_version="v2"))
    assert not is_usable_v3_plan(_plan(scenes=[]))
