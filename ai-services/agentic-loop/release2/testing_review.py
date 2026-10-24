"""Release 2 Testing and Security Review.

Evaluates supplied pre-commit and post-commit testing evidence.
Reported check statuses are not independently verified test executions.
"""

from .review_engine import execute_review


REQUIRED_CHECKS = (
    "ruff",
    "detect_secrets",
    "pip_audit",
    "pytest",
)


def validate_testing_evidence(evidence):
    """Validate the supplied testing and security check results."""

    if not isinstance(evidence, dict):
        raise ValueError("Testing evidence must be a JSON object")

    results = evidence.get("checks")

    if not isinstance(results, dict):
        raise ValueError("Evidence must contain a checks object")

    missing = [
        name
        for name in REQUIRED_CHECKS
        if name not in results
    ]

    checks = {}
    details = {}

    for name in REQUIRED_CHECKS:
        check = results.get(name)

        if not isinstance(check, dict):
            checks[name] = False

            details[name] = {
                "status": "missing" if name in missing else "invalid",
                "reason": "Check result must be a JSON object",
            }
            continue

        reported_status = check.get("status")
        checks[name] = reported_status == "pass"

        details[name] = {
            "reported_status": reported_status,
            "reported_pass": checks[name],
            "description": str(
                check.get("description", "")
            )[:300],
            "evidence": str(
                check.get("evidence", "")
            )[:500],
        }

    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "details": details,
        "missing_checks": missing,
        "verification_level": "reported_results_only",
        "independently_verified": False,
    }


def summarise_testing_evidence(evidence, validation):
    """Prepare concise testing evidence for the AI reviewer."""

    return {
        "repository": evidence.get(
            "repository",
            "Not specified",
        ),
        "branch": evidence.get(
            "branch",
            "Not specified",
        ),
        "commit": evidence.get(
            "commit",
            "Not specified",
        ),
        "checks": validation["details"],
        "validation": {
            "status": validation["status"],
            "checks": validation["checks"],
            "missing_checks": validation["missing_checks"],
            "verification_level": "reported_results_only",
        },
        "limitations": (
            "Check results were provided by the caller. "
            "This review did not independently execute "
            "Ruff, detect-secrets, pip-audit or pytest."
        ),
    }


def review_testing(evidence):
    """Review testing and security evidence."""

    validation = validate_testing_evidence(evidence)

    summary = summarise_testing_evidence(
        evidence,
        validation,
    )

    instructions = """
Review the supplied Release 2 testing evidence.

Evaluate:
- Reported Ruff linting and security scan results.
- Reported detect-secrets results.
- Reported pip-audit dependency scan results.
- Reported pytest automated test results.
- Missing, failed or invalid checks.
- Whether the evidence supports release readiness.

Important:
- Reported pass/fail values are not proof of execution.
- Do not invent test executions or outcomes.
- Do not change the supplied statuses.
- Do not claim all checks passed when any check failed or is missing.
- Identify limitations and missing evidence.
- Recommend corrective actions where necessary.

Keep PLAN, ACT, OBSERVE and ADAPT sections concise.
"""

    result = execute_review(
        mode="testing",
        evidence=summary,
        instructions=instructions,
    )

    result["validation"] = validation

    return result
