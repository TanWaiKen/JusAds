import os
import re

# Mapping of corrupted byte sequences to clean ASCII/standard Unicode equivalents
REPLACEMENTS = {
    # Corrupted character variations
    "—": "—",
    "—": "—",
    "→": "→",
    "→": "→",
    "←": "←",
    "←": "←",
    "─": "─",
    "─": "─",
    "┬": "┬",
    "┬": "┬",
    "└": "└",
    "└": "└",
    "┐": "┐",
    "┐": "┐",
    "═": "═",
    "═": "═",
    "═": "═",
    "═‘": "║",
    "═”": "╔",
    "═—": "╗",
    "═š": "╚",
    "═": "╝",
    "'": "'",
    "'": "'",
    """: '"',
    """: '"',
    "—": "—",
    "–": "–",
    # Double corruptions
    "'": "'",
    """: '"',
    "": "",
}

# Specific structural comment simplifications (converting unicode decorations to simple ASCII line-rules)
UNICODE_BOX_PATTERN = re.compile(r"[─┐┐┬└═║╔╗╚╝─┼═─→┐┐└┬┴┤├╪╫╧╨╥╟╢]+", re.UNICODE)

def clean_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, "r", encoding="cp1252") as f:
                content = f.read()
        except Exception as e:
            print(f"Skipping {filepath} due to read error: {e}")
            return

    original_content = content
    
    # 1. Apply string replacements
    for bad, good in REPLACEMENTS.items():
        content = content.replace(bad, good)
        
    # 2. Convert decorative box-drawing lines in comments to simple ASCII dashes/equals
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if line.strip().startswith("#"):
            # Replace box-drawing line-rules with standard ASCII equivalents
            clean_line = line
            # E.g., change "# --- Node" to "# --- Node"
            clean_line = clean_line.replace("─", "-").replace("═", "=").replace("→", "->").replace("â", "")
            # Clean up residual artifacts
            lines[idx] = clean_line

    content = "\n".join(lines) + ("\n" if content.endswith("\n") else "")
    
    if content != original_content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Cleaned: {filepath}")

def main():
    backend_dir = r"c:\Users\tanwa\OneDrive\TWK developer\Documents\Langhub-main\backend"
    for root, dirs, files in os.walk(backend_dir):
        # Skip pycache and virtual environments
        if "__pycache__" in root or ".venv" in root or ".pytest_cache" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                clean_file(filepath)

if __name__ == "__main__":
    main()
