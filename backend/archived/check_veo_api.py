from google.genai import types
import json

def get_fields(cls):
    return [k for k, v in cls.__annotations__.items()] if hasattr(cls, '__annotations__') else dir(cls)

info = {
    "GenerateVideosSource": get_fields(types.GenerateVideosSource),
    "GenerateVideosConfig": get_fields(types.GenerateVideosConfig)
}

print(json.dumps(info, indent=2))
