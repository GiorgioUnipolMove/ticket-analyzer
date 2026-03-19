from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Interfaccia base per tutti i provider LLM."""

    @abstractmethod
    def call(self, system_prompt: str, user_prompt: str) -> str:
        """Chiama il modello e restituisce la risposta testuale."""
        pass

    @abstractmethod
    def name(self) -> str:
        """Nome descrittivo del provider + modello."""
        pass
