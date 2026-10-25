"""Review and optionally run the external LoRA fine-tuning pipeline."""

import argparse
from pathlib import Path

from story_ml.training import load_config, readiness_report, run_training


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    report = readiness_report(config)
    print(report)
    if args.check_only:
        return
    print(run_training(config, confirm=args.confirm))


if __name__ == "__main__":
    main()
