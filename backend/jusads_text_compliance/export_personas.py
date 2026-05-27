"""Export personas from Qdrant to JSON files for easy spot-checking.

Creates human-readable JSON files in the personas/ directory organized by market.

Usage:
    python -m jusads_text_compliance.export_personas
"""

import json
import logging
from pathlib import Path

from .qdrant_client import JusAdsQdrantClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def export_personas_to_json():
    """Export all personas from Qdrant to JSON files."""
    client = JusAdsQdrantClient()
    personas_dir = Path(__file__).parent / "personas"
    personas_dir.mkdir(exist_ok=True)

    markets = ["malaysia", "singapore"]
    ethnicities = ["malay", "chinese", "indian"]

    all_personas = {}

    for market in markets:
        all_personas[market] = {}

        for ethnicity in ethnicities:
            logger.info("Fetching persona: %s / %s", market, ethnicity)
            persona_text = client.get_persona(market=market, ethnicity=ethnicity)

            if persona_text:
                all_personas[market][ethnicity] = persona_text
                logger.info("✓ Found persona for %s / %s", market, ethnicity)
            else:
                logger.warning("✗ No persona found for %s / %s", market, ethnicity)

    # Save to JSON file
    output_file = personas_dir / "all_personas.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_personas, f, indent=2, ensure_ascii=False)

    logger.info("Personas exported to: %s", output_file)

    # Also create individual files per market
    for market, personas in all_personas.items():
        market_file = personas_dir / f"{market}_personas.json"
        with open(market_file, "w", encoding="utf-8") as f:
            json.dump(personas, f, indent=2, ensure_ascii=False)
        logger.info("Market personas exported to: %s", market_file)

    print("\n✓ Personas exported successfully!")
    print(f"  Location: {personas_dir.absolute()}")
    print(f"  Files: all_personas.json, malaysia_personas.json, singapore_personas.json")


if __name__ == "__main__":
    export_personas_to_json()
