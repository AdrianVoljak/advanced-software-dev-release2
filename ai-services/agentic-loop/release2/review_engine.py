
"""Reliable, evidence-based review engine for Release 2.

Deterministic results are authoritative. Ollama provides optional
advisory suggestions but cannot override validation findings.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

from llm_client import OLLAMA_BASE_URL, OLLAMA_MODEL


BASE_DIR = Path(__file__).resolve().parents[1]
REPORTS_DIR = BASE_DIR / "reports" / "release2"

VALID_MODES = {"multi_agent", "testing", "deployment"}

CHECK_LABELS = {
    "ruff": "Ruff linting",
    "detect_secrets": "detect-secrets scanning",  # pragma: allowlist secret
    "pip_audit": "pip-audit dependency scanning",
    "pytest": "pytest automated tests",
    "build": "Application build",
    "deployment": "Cloud deployment",
    "health": "Application health",
    "security": "Security validation",
    "planner_present": "Planner execution",
    "worker_present": "Worker execution",
    "reviewer_present": "Reviewer execution",
    "human_review_present": "Human review",
    "audit_events_complete": "Required audit events",
    "correct_event_order": "Audit event ordering",
    "final_status_matches_decision": "Final status and human decision",
}

logger = logging.getLogger(__name__)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def get_validation(evidence):
    """Extract deterministic validation from supplied review evidence."""
    if not isinstance(evidence, dict):
        raise ValueError("Review evidence must be a JSON object")

    validation = evidence.get("validation")

    if not isinstance(validation, dict):
        raise ValueError("Evidence must include deterministic validation")

    checks = validation.get("checks")

    if not isinstance(checks, dict) or not checks:
        raise ValueError("Validation must contain check results")

    if not all(isinstance(value, bool) for value in checks.values()):
        raise ValueError("Validation check values must be boolean")

    expected_status = "pass" if all(checks.values()) else "fail"

    if validation.get("status") != expected_status:
        raise ValueError(
            "Validation status contradicts its check results"
        )

    return validation


def status_label(passed):
    return "PASS" if passed else "FAIL"



def describe_check(name, passed, validation, mode):
    """Build a finding from deterministic validation and supplied evidence."""
    label = CHECK_LABELS.get(
        name,
        name.replace("_", " ").title(),
    )

    if mode == "multi_agent":
        return f"- **{label}: {status_label(passed)}**"

    details = validation.get("details", {})
    detail = details.get(name, {}) if isinstance(details, dict) else {}

    if not isinstance(detail, dict):
        detail = {}

    reported_status = detail.get("reported_status")

    if reported_status is None:
        evidence_status = detail.get("status", "not supplied")
        return (
            f"- **{label}: {status_label(passed)}** "
            f"(evidence status: {evidence_status})"
        )

    evidence_text = (
        str(detail.get("evidence") or "").strip()
        or str(detail.get("description") or "").strip()
    )

    evidence_text = " ".join(evidence_text.split())

    if evidence_text:
        evidence_description = f" — {evidence_text[:250]}"
    else:
        evidence_description = " — No supporting description supplied"

    return (
        f"- **{label}: {status_label(passed)}** "
        f"(reported: {reported_status})"
        f"{evidence_description}"
    )

def build_review(mode, evidence, instructions):
    """Create an authoritative review from deterministic findings."""
    del instructions  # Mode-specific instructions do not override checks.

    validation = get_validation(evidence)
    checks = validation["checks"]
    overall_pass = validation["status"] == "pass"

    if mode == "testing":
        subject = "Release 2 testing and security evidence"
        limitation = (
            "Results were supplied by the caller. The reviewer did not "
            "independently run Ruff, detect-secrets, pip-audit or pytest."
        )
    elif mode == "deployment":
        subject = "Release 2 cloud deployment evidence"
        limitation = (
            "Results were supplied by the caller. The reviewer did not "
            "independently build, deploy or test Azure resources."
        )
    else:
        subject = "Release 2 Multi-Agent workflow coordination"
        limitation = (
            "Coordination checks were derived from the saved workflow "
            "records. Passing them does not independently establish "
            "the factual accuracy of AI-generated agent outputs."
        )

    plan = (
        f"Review {subject}, identify failed or missing checks, "
        "and determine whether the available evidence supports "
        "the next release step."
    )

    act = (
        "Examined the supplied structured evidence and deterministic "
        "validation results.\n\n"
        f"**Verification scope:** {limitation}"
    )

    findings = [
        describe_check(name, passed, validation, mode)
        for name, passed in checks.items()
    ]

    missing = validation.get("missing_checks", [])
    if not missing:
        missing = validation.get("missing_events", [])

    if missing:
        findings.append(
            "- **Missing evidence:** " + ", ".join(map(str, missing))
        )

    overall = status_label(overall_pass)

    observe = (
        "\n".join(findings)
        + f"\n\n**Overall validation: {overall}.**"
    )

    failed = [
        CHECK_LABELS.get(name, name.replace("_", " "))
        for name, passed in checks.items()
        if not passed
    ]

    if failed:
        adapt = (
            "**Corrective action required.** Investigate and resolve "
            "the following reported failures or missing checks: "
            + ", ".join(failed)
            + ".\n\n"
            "Rerun the affected checks, capture their actual results, "
            "and submit updated evidence before claiming readiness."
        )
    else:
        adapt = (
            "All required deterministic checks passed. "
            "Preserve the supporting logs and results, confirm "
            "the evidence is authentic and current, and proceed "
            "to the next appropriate verification stage."
        )

    if mode == "deployment":
        if overall_pass:
            adapt += (
                "\n\nReported success alone does not independently "
                "establish cloud deployment readiness."
            )
        else:
            adapt += (
                "\n\n**Deployment readiness has not been established.**"
            )

    if mode == "testing" and not overall_pass:
        adapt += (
            "\n\n**Testing readiness has not been established.**"
        )

    if mode == "multi_agent":
        adapt += (
            "\n\nSeparately assess agent-output accuracy against "
            "the original source evidence."
        )

    return (
        f"## PLAN\n{plan}\n\n"
        f"## ACT\n{act}\n\n"
        f"## OBSERVE\n{observe}\n\n"
        f"## ADAPT\n{adapt}"
    )



def generate_ai_advisory(mode, evidence):
    """Generate optional corrective advice for failed checks only."""
    validation = get_validation(evidence)

    failed_checks = [
        name
        for name, passed in validation["checks"].items()
        if not passed
    ]

    # A passing review does not need speculative corrective advice.
    if not failed_checks:
        return None

    missing_checks = validation.get("missing_checks", [])
    missing_events = validation.get("missing_events", [])

    compact = {
        "review_mode": mode,
        "overall_status": "fail",
        "failed_checks": failed_checks,
        "missing_checks": missing_checks,
        "missing_events": missing_events,
    }

    prompt = (
        "You are assisting a software quality reviewer.\n"
        "The application has already determined which checks failed.\n"
        "Your only task is to recommend corrective actions.\n\n"
        "Rules:\n"
        "- Write at most three short actionable recommendations.\n"
        "- Focus only on the listed failed checks.\n"
        "- Do not reinterpret pass/fail results.\n"
        "- Do not claim tests or deployments were executed.\n"
        "- Do not invent failures, missing events or missing evidence.\n"
        "- Do not recommend investigating missing events unless "
        "missing_events is nonempty.\n"
        "- Do not recommend investigating missing checks unless "
        "missing_checks is nonempty.\n"
        "- Do not restate these instructions.\n"
        "- Do not output JSON, headings or Markdown code blocks.\n\n"
        "VALIDATED FAILURE SUMMARY:\n"
        f"{json.dumps(compact, separators=(',', ':'))}"
    )

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 240,
                    "temperature": 0.1,
                },
            },
            timeout=90,
        )

        response.raise_for_status()

        payload = response.json()

        if payload.get("done_reason") == "length":
            logger.warning("AI advisory exceeded token limit")
            return None

        advisory = payload.get("response", "").strip()

        if not advisory or len(advisory) > 1200:
            return None

        advisory_upper = advisory.upper()

        forbidden = (
            "VALIDATED FAILURE SUMMARY:",
            "YOU ARE ASSISTING A SOFTWARE QUALITY REVIEWER",
            "```",
        )

        if any(value in advisory_upper for value in forbidden):
            return None

        # Reject recommendations that introduce unsupported missing items.
        if (
            not missing_events
            and "missing event" in advisory.lower()
        ):
            return None

        if (
            not missing_checks
            and "missing check" in advisory.lower()
        ):
            return None

        return advisory

    except (requests.RequestException, ValueError, KeyError) as error:
        logger.warning("AI advisory unavailable: %s", error)
        return None


def save_review(mode, evidence, review, advisory=None):
    """Save the authoritative review and supplied summary evidence."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    generated_at = timestamp()

    filename = (
        f"{mode}-review-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S%f')}.md"
    )

    report_path = REPORTS_DIR / filename

    content = (
        f"# Release 2 {mode.replace('_', ' ').title()} Review\n\n"
        f"Generated: {generated_at}\n\n"
        "## Evidence\n\n"
        f"```json\n{json.dumps(evidence, indent=2, default=str)}\n```\n\n"
        "## Review Results\n\n"
        f"{review}\n"
    )

    if advisory:
        content += (
            "\n## AI Advisory — Unverified Suggestions\n\n"
            "The following suggestions were generated by Ollama. "
            "They are not independently verified findings and "
            "must not override the deterministic review.\n\n"
            f"{advisory}\n"
        )

    report_path.write_text(content, encoding="utf-8")

    return report_path


def execute_review(mode, evidence, instructions):
    """Validate, generate, and persist one Release 2 review."""
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported review mode: {mode}")

    if not isinstance(instructions, str):
        raise ValueError("Review instructions must be a string")

    review = build_review(mode, evidence, instructions)

    advisory = generate_ai_advisory(mode, evidence)

    report_path = save_review(
        mode,
        evidence,
        review,
        advisory,
    )

    return {
        "status": "completed",
        "mode": mode,
        "generated_at": timestamp(),
        "review": review,
        "ai_advisory": advisory,
        "ai_advisory_status": (
            "generated" if advisory else "unavailable"
        ),
        "report": str(report_path),
    }
