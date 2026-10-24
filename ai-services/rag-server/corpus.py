"""Build the Assessment Tracker RAG knowledge base.

Sources:
1. Live assessment records from the Assessment Tracker database API.
2. Markdown and text documents from the configured documents directory.

Each assessment becomes a searchable passage with citation metadata.
An unavailable assessment service is recorded without preventing
document indexing.
"""

import logging
import os
from pathlib import Path

import requests

from retrieval import Index


logger = logging.getLogger(__name__)

TIMEOUT = int(os.getenv("RAG_UPSTREAM_TIMEOUT", "10"))
RECORD_WEIGHT = float(os.getenv("RAG_RECORD_WEIGHT", "1.6"))

DOCUMENTS_DIR = Path(
    os.getenv(
        "RAG_DOCUMENTS_DIR",
        str(Path(__file__).resolve().parent / "documents"),
    )
)

ASSESSMENT = os.getenv(
    "ASSESSMENT_DB_URL",
    "http://localhost:5008",
).rstrip("/")


def _fetch_assignments(student_id=None):
    """Retrieve assessment records from the database service."""
    params = {"student_id": student_id} if student_id is not None else None

    response = requests.get(
        f"{ASSESSMENT}/assignments",
        params=params,
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    body = response.json()

    if isinstance(body, list):
        return body

    if isinstance(body, dict) and isinstance(body.get("assignments"), list):
        return body["assignments"]

    raise ValueError("Unexpected assessment database response format")


def _clean(value, fallback=""):
    text = str(value).strip() if value not in (None, "") else ""
    return text or fallback


def build_index(student_id=None):
    """Build a fresh index and return (index, report)."""
    index = Index()

    report = {
        "sources": {},
        "unavailable": [],
    }

    # -------------------------------------------------- assessments
    assessment_count = 0

    try:
        rows = _fetch_assignments(student_id)

        for row in rows:
            # Ensure that a student-scoped request excludes other students.
            if (
                student_id is not None
                and str(row.get("student_id")) != str(student_id)
            ):
                continue

            assignment_id = row.get("assignment_id")
            title = _clean(row.get("title"), "An assignment")
            due = _clean(row.get("due_date"), "no due date")
            weight = row.get("weighting")
            status = _clean(
                row.get("status"),
                "not started",
            ).replace("_", " ")
            description = _clean(row.get("description"))
            course_id = row.get("course_id")

            passage = (
                f"Assignment: {title}. "
                f"The assignment {title} is due on {due}. "
                f"It is worth {weight} percent of the subject mark. "
                f"Its status is {status}. "
                f"It belongs to course {course_id}. "
                f"{description}"
            )

            index.add(
                f"assessment tracker, assignment {assignment_id}",
                passage,
                {
                    "type": "assignment",
                    "assignment_id": assignment_id,
                    "student_id": row.get("student_id"),
                    "course_id": course_id,
                    "due_date": due,
                    "weighting": weight,
                    "status": status,
                },
                weight=RECORD_WEIGHT,
            )

            assessment_count += 1

        report["sources"]["assignments"] = assessment_count

    except (requests.RequestException, ValueError, TypeError) as error:
        logger.warning(
            "Assessment RAG source unavailable: %s",
            error,
        )

        report["sources"]["assignments"] = 0
        report["unavailable"].append(
            {
                "source": "assignments",
                "reason": type(error).__name__,
            }
        )

    # -------------------------------------------------- documents
    document_count = 0

    if DOCUMENTS_DIR.is_dir():
        for path in sorted(DOCUMENTS_DIR.iterdir()):
            if not path.is_file() or path.suffix.lower() not in (".md", ".txt"):
                continue

            try:
                content = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError as error:
                logger.warning(
                    "Could not read RAG document %s: %s",
                    path.name,
                    error,
                )
                report["unavailable"].append(
                    {
                        "source": path.name,
                        "reason": type(error).__name__,
                    }
                )
                continue

            for paragraph_number, paragraph in enumerate(
                (
                    block.strip()
                    for block in content.split("\n\n")
                    if block.strip()
                ),
                start=1,
            ):
                index.add(
                    f"{path.name}, paragraph {paragraph_number}",
                    paragraph,
                    {
                        "type": "document",
                        "file": path.name,
                    },
                )
                document_count += 1

    report["sources"]["documents"] = document_count

    index.finalise()
    report["passages"] = len(index)

    return index, report
