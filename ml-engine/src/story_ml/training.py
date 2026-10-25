"""Optional LoRA fine-tuning with explicit readiness and confirmation checks."""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrainingConfig:
    model_name: str = "google/flan-t5-small"
    data_dir: str = "../Datasets/story-refinement"
    output_dir: str = "../Datasets/story-refinement/models/story-refinement-lora"
    checkpoint_dir: str = "../Datasets/story-refinement/checkpoints"
    seed: int = 42
    num_train_epochs: float = 1.0
    learning_rate: float = 0.0002
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 8
    max_length: int = 1024
    allow_cpu: bool = False
    license_confirmed: bool = False


def load_config(path: Path) -> TrainingConfig:
    values = json.loads(path.read_text(encoding="utf-8"))
    return TrainingConfig(**values)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def readiness_report(config: TrainingConfig) -> dict[str, Any]:
    data_dir = Path(config.data_dir).resolve()
    train = _read_jsonl(data_dir / "splits" / "train.jsonl")
    validation = _read_jsonl(data_dir / "splits" / "validation.jsonl")
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        torch_version = torch.__version__
    except ImportError:
        cuda_available = False
        torch_version = None
    blockers = []
    if not train or not validation:
        blockers.append("Non-empty reviewed train and validation splits are required.")
    if not config.license_confirmed:
        blockers.append("Confirm that the selected model licence permits this research use.")
    if not cuda_available and not config.allow_cpu:
        blockers.append("No CUDA device is available; set allow_cpu=true only for a small experimental run.")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "train_examples": len(train),
        "validation_examples": len(validation),
        "cuda_available": cuda_available,
        "torch_version": torch_version,
        "python_version": platform.python_version(),
    }


def _prompt(record: dict[str, Any]) -> str:
    return (
        "### Requirement\n"
        f"{record['requirement_text']}\n"
        "### Context\n"
        f"{record['project_context']}\n"
        "### Role\n"
        f"{record['role']}\n"
        "### Expected JSON\n"
        "Return JSON with exactly these top-level keys: "
        "user_story, acceptance_criteria, unsupported_assumptions."
    )


def _target(record: dict[str, Any]) -> str:
    return json.dumps(
        {
            "user_story": record["target_user_story"],
            "acceptance_criteria": [
                {
                    "id": str(item.get("id") or f"AC{index}"),
                    "given": item["given"],
                    "when": item["when"],
                    "then": item["then"],
                }
                for index, item in enumerate(record["acceptance_criteria"], start=1)
            ],
            "unsupported_assumptions": record["assumptions"],
        },
        ensure_ascii=True,
    )


def run_training(config: TrainingConfig, confirm: bool = False) -> dict[str, Any]:
    report = readiness_report(config)
    if not confirm:
        raise RuntimeError("Training is disabled until the configuration is reviewed and --confirm is supplied.")
    if not report["ready"]:
        raise RuntimeError("Training cannot start: " + " ".join(report["blockers"]))
    try:
        from datasets import load_dataset
        from peft import LoraConfig, get_peft_model
        from transformers import (
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            DataCollatorForSeq2Seq,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Optional fine-tuning dependencies are missing. Install the ml-engine[training] extra."
        ) from exc

    data_dir = Path(config.data_dir).resolve()
    output_dir = Path(config.output_dir).resolve()
    dataset = load_dataset(
        "json",
        data_files={
            "train": str(data_dir / "splits" / "train.jsonl"),
            "validation": str(data_dir / "splits" / "validation.jsonl"),
        },
    )
    tokenizer = AutoTokenizer.from_pretrained(config.model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(config.model_name)
    model = get_peft_model(
        model,
        LoraConfig(
            r=8,
            lora_alpha=16,
            lora_dropout=0.05,
            target_modules=["q_proj", "v_proj"],
            task_type="CAUSAL_LM",
        ),
    )

    def tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        records = [
            _prompt({key: batch[key][index] for key in batch})
            for index in range(len(batch["requirement_text"]))
        ]
        targets = [
            _target({key: batch[key][index] for key in batch})
            for index in range(len(batch["requirement_text"]))
        ]
        model_inputs = tokenizer(
            records,
            truncation=True,
            max_length=config.max_length,
        )
        model_inputs["labels"] = tokenizer(
            text_target=targets,
            truncation=True,
            max_length=config.max_length,
        )["input_ids"]
        return model_inputs

    tokenized = dataset.map(tokenize, batched=True, remove_columns=dataset["train"].column_names)
    output_dir.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=str(Path(config.checkpoint_dir).resolve()),
        num_train_epochs=config.num_train_epochs,
        learning_rate=config.learning_rate,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        seed=config.seed,
        report_to="none",
        fp16=bool(report["cuda_available"]),
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        tokenizer=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer, model=model),
    )
    trainer.train()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    manifest = {
        "trained_at": datetime.now(UTC).isoformat(),
        "config": asdict(config),
        "readiness": report,
        "python_version": sys.version,
    }
    (output_dir / "training_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
