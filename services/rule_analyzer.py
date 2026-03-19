import time
from services.data_loader import DataLoader
from services.rules import RuleEngine, extract_texts
from utils.progress import save_progress
from config import Config


class RuleBasedAnalyzer:
    """Analizzatore rule-based: applica regole deterministiche + keyword matching."""

    def __init__(self, data: DataLoader):
        self.data = data
        self.engine = RuleEngine()

    def run(self, start_idx: int, end_idx: int, results: dict) -> dict:
        total = end_idx - start_idx
        t_start = time.time()
        actually_processed = 0

        for idx in range(start_idx, end_idx):
            row = self.data.df_main.iloc[idx]
            tid = str(row.get('id_interaction', '')).strip()

            # Skip se già analizzato (resume)
            if tid in results:
                continue

            cid = str(row.get('ClienteID', '')).strip()
            if cid.lower() in ('nan', '', 'none'):
                cid = ''

            # Estrai testi separati per ticket e cliente
            ticket_text, client_text, all_text = extract_texts(
                tid, cid,
                self.data.post_ticket_lookup,
                self.data.notes_lookup,
                self.data.post_pulse_lookup,
            )

            # Valuta regole
            analisi = self.engine.evaluate(row, ticket_text, client_text, all_text)
            results[tid] = analisi
            actually_processed += 1

            if actually_processed % 1000 == 0:
                elapsed = time.time() - t_start
                print(f"  [{actually_processed}/{total}] Processate {actually_processed} righe in {elapsed:.1f}s")

            if actually_processed % Config.BATCH_SAVE_EVERY == 0:
                save_progress(results, idx, 'rules')

        # Salvataggio finale
        save_progress(results, end_idx - 1, 'rules')

        total_time = time.time() - t_start
        print(f"\n  Processate: {len(results)} | Tempo: {total_time:.1f}s")

        return results
