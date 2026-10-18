
import json

import httpx


class LocalLLM:
    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate_json(self, prompt: str) -> dict:
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=180.0,
        )
        response.raise_for_status()

        result = response.json()
        return json.loads(result["response"])
