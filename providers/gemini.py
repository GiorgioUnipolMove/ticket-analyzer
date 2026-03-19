from providers.base import LLMProvider


class GeminiProvider(LLMProvider):

    def __init__(self, api_key: str, model: str):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def call(self, system_prompt: str, user_prompt: str) -> str:
        full_prompt = system_prompt + "\n\n" + user_prompt
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
        )
        return response.text.strip()

    def name(self) -> str:
        return f"Gemini ({self.model})"
