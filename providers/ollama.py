from providers.base import LLMProvider


class OllamaProvider(LLMProvider):

    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        import requests
        self._requests = requests
        self.model = model
        self.base_url = base_url

    def call(self, system_prompt: str, user_prompt: str) -> str:
        full_prompt = system_prompt + "\n\n" + user_prompt
        response = self._requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": full_prompt, "stream": False},
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    def name(self) -> str:
        return f"Ollama ({self.model})"
