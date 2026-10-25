"""Where this component's datasets and trained models live.

They are never stored in the repository: they go in AgilePlatform/Datasets/story-refinement,
next to the repositories, or wherever the STORY_DATA_DIR environment variable points.
"""

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = Path(
    os.environ.get("STORY_DATA_DIR", REPO_ROOT.parent / "Datasets" / "story-refinement")
).resolve()


@dataclass(frozen=True)
class LLMSettings:
    """Local-only inference settings. No cloud provider is supported."""

    base_url: str = os.environ.get("STORY_LLM_BASE_URL", "http://localhost:11434")
    model: str = os.environ.get("STORY_LLM_MODEL", "llama3.2")
    timeout_seconds: float = float(os.environ.get("STORY_LLM_TIMEOUT_SECONDS", "30"))
    candidate_count: int = int(os.environ.get("STORY_CANDIDATE_COUNT", "3"))


@dataclass(frozen=True)
class RankingSettings:
    """Documented default weights for candidate ranking."""

    invest: float = float(os.environ.get("STORY_WEIGHT_INVEST", "0.20"))
    clarity: float = float(os.environ.get("STORY_WEIGHT_CLARITY", "0.15"))
    completeness: float = float(os.environ.get("STORY_WEIGHT_COMPLETENESS", "0.15"))
    testability: float = float(os.environ.get("STORY_WEIGHT_TESTABILITY", "0.15"))
    consistency: float = float(os.environ.get("STORY_WEIGHT_CONSISTENCY", "0.15"))
    context_relevance: float = float(
        os.environ.get("STORY_WEIGHT_CONTEXT_RELEVANCE", "0.10")
    )
    acceptance_criteria_coverage: float = float(
        os.environ.get("STORY_WEIGHT_AC_COVERAGE", "0.10")
    )

    def as_dict(self) -> dict[str, float]:
        return {key: value for key, value in self.__dict__.items()}
