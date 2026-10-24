
"""GitHub Actions client for Adrian's Release 2 CI reviews."""

import io
import os
import zipfile

import requests


GITHUB_API = "https://api.github.com"

REPOSITORY = os.getenv(
    "GITHUB_REPOSITORY",
    "AdrianVoljak/advanced-software-dev-release2",
)

WORKFLOW_FILE = "student-adrianvoljak.yml"

TOKEN = os.getenv("GITHUB_TOKEN")


def _headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    return headers


def get_completed_runs(limit=5):
    """Retrieve completed runs of Adrian's workflow only."""
    url = (
        f"{GITHUB_API}/repos/{REPOSITORY}"
        f"/actions/workflows/{WORKFLOW_FILE}/runs"
    )

    response = requests.get(
        url,
        headers=_headers(),
        params={
            "status": "completed",
            "per_page": limit,
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json().get("workflow_runs", [])


def get_jobs(run_id):
    """Retrieve jobs and individual step results for a CI run."""
    url = (
        f"{GITHUB_API}/repos/{REPOSITORY}"
        f"/actions/runs/{run_id}/jobs"
    )

    response = requests.get(
        url,
        headers=_headers(),
        timeout=30,
    )

    response.raise_for_status()

    return response.json().get("jobs", [])


def get_run_logs(run_id, max_chars=12000):
    """Retrieve CI logs for troubleshooting failed runs."""
    url = (
        f"{GITHUB_API}/repos/{REPOSITORY}"
        f"/actions/runs/{run_id}/logs"
    )

    response = requests.get(
        url,
        headers=_headers(),
        timeout=30,
    )

    response.raise_for_status()

    log_parts = []

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for filename in archive.namelist():
            if not filename.endswith(".txt"):
                continue

            with archive.open(filename) as file:
                content = file.read().decode(
                    "utf-8",
                    errors="replace",
                )

            log_parts.append(
                f"\n--- {filename} ---\n{content}"
            )

    logs = "\n".join(log_parts)

    if len(logs) > max_chars:
        half = max_chars // 2
        logs = (
            logs[:half]
            + "\n\n[... log output truncated ...]\n\n"
            + logs[-half:]
        )

    return logs


def build_ci_evidence(run):
    """Build a summary of GitHub Actions results for AI review."""
    jobs = get_jobs(run["id"])

    lines = [
        f"Repository: {REPOSITORY}",
        f"Workflow: {run.get('name')}",
        f"Workflow File: {WORKFLOW_FILE}",
        f"Run ID: {run.get('id')}",
        f"Branch: {run.get('head_branch')}",
        f"Commit: {run.get('head_sha')}",
        f"Event: {run.get('event')}",
        f"Conclusion: {run.get('conclusion')}",
        f"Created At: {run.get('created_at')}",
        f"Updated At: {run.get('updated_at')}",
        "",
        "Jobs:",
    ]

    for job in jobs:
        lines.append(
            f"- {job.get('name')}: {job.get('conclusion')}"
        )

        for step in job.get("steps", []):
            lines.append(
                f"    - {step.get('name')}: "
                f"{step.get('conclusion')}"
            )

    if run.get("conclusion") != "success":
        try:
            logs = get_run_logs(run["id"])

            if logs:
                lines.extend([
                    "",
                    "Failure Logs:",
                    logs,
                ])

        except (requests.RequestException, zipfile.BadZipFile) as error:
            lines.extend([
                "",
                "Failure Logs:",
                f"Unable to retrieve logs: {type(error).__name__}",
            ])

    else:
        lines.extend([
            "",
            "CI Summary:",
            "The workflow completed successfully.",
            "Job and step conclusions are listed above.",
            "Raw logs were not retrieved for this successful run.",
        ])

    return "\n".join(lines)
