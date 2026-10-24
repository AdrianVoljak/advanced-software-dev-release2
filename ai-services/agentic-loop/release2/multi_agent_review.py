
"""Release 2 Multi-Agent workflow review.

Validates workflow coordination using saved history and audit events.
Sends concise evidence to the AI reviewer while preserving full
source evidence in the saved report.
"""

import json
import os
from pathlib import Path

from .review_engine import execute_review


BASE_DIR = Path(__file__).resolve().parents[2]

MULTI_AGENT_LOG_DIR = Path(
    os.getenv(
        "MULTI_AGENT_LOG_DIR",
        str(BASE_DIR / "multi-agent-server" / "logs"),
    )
)

HISTORY_FILE = MULTI_AGENT_LOG_DIR / "workflow_history.jsonl"
AUDIT_FILE = MULTI_AGENT_LOG_DIR / "coordination_audit.jsonl"


def load_jsonl(path):
    """Read existing JSONL evidence records."""
    if not path.is_file():
        raise FileNotFoundError(f"Evidence file not found: {path}")

    records = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path.name}"
                ) from exc

    return records


def collect_workflow_evidence(workflow_id):
    """Retrieve the latest workflow state and associated audit events."""
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise ValueError("workflow_id is required")

    history = load_jsonl(HISTORY_FILE)
    audit = load_jsonl(AUDIT_FILE)

    matching_history = [
        record
        for record in history
        if record.get("workflow_id") == workflow_id
    ]

    if not matching_history:
        raise ValueError(f"Workflow not found: {workflow_id}")

    workflow = matching_history[-1]

    events = [
        record
        for record in audit
        if record.get("workflow_id") == workflow_id
    ]

    return {
        "workflow": workflow,
        "audit_events": events,
    }


def validate_workflow_evidence(evidence):
    """Deterministically validate agent and human-review coordination."""
    workflow = evidence["workflow"]
    events = evidence["audit_events"]

    event_names = [event.get("event") for event in events]

    required_events = [
        "workflow_started",
        "planner_completed",
        "worker_completed",
        "reviewer_completed",
        "human_review_completed",
    ]

    missing_events = [
        event
        for event in required_events
        if event not in event_names
    ]

    positions = [
        event_names.index(event)
        for event in required_events
        if event in event_names
    ]

    correct_order = (
        not missing_events
        and positions == sorted(positions)
    )

    human_review = workflow.get("human_review")

    valid_decisions = {
        "approved",
        "partially_accepted",
        "rejected",
    }

    decision = (
        human_review.get("decision")
        if isinstance(human_review, dict)
        else None
    )

    checks = {
        "planner_present": bool(workflow.get("planner")),
        "worker_present": bool(workflow.get("worker")),
        "reviewer_present": bool(workflow.get("reviewer")),
        "human_review_present": decision in valid_decisions,
        "audit_events_complete": not missing_events,
        "correct_event_order": correct_order,
        "final_status_matches_decision": workflow.get("status") == decision,
    }

    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "missing_events": missing_events,
    }


def summarise_workflow_evidence(evidence, validation):
    """Create concise evidence for the AI without inventing findings."""
    workflow = evidence["workflow"]

    planner = workflow.get("planner") or {}
    worker = workflow.get("worker") or {}
    reviewer = workflow.get("reviewer") or {}
    human_review = workflow.get("human_review") or {}

    # Restrict verbose generated text, not deterministic check results.
    return {
        "workflow_id": workflow.get("workflow_id"),
        "request": workflow.get("request"),
        "workflow_status": workflow.get("status"),
        "planner": {
            "present": bool(planner),
            "status": planner.get("status"),
            "objective": planner.get("objective"),
            "plan_excerpt": str(planner.get("plan", ""))[:900],
        },
        "worker": {
            "present": bool(worker),
            "status": worker.get("status"),
            "evidence_count": worker.get("evidence_count"),
            "output_excerpt": str(worker.get("output", ""))[:1200],
        },
        "reviewer": {
            "present": bool(reviewer),
            "status": reviewer.get("status"),
            "review_excerpt": str(reviewer.get("review", ""))[:1200],
        },
        "human_review": {
            "decision": human_review.get("decision"),
            "comments": human_review.get("comments"),
            "reviewed_at": human_review.get("reviewed_at"),
        },
        "audit_events": [
            event.get("event")
            for event in evidence["audit_events"]
        ],
        "validation": validation,
        "limitations": (
            "Agent outputs are excerpts. Deterministic coordination "
            "checks are based on the original stored records. "
            "The AI review cannot independently verify omitted content."
        ),
    }


def review_multi_agent_workflow(workflow_id):
    """Validate and review a saved Multi-Agent workflow."""
    evidence = collect_workflow_evidence(workflow_id)

    validation = validate_workflow_evidence(evidence)

    summary = summarise_workflow_evidence(evidence, validation)

    instructions = """
Review the Multi-Agent workflow using the supplied summary.

Evaluate:
- Planner, Worker and Reviewer execution.
- Recorded audit event ordering.
- Presence and validity of the human review.
- Consistency between final status and human decision.
- Risks or limitations visible in the supplied excerpts.

The deterministic validation results are based on the stored
workflow history and audit events.

Do not claim the full agent outputs were independently checked.
Do not claim factual accuracy solely because workflow validation passed.

Keep each PLAN, ACT, OBSERVE and ADAPT section short.
"""

    # The AI receives compact evidence to reduce output problems.
    result = execute_review(
        mode="multi_agent",
        evidence=summary,
        instructions=instructions,
    )

    result["validation"] = validation
    result["workflow_id"] = workflow_id

    return result
