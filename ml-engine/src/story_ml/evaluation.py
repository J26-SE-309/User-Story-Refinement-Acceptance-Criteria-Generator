"""Deterministic candidate evaluation and unsupported-claim checks."""

import re

from story_ml.config import RankingSettings
from story_ml.types import CandidateDraft, Finding, QualityEvaluation, RetrievedContext

_WORD = re.compile(r"[a-z0-9]+")
_INVEST = ("independent", "negotiable", "valuable", "estimable", "small", "testable")
_NON_EVIDENCE_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "can",
    "for",
    "i",
    "in",
    "is",
    "it",
    "of",
    "so",
    "that",
    "the",
    "to",
    "want",
}


def _words(text: str) -> set[str]:
    words = set(_WORD.findall(text.lower()))
    normalized: set[str] = set()
    for word in words:
        if len(word) > 5 and word.endswith("ing"):
            word = word[:-3]
        elif len(word) > 4 and word.endswith("ed"):
            word = word[:-2]
        elif len(word) > 4 and word.endswith("s"):
            word = word[:-1]
        normalized.add(word)
    return normalized


def detect_findings(
    candidate: CandidateDraft, requirement: str, context: list[RetrievedContext]
) -> list[Finding]:
    evidence_text = requirement + " " + " ".join(item.document.text for item in context)
    evidence_words = _words(evidence_text)
    findings: list[Finding] = []
    for statement in [
        candidate.user_story,
        *(criterion.then for criterion in candidate.acceptance_criteria),
    ]:
        statement_words = _words(statement)
        novel = statement_words - evidence_words
        meaningful = {
            word for word in novel if len(word) > 3 and word not in _NON_EVIDENCE_WORDS
        }
        if meaningful:
            findings.append(
                Finding(
                    statement=statement,
                    reason="Meaningful terms are absent from the requirement and retrieved evidence.",
                    evidence=tuple(item.document.source_reference for item in context),
                    kind="unsupported_claim",
                )
            )
        statement_raw = set(_WORD.findall(statement.lower()))
        for document in context:
            document_raw = set(_WORD.findall(document.document.text.lower()))
            if len(statement_words & _words(document.document.text)) < 2:
                continue
            if ("cannot" in document_raw and "can" in statement_raw) or (
                "unavailable" in document_raw and "available" in statement_raw
            ):
                findings.append(
                    Finding(
                        statement=statement,
                        reason="The statement conflicts with an explicit rule in retrieved project context.",
                        evidence=(document.document.source_reference,),
                        kind="contradiction",
                    )
                )
    return findings


def evaluate_candidate(
    candidate: CandidateDraft, requirement: str, context: list[RetrievedContext]
) -> QualityEvaluation:
    findings = detect_findings(candidate, requirement, context)
    story_words = _words(candidate.user_story)
    requirement_words = _words(requirement)
    overlap = len(story_words & requirement_words) / max(1, len(requirement_words))
    criteria_count = len(candidate.acceptance_criteria)
    complete_criteria = sum(
        bool(criteria.given.strip() and criteria.when.strip() and criteria.then.strip())
        for criteria in candidate.acceptance_criteria
    )
    testable = complete_criteria == criteria_count and criteria_count > 0
    one_goal = (
        candidate.user_story.lower().startswith("as a ")
        and " i want " in candidate.user_story.lower()
    )
    invest = {
        "independent": one_goal,
        "negotiable": one_goal,
        "valuable": "so that" in candidate.user_story.lower(),
        "estimable": one_goal and len(story_words) <= 45,
        "small": one_goal and len(story_words) <= 35,
        "testable": testable,
    }
    scores = {
        "invest": sum(invest.values()) / len(_INVEST),
        "clarity": 1.0
        if one_goal and len(story_words) <= 45
        else 0.5
        if one_goal
        else 0.0,
        "completeness": min(1.0, complete_criteria / 3),
        "testability": 1.0 if testable else complete_criteria / max(1, criteria_count),
        "consistency": 0.0
        if any(item.kind == "contradiction" for item in findings)
        else 1.0,
        "context_relevance": min(1.0, overlap + 0.25) if context else overlap * 0.75,
        "acceptance_criteria_coverage": min(
            1.0, complete_criteria / max(1, criteria_count)
        ),
    }
    scores["overall"] = sum(scores.values()) / 7
    explanations = {
        "invest": f"{sum(invest.values())}/6 INVEST dimensions met.",
        "completeness": f"{complete_criteria}/{criteria_count} acceptance criteria are complete.",
        "context_relevance": "Requirement-term overlap is used as a heuristic, not proof of support.",
    }
    return QualityEvaluation(
        invest=invest,
        scores=scores,
        explanations=explanations,
        findings=findings,
        valid=bool(candidate.user_story.strip() and testable and not findings),
    )


def rank_candidates(
    candidates: list[CandidateDraft],
    requirement: str,
    context: list[RetrievedContext],
    settings: RankingSettings | None = None,
) -> tuple[list[tuple[CandidateDraft, QualityEvaluation]], list[Finding]]:
    settings = settings or RankingSettings()
    weights = settings.as_dict()
    evaluated = [
        (candidate, evaluate_candidate(candidate, requirement, context))
        for candidate in candidates
    ]
    valid = [item for item in evaluated if item[1].valid]
    valid.sort(
        key=lambda item: sum(
            weights.get(key, 0.0) * item[1].scores.get(key, 0.0)
            for key in weights
            if key in item[1].scores
        ),
        reverse=True,
    )
    risks = [finding for _, evaluation in evaluated for finding in evaluation.findings]
    return valid, risks
