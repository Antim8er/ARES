from __future__ import annotations
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Models that can be used by default
# Any string works for LM Studio as it routes to the loaded model
DEFAULT_MODEL = os.getenv("ARES_DEFAULT_MODEL", "local-model")


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)

# Suggested models for LM Studio:
# - bartowski/Qwen2.5-14B_Uncensored_Instruct-GGUF
# - Qwen/Qwen2.5-Coder-7B-Instruct-GGUF
# - meta-llama/Llama-3.1-8B-Instruct-GGUF