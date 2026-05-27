"""Local CLI runner for the content compliance pipeline.

Provides a command-line interface for testing the compliance pipeline locally,
accepting the same input schema as the Lambda handler and returning the same
ComplianceResult output schema.

Supports:
- Text content passed directly as an argument
- Image content read from a local file path (base64-encoded automatically)
- Video content referenced by local file path

Requirements: 9.1, 9.2, 9.3, 9.4, 9.6
"""

import argparse
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the culture_compliance directory
load_dotenv(Path(__file__).resolve().parent / ".env")

# Configure logging to stdout for intermediate step visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# --- Required Environment Variables ---

REQUIRED_ENV_VARS = {
    "AWS_ACCESS_KEY_ID": "AWS access key for Bedrock API calls",
    "AWS_SECRET_ACCESS_KEY": "AWS secret key for Bedrock API calls",
    "QDRANT_URL": "Qdrant Cloud cluster URL for guideline retrieval",
    "QDRANT_API_KEY": "Qdrant API key for authentication",
}


def validate_environment() -> list[str]:
    """Validate that all required environment variables are set.

    Returns:
        A list of error messages for missing variables. Empty if all are set.
    """
    missing = []
    for var_name, description in REQUIRED_ENV_VARS.items():
        value = os.environ.get(var_name, "").strip()
        if not value:
            missing.append(f"  - {var_name}: {description}")
    return missing


def read_image_content(file_path: str) -> str:
    """Read an image file and return its base64-encoded content.

    Args:
        file_path: Path to the image file on the local filesystem.

    Returns:
        Base64-encoded string of the image bytes.

    Raises:
        FileNotFoundError: If the file does not exist.
        IOError: If the file cannot be read.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {file_path}")
    if not path.is_file():
        raise IOError(f"Path is not a file: {file_path}")

    logger.info("Reading image file: %s (%.2f KB)", path.name, path.stat().st_size / 1024)
    image_bytes = path.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    logger.info("Image base64-encoded: %d characters", len(encoded))
    return encoded


def read_video_path(file_path: str) -> str:
    """Validate a video file path exists and return it.

    For local execution, video content is passed as the file path directly
    (not base64-encoded) since the video pipeline reads from the filesystem.

    Args:
        file_path: Path to the video file on the local filesystem.

    Returns:
        The validated file path string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")
    if not path.is_file():
        raise IOError(f"Path is not a file: {file_path}")

    logger.info("Video file validated: %s (%.2f MB)", path.name, path.stat().st_size / (1024 * 1024))
    return str(path.resolve())


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="compliance-cli",
        description=(
            "Local CLI runner for the content compliance pipeline. "
            "Evaluates content against Malaysia (MCMC) or Singapore (IMDA/ASAS) "
            "regulatory guidelines."
        ),
    )
    parser.add_argument(
        "content",
        help=(
            "Content to evaluate. For text: the text string directly. "
            "For image: path to an image file (JPEG, PNG, WebP). "
            "For video: path to a video file (MP4, MOV, WebM)."
        ),
    )
    parser.add_argument(
        "--content-type",
        choices=["text", "image", "video"],
        default="text",
        help="Type of content being submitted (default: text)",
    )
    parser.add_argument(
        "--market",
        choices=["malaysia", "singapore"],
        default="malaysia",
        help="Target regulatory market (default: malaysia)",
    )
    parser.add_argument(
        "--ethnicity",
        choices=["malay", "chinese", "indian", "all"],
        default="all",
        help="Target ethnic audience for cultural guideline filtering (default: all)",
    )
    parser.add_argument(
        "--age-group",
        choices=["all_ages", "adults_only", "children"],
        default="all_ages",
        help="Target age group for cultural guideline filtering (default: all_ages)",
    )
    return parser


def main() -> None:
    """CLI entry point for local pipeline testing.

    Parses arguments, validates environment, prepares the content submission,
    invokes the pipeline, and prints the result as JSON to stdout.
    """
    parser = build_parser()
    args = parser.parse_args()

    # --- Validate environment variables ---
    logger.info("Validating environment variables...")
    missing_vars = validate_environment()
    if missing_vars:
        print(
            "\n❌ Missing required environment variables:\n"
            + "\n".join(missing_vars)
            + "\n\nPlease set these variables in your environment or .env file.",
            file=sys.stderr,
        )
        sys.exit(1)
    logger.info("All required environment variables are set.")

    # --- Prepare content ---
    content_type = args.content_type
    content = args.content

    try:
        if content_type == "image":
            logger.info("Content type: image — reading and encoding file...")
            content = read_image_content(content)
        elif content_type == "video":
            logger.info("Content type: video — validating file path...")
            content = read_video_path(content)
        else:
            logger.info("Content type: text — using content directly.")
    except (FileNotFoundError, IOError) as e:
        print(f"\n❌ File error: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Build submission and run pipeline ---
    # Import here to avoid import errors if env vars are missing
    from culture_compliance.models.schemas import ContentSubmission, ContentType, Market
    from culture_compliance.orchestrator import run_pipeline

    logger.info("=" * 60)
    logger.info("Starting compliance pipeline")
    logger.info("  Content type: %s", content_type)
    logger.info("  Market: %s", args.market)
    logger.info("  Ethnicity: %s", args.ethnicity)
    logger.info("  Age group: %s", args.age_group)
    if content_type == "text":
        logger.info("  Content preview: %.100s...", content)
    logger.info("=" * 60)

    start_time = time.time()

    try:
        submission = ContentSubmission(
            content=content,
            content_type=ContentType(content_type),
            market=Market(args.market),
            target_ethnicity=args.ethnicity,
            target_age_group=args.age_group,
        )

        result = run_pipeline(submission)
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error("Pipeline failed after %d ms: %s", elapsed_ms, str(e))
        error_response = {
            "error_type": "pipeline_error",
            "message": str(e),
            "details": {"elapsed_ms": elapsed_ms},
        }
        print(json.dumps(error_response, indent=2, ensure_ascii=False))
        sys.exit(1)

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info("=" * 60)
    logger.info("Pipeline completed in %d ms", elapsed_ms)
    logger.info("=" * 60)

    # --- Output result ---
    if isinstance(result, dict):
        output = result
    else:
        output = result.model_dump() if hasattr(result, "model_dump") else vars(result)

    print("\n" + json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
