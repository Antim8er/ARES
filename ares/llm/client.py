from __future__ import annotations
import os
import json
import urllib.request
import urllib.error
from typing import Optional
from rich.console import Console

from ares.config import DEFAULT_BASE_URL, DEFAULT_API_KEY

console = Console()


class LLMConnectionError(Exception):
    """Raised when the LLM server cannot be reached."""
    pass


class DummyMessage:
    def __init__(self, content: str):
        self.content = content


class DummyChoice:
    def __init__(self, message: DummyMessage):
        self.message = message


class DummyResponse:
    def __init__(self, choices: list[DummyChoice]):
        self.choices = choices


def normalize_base_url(url: str) -> str:
    """Normalize base URL ensuring /v1 suffix for OpenAI-compatible endpoints."""
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


class ChatCompletions:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = normalize_base_url(base_url)
        self.api_key = api_key

    def create(self, model: str, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1000):
        endpoints_to_try = [self.base_url]

        # If pointing to default LM Studio and it might not be up, register Ollama as fallback
        if "1234" in self.base_url:
            endpoints_to_try.append("http://localhost:11434/v1")
        elif "11434" in self.base_url:
            endpoints_to_try.append("http://localhost:1234/v1")

        last_error = None

        for endpoint in endpoints_to_try:
            url = f"{endpoint}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            data = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers=headers
            )

            try:
                # 120 second timeout for local/remote model processing
                with urllib.request.urlopen(req, timeout=120) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    content = result["choices"][0]["message"]["content"]
                    self.base_url = endpoint
                    return DummyResponse([DummyChoice(DummyMessage(content))])
            except (urllib.error.URLError, ConnectionError, OSError) as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                break

        # If all candidates failed:
        error_msg = (
            f"\n[bold red]Unable to connect to LLM server at:[/bold red] {self.base_url}\n"
            f"[dim]Detail: {last_error}[/dim]\n\n"
            "[bold yellow]Troubleshooting:[/bold yellow]\n"
            "  1. [cyan]LM Studio:[/cyan] Open LM Studio -> Local Server -> Start Server (default: http://localhost:1234/v1)\n"
            "  2. [cyan]Ollama:[/cyan] Run `ollama serve` (default: http://localhost:11434/v1)\n"
            "  3. [cyan]Custom URL / Cloud:[/cyan] Set `ARES_LLM_URL` in .env or pass `--url <endpoint>`\n"
        )
        console.print(error_msg)
        raise LLMConnectionError(str(last_error))


class Chat:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.completions = ChatCompletions(base_url, api_key=api_key)


class LocalClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.chat = Chat(base_url, api_key=api_key)


def get_client(base_url: Optional[str] = None, api_key: Optional[str] = None) -> LocalClient:
    resolved_url = base_url or DEFAULT_BASE_URL
    resolved_key = api_key or DEFAULT_API_KEY
    return LocalClient(resolved_url, api_key=resolved_key)
