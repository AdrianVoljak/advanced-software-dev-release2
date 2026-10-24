
import json
import os
import re
import sys
from pathlib import Path


AI_SERVICES_DIR = Path(__file__).resolve().parents[2]

if str(AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_DIR))

from shared_llm.ollama_client import OllamaClient  # noqa: E402


BASE_DIR = Path(__file__).resolve().parents[1]
PROMPT_PATH = BASE_DIR / "prompts" / "reviewer_prompt.txt"

OLLAMA_REVIEW_MODEL = os.getenv(
    "OLLAMA_REVIEW_MODEL",
    "llama3.1:8b",
)


def load_prompt():
    """Load the Reviewer Agent's instructions."""
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def review_is_complete(review):
    """Validate the required review sections and their contents."""

    if not isinstance(review, str) or not review.strip():
        return False

    headings = (
        "Risk",
        "Correction",
        "Retest",
        "Recommendation",
    )

    positions = []

    for heading in headings:
        pattern = (
            rf"(?im)^[ \t]*(?:\#{{1,6}}[ \t]*)?"
            rf"(?:\*\*)?{heading}:(?:\*\*)?[ \t]*"
        )

        match = re.search(pattern, review)

        if match is None:
            return False

        positions.append((match.start(), match.end()))

    # Ensure the four sections appear in the required order.
    if positions != sorted(positions):
        return False

    # Ensure each section contains meaningful content.
    for index, (_, content_start) in enumerate(positions):
        content_end = (
            positions[index + 1][0]
            if index + 1 < len(positions)
            else len(review)
        )

        section_content = review[content_start:content_end].strip()

        if not section_content:
            return False

    return True


def review_workflow(
    user_request,
    planner_result,
    worker_result,
    evidence,
):
    """
    Independently review the Worker's output against
    the Planner's instructions and original evidence.
    """

    if not isinstance(user_request, str) or not user_request.strip():
        raise ValueError("User request must be a non-empty string")

    if not isinstance(planner_result, dict):
        raise ValueError("Planner result must be a dictionary")

    if not isinstance(worker_result, dict):
        raise ValueError("Worker result must be a dictionary")

    if not isinstance(evidence, (dict, list)):
        raise ValueError("Evidence must be a dictionary or list")

    plan = planner_result.get("plan", "")
    worker_output = worker_result.get("output", "")

    if not isinstance(plan, str) or not plan.strip():
        raise ValueError("Planner result does not contain a valid plan")

    if not isinstance(worker_output, str) or not worker_output.strip():
        raise ValueError("Worker result does not contain a valid output")

    client = OllamaClient()

    prompt = f"""
{load_prompt()}

Original User Request:
{user_request}

Planner Instructions:
{plan}

Worker Output:
{worker_output}

ORIGINAL APPLICATION EVIDENCE:
{json.dumps(evidence, indent=2)}

IMPORTANT:
Review the Worker against the original application evidence.
Do not treat Planner instructions or Worker output as evidence.
Identify unsupported claims, missing information and contradictions.
Do not make the final human approval decision.
"""

    response = client.generate(
        prompt=prompt,
        model=OLLAMA_REVIEW_MODEL,
        timeout=180,
    )

    if not review_is_complete(response):
        raise RuntimeError(
            "Reviewer Agent returned an incomplete or invalid review"
        )

    return {
        "status": "success",
        "agent": "reviewer_agent",
        "model": OLLAMA_REVIEW_MODEL,
        "review": response,
        "human_approval_required": True,
    }
