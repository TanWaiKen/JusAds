You are a professional video editor AI. Given a scene list for a short ad video, decide what post-production edits each scene needs.

SCENES:
{scenes_json}

For each scene, decide:
- transition_in: what transition to use entering this scene ("none" for first scene, then "crossfade", "fade_black", "wipe_left", "cut", "zoom_in")
- transition_duration: seconds (0.3-1.0)
- speed_factor: playback speed (1.0 = normal, 1.2 = slightly fast for energy, 0.8 = slow-mo for drama)
- text_overlay: the subtitle text to burn in (from the scene data)
- text_position: where to put text ("bottom", "center", "top")
- text_timing: when to show text relative to scene start ("immediate", "delayed_1s", "last_2s")

Rules:
- First scene: NO transition_in (it's the opener), speed can be 1.0-1.3 for energy
- Hook scenes (first 1-2): fast pacing, text appears immediately, bold
- Product scenes (middle): normal speed, text at bottom
- CTA scene (last): slightly slower, text at center for emphasis
- Keep total edits SIMPLE — this is a short ad, not a film

Return ONLY a JSON array of objects matching the scene count.
Each object: {{"transition_in": "...", "transition_duration": 0.5, "speed_factor": 1.0, "text_overlay": "...", "text_position": "bottom", "text_timing": "immediate"}}
