"""Local transformer service for refining validated software requirements."""

import os

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


MODEL_PATH = os.getenv(
    "STORY_MODEL_PATH",
    "../../models/story-refinement-model",
)

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_PATH)

device = "cuda" if torch.cuda.is_available() else "cpu"

model.to(device)
model.eval()


def generate_refinement(
    requirement: str,
    domain: str = "General",
) -> str:
    prompt = (
        "Refine the following software requirement into "
        "one Agile user story and five testable acceptance criteria.\n\n"
        f"Domain: {domain}\n"
        f"Validated Requirement: {requirement}"
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )

    inputs = {key: value.to(device) for key, value in inputs.items()}

    with torch.no_grad():
        generated = model.generate(
            **inputs,
            max_new_tokens=512,
            num_beams=4,
            do_sample=False,
        )

    return tokenizer.decode(generated[0], skip_special_tokens=True)
