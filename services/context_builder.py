import pandas as pd


class ContextBuilder:
    """Costruisce il contesto testuale per ogni riga del ticket."""

    # Campi strutturati da includere nel contesto
    FIELDS = [
        'id_interaction', 'contrattoid', 'stato_contratto',
        'pxcreatedatetime', 'pyresolvedtimestamp', 'pystatuswork',
        'serialnumber', 'causale_dispositivo', 'flag_recesso_obu',
        'tipologia_cliente', 'data_rientro_in_magazzino',
        'stato_dispositivo', 'data_recesso_dispositivo',
        'stato_obu', 'data_cessazione_obu', 'data_fattura',
        'doc_fiscal_date', 'STATO FATTURA', 'NOTE',
        "E' nell'elenco dell'altro file", 'Note ',
    ]

    MAX_POSTS = 5        # max post per ticket
    MAX_NOTES = 3        # max note per ticket
    MAX_CLIENT_POSTS = 3 # max post cliente da anagrafica
    MAX_TEXT_LEN = 500   # troncamento singolo testo

    def __init__(self, post_pulse_lookup: dict, post_ticket_lookup: dict, notes_lookup: dict):
        self.post_pulse_lookup = post_pulse_lookup
        self.post_ticket_lookup = post_ticket_lookup
        self.notes_lookup = notes_lookup

    def build(self, row: pd.Series) -> str:
        tid = str(row.get('id_interaction', '')).strip()
        cid = str(row.get('ClienteID', '')).strip()

        parts = [self._structured_fields(row)]
        parts.append(self._ticket_posts(tid))
        parts.append(self._ticket_notes(tid))
        parts.append(self._client_posts(cid, tid))

        return '\n'.join(p for p in parts if p)

    def _structured_fields(self, row: pd.Series) -> str:
        lines = ["DATI STRUTTURATI:"]
        for field in self.FIELDS:
            val = row.get(field, '')
            val_str = str(val).strip() if pd.notna(val) else 'NULL'
            if val_str == 'nan':
                val_str = 'NULL'
            lines.append(f"  {field}: {val_str}")
        return '\n'.join(lines)

    def _ticket_posts(self, ticket_id: str) -> str:
        posts = self.post_ticket_lookup.get(ticket_id, [])
        if not posts:
            return ''
        lines = ["POST SU TICKET:"]
        for p in posts[:self.MAX_POSTS]:
            lines.append(f"  - {p[:self.MAX_TEXT_LEN]}")
        return '\n'.join(lines)

    def _ticket_notes(self, ticket_id: str) -> str:
        notes = self.notes_lookup.get(ticket_id, [])
        if not notes:
            return ''
        lines = ["NOTE TICKET:"]
        for n in notes[:self.MAX_NOTES]:
            for key, val in n.items():
                if val:
                    lines.append(f"  {key}: {val[:self.MAX_TEXT_LEN]}")
        return '\n'.join(lines)

    def _client_posts(self, client_id: str, ticket_id: str) -> str:
        posts = self.post_pulse_lookup.get(client_id, [])
        if not posts:
            return ''

        # Priorità: post che menzionano il ticket corrente
        relevant = [p for p in posts if ticket_id in p]
        if not relevant:
            relevant = posts[:self.MAX_CLIENT_POSTS]
        else:
            relevant = relevant[:self.MAX_CLIENT_POSTS]

        lines = ["POST CLIENTE (da anagrafica):"]
        for p in relevant:
            lines.append(f"  - {p[:self.MAX_TEXT_LEN]}")
        return '\n'.join(lines)
