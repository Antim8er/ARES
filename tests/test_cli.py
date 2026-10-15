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


def test_normalize_command():
    """Verify command normalization for deduplication."""
    from ares.cli import normalize_command
    assert normalize_command("nmap -p- example.com") == "nmap -p- example.com"
    assert normalize_command("NMAP   -p-   example.com") == "nmap -p- example.com"
    assert normalize_command("nmap.exe -p- example.com") == "nmap -p- example.com"
    assert normalize_command("") == ""


def test_clean_command_output_removes_nmap_stats():
    """Verify transient Nmap progress lines are filtered while scan results remain intact."""
    from ares.cli import clean_command_output
    raw_nmap_output = """Starting Nmap 7.80 ( https://nmap.org ) at 2026-10-15 23:01 India Standard Time
Stats: 0:06:38 elapsed; 0 hosts completed (1 up), 1 undergoing SYN Stealth Scan
SYN Stealth Scan Timing: About 19.94% done; ETC: 23:34 (0:26:30 remaining)
Stats: 0:11:50 elapsed; 0 hosts completed (1 up), 1 undergoing SYN Stealth Scan
SYN Stealth Scan Timing: About 32.50% done; ETC: 23:37 (0:24:30 remaining)
Nmap scan report for example.com (23.227.38.32)
Host is up (0.96s latency).
PORT     STATE SERVICE
80/tcp   open  http
443/tcp  open  https
8080/tcp open  http-proxy

Nmap done: 1 IP address (1 host up) scanned in 2411.91 seconds"""

    cleaned = clean_command_output(raw_nmap_output)
    assert "Stats:" not in cleaned
    assert "SYN Stealth Scan Timing:" not in cleaned
    assert "80/tcp   open  http" in cleaned
    assert "443/tcp  open  https" in cleaned
    assert "8080/tcp open  http-proxy" in cleaned
    assert "Nmap done:" in cleaned


def test_smart_truncate():
    """Ensure smart_truncate preserves findings in both header and tail."""
    from ares.cli import smart_truncate
    short_text = "Short output"
    assert smart_truncate(short_text, max_chars=100) == short_text

    long_text = "HEADER_INFO\n" + ("x" * 2000) + "\nTAIL_FINDINGS_PORT_80_OPEN"
    truncated = smart_truncate(long_text, max_chars=500)
    assert "HEADER_INFO" in truncated
    assert "TAIL_FINDINGS_PORT_80_OPEN" in truncated
    assert "output truncated for brevity" in truncated
    assert len(truncated) <= 500


def test_get_tools_context():
    """Ensure tools context provides available and unavailable tool lists."""
    from ares.cli import get_tools_context
    ctx = get_tools_context()
    assert "Available CLI tools" in ctx
    assert "UNAVAILABLE tools" in ctx


def test_has_placeholders():
    """Verify placeholder tokens are correctly detected."""
    from ares.cli import has_placeholders
    assert has_placeholders("nmap <target-ip>") == "<target-ip>"
    assert has_placeholders("curl [target]") == "[target]"
    assert has_placeholders("nikto -h {ip}") == "{ip}"
    assert has_placeholders("ping TARGET_IP") == "TARGET_IP"
    assert has_placeholders("nmap -sV example.com") is None


def test_session_command_regex_extraction():
    """Ensure commands from past reports are correctly extracted when resuming sessions."""
    import re
    from ares.cli import normalize_command
    report = """# Pentest Report
### Step 1: `nmap -p- example.com`
Output: some output
### Step 2: `nikto -h example.com`
Output: some error
"""
    executed = {}
    for match in re.finditer(r"### Step (\d+): `(.*?)`", report):
        step_num = int(match.group(1))
        cmd_norm = normalize_command(match.group(2))
        if cmd_norm:
            executed[cmd_norm] = step_num

    assert "nmap -p- example.com" in executed
    assert executed["nmap -p- example.com"] == 1
    assert "nikto -h example.com" in executed
    assert executed["nikto -h example.com"] == 2



