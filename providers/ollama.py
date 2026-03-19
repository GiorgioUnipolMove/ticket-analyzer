from providers.base import LLMProvider


class OllamaProvider(LLMProvider):

    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        import requests
        self._requests = requests
        self.model = model
        self.base_url = base_url.rstrip('/')
        self._health_check()

    def _health_check(self):
        """Verifica che Ollama sia raggiungibile e il modello disponibile."""
        try:
            resp = self._requests.get(f"{self.base_url}/api/tags", timeout=30)
            resp.raise_for_status()
        except self._requests.ConnectionError:
            raise ConnectionError(
                f"Ollama non raggiungibile su {self.base_url}. "
                "Assicurati che sia avviato con: ollama serve"
            )
        except self._requests.RequestException as e:
            raise ConnectionError(f"Errore connessione Ollama: {e}")

        models = [m['name'] for m in resp.json().get('models', [])]
        # Ollama restituisce nomi come "llama3.1:8b" o "llama3.1:latest"
        model_base = self.model.split(':')[0]
        if not any(model_base in m for m in models):
            available = ', '.join(models) if models else 'nessuno'
            raise ValueError(
                f"Modello '{self.model}' non trovato in Ollama. "
                f"Modelli disponibili: {available}. "
                f"Scaricalo con: ollama pull {self.model}"
            )

    def call(self, system_prompt: str, user_prompt: str) -> str:
        response = self._requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()

    def name(self) -> str:
        return f"Ollama ({self.model})"
