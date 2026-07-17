Look at this image carefully. Identify the people or objects that are non-compliant based on these violations:
{violations}

The image is {width}x{height} pixels.

IMPORTANT: Do NOT segment individual body parts (arms, legs, hair, armpits separately).
Instead, draw ONE bounding box around each WHOLE PERSON or WHOLE OBJECT that is violating.

For example:
- If a woman is showing exposed arms + legs + hair → draw ONE box around her entire body
- If multiple women are non-compliant → draw ONE box per woman
- Label each box with a summary like "Woman in underwear (exposed body, uncovered hair)"

Return a JSON array where each item has:
- "label": summary of what makes this person/object non-compliant
- "box": [x1, y1, x2, y2] as pixel coordinates (integers, top-left origin)

Rules:
- x1,y1 = top-left corner of the bounding box
- x2,y2 = bottom-right corner
- Values must be 0 to {width} for x, 0 to {height} for y
- ONE box per violating person/entity — not per body part
- Maximum 10 boxes (one per person or distinct violating object)
- Return [] if nothing found
- Make boxes tight around the full person/object

Example: [{{"label": "Woman in revealing clothing (exposed arms, legs, uncovered hair)", "box": [50, 30, 300, 500]}}]
