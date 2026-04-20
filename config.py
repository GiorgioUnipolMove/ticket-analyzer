import os
from pathlib import Path
from dotenv import load_dotenv

# Carica .env dalla root del progetto
load_dotenv(Path(__file__).parent / ".env")


class Config:
    """Configurazione centralizzata caricata da .env"""

    # API Keys
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Provider
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "gemini")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "")

    # Modelli di default per provider
    PROVIDER_MODELS: dict = {
        "claude": "claude-sonnet-4-20250514",
        "gemini": "gemini-2.0-flash",
        "ollama": "llama3.1:8b",
    }

    # Rate limits (requests per minute)
    RATE_LIMITS: dict = {
        "claude": 50,
        "gemini": 14,    # Gemini free tier: 15 RPM
        "ollama": 999,   # locale, nessun limite
    }

    # File
    INPUT_FILE: str = os.getenv("INPUT_FILE", "Restituzione_device_aggiuntivi_ANALISI OPS_Personale.xlsx")
    OUTPUT_FILE: str = os.getenv("OUTPUT_FILE", "output_analisi.xlsx")
    PROGRESS_FILE: str = "progress.json"

    # Parametri esecuzione
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY: int = int(os.getenv("RETRY_DELAY", "5"))
    BATCH_SAVE_EVERY: int = int(os.getenv("BATCH_SAVE_EVERY", "50"))

    @classmethod
    def get_model(cls, provider: str, model_override: str = None) -> str:
        if model_override:
            return model_override
        if cls.DEFAULT_MODEL:
            return cls.DEFAULT_MODEL
        return cls.PROVIDER_MODELS.get(provider, "")

    @classmethod
    def get_api_key(cls, provider: str) -> str:
        keys = {
            "claude": cls.ANTHROPIC_API_KEY,
            "gemini": cls.GEMINI_API_KEY,
            "ollama": "",
        }
        return keys.get(provider, "")

    @classmethod
    def get_rate_limit(cls, provider: str) -> int:
        return cls.RATE_LIMITS.get(provider, 50)
