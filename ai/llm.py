"""Thin LLM layer. The solver never depends on it; every caller has a non-AI fallback."""
import json
import os
import re
from typing import Protocol

MODELS = {"parse": "claude-haiku-5-5", "intent": "claude-haiku-5-5", "explain": "claude-haiku-5-5",
          "rules": "claude-sonnet-5-5", "eval": "claude-sonnet-5-5"}


class LLMClient(Protocol):
    def complete(self, system: str, user: str, model: str) -> str: ...


class AnthropicClient:
    def __init__(self, api_key=None):
        import anthropic
        self._c = anthropic.Anthropic(api_key=api_key)

    def complete(self, system: str, user: str, model: str) -> str:
        r = self._c.messages.create(model=model, max_tokens=1500, system=system,
                                    messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in r.content if b.type == "text")


def get_client():
    key = os.environ.get("ANTHROPIC_API_KEY")
    return AnthropicClient(key) if key else None


def extract_json(text: str):
    text = re.sub(r"```(?:json)?", "", text)
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j < i:
        raise ValueError("no JSON object in model output")
    return json.loads(text[i:j + 1])
