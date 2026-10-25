
"""Lazy, explicit inference for the configured fine-tuned FLAN-T5 model."""

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.schemas import (
    AcceptanceCriterion,
    QualityScores,
    RefinedStory,
    RefinementRequest,
)
from app.quality import validate_story_quality


_lock = threading.Lock()
_tokenizer: Any | None = None
_model: Any | None = None
_device: str | None = None


class ModelUnavailableError(RuntimeError):
    """The configured model cannot be loaded."""


class InvalidModelOutputError(RuntimeError):
    """The model returned output that cannot satisfy the API contract."""


def model_path() -> Path:
    """Resolve the configured model path to an absolute path."""
    configured = Path(get_settings().story_model_path).expanduser()

    if configured.is_absolute():
        return configured.resolve()

    # story_model.py -> services -> app -> backend -> project root
    project_root = Path(__file__).resolve().parents[3]
    return (project_root / configured).resolve()


def _required_model_files(path: Path) -> list[str]:
    """Return required model files that are missing."""
    required: list[str] = []

    for filename in ("config.json", "tokenizer_config.json"):
        if not (path / filename).is_file():
            required.append(filename)

    if not any(
        (path / name).is_file()
        for name in ("tokenizer.json", "spiece.model")
    ):
        required.append("tokenizer.json or spiece.model")

    weight_files = (
        "model.safetensors",
        "pytorch_model.bin",
        "model.safetensors.index.json",
        "pytorch_model.bin.index.json",
    )
    if not any((path / name).is_file() for name in weight_files):
        required.append("model.safetensors or pytorch_model.bin")

    return required


def status() -> tuple[bool, str, dict[str, str]]:
    """Check model files and report model configuration."""
    path = model_path()
    missing = (
        _required_model_files(path)
        if path.is_dir()
        else ["model directory"]
    )

    try:
        import torch

        cuda_available = torch.cuda.is_available()
    except ImportError:
        cuda_available = False

    settings = get_settings()
    requested_device = settings.story_model_device

    details = {
        "model_path": str(path),
        "device": _device
        or (
            requested_device
            if requested_device != "auto"
            else ("cuda" if cuda_available else "cpu")
        ),
        "model_type": "fine-tuned FLAN-T5",
    }

    if missing:
        details["missing_files"] = ", ".join(missing)
        return (
            False,
            f"Model unavailable at '{path}': missing "
            f"{', '.join(missing)}.",
            details,
        )

    return (
        True,
        "Configured fine-tuned FLAN-T5 model files are available.",
        details,
    )


def _load() -> tuple[Any, Any, str]:
    """Load the tokenizer and model once, safely across threads."""
    global _model, _tokenizer, _device

    if _model is not None and _tokenizer is not None and _device:
        return _tokenizer, _model, _device

    with _lock:
        if _model is not None and _tokenizer is not None and _device:
            return _tokenizer, _model, _device

        available, message, _ = status()
        if not available:
            raise ModelUnavailableError(message)

        path = model_path()
        settings = get_settings()

        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            requested_device = settings.story_model_device

            if requested_device not in {"auto", "cpu", "cuda"}:
                raise ValueError(
                    "STORY_MODEL_DEVICE must be 'auto', 'cpu', or 'cuda'."
                )

            if requested_device == "cuda" and not torch.cuda.is_available():
                raise RuntimeError(
                    "CUDA was requested but is unavailable. "
                    "Set STORY_MODEL_DEVICE=cpu or install a compatible "
                    "PyTorch CUDA build."
                )

            if requested_device == "cuda":
                device = "cuda"
            elif requested_device == "cpu":
                device = "cpu"
            else:
                device = "cuda" if torch.cuda.is_available() else "cpu"

            tokenizer = AutoTokenizer.from_pretrained(
                str(path),
                local_files_only=True,
            )
            model = AutoModelForSeq2SeqLM.from_pretrained(
                str(path),
                local_files_only=True,
            )

            model.to(device)
            model.eval()

        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            _tokenizer = None
            _model = None
            _device = None

            raise ModelUnavailableError(
                f"Unable to load model from '{path}': {exc}"
            ) from exc

        # Publish only after both objects have loaded successfully.
        _tokenizer = tokenizer
        _model = model
        _device = device

    return _tokenizer, _model, _device


def load_model() -> None:
    """Load the configured model during application startup."""
    _load()


def _extract_json_object(raw: str) -> dict[str, Any]:
    """Extract a JSON object, including one wrapped in a code fence."""
    text = raw.strip()

    if not text:
        raise InvalidModelOutputError("The model returned empty output.")

    fenced = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        text = fenced.group(1).strip()

    # First try parsing the entire response.
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Some models put explanatory text before or after the JSON.
        # Decode the first JSON object rather than trusting arbitrary text.
        start = text.find("{")
        if start < 0:
            raise InvalidModelOutputError(
                "The model output does not contain a JSON object."
            )

        try:
            payload, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError as exc:
            raise InvalidModelOutputError(
                "The model returned malformed JSON."
            ) from exc

    if not isinstance(payload, dict):
        raise InvalidModelOutputError(
            "The model output must be a JSON object."
        )

    return payload


def _parse_output(
    raw: str,
    request: RefinementRequest,
) -> tuple[str, list[AcceptanceCriterion], list[str]]:
    """Parse and validate generated story and acceptance criteria."""
    del request  # Kept for future request-specific validation.

    payload = _extract_json_object(raw)

    story_value = payload.get("user_story")
    raw_criteria = payload.get("acceptance_criteria")
    raw_assumptions = payload.get("unsupported_assumptions", [])

    if not isinstance(story_value, str):
        raise InvalidModelOutputError(
            "'user_story' must be a string."
        )

    story = story_value.strip()

    if not isinstance(raw_criteria, list) or not raw_criteria:
        raise InvalidModelOutputError(
            "'acceptance_criteria' must be a non-empty list."
        )

    if not isinstance(raw_assumptions, list):
        raise InvalidModelOutputError(
            "'unsupported_assumptions' must be a list."
        )

    criteria: list[AcceptanceCriterion] = []

    for index, item in enumerate(raw_criteria, start=1):
        if not isinstance(item, dict):
            raise InvalidModelOutputError(
                f"Acceptance criterion {index} must be an object."
            )

        values: dict[str, str] = {}

        for field in ("given", "when", "then"):
            value = item.get(field)

            if not isinstance(value, str) or not value.strip():
                raise InvalidModelOutputError(
                    f"Acceptance criterion {index} has an invalid "
                    f"'{field}' value."
                )

            values[field] = value.strip()

        criteria.append(
            AcceptanceCriterion(
                id=str(item.get("id") or f"AC{index}").strip(),
                given=values["given"],
                when=values["when"],
                then=values["then"],
            )
        )

    assumptions = [
        item.strip()
        for item in raw_assumptions
        if isinstance(item, str) and item.strip()
    ]

    if not story:
        raise InvalidModelOutputError(
            "The model returned an empty user story."
        )

    return story, criteria, assumptions


def _build_context(request: RefinementRequest) -> str:
    """Build context while omitting empty optional fields."""
    fields = (
        ("Actor", request.user_role),
        ("Feature/module", request.feature_module),
        ("Business goal", request.business_goal),
        ("Related requirements", request.related_requirements),
        (
            "Existing system context",
            request.existing_system_context or request.project_context,
        ),
        ("Additional constraints", request.additional_constraints),
    )

    return "\n".join(
        f"{label}: {value.strip() if isinstance(value, str) else value}"
        for label, value in fields
        if value is not None and str(value).strip()
    )


def _quality_scores(
    story: str,
    criteria: list[AcceptanceCriterion],
    quality: Any,
    context: str,
) -> QualityScores:
    """
    Produce conservative heuristic scores from available quality checks.

    These are rule-based indicators, not calibrated probabilities or
    expert judgements about story quality.
    """
    checks = quality.checks
    errors = quality.errors

    invest_keys = (
        "independent",
        "negotiable",
        "valuable",
        "estimable",
        "small",
        "testable",
    )

    # Only mark an INVEST item true when the validator explicitly reports
    # that check. Missing checks must not be assumed to have passed.
    invest = {
        key: bool(checks.get(key, False))
        for key in invest_keys
    }

    invest_score = sum(invest.values()) / len(invest)

    complete_fields = sum(
        bool(value.strip())
        for item in criteria
        for value in (item.given, item.when, item.then)
    )
    total_fields = len(criteria) * 3
    completeness = (
        complete_fields / total_fields if total_fields else 0.0
    )

    duplicate_criteria = any(
        getattr(error, "code", None) == "duplicate_criterion"
        for error in errors
    )

    return QualityScores(
        invest=invest,
        invest_score=round(invest_score, 2),
        completeness=round(completeness, 2),
        clarity=1.0 if checks.get("user_story_format", False) else 0.0,
        testability=(
            1.0
            if checks.get("given_when_then_complete", False)
            else 0.0
        ),
        consistency=0.0 if duplicate_criteria else 1.0,
        context_relevance=1.0 if context.strip() else 0.0,
    )


def generate_refinement(request: RefinementRequest) -> RefinedStory:
    """Generate a refined user story and testable acceptance criteria."""
    import torch

    started = time.perf_counter()
    tokenizer, model, device = _load()

    requirement = request.validated_requirement.strip()
    if not requirement:
        raise ValueError("validated_requirement must not be empty.")

    context = _build_context(request)

    prompt = (
        "Task: Refine the validated software requirement into one "
        "Agile user story and clear, testable acceptance criteria.\n"
        "Return JSON only, without Markdown or explanatory text.\n"
        "Use exactly these top-level keys:\n"
        "{"
        '"user_story": "As a ..., I want ..., so that ...", '
        '"acceptance_criteria": ['
        '{"id": "AC1", "given": "...", "when": "...", "then": "..."}'
        '], "unsupported_assumptions": []'
        "}\n"
        "Requirements:\n"
        "- Keep the story faithful to the validated requirement.\n"
        "- Each criterion must have specific Given, When, and Then fields.\n"
        "- Make criteria observable and testable.\n"
        "- Include negative, boundary, and error cases when justified "
        "by the requirement.\n"
        "- Do not invent business rules, permissions, limits, or behavior.\n"
        "- List unresolved assumptions in unsupported_assumptions.\n"
        f"Validated requirement: {requirement}\n"
        f"Context:\n{context or 'None'}"
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )
    inputs = {key: value.to(device) for key, value in inputs.items()}

    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=512,
            num_beams=4,
            do_sample=False,
        )

    raw = tokenizer.decode(
        generated[0],
        skip_special_tokens=True,
    )
    print("\n--- STORY MODEL DEBUG ---")
    print("Output token count:", len(generated[0]))
    print("--- END STORY MODEL DEBUG ---\n")
     print("Model directory:", model_path())
    print("Decoded output:", repr(raw))

    story, criteria, assumptions = _parse_output(raw, request)

    quality = validate_story_quality(
        story,
        criteria,
        requirement,
        assumptions,
    )

    scores = _quality_scores(
        story=story,
        criteria=criteria,
        quality=quality,
        context=context,
    )

    return RefinedStory(
        requirement_id=request.requirement_id,
        story_id=f"{request.requirement_id}-S1",
        user_story=story,
        acceptance_criteria=criteria,
        quality_scores=scores,
        unsupported_assumptions=assumptions,
        processing_time_ms=int(
            (time.perf_counter() - started) * 1000
        ),
        model_metadata={
            "model_version": "trained_user_story_model",
            "model_type": "fine-tuned-FLAN-T5",
            "device": device,
            "requires_human_review": "true",
        },
    )
