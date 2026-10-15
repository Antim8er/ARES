#!/usr/bin/env python
"""Ares CLI – The Most Powerful AI Powered Cybersecurity Tool"""

from __future__ import annotations
import os
import sys
from typing import Optional
import subprocess
import platform
import re
import json
import shlex
import shutil
from urllib.parse import urlparse
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Confirm
from rich.status import Status
from rich.text import Text
from rich import box

# Fix Windows Console Encoding & Subprocess Python UTF-8
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

console = Console()

# Core configuration & LLM client
from ares.config import DEFAULT_MODEL, DEFAULT_BASE_URL, DEFAULT_API_KEY
from ares.llm.client import get_client, LLMConnectionError
from ares.llm.prompts import NEXT_COMMAND_PROMPT

app = typer.Typer(
    name="ares",
    help="The most powerful AI powered cybersecurity tool",
    add_completion=False,
    no_args_is_help=False,
)

BANNER = r"""
[bold green]  ###                      [/bold green]
[bold green]    ###                    [/bold green] [bold white]A . R . E . S .[/bold white]
[bold green]      ###                  [/bold green] [bold dim white]AUTONOMOUS RECONNAISSANCE[/bold dim white]
[bold green]        ###    #########   [/bold green] [bold dim white]& EXPLOITATION SYSTEM[/bold dim white]
[bold green]      ###                  [/bold green] 
[bold green]    ###                    [/bold green] [bold green][ AI-POWERED PEN_TEST CLI ][/bold green]
[bold green]  ###                      [/bold green]
"""

def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


# ---------------------------------------------------------------------------
# Guardrail & Tool helpers
# ---------------------------------------------------------------------------

KNOWN_TOOLS = ["nmap", "curl", "python", "git", "powershell", "sqlmap", "nikto", "gobuster", "ffuf", "hydra", "wpscan"]

SHELL_BUILTINS = {
    "cmd", "powershell", "pwsh", "bash", "sh", "zsh",
    "echo", "cd", "dir", "type", "findstr", "where", "set", "cls",
    "exit", "del", "copy", "move", "mkdir", "rmdir",
    "invokewebrequest", "invokerestmethod", "testnetconnection", "getcontent", "startprocess"
}

def ensure_python_in_path():
    """Ensure running Python directory and scripts are in PATH so CLI/inline scripts work reliably."""
    py_dir = os.path.dirname(sys.executable)
    scripts_dir = os.path.join(py_dir, "Scripts")
    path_entries = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    new_entries = []
    if py_dir not in path_entries:
        new_entries.append(py_dir)
    if scripts_dir not in path_entries:
        new_entries.append(scripts_dir)
    if new_entries:
        os.environ["PATH"] = os.pathsep.join(new_entries + path_entries)

def refresh_system_path():
    """Refresh PATH environment variable from Windows registry without wiping runtime paths."""
    if platform.system() == "Windows":
        try:
            import winreg
            sys_path = ""
            user_path = ""
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
                sys_path = winreg.ExpandEnvironmentStrings(winreg.QueryValueEx(key, "Path")[0])
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                    user_path = winreg.ExpandEnvironmentStrings(winreg.QueryValueEx(key, "Path")[0])
            except FileNotFoundError:
                user_path = ""
            current_paths = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
            registry_paths = [p for p in (sys_path + ";" + user_path).split(";") if p]
            merged = []
            for p in current_paths + registry_paths:
                if p not in merged:
                    merged.append(p)
            os.environ["PATH"] = os.pathsep.join(merged)
        except Exception:
            pass
    ensure_python_in_path()

def get_tools_context() -> str:
    """Return summary of available and unavailable CLI tools on this system."""
    installed = []
    unavailable = []
    for t in KNOWN_TOOLS:
        if shutil.which(t):
            installed.append(t)
        else:
            unavailable.append(t)
    return (
        f"Available CLI tools on this machine: {', '.join(installed) if installed else 'None detected'}\n"
        f"UNAVAILABLE tools: {', '.join(unavailable)} "
        f"(CRITICAL: Do NOT run commands for unavailable tools. Use available tools like Python, curl, or PowerShell instead.)"
    )

def normalize_command(command: str) -> str:
    """Normalize command for deduplication (lowercase binary, normalized whitespace)."""
    if not command:
        return ""
    tokens = command.strip().split()
    if not tokens:
        return ""
    first_token = tokens[0].lower().strip('"').strip("'")
    if first_token.endswith(".exe"):
        first_token = first_token[:-4]
    tokens[0] = first_token
    return " ".join(tokens)

def clean_command_output(output: str) -> str:
    """Clean transient progress/stats lines from command output so key findings aren't crowded out."""
    if not output:
        return ""
    output = strip_ansi(output)
    lines = output.splitlines()
    filtered_lines = []
    noise_patterns = [
        re.compile(r"^Stats:\s+\d+:\d+:\d+\s+elapsed", re.IGNORECASE),
        re.compile(r".*Timing:\s+About\s+\d+", re.IGNORECASE),
        re.compile(r"^About\s+\d+\.\d+%\s+done", re.IGNORECASE),
        re.compile(r"^Initiating\s+.*Scan\s+at\b", re.IGNORECASE),
        re.compile(r"^Completed\s+.*Scan\s+at\b", re.IGNORECASE),
        re.compile(r"^\s*\[[=\s>-]+\]\s*\d+%", re.IGNORECASE),
        re.compile(r"^\s*%\s+Total\b", re.IGNORECASE),
        re.compile(r"^\s*Dload\s+Upload\b", re.IGNORECASE),
        re.compile(r"^\s*\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\b", re.IGNORECASE),
    ]
    for line in lines:
        stripped = line.strip()
        if not stripped:
            filtered_lines.append("")
            continue
        if any(pat.search(stripped) for pat in noise_patterns):
            continue
        filtered_lines.append(line)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(filtered_lines)).strip()
    return cleaned

def smart_truncate(text: str, max_chars: int = 1500) -> str:
    """Intelligently truncate long output preserving both the header and findings/tail."""
    if not text or len(text) <= max_chars:
        return text
    head_size = int(max_chars * 0.3)
    tail_size = max_chars - head_size - 60
    head = text[:head_size].rstrip()
    tail = text[-tail_size:].lstrip()
    return f"{head}\n\n... [output truncated for brevity — findings below] ...\n\n{tail}"

def sanitize_target(raw_target: str) -> str:
    """Extract clean hostname/IP from a target that may be a full URL.

    Examples:
        https://example.com/path  -> example.com
        http://10.0.0.1:8080/     -> 10.0.0.1
        scanme.nmap.org           -> scanme.nmap.org  (unchanged)
    """
    raw_target = raw_target.strip()
    if "://" in raw_target:
        parsed = urlparse(raw_target)
        return parsed.hostname or raw_target
    # Strip trailing slashes from bare domains
    return raw_target.rstrip("/")


# Regex to detect unreplaced placeholder tokens like <target-ip>, [target], {ip}, TARGET_IP
_PLACEHOLDER_RE = re.compile(
    r'<[a-zA-Z][a-zA-Z0-9_\-]*>'        # <target-ip>, <url>, <domain>
    r'|\[[a-zA-Z][a-zA-Z0-9_\-]*\]'      # [target], [IP]
    r'|\{[a-zA-Z][a-zA-Z0-9_\-]*\}'      # {target}, {ip}
    r'|(?<!\w)TARGET_IP(?:_ADDRESS)?(?!\w)'  # TARGET_IP, TARGET_IP_ADDRESS
)


def has_placeholders(command: str) -> str | None:
    """Return the first placeholder token found in a command, or None if clean."""
    match = _PLACEHOLDER_RE.search(command)
    return match.group(0) if match else None


def infer_tool_from_command(command: str) -> str:
    """Extract the tool binary name from the first token of a command.

    Strips .exe suffix on Windows for consistency.
    """
    if not command:
        return ""
    first_token = command.split()[0].strip('"').strip("'")
    if first_token.lower().endswith(".exe"):
        first_token = first_token[:-4]
    return first_token


@app.command("ask")
def ask(
    question: Optional[str] = typer.Argument(None, help="Pentest task or question (optional, will prompt if empty)"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="Model"),
    simulate: bool = typer.Option(True, "--simulate/--no-simulate"),
    real: bool = typer.Option(False, "--real", help="Execute commands for real"),
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Target e.g. scanme.nmap.org"),
    auto_confirm: bool = typer.Option(False, "--auto-confirm", help="Auto-confirm all executions (dangerous)"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="LLM endpoint URL (e.g. http://localhost:11434/v1 for Ollama)"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="API key for authenticated endpoints"),
):
    console.print(Panel(
        Text.from_markup(BANNER, justify="left", style="bold"),
        border_style="magenta",
        box=box.DOUBLE,
        padding=(1, 2),
        expand=False,
    ))

    os_name = platform.system()
    console.print(f"[bold cyan]Detected OS:[/bold cyan] {os_name}")

    ensure_python_in_path()
    refresh_system_path()

    client = get_client(base_url=url, api_key=api_key)
    console.print(f"[dim]→ Using model: {model} | Endpoint: {client.chat.completions.base_url}[/dim]")
    console.print(f"[dim]→ {get_tools_context().splitlines()[0]}[/dim]")

    if real:
        simulate = False
        console.print("[bold yellow]REAL EXECUTION MODE ACTIVE — USE WITH CAUTION[/bold yellow]")

    # --- Sanitize target: strip URL scheme/path so tools get a clean hostname ---
    if target:
        raw_target = target
        actual_target = sanitize_target(target)
        if actual_target != raw_target:
            console.print(f"[dim]→ Sanitized target: {raw_target} → {actual_target}[/dim]")
    else:
        actual_target = "None provided (Ask the user)"
    
    # Load session if it exists
    session_file = ".ares_session.json"
    executed_commands: dict[str, int] = {}
    if os.path.exists(session_file) and Confirm.ask("Found a previous session. Resume?", default=True):
        with open(session_file, 'r', encoding='utf-8') as f:
            session = json.load(f)
            report = session.get("report", "")
            previous_output = session.get("previous_output", "")
            step_count = session.get("step_count", 0)
            saved_cmds = session.get("executed_commands", [])
            if saved_cmds:
                executed_commands = {normalize_command(cmd): idx + 1 for idx, cmd in enumerate(saved_cmds)}
            else:
                for match in re.finditer(r"### Step (\d+): `(.*?)`", report):
                    step_num = int(match.group(1))
                    cmd_norm = normalize_command(match.group(2))
                    if cmd_norm:
                        executed_commands[cmd_norm] = step_num
    else:
        report = f"# Pentest Report\n**OS:** {os_name}\n**Started:** 2026-01-20\n\n## Findings & Steps\n"
        previous_output = ""
        step_count = 0

    attempted_installs = set()
    conversation_history = []

    while True:
        if not question:
            try:
                question = console.input("\n[bold magenta]Ares > [/bold magenta]")
            except (KeyboardInterrupt, EOFError):
                break
            if not question.strip():
                continue
            if question.strip().lower() in ['exit', 'quit']:
                break
        
        report += f"\n### New Task: {question} (Target: {actual_target})\n"
        initial_plan_done = False
        task_finished = False
        last_failed_command = None      # Track last command that failed
        consecutive_failures = 0        # Count back-to-back failures

        while True:
            with console.status("[bold cyan]Ares thinking...[/bold cyan]", spinner="dots12"):
                conv_text = "\n".join(conversation_history[-10:])
                context_prefix = f"Conversation History:\n{conv_text}\n\n" if conv_text else ""
                
                target_str = actual_target if actual_target != "None provided (Ask the user)" else "UNKNOWN"
                tools_summary = get_tools_context()
                
                context = (
                    f"{context_prefix}Task: {question}\n"
                    f"Target: {target_str}\n"
                    f"OS: {os_name}\n"
                    f"{tools_summary}\n"
                    f"CRITICAL: You are running on {os_name}. Use {os_name}-compatible commands (e.g. CMD or 'powershell -c' on Windows).\n"
                    f"Previous command output:\n{previous_output}\n\n"
                    f"Current report tail (findings and previous steps):\n{report[-2500:]}\n"
                )

                if not initial_plan_done:
                    context = f"User Input: {question}\n(If this is a task, create an initial high-level plan. If it's a conversational message, respond accordingly.)\n\n" + context
                    initial_plan_done = True

                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": NEXT_COMMAND_PROMPT},
                            {"role": "user", "content": context + "\n\n→ Generate the next step:"},
                        ],
                        temperature=0.25,
                        max_tokens=1000,
                    )
                except LLMConnectionError:
                    console.print("[bold red]Session stopped due to LLM connection failure.[/bold red]")
                    return

            answer = response.choices[0].message.content.strip()

            if answer == "END FLOW":
                console.print("[yellow]Session terminated by engine.[/yellow]")
                return
            
            # Clean up markdown JSON block if present
            if answer.startswith("```json"):
                answer = answer[7:]
            if answer.startswith("```"):
                answer = answer[3:]
            if answer.endswith("```"):
                answer = answer[:-3]
            answer = answer.strip()

            try:
                parsed = json.loads(answer)
            except json.JSONDecodeError:
                console.print(f"[bold red]Failed to parse LLM JSON response:[/bold red]\n{answer}")
                if step_count > 0:
                    console.print("[yellow]Retrying with schema reminder...[/yellow]")
                    previous_output = "SYSTEM: You must return valid JSON matching the schema without any additional markdown or text."
                    continue
                else:
                    console.print("[yellow]Model did not provide valid JSON. Please verify your selected model supports instruction/JSON output.[/yellow]")
                    break

            extracted_command = parsed.get("command", "")
            is_completed = parsed.get("is_task_completed", False)
            analysis = parsed.get("analysis", "")
            plan = parsed.get("plan", "")
            tool_required = parsed.get("tool_required", "")
            message_to_user = parsed.get("message_to_user", "")

            # --- Guardrail: auto-fill tool_required from command if model left it empty ---
            if extracted_command and not tool_required:
                tool_required = infer_tool_from_command(extracted_command)
                if tool_required:
                    console.print(f"[dim]→ Auto-detected tool: {tool_required}[/dim]")

            if analysis or plan or tool_required:
                panel_text = f"**Analysis:** {analysis}\n\n**Plan:** {plan}\n\n**Tool:** {tool_required}"
                console.print(Panel(
                    Markdown(panel_text),
                    title=f"[bold green]Ares • {model}[/bold green]",
                    border_style="green",
                    padding=(1, 2),
                    box=box.HEAVY_EDGE,
                ))

            if message_to_user:
                cleaned_msg = message_to_user.strip()
                if cleaned_msg.lower().rstrip(".") in ["optional", "none", "n/a", "null", "undefined"]:
                    message_to_user = ""

            if message_to_user and not extracted_command:
                console.print(f"\n[bold magenta]Ares:[/bold magenta] {message_to_user}")
                # We do not add conversational responses to the report to prevent model confusion

            if is_completed:
                task_finished = True
                console.print("[green]AI considers objective complete → stopping.[/green]")
                report += "\n\n## Final Summary\nGoal achieved or no further safe steps identified."
                break
                
            if not extracted_command:
                # If in active pentest task and AI provided a plan but forgot the command, prompt for command
                if step_count > 0 and not is_completed and not message_to_user:
                    console.print("[yellow]AI generated a plan but no command. Prompting for command...[/yellow]")
                    previous_output = (
                        f"SYSTEM: You provided a plan but left 'command' empty. "
                        f"You must provide a concrete, unexecuted CLI command in 'command' to proceed with your plan, "
                        f"or set 'is_task_completed': true if the pentest task is finished."
                    )
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        task_finished = True
                        break
                    continue

                # Remove the conversational task from the report so it doesn't pollute pentest history
                task_header = f"\n### New Task: {question} (Target: {actual_target})\n"
                if report.endswith(task_header):
                    report = report[:-len(task_header)]
                
                if message_to_user:
                    conversation_history.append(f"User: {question}")
                    conversation_history.append(f"Ares: {message_to_user}")
                
                break

            # --- Guardrail: Block commands containing unreplaced placeholders ---
            placeholder = has_placeholders(extracted_command)
            if placeholder:
                console.print(f"[bold red]⚠ Blocked command containing placeholder: {placeholder}[/bold red]")
                console.print(f"[dim]Rejected: {extracted_command}[/dim]")
                previous_output = (
                    f"SYSTEM ERROR: Your command was REJECTED because it contained the placeholder '{placeholder}'. "
                    f"Placeholders like <target-ip>, [target], {{ip}} are FORBIDDEN. "
                    f"The actual target is: {actual_target} — use it directly in your command. "
                    f"Generate a corrected command now."
                )
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    console.print("[bold red]Too many consecutive failures — stopping to prevent infinite loop.[/bold red]")
                    task_finished = True
                    report += "\n\n## Final Summary\nStopped: model repeatedly generated invalid commands."
                    break
                continue

            # --- Guardrail: Detect already executed commands (prevent duplicate loops) ---
            norm_cmd = normalize_command(extracted_command)
            if norm_cmd in executed_commands:
                prev_step = executed_commands[norm_cmd]
                console.print(f"[bold yellow]⚠ AI attempted to repeat command from Step {prev_step}: `{extracted_command}`[/bold yellow]")
                previous_output = (
                    f"SYSTEM ERROR: You already executed this exact command in Step {prev_step}: `{extracted_command}`. "
                    f"Repeating previously executed commands is strictly FORBIDDEN. "
                    f"You must provide a NEW, DIFFERENT command. For web targets on ports 80/443, pick one of:\n"
                    f"  - Check robots.txt: curl -sL https://{actual_target}/robots.txt\n"
                    f"  - Check sensitive paths: python -c \"import urllib.request; [print(p, urllib.request.urlopen('https://{actual_target}' + p).getcode()) for p in ['/robots.txt', '/.env', '/admin', '/login', '/sitemap.xml'] if True]\"\n"
                    f"  - Test Nmap web vulnerability scripts: nmap -sV --script http-enum,http-headers -p 80,443 {actual_target}\n"
                    f"  - Extract page title and forms: python -c \"import urllib.request, re; html = urllib.request.urlopen('https://{actual_target}').read().decode('utf-8', 'ignore'); print('Title:', re.findall(r'<title>(.*?)</title>', html, re.I))\"\n"
                    f"Generate your next new command now."
                )
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    console.print("[bold red]Too many consecutive failures — stopping to prevent infinite loop.[/bold red]")
                    task_finished = True
                    report += "\n\n## Final Summary\nStopped: model repeatedly generated duplicate commands."
                    break
                continue

            # --- Guardrail: Detect repeated failed commands ---
            if extracted_command == last_failed_command:
                console.print(f"[bold yellow]⚠ Model repeated a previously failed command — requesting alternative[/bold yellow]")
                previous_output = (
                    f"SYSTEM ERROR: You repeated the exact same command that already failed: `{extracted_command}`. "
                    f"Do NOT repeat failed commands. Analyze WHY it failed and either: "
                    f"(1) fix the syntax/arguments, (2) use a different tool, or (3) ask the user for guidance."
                )
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    console.print("[bold red]Too many consecutive failures — stopping to prevent infinite loop.[/bold red]")
                    task_finished = True
                    report += "\n\n## Final Summary\nStopped: model repeatedly generated failing commands."
                    break
                continue

            # --- Proactive Tool Check & Missing Tool Guardrail ---
            effective_tool = tool_required or infer_tool_from_command(extracted_command)
            if effective_tool and effective_tool.lower() not in SHELL_BUILTINS:
                if not shutil.which(effective_tool):
                    if effective_tool not in attempted_installs:
                        console.print(f"[yellow]Proactively detected missing tool: {effective_tool}[/yellow]")
                        attempted_installs.add(effective_tool)
                        install_cmd = None
                        if os_name == "Windows":
                            install_cmd = f"winget install {effective_tool} -e --accept-source-agreements --accept-package-agreements"
                        elif os_name == "Linux":
                            install_cmd = f"sudo apt update && sudo apt install -y {effective_tool}"
                        elif os_name == "Darwin":
                            install_cmd = f"brew install {effective_tool}"

                        if install_cmd and (auto_confirm or Confirm.ask(f"Attempt to install {effective_tool} now?", default=False)):
                            console.print(f"[green]Running install for {effective_tool}...[/green]")
                            subprocess.run(install_cmd, shell=True)
                            refresh_system_path()
                            if shutil.which(effective_tool):
                                console.print(f"[green]Successfully installed {effective_tool}![/green]")
                            else:
                                console.print(f"[bold red]Install attempt completed, but '{effective_tool}' is still not found on PATH.[/bold red]")

                    # Verify if tool is actually present after install attempt
                    if not shutil.which(effective_tool):
                        console.print(f"[bold red]Tool '{effective_tool}' is not installed or available on this system. Skipping execution.[/bold red]")
                        previous_output = (
                            f"SYSTEM ERROR: The tool '{effective_tool}' is NOT installed or available on this {os_name} system. "
                            f"Auto-install was unsuccessful or unavailable. Do NOT call '{effective_tool}' again. "
                            f"Instead, use an available tool (e.g. Python scripts using urllib/requests, curl, PowerShell) "
                            f"or choose an installed tool from the available tools list to perform this task."
                        )
                        last_failed_command = extracted_command
                        consecutive_failures += 1
                        report += f"\n### Step (Skipped): `{extracted_command}`\nTool '{effective_tool}' is not installed on system.\n"
                        if consecutive_failures >= 3:
                            console.print("[bold red]Too many consecutive failures — stopping to prevent infinite loop.[/bold red]")
                            task_finished = True
                            report += "\n\n## Final Summary\nStopped: required tools are not installed."
                            break
                        continue

            if step_count >= 20:
                console.print("[yellow]Maximum steps (20) reached. Stopping to prevent infinite loop.[/yellow]")
                task_finished = True
                report += "\n\n## Final Summary\nStopped due to reaching max step limit."
                break

            step_count += 1
            console.print(f"\n[bold cyan]Step {step_count}:[/bold cyan] {extracted_command}")

            if simulate or not real:
                console.print("[yellow]Simulation mode — no real execution[/yellow]")
                previous_output = "SIMULATED SUCCESS (assume command worked and generated expected output. Output [TASK_COMPLETED] if finished)."
                report += f"\n### Step {step_count}: `{extracted_command}`\n(simulated)\n"
                executed_commands[norm_cmd] = step_count
                consecutive_failures = 0
                last_failed_command = None
                continue

            # Real execution decision
            should_execute = auto_confirm or Confirm.ask(f"Execute step {step_count} now?", default=False)
            if not should_execute:
                console.print("[yellow]Execution skipped → ending flow.[/yellow]")
                task_finished = True
                report += "\n\n## Final Summary\nExecution manually aborted by user."
                break

            needs_elevation = any(keyword in extracted_command.lower() for keyword in [
                'sudo', 'net ', 'sc ', 'reg ', 'netsh', 'choco', 'powershell -command', 'icacls', 'mklink', 'takeown'
            ])

            output = ""
            return_code = 0

            with console.status(f"[bold green]Executing step {step_count}...[/bold green]", spinner="dots8"):

                if os_name == "Windows" and needs_elevation:
                    finish_part = ' & echo. & echo === COMMAND FINISHED === & pause'
                    args = ["/k", extracted_command + finish_part]
                    try:
                        subprocess.Popen(
                            [
                                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                                "Start-Process", "cmd.exe", "-Verb", "RunAs", "-ArgumentList"
                            ] + args,
                            shell=False,
                            creationflags=0x00000010,
                        )
                        console.print("[green]Elevated CMD window launched[/green]")
                        output = "Command executed in separate elevated CMD window (output visible there only)"
                        return_code = 0
                    except Exception as e:
                        console.print(f"[red]Failed to launch elevated CMD:[/red] {e}")
                        output = f"Launch error: {str(e)}"
                        return_code = 1

                else:
                    # Shell Injection Prevention check
                    safe_shell = False
                    cmd_args = extracted_command
                    # If there are no pipes or redirections, try to use shell=False
                    if not any(char in extracted_command for char in ['|', '>', '<', '&']):
                        try:
                            cmd_args = shlex.split(extracted_command)
                            safe_shell = False
                        except ValueError:
                            safe_shell = True
                    else:
                        safe_shell = True # Needs shell for piping

                    try:
                        process = subprocess.Popen(
                            cmd_args,
                            shell=safe_shell,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            bufsize=1,
                            universal_newlines=True,
                            env=dict(os.environ),
                        )

                        output_lines = []
                        while True:
                            line = process.stdout.readline()
                            if line:
                                clean = strip_ansi(line.rstrip())
                                output_lines.append(clean)
                                console.print(clean)
                            if process.poll() is not None:
                                break

                        process.wait()
                        output = "\n".join(output_lines)
                        return_code = process.returncode
                    except Exception as e:
                        output = f"Execution failed: {str(e)}"
                        return_code = 1

            console.print(f"[dim]Exit code indication: {return_code}[/dim]")

            # Clean output of transient progress/stats noise
            cleaned_output = clean_command_output(output)

            # --- Track failures for repeat/consecutive detection ---
            if return_code != 0:
                last_failed_command = extracted_command
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    console.print("[bold red]3 consecutive command failures — stopping to prevent infinite loop.[/bold red]")
                    task_finished = True
                    report += "\n\n## Final Summary\nStopped: 3 consecutive command failures."
                    break
            else:
                last_failed_command = None
                consecutive_failures = 0

            # Store smart-truncated findings into report and previous_output
            report_snippet = smart_truncate(cleaned_output, max_chars=1200)
            report += f"\n### Step {step_count}: `{extracted_command}`\nOutput:\n{report_snippet}\n"
            previous_output = f"Command: {extracted_command}\nOutput:\n{smart_truncate(cleaned_output, max_chars=2500)}"
            executed_commands[norm_cmd] = step_count

            # Save checkpoint
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "report": report,
                    "previous_output": previous_output,
                    "step_count": step_count,
                    "executed_commands": list(executed_commands.keys()),
                }, f, indent=2)

        # Show final report
        if task_finished:
            console.print("\n[bold blue]Final Pentest Report[/bold blue]")
            console.print(Panel(Markdown(report), border_style="blue", box=box.ROUNDED))
            
            # Cleanup session file on success
            if os.path.exists(session_file):
                os.remove(session_file)

        question = None

if __name__ == "__main__":
    app()
