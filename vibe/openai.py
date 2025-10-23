"""Minimal OpenAI-compatible client wrapper that supports custom endpoints.

This wrapper sends a JSON payload {"model": model, "prompt": prompt} as POST
to OPENAI_API_URL with Authorization Bearer header. It returns the first text
it can find in the JSON response (common shapes supported). Adjust parse_response
for non-standard APIs.
"""
from typing import Optional
import requests


class OpenAIClient:
    def __init__(self, api_url: str, api_key: str, timeout: float = 20.0):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout

    def generate(self, prompt: str, model: str = "openai/gpt-oss-20b") -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "prompt": prompt}
        try:
            resp = requests.post(self.api_url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            return self.parse_response(resp.json())
        except Exception:
            raise

    def parse_response(self, data: dict) -> str:
        if not isinstance(data, dict):
            return str(data)
        # common fields: 'choices' -> [{'text': ...}] or 'output' keys
        if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
            first = data["choices"][0]
            if isinstance(first, dict) and "text" in first:
                return first["text"]
        for key in ("text", "output", "result", "message"):
            if key in data:
                return str(data[key])
        return str(data)
