"""Where this component's datasets and trained models live.

They are never stored in the repository: they go in AgilePlatform/Datasets/story-refinement,
next to the repositories, or wherever the STORY_DATA_DIR environment variable points.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = Path(os.environ.get("STORY_DATA_DIR", REPO_ROOT.parent / "Datasets" / "story-refinement")).resolve()
