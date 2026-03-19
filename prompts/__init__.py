from prompts.system import SYSTEM_PROMPT
from prompts.examples import FEW_SHOT_EXAMPLES


def get_system_prompt() -> str:
    """Restituisce il system prompt completo con gli esempi few-shot."""
    return SYSTEM_PROMPT.format(examples=FEW_SHOT_EXAMPLES)
