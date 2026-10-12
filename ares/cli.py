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
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Confirm
from rich.status import Status
from rich.text import Text
from rich import box

# Fix Windows Console Encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
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

    client = get_client(base_url=url, api_key=api_key)
    console.print(f"[dim]→ Using model: {model} | Endpoint: {client.chat.completions.base_url}[/dim]")

    if real:
        simulate = False
        console.print("[bold yellow]REAL EXECUTION MODE ACTIVE — USE WITH CAUTION[/bold yellow]")

    actual_target = target if target else "None provided (Ask the user)"
    
    # Load session if it exists
    session_file = ".ares_session.json"
    if os.path.exists(session_file) and Confirm.ask("Found a previous session. Resume?", default=True):
        with open(session_file, 'r', encoding='utf-8') as f:
            session = json.load(f)
            report = session.get("report", "")
            previous_output = session.get("previous_output", "")
            step_count = session.get("step_count", 0)
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

        while True:
            with console.status("[bold cyan]Ares thinking...[/bold cyan]", spinner="dots12"):
                conv_text = "\n".join(conversation_history[-10:])
                context_prefix = f"Conversation History:\n{conv_text}\n\n" if conv_text else ""
                
                target_str = actual_target if actual_target != "None provided (Ask the user)" else "UNKNOWN (Check Task or Conversation History, otherwise ask user)"
                
                context = (
                f"{context_prefix}Task: {question}\n"
                f"Target: {target_str}\n"
                f"CRITICAL: You are running on {os_name}. Use {os_name}-compatible commands (e.g. CMD or 'powershell -c' on Windows).\n"
                f"Previous command output (truncated):\n{previous_output[:1400]}\n"
                f"Current report tail:\n{report[-1000:]}\n"
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

            if analysis or plan or tool_required:
                panel_text = f"**Analysis:** {analysis}\n\n**Plan:** {plan}\n\n**Tool:** {tool_required}"
                console.print(Panel(
                    Markdown(panel_text),
                    title=f"[bold green]Ares • {model}[/bold green]",
                    border_style="green",
                    padding=(1, 2),
                    box=box.HEAVY_EDGE,
                ))

            if message_to_user and not extracted_command:
                console.print(f"\n[bold magenta]Ares:[/bold magenta] {message_to_user}")
                # We do not add conversational responses to the report to prevent model confusion

            if is_completed:
                task_finished = True
                console.print("[green]AI considers objective complete → stopping.[/green]")
                report += "\n\n## Final Summary\nGoal achieved or no further safe steps identified."
                break
                
            if not extracted_command:
                # Remove the conversational task from the report so it doesn't pollute pentest history
                task_header = f"\n### New Task: {question} (Target: {actual_target})\n"
                if report.endswith(task_header):
                    report = report[:-len(task_header)]
                
                if message_to_user:
                    conversation_history.append(f"User: {question}")
                    conversation_history.append(f"Ares: {message_to_user}")
                
                break

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
                continue

            # --- Proactive Tool Check ---
            if tool_required and tool_required.lower() not in ["cmd", "powershell", "echo", "cd", "dir"]:
                if not shutil.which(tool_required) and tool_required not in attempted_installs:
                    console.print(f"[yellow]Proactively detected missing tool: {tool_required}[/yellow]")
                    attempted_installs.add(tool_required)
                    install_cmd = None
                    if os_name == "Windows":
                        install_cmd = f"winget install {tool_required} -e --accept-source-agreements --accept-package-agreements"
                    elif os_name == "Linux":
                        install_cmd = f"sudo apt update && sudo apt install -y {tool_required}"
                    elif os_name == "Darwin":
                        install_cmd = f"brew install {tool_required}"

                    if install_cmd and (auto_confirm or Confirm.ask(f"Attempt to install {tool_required} now?", default=False)):
                        console.print(f"[green]Running install for {tool_required}...[/green]")
                        subprocess.run(install_cmd, shell=True)
                        console.print("[green]Install attempt completed.[/green]")
                        
                        # Refresh PATH on Windows
                        if os_name == "Windows":
                            try:
                                import winreg
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
                                    sys_path = winreg.ExpandEnvironmentStrings(winreg.QueryValueEx(key, "Path")[0])
                                try:
                                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                                        user_path = winreg.ExpandEnvironmentStrings(winreg.QueryValueEx(key, "Path")[0])
                                except FileNotFoundError:
                                    user_path = ""
                                os.environ["PATH"] = sys_path + ";" + user_path
                            except Exception:
                                pass

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
                            universal_newlines=True
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

            report += f"\n### Step {step_count}: `{extracted_command}`\nOutput (truncated):\n{output[:350]}...\n"
            previous_output = f"Command: {extracted_command}\nOutput:\n{output}"

            # Save checkpoint
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "report": report,
                    "previous_output": previous_output,
                    "step_count": step_count
                }, f)

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
