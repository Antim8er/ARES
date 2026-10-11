<p align="center">
  <img src="logo.png" alt="A.R.E.S. CLI Banner" width="600"/>
</p>

# A.R.E.S. CLI 🧠
**Autonomous Reconnaissance & Exploitation System**

An agentic, LLM-powered penetration testing CLI that dynamically plans, installs missing tools, and executes technical security workflows against target systems.

> [!WARNING]
> **DISCLAIMER:** This tool is intended for educational purposes and authorized auditing ONLY. The creators take no responsibility for misuse or damage caused by this software. By executing this tool, you acknowledge you possess explicit, written permission to audit the target.

---

## Features
- **Unrestricted Agentic Planning:** Powered by local LLMs to map, analyze, and audit systems.
- **Proactive Tool Installation:** Automatically detects missing tools (e.g. `nmap`, `sqlmap`) and installs them dynamically using your package manager (`winget`, `apt`, `brew`).
- **Session Checkpointing:** Automatically checkpoints audit progress so you can resume if interrupted.
- **Shell-Safe Execution:** Sanitizes command execution to prevent unintended shell injections while preserving pipe and redirection capabilities.

---

## Prerequisites
- **Python:** 3.8 or newer
- **Local LLM Engine:** [LM Studio](https://lmstudio.ai/) (or any OpenAI-compatible local server)

---

## Installation

Clone the repository and install in editable mode:

```bash
git clone https://github.com/Antim8er/ARES.git
cd ARES
pip install -e .
```

---

## Connecting Your Local AI (LM Studio)

A.R.E.S. runs entirely with local Large Language Models via LM Studio:

1. Download and launch [LM Studio](https://lmstudio.ai/).
2. Search and download an uncensored or technical coding model:
   - **Recommended (16GB RAM):** `bartowski/Qwen2.5-14B_Uncensored_Instruct-GGUF` (Download `Q4_K_M` quantization)
3. Start the Local Server in LM Studio (default: `http://localhost:1234/v1`).
4. Configure your `.env` file (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```
   Default settings in `.env`:
   ```env
   LMSTUDIO_BASE_URL="http://localhost:1234/v1"
   ARES_DEFAULT_MODEL="local-model"
   ```

---

## Usage

Start an audit session by asking ARES to accomplish a goal:

```bash
ares-cli "Scan my local network for vulnerabilities"
```

ARES will boot up, analyze the request, form a structured JSON plan, and begin executing commands step-by-step.

### Command Options:
- `--model`, `-m`: Specify the LLM model name.
- `--simulate / --no-simulate`: Toggle simulation mode (simulation is enabled by default for safety).
- `--real`: Execute commands directly against the system.
- `--target`, `-t`: Specify a target host or IP (e.g. `scanme.nmap.org`).
- `--auto-confirm`: Auto-confirm all execution steps (caution: dangerous).

---

## Development & Testing

Install development dependencies and run tests:

```bash
pip install -r requirements-dev.txt
pytest
```

---

## License

This project is licensed under the [MIT License](LICENSE).
