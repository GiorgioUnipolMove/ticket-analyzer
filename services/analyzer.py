import time
from config import Config
from providers.base import LLMProvider
from prompts import get_system_prompt
from services.context_builder import ContextBuilder
from services.data_loader import DataLoader
from utils.rate_limiter import RateLimiter
from utils.progress import save_progress


class Analyzer:
    """Orchestratore principale: itera le righe, chiama l'LLM, traccia i progressi."""

    def __init__(self, provider: LLMProvider, data: DataLoader, provider_name: str):
        self.provider = provider
        self.data = data
        self.provider_name = provider_name
        self.rate_limiter = RateLimiter(Config.get_rate_limit(provider_name))
        self.system_prompt = get_system_prompt()
        self.context_builder = ContextBuilder(
            data.post_pulse_lookup,
            data.post_ticket_lookup,
            data.notes_lookup,
        )

    def run(self, start_idx: int, end_idx: int, results: dict) -> dict:
        total = end_idx - start_idx
        t_start = time.time()
        errors = 0

        for idx in range(start_idx, end_idx):
            row = self.data.df_main.iloc[idx]
            tid = str(row.get('id_interaction', '')).strip()

            # Skip se già analizzato (resume)
            if tid in results:
                continue

            context = self.context_builder.build(row)
            analisi = self._call_with_retry(context)
            results[tid] = analisi

            if analisi.startswith("ERRORE"):
                errors += 1

            processed = idx - start_idx + 1
            elapsed = time.time() - t_start
            avg_time = elapsed / processed
            remaining = (end_idx - idx - 1) * avg_time

            print(f"  [{processed}/{total}] {tid}: {analisi[:80]}...")

            if processed % 10 == 0:
                print(f"    ⏱️  Media: {avg_time:.1f}s/riga | Rimanente: {remaining / 60:.0f} min | Errori: {errors}")

            if processed % Config.BATCH_SAVE_EVERY == 0:
                save_progress(results, idx, self.provider_name)
                print(f"    💾 Progresso salvato ({len(results)} analisi)")

        # Salvataggio finale
        save_progress(results, end_idx - 1, self.provider_name)

        total_time = time.time() - t_start
        print(f"\n  Processate: {len(results)} | Errori: {errors} | Tempo: {total_time / 60:.1f} min")

        return results

    def _call_with_retry(self, context: str) -> str:
        user_prompt = f"Genera l'analisi per questo ticket:\n\n{context}"

        for attempt in range(Config.MAX_RETRIES):
            try:
                self.rate_limiter.wait_if_needed()
                return self.provider.call(self.system_prompt, user_prompt)
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = any(kw in err_str for kw in ("rate", "429", "quota", "resource"))

                if is_rate_limit:
                    wait = Config.RETRY_DELAY * (attempt + 1) * 2
                    print(f"    ⏳ Rate limit API, attendo {wait}s...")
                    time.sleep(wait)
                elif attempt < Config.MAX_RETRIES - 1:
                    print(f"    ⚠️  Errore: {e}, retry {attempt + 1}/{Config.MAX_RETRIES}")
                    time.sleep(Config.RETRY_DELAY)
                else:
                    return f"ERRORE API: {str(e)[:100]}"

        return "ERRORE: max retry raggiunto"
