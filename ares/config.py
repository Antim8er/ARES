from __future__ import annotations
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Models that can be used by default
# Any string works for LM Studio as it routes to the loaded model
DEFAULT_MODEL = os.getenv("ARES_DEFAULT_MODEL", "local-model")

# Base URL resolution: checks ARES_LLM_URL, OPENAI_BASE_URL, OLLAMA_BASE_URL, LMSTUDIO_BASE_URL
DEFAULT_BASE_URL = (
    os.getenv("ARES_LLM_URL")
    or os.getenv("OPENAI_BASE_URL")
    or os.getenv("OLLAMA_BASE_URL")
    or os.getenv("LMSTUDIO_BASE_URL")
    or "http://localhost:1234/v1"
)

# API key if using authenticated proxy, OpenRouter, or cloud endpoint
DEFAULT_API_KEY = os.getenv("ARES_API_KEY") or os.getenv("OPENAI_API_KEY")


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)

# Suggested models for LM Studio / Ollama:
# - bartowski/Qwen2.5-14B_Uncensored_Instruct-GGUF
# - Qwen/Qwen2.5-Coder-7B-Instruct-GGUF
# - meta-llama/Llama-3.1-8B-Instruct-GGUF
# - deepseek-r1 / qwen2.5 (via Ollama)