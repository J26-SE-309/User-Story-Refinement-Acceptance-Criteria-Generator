"""Lazy, explicit inference for the configured fine-tuned FLAN-T5 model."""

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.schemas import AcceptanceCriterion, QualityScores, RefinedStory, RefinementRequest
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
    configured = Path(get_settings().story_model_path).expanduser()
    return configured if configured.is_absolute() else (Path(__file__).resolve().parents[3] / configured).resolve()


def _required_model_files(path: Path) -> list[str]:
    required = ["config.json", "tokenizer_config.json"]
    if not (path / "tokenizer.json").exists() and not (path / "spiece.model").exists():
        required.append("tokenizer.json or spiece.model")
    if not any((path / name).exists() for name in ("model.safetensors", "pytorch_model.bin")):
        required.append("model.safetensors or pytorch_model.bin")
    return required


def status() -> tuple[bool, str, dict[str, str]]:
    path = model_path()
    missing = _required_model_files(path) if path.exists() else ["model directory"]
    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except ImportError:
        cuda_available = False
    details = {
        "model_path": str(path),
        "device": _device or ("cuda" if cuda_available else "cpu"),
        "model_type": "fine-tuned FLAN-T5",
    }
    if missing:
        details["missing_files"] = ", ".join(missing)
        return False, f"Model unavailable — missing {', '.join(missing)}.", details
    return True, "Configured fine-tuned FLAN-T5 model is available.", details


def _load() -> tuple[Any, Any, str]:
    global _model, _tokenizer, _device
    if _model is not None and _tokenizer is not None and _device is not None:
        return _tokenizer, _model, _device
    with _lock:
        if _model is not None and _tokenizer is not None and _device is not None:
            return _tokenizer, _model, _device
        available, message, _ = status()
        if not available:
            raise ModelUnavailableError(message)
        path = model_path()
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            _tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
            _model = AutoModelForSeq2SeqLM.from_pretrained(path, local_files_only=True)
            _device = "cuda" if torch.cuda.is_available() and get_settings().story_model_device in {"auto", "cuda"} else "cpu"
            if get_settings().story_model_device == "cpu":
                _device = get_settings().story_model_device
            _model.to(_device)
            _model.eval()
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            _tokenizer = _model = _device = None
            raise ModelUnavailableError(f"Unable to load model from {path}: {exc}") from exc
    return _tokenizer, _model, _device


def load_model() -> None:
    """Load the configured model and tokenizer once during application startup."""
    _load()


def _parse_output(raw: str, request: RefinementRequest) -> tuple[str, list[AcceptanceCriterion], list[str]]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else text
    try:
        payload = json.loads(candidate)
        story = str(payload["user_story"]).strip()
        criteria = [
            AcceptanceCriterion(id=str(item.get("id", f"AC{index}")), given=str(item["given"]).strip(),
                                when=str(item["when"]).strip(), then=str(item["then"]).strip())
            for index, item in enumerate(payload["acceptance_criteria"], start=1)
        ]
        assumptions = [str(item).strip() for item in payload.get("unsupported_assumptions", []) if str(item).strip()]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise InvalidModelOutputError(
            "The configured model returned invalid structured output; expected JSON with "
            "user_story and acceptance_criteria."
        ) from exc
    if not story or not criteria or any(not value for item in criteria for value in (item.given, item.when, item.then)):
        raise InvalidModelOutputError("The configured model returned an incomplete story or acceptance criteria.")
    return story, criteria, assumptions


def generate_refinement(request: RefinementRequest) -> RefinedStory:
    import torch

    started = time.perf_counter()
    tokenizer, model, device = _load()
    context = "\n".join(filter(None, [
        f"Actor: {request.user_role}",
        f"Feature/module: {request.feature_module}",
        f"Business goal: {request.business_goal}",
        f"Related requirements: {request.related_requirements}",
        f"Existing system context: {request.existing_system_context or request.project_context}",
        f"Additional constraints: {request.additional_constraints}",
    ]))
    prompt = (
        "Generate JSON only with keys user_story, acceptance_criteria, and unsupported_assumptions. "
        "user_story must be one Agile story in the form 'As a ..., I want ..., so that ...'. "
        "acceptance_criteria must contain testable objects with id, given, when, then.\n"
        f"Validated requirement: {request.validated_requirement}\nContext:\n{context or 'None'}"
    )
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    inputs = {key: value.to(device) for key, value in inputs.items()}
    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=512, num_beams=4, do_sample=False)
    raw = tokenizer.decode(generated[0], skip_special_tokens=True)
    story, criteria, assumptions = _parse_output(raw, request)
    quality = validate_story_quality(story, criteria, request.validated_requirement, assumptions)
    scores = QualityScores(
        invest={key: True for key in ("independent", "negotiable", "valuable", "estimable", "small", "testable")},
        invest_score=1.0 if quality.valid else 0.5,
        completeness=1.0 if criteria else 0.0,
        clarity=1.0 if quality.checks["user_story_format"] else 0.0,
        testability=1.0 if quality.checks["given_when_then_complete"] else 0.0,
        consistency=1.0 if not any(item.code == "duplicate_criterion" for item in quality.errors) else 0.0,
        context_relevance=1.0 if context else 0.0,
    )
    return RefinedStory(
        requirement_id=request.requirement_id, story_id=f"{request.requirement_id}-S1",
        user_story=story, acceptance_criteria=criteria, quality_scores=scores,
        unsupported_assumptions=assumptions, processing_time_ms=int((time.perf_counter() - started) * 1000),
        model_metadata={"model_version": "fine-tuned-FLAN-T5", "requires_human_review": "true"},
    )
