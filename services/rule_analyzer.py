import time
from collections import defaultdict
from services.data_loader import DataLoader
from services.rules import RuleEngine, extract_texts
from utils.progress import save_progress
from config import Config


class RuleBasedAnalyzer:
    """Analizzatore rule-based: applica regole deterministiche + keyword matching.

    Dopo l'analisi per-ticket esegue un passaggio cross-ticket per rilevare:
    - Ticket multipli sullo stesso contratto con esiti discordanti (requisito 3)
    """

    def __init__(self, data: DataLoader):
        self.data = data
        self.engine = RuleEngine()
        # Mappa contrattoid → lista di ticket_id, popolata durante run()
        self._contract_tickets: dict[str, list[str]] = defaultdict(list)
        # Flag anomalie multi-ticket: ticket_id → stringa di flag
        self.multi_ticket_flags: dict[str, str] = {}

    def run(self, start_idx: int, end_idx: int, results: dict) -> dict:
        total = end_idx - start_idx
        t_start = time.time()
        actually_processed = 0

        for idx in range(start_idx, end_idx):
            row = self.data.df_main.iloc[idx]
            tid = str(row.get('id_interaction', '')).strip()

            # Registra ticket → contratto (serve per multi-ticket detection)
            contratto = str(row.get('contrattoid', '')).strip()
            if contratto and contratto.lower() not in ('nan', '', 'none'):
                self._contract_tickets[contratto].append(tid)

            # Skip se già analizzato (resume)
            if tid in results:
                continue

            cid = str(row.get('ClienteID', '')).strip()
            if cid.lower() in ('nan', '', 'none'):
                cid = ''

            # Estrai testi separati per ticket e cliente
            ticket_text, client_text, all_text, post_text, note_cliente_text = extract_texts(
                tid, cid,
                self.data.post_ticket_lookup,
                self.data.notes_lookup,
                self.data.post_pulse_lookup,
            )

            # Valuta regole
            analisi = self.engine.evaluate(
                row, ticket_text, client_text, all_text,
                post_text, note_cliente_text,
            )
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

        # Rilevamento ticket multipli per contratto con esiti discordanti
        self._detect_multi_ticket_inconsistencies(results)

        return results

    # ------------------------------------------------------------------
    # Multi-ticket inconsistency detection (requisito 3)
    # ------------------------------------------------------------------

    def _detect_multi_ticket_inconsistencies(self, results: dict):
        """Raggruppa ticket per contratto e segnala esiti discordanti.

        Un esito è considerato "discordante" quando due ticket sullo stesso
        contratto hanno categorie di analisi diverse (es. uno risolto, l'altro
        in attesa; oppure uno annullato e l'altro con OTP completato).

        Il flag viene scritto in self.multi_ticket_flags[ticket_id].
        """
        flagged = 0
        for contratto, tids in self._contract_tickets.items():
            # Considera solo contratti con almeno 2 ticket
            tids_con_analisi = [t for t in tids if t in results]
            if len(tids_con_analisi) < 2:
                continue

            analisi_per_ticket = {t: results[t] for t in tids_con_analisi}
            categorie = {t: self._categorize_outcome(a) for t, a in analisi_per_ticket.items()}

            valori_categorie = set(categorie.values())
            if len(valori_categorie) > 1:
                # Esiti discordanti rilevati
                elenco = '; '.join(
                    f"{t}={categorie[t]}" for t in sorted(tids_con_analisi)
                )
                flag_msg = (
                    f"ATTENZIONE: contratto {contratto} ha {len(tids_con_analisi)} ticket "
                    f"con esiti discordanti ({elenco}). Verificare gestione uniforme."
                )
                for t in tids_con_analisi:
                    self.multi_ticket_flags[t] = flag_msg
                flagged += 1

        if flagged:
            print(f"  [Multi-ticket] {flagged} contratti con ticket multipli e esiti discordanti")
        else:
            print(f"  [Multi-ticket] Nessun contratto con esiti discordanti rilevato")

    @staticmethod
    def _categorize_outcome(analisi: str) -> str:
        """Mappa un testo di analisi a una macro-categoria per confronto.

        Le categorie sono volutamente grossolane: servono solo a rilevare
        discordanze significative tra ticket sullo stesso contratto.
        """
        if not analisi:
            return 'sconosciuto'
        a = analisi.lower()
        if 'anomalia' in a:
            return 'anomalia'
        if any(kw in a for kw in ('duplicato', 'doppio')):
            return 'duplicato'
        if any(kw in a for kw in ('annullato', 'annulla')):
            return 'annullato'
        if any(kw in a for kw in ('otp', 'lettera di vettura', 'ldv')):
            return 'procedura_completata'
        if any(kw in a for kw in ('riconsegnato', 'rientrato', 'completata', 'restituzione completata')):
            return 'risolto'
        if any(kw in a for kw in ('cessato', 'recesso')):
            return 'cessato_recesso'
        if any(kw in a for kw in ('mancato contatto', 'contatto ko', 'non risponde')):
            return 'mancato_contatto'
        if any(kw in a for kw in ('aperto ahd', 'ahd')):
            return 'escalation'
        if any(kw in a for kw in ('cambiato idea', 'ripensato', 'non vuole')):
            return 'cliente_rinuncia'
        if any(kw in a for kw in ('ancora aperto', 'open', 'new')):
            return 'aperto'
        if 'errore' in a:
            return 'errore'
        return 'altro'
