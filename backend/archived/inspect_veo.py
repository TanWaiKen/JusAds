from google.genai import types
import json

def get_fields(cls):
    if hasattr(cls, '__annotations__'):
        return {k: str(v) for k, v in cls.__annotations__.items()}
    return dir(cls)

try:
    info = {
        "GenerateVideosSource": get_fields(types.GenerateVideosSource) if hasattr(types, 'GenerateVideosSource') else "Not found",
        "GenerateVideosConfig": get_fields(types.GenerateVideosConfig) if hasattr(types, 'GenerateVideosConfig') else "Not found",
    }
    
    with open("backend/veo_types.json", "w") as f:
        json.dump(info, indent=2, fp=f)
except Exception as e:
    with open("backend/veo_types.json", "w") as f:
        f.write(str(e))
