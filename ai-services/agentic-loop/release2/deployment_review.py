
"""Release 2 Cloud Deployment Report Review.

Validates supplied deployment check results and generates an
evidence-based AI review.

Reported checks are not treated as independently verified
Azure deployment results.
"""

from .review_engine import execute_review


REQUIRED_CHECKS = (
    "build",
    "deployment",
    "health",
    "security",
)


def validate_deployment_evidence(evidence):
    """Validate the structure and reported deployment check statuses."""

    if not isinstance(evidence, dict):
        raise ValueError("Deployment evidence must be a JSON object")

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
                "reason": "Check result must be an object",
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


def summarise_deployment_evidence(evidence, validation):
    """Prepare concise deployment evidence for AI analysis."""

    summary = {
        "deployment_target": evidence.get(
            "deployment_target",
            "Not specified",
        ),
        "environment": evidence.get(
            "environment",
            "Not specified",
        ),
        "repository": evidence.get(
            "repository",
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
            "Check results were supplied by the caller. "
            "The review process did not independently execute "
            "build, deployment, health or security checks."
        ),
    }

    return summary


def review_deployment(evidence):
    """Review supplied cloud deployment evidence."""

    validation = validate_deployment_evidence(evidence)

    summary = summarise_deployment_evidence(
        evidence,
        validation,
    )

    instructions = """
Review the supplied Azure cloud deployment report.

Evaluate:
- Reported build results.
- Reported deployment results.
- Reported application health checks.
- Reported security checks.
- Missing or failed evidence.
- Whether the reported evidence supports release readiness.

Important:
- Treat check statuses as reported evidence, not verified execution.
- Do not claim Azure resources were accessed or tested.
- Do not claim deployment succeeded if required checks failed.
- Do not invent Azure services, endpoints or test outcomes.
- Identify any missing verification evidence.
- Recommend corrective actions where necessary.

Keep PLAN, ACT, OBSERVE and ADAPT sections concise.
"""

    result = execute_review(
        mode="deployment",
        evidence=summary,
        instructions=instructions,
    )

    result["validation"] = validation

    return result
