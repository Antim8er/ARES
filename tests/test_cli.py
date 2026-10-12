from __future__ import annotations
import ares
from ares.cli import app
from ares.config import DEFAULT_MODEL, get_env
from ares.core.utils import suggest_safe_command
from ares.llm.client import DummyMessage, DummyChoice, DummyResponse, get_client
from ares.llm.prompts import SYSTEM_PROMPT, NEXT_COMMAND_PROMPT
from typer.testing import CliRunner

runner = CliRunner()


def test_version():
    """Verify package version is defined and synchronized."""
    assert ares.__version__ == "0.1.0"


def test_cli_help():
    """Ensure the top-level CLI help command executes successfully."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert len(result.output) > 0


def test_config_defaults():
    """Ensure default configuration and environment fallback behave correctly."""
    assert isinstance(DEFAULT_MODEL, str)
    assert get_env("NON_EXISTENT_KEY_12345", "fallback") == "fallback"


def test_prompts_exported():
    """Ensure prompt templates are defined and consistent."""
    assert isinstance(SYSTEM_PROMPT, str)
    assert isinstance(NEXT_COMMAND_PROMPT, str)
    assert SYSTEM_PROMPT == NEXT_COMMAND_PROMPT


def test_utils_safe_command():
    """Verify safe command suggestion utility returns expected recommendations."""
    nmap_suggestion = suggest_safe_command("scan ports", "127.0.0.1")
    assert "nmap" in nmap_suggestion
    assert "127.0.0.1" in nmap_suggestion

    http_suggestion = suggest_safe_command("check web http headers", "example.com")
    assert "curl" in http_suggestion
    assert "example.com" in http_suggestion

    default_suggestion = suggest_safe_command("unknown task", "127.0.0.1")
    assert "No specific safe command" in default_suggestion


def test_llm_dummy_objects():
    """Ensure LLM client response wrappers function as intended."""
    msg = DummyMessage("hello world")
    choice = DummyChoice(msg)
    response = DummyResponse([choice])

    assert response.choices[0].message.content == "hello world"


def test_llm_client_instantiation():
    """Ensure local client initializes with default or configured base URL."""
    client = get_client()
    assert client.chat is not None
    assert client.chat.completions is not None


def test_llm_client_custom_options():
    """Ensure client properly receives custom base URL and API key."""
    from ares.llm.client import normalize_base_url, LLMConnectionError
    assert normalize_base_url("http://localhost:11434") == "http://localhost:11434/v1"
    assert normalize_base_url("http://localhost:11434/v1") == "http://localhost:11434/v1"

    client = get_client(base_url="http://custom-host:8000", api_key="secret-token")
    assert client.chat.completions.base_url == "http://custom-host:8000/v1"
    assert client.chat.completions.api_key == "secret-token"
    assert issubclass(LLMConnectionError, Exception)

