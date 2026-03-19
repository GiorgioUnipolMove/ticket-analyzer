import json
import os
from config import Config


def save_progress(results: dict, last_idx: int, provider_name: str):
    """Salva lo stato corrente su disco per poter riprendere."""
    with open(Config.PROGRESS_FILE, 'w') as f:
        json.dump({
            'last_idx': last_idx,
            'provider': provider_name,
            'count': len(results),
            'results': results,
        }, f)


def load_progress() -> tuple[int, dict, str]:
    """Carica lo stato precedente. Restituisce (last_idx, results, provider)."""
    if not os.path.exists(Config.PROGRESS_FILE):
        return -1, {}, ''

    with open(Config.PROGRESS_FILE, 'r') as f:
        data = json.load(f)

    return (
        data.get('last_idx', -1),
        data.get('results', {}),
        data.get('provider', ''),
    )


def clear_progress():
    """Cancella il file di progresso."""
    if os.path.exists(Config.PROGRESS_FILE):
        os.remove(Config.PROGRESS_FILE)
        print(f"  🗑️  Progresso cancellato ({Config.PROGRESS_FILE})")
