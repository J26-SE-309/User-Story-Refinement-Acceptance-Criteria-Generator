"""Deterministic quality checks for generated stories.

These checks identify structural problems and signals for human review. They do
not establish semantic correctness.
"""

import re
from collections.abc import Iterable

from app.schemas import AcceptanceCriterion, QualityFinding, QualityValidationResponse

_STORY_PATTERN = re.compile(
    r"^As a (?P<role>.+), I want (?P<goal>.+), so that (?P<benefit>.+)\.$",
    re.IGNORECASE,
)
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _finding(code: str, message: str, field: str | None = None) -> QualityFinding:
    return QualityFinding(code=code, message=message, field=field)


def _normalise(value: str) -> str:
    return " ".join(value.lower().split())


def _tokens(values: Iterable[str]) -> set[str]:
    return set().union(*(_TOKEN_PATTERN.findall(value.lower()) for value in values))


def validate_story_quality(
    user_story: str,
    acceptance_criteria: list[AcceptanceCriterion],
    requirement_text: str | None = None,
    assumptions: list[str] | None = None,
) -> QualityValidationResponse:
    errors: list[QualityFinding] = []
    warnings: list[QualityFinding] = []

    story_match = _STORY_PATTERN.match(user_story.strip())
    if not story_match:
        errors.append(
            _finding(
                "invalid_user_story_format",
                'User story must follow "As a [user role], I want [goal], so that [benefit]."',
                "user_story",
            )
        )
    else:
        for name, label in (("role", "user role"), ("goal", "goal"), ("benefit", "benefit")):
            if not story_match.group(name).strip():
                errors.append(_finding("missing_story_field", f"The {label} is empty.", "user_story"))

    if not acceptance_criteria:
        errors.append(_finding("empty_acceptance_criteria", "At least one acceptance criterion is required."))

    seen: set[str] = set()
    for index, criterion in enumerate(acceptance_criteria, start=1):
        values = {"given": criterion.given, "when": criterion.when, "then": criterion.then}
        for field, value in values.items():
            if not value.strip():
                errors.append(
                    _finding("missing_criterion_field", f"Criterion {index} has an empty {field} field.", field)
                )
        key = _normalise(" ".join(values.values()))
        if key in seen:
            errors.append(_finding("duplicate_criterion", f"Criterion {index} duplicates another criterion."))
        seen.add(key)

    if requirement_text:
        source_tokens = _tokens([requirement_text])
        generated_tokens = _tokens(
            [user_story] + [value for criterion in acceptance_criteria for value in (
                criterion.given, criterion.when, criterion.then
            )]
        )
        if source_tokens and len(source_tokens & generated_tokens) / len(source_tokens) < 0.2:
            warnings.append(
                _finding(
                    "low_requirement_coverage",
                    "Generated content has little lexical overlap with the validated "
                    "requirement; human review is required.",
                )
            )

    if assumptions:
        warnings.extend(
            _finding("unsupported_assumption", assumption, "assumptions")
            for assumption in assumptions
            if assumption.strip()
        )

    criterion_text = [_normalise(" ".join((item.given, item.when, item.then))) for item in acceptance_criteria]
    if any("must " in text and "must not " in text for text in criterion_text):
        warnings.append(
            _finding(
                "potential_contradiction",
                "Criteria contain potentially conflicting must/must-not statements.",
            )
        )

    return QualityValidationResponse(
        valid=not errors,
        requires_human_review=True,
        errors=errors,
        warnings=warnings,
        checks={
            "user_story_format": not any(item.code == "invalid_user_story_format" for item in errors),
            "acceptance_criteria_present": bool(acceptance_criteria),
            "given_when_then_complete": not any(item.code == "missing_criterion_field" for item in errors),
            "duplicates_checked": True,
            "semantic_correctness_proven": False,
        },
    )
