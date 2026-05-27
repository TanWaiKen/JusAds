"""Quick setup test for JusAds Text Compliance

Verifies that:
1. Environment variables are set
2. Qdrant connection works
3. Google Gemini API is accessible
4. Collections exist in Qdrant

Run:
    python -m jusads_text_compliance.test_setup
"""

import sys

from .config import (
    GOOGLE_API_KEY,
    QDRANT_API_KEY,
    QDRANT_URL,
    REGULATORY_COLLECTION_MALAYSIA,
    CULTURAL_COLLECTION,
    PERSONA_COLLECTION,
)


def test_environment():
    """Check that required environment variables are set."""
    print("=" * 70)
    print("  STEP 1: Checking Environment Variables")
    print("=" * 70)

    issues = []

    if not QDRANT_URL:
        issues.append("[X] QDRANT_URL not set")
    else:
        print(f"[OK] QDRANT_URL: {QDRANT_URL}")

    if not QDRANT_API_KEY:
        issues.append("[X] QDRANT_API_KEY not set")
    else:
        print(f"[OK] QDRANT_API_KEY: {QDRANT_API_KEY[:10]}***")

    if not GOOGLE_API_KEY:
        issues.append("[X] GOOGLE_API_KEY not set")
    else:
        print(f"[OK] GOOGLE_API_KEY: {GOOGLE_API_KEY[:10]}***")

    if issues:
        print("\n" + "\n".join(issues))
        print("\nPlease set missing environment variables in backend/.env")
        return False

    print("\n[OK] All environment variables are set\n")
    return True


def test_qdrant_connection():
    """Test connection to Qdrant and check collections."""
    print("=" * 70)
    print("  STEP 2: Testing Qdrant Connection")
    print("=" * 70)

    try:
        from .qdrant_client import JusAdsQdrantClient

        client = JusAdsQdrantClient()
        print("[OK] Connected to Qdrant")

        # Check collections
        collections = client.client.get_collections().collections
        collection_names = [c.name for c in collections]

        print(f"\nFound {len(collection_names)} collections:")
        for name in collection_names:
            print(f"  - {name}")

        # Verify required collections exist
        required = [
            REGULATORY_COLLECTION_MALAYSIA,
            CULTURAL_COLLECTION,
            PERSONA_COLLECTION,
        ]

        missing = [c for c in required if c not in collection_names]
        if missing:
            print(f"\n[X] Missing required collections: {missing}")
            print("\nRun these commands to create them:")
            print("  cd backend/")
            print("  python -m culture_compliance.ingest --market malaysia")
            print("  python -m culture_compliance.ingest_cultural")
            print("  python -m culture_compliance.ingest_personas")
            return False

        print("\n[OK] All required collections exist\n")
        return True

    except Exception as e:
        print(f"[X] Qdrant connection failed: {e}")
        return False


def test_gemini_api():
    """Test Google Gemini API access."""
    print("=" * 70)
    print("  STEP 3: Testing Google Gemini API")
    print("=" * 70)

    try:
        from google import genai

        client = genai.Client(api_key=GOOGLE_API_KEY)

        # Test embedding
        from .embeddings import embed_text

        embedding = embed_text("test")
        if embedding and len(embedding) == 768:
            print(f"[OK] Text embedding works (768-dim vector)")
        else:
            print(f"[X] Text embedding returned unexpected result")
            return False

        # Test LLM
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents="Say 'Hello'",
        )
        if response and response.text:
            print(f"[OK] LLM works (response: {response.text[:50]}...)")
        else:
            print("[X] LLM returned no response")
            return False

        print("\n[OK] Google Gemini API is working\n")
        return True

    except Exception as e:
        print(f"[X] Gemini API test failed: {e}")
        return False


def main():
    """Run all setup tests."""
    print("\n")
    print("=" * 70)
    print("  JusAds Text Compliance - Setup Test")
    print("=" * 70)
    print()

    # Run tests
    env_ok = test_environment()
    if not env_ok:
        sys.exit(1)

    qdrant_ok = test_qdrant_connection()
    if not qdrant_ok:
        sys.exit(1)

    gemini_ok = test_gemini_api()
    if not gemini_ok:
        sys.exit(1)

    # All tests passed
    print("=" * 70)
    print("  [OK] SETUP TEST PASSED")
    print("=" * 70)
    print()
    print("You're ready to use JusAds Text Compliance!")
    print()
    print("Try this command:")
    print('  python -m jusads_text_compliance.cli --text "Your ad copy here"')
    print()


if __name__ == "__main__":
    main()
