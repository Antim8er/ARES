import os
import json
import urllib.request
from rich.console import Console

console = Console()

class DummyMessage:
    def __init__(self, content):
        self.content = content

class DummyChoice:
    def __init__(self, message):
        self.message = message

class DummyResponse:
    def __init__(self, choices):
        self.choices = choices

class ChatCompletions:
    def __init__(self, base_url):
        self.base_url = base_url
    
    def create(self, model, messages, temperature=0.7, max_tokens=1000):
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
        try:
            # 120 second timeout for local model processing
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result['choices'][0]['message']['content']
                return DummyResponse([DummyChoice(DummyMessage(content))])
        except Exception as e:
            console.print(f"\n[bold red]LLM Request Failed:[/bold red] {e}")
            console.print("[yellow]Make sure LM Studio local server is running![/yellow]")
            # Returning "END FLOW" gracefully stops the CLI if the server is unreachable
            return DummyResponse([DummyChoice(DummyMessage("END FLOW"))])

class Chat:
    def __init__(self, base_url):
        self.completions = ChatCompletions(base_url)

class LocalClient:
    def __init__(self, base_url):
        self.chat = Chat(base_url)

def get_client():
    # LM Studio default local server URL
    base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    return LocalClient(base_url)
