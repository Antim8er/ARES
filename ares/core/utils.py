# src/core/utils.py

def suggest_safe_command(task: str, target: str) -> str:
    """
    Simple helper to suggest a safe, ethical command based on task.
    Returns a string suggestion that can be included in the prompt or answer.
    """
    task_lower = task.lower()

    if "port" in task_lower or "open ports" in task_lower or "scan ports" in task_lower:
        return (
            f"Recommended safe command for port scanning:\n"
            f"```bash\n"
            f"nmap -sV -T4 {target}\n"
            f"```\n"
            f"-sV: service/version detection\n"
            f"-T4: aggressive but safe timing\n"
            f"Use on authorized targets only (e.g. scanme.nmap.org)."
        )

    elif "http" in task_lower or "web" in task_lower or "headers" in task_lower:
        return (
            f"Recommended safe command for HTTP header check:\n"
            f"```bash\n"
            f"curl -I {target}\n"
            f"```\n"
            f"Reveals server type, security headers, etc. Safe recon."
        )

    else:
        return (
            "No specific safe command suggestion for this task yet.\n"
            "ARES will decide based on the full context."
        )