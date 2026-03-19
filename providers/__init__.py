from config import Config
from providers.base import LLMProvider
from providers.claude import ClaudeProvider
from providers.gemini import GeminiProvider
from providers.ollama import OllamaProvider


def create_provider(provider_name: str, model: str = None) -> LLMProvider:
    """Factory: crea il provider LLM in base al nome."""
    model = Config.get_model(provider_name, model)
    api_key = Config.get_api_key(provider_name)

    if provider_name == "claude":
        if not api_key:
            raise ValueError("Imposta ANTHROPIC_API_KEY nel file .env")
        return ClaudeProvider(api_key, model)

    elif provider_name == "gemini":
        if not api_key:
            raise ValueError("Imposta GEMINI_API_KEY nel file .env (gratis su https://aistudio.google.com/apikey)")
        return GeminiProvider(api_key, model)

    elif provider_name == "ollama":
        return OllamaProvider(model, Config.OLLAMA_BASE_URL)

    else:
        raise ValueError(f"Provider '{provider_name}' non supportato. Usa: claude, gemini, ollama")
