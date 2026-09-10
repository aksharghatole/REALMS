from abc import ABC, abstractmethod
import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


class AIProvider(ABC):
    @abstractmethod
    def generate_npc_response(self, context: str, player_message: str) -> str: ...

    @abstractmethod
    def interpret_player_input(self, text: str) -> dict[str, object]: ...

    def summarize_memory(self, transcript: str) -> str:
        return transcript[-500:]

    def generate_narration(self, event: str) -> str:
        return event

    @property
    def name(self) -> str:
        return self.__class__.__name__


class NullAIProvider(AIProvider):
    def generate_npc_response(self, context: str, player_message: str) -> str:
        return ""

    def interpret_player_input(self, text: str) -> dict[str, object]:
        return {"intent": "TALK", "text": text}


class FallbackAIProvider(NullAIProvider):
    def generate_npc_response(self, context: str, player_message: str) -> str:
        return ""


class CompatibleHTTPProvider(AIProvider):
    """Optional OpenAI-compatible client using only the Python standard library."""

    def __init__(self, base_url: str, model: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    @property
    def available(self) -> bool:
        try:
            with urlopen(Request(f"{self.base_url}/models"), timeout=0.5):
                return True
        except OSError:
            return False

    def _chat(self, system: str, user: str) -> str:
        payload = json.dumps({"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0.7}).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            with urlopen(Request(f"{self.base_url}/chat/completions", data=payload, headers=headers), timeout=8) as response:
                body = json.loads(response.read().decode())
            return str(body["choices"][0]["message"]["content"])
        except (OSError, URLError, KeyError, IndexError, json.JSONDecodeError):
            return ""

    def generate_npc_response(self, context: str, player_message: str) -> str:
        return self._chat("You are an NPC in a grounded persistent RPG. Never invent facts outside the context. If you do not know, say so.", f"NPC context:\n{context}\n\nPlayer message:\n{player_message}")

    def interpret_player_input(self, text: str) -> dict[str, object]:
        raw = self._chat("Return only JSON with an intent field. Allowed intents: TALK, ASK, PERSUADE, THREATEN, OFFER, PROMISE, REVEAL_INFORMATION, GIVE_ITEM, ATTACK, FLEE.", text)
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) and isinstance(value.get("intent"), str) else {"intent": "TALK", "text": text}
        except json.JSONDecodeError:
            return {"intent": "TALK", "text": text}


class OllamaProvider(CompatibleHTTPProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None):
        super().__init__(base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"), model or os.getenv("OLLAMA_MODEL", "llama3.2"))


class OpenAIProvider(CompatibleHTTPProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        super().__init__(os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"), model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"), api_key or os.getenv("OPENAI_API_KEY", ""))


def configured_provider() -> AIProvider:
    return provider_for_mode(os.getenv("AI_PROVIDER", "none"))


def provider_for_mode(mode: str) -> AIProvider:
    mode = mode.lower()
    if mode in {"none", "off", "fallback"}:
        return FallbackAIProvider()
    if mode == "ollama":
        return OllamaProvider()
    if mode == "openai" and os.getenv("OPENAI_API_KEY"):
        return OpenAIProvider()
    if mode == "auto":
        ollama = OllamaProvider()
        if ollama.available:
            return ollama
        if os.getenv("OPENAI_API_KEY"):
            return OpenAIProvider()
        return FallbackAIProvider()
    return FallbackAIProvider()