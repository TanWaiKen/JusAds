Analyze the user's advertisement request:
"{user_message}"

Decide which media outputs the user is EXPLICITLY asking you to CREATE/GENERATE.

IMPORTANT RULES:
- The user MUST explicitly mention or imply they want you to GENERATE/CREATE/MAKE a specific media type.
- Simply mentioning a concept (e.g., "my coffee shop") is NOT a request to generate anything.
- The message MUST contain action words (generate, create, make, design, produce, write) OR explicit media type words (image, video, text, audio, poster, banner, clip, reel, caption, voiceover).
- If the user is just chatting, asking questions, or describing something without requesting generation, return [].
- IMPORTANT: If the user says "yes", "continue", "do it", "go ahead", "generate it", "make it", "proceed" — these are CONFIRMATIONS of a previous plan. In that case, look for media type context in the same message or return ["text", "image"] as a default confirmation response.

Media types:
1. "text" — ONLY if they ask for: ad copy, captions, headlines, taglines, slogans, descriptions
2. "image" — ONLY if they ask for: ad image, poster, banner, visual, graphic, picture, photo
3. "audio" — ONLY if they ask for: radio ad, voiceover, sound, jingle, podcast ad, audio, TTS
4. "video" — ONLY if they ask for: video ad, clip, reel, TikTok video, footage, video content

Return ONLY a JSON list. Examples:
- "Generate a TikTok video ad for my coffee" → ["video"]
- "Create image and text ads for shoes" → ["text", "image"]
- "I want to promote my restaurant" → [] (no specific media type requested)
- "Make me a poster" → ["image"]
- "Yes, generate the audio" → ["audio"]
- "Continue with the audio ad" → ["audio"]
- "Hi, how are you?" → []

If nothing matches, return: []
Do not return any other text.
