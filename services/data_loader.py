import pandas as pd


class DataLoader:
    """Carica il file Excel con i 4 tab e costruisce i dizionari di lookup."""

    def __init__(self, input_file: str):
        self.input_file = input_file
        self.df_main: pd.DataFrame = None
        self.post_pulse_lookup: dict[str, list[str]] = {}
        self.post_ticket_lookup: dict[str, list[str]] = {}
        self.notes_lookup: dict[str, list[dict]] = {}

    def load(self):
        print(f"Caricamento {self.input_file}...")

        self.df_main = self._read_sheet('Restituzione_Device_Agg')
        df_post_pulse = self._read_sheet('Post Pulse su Anag Cliente')
        df_post_ticket = self._read_sheet('Post su TicketID')
        df_notes = self._read_sheet('NoteByTicketID')

        self._augment_obu_count()

        print(f"  Tab principale: {len(self.df_main)} righe")
        print(f"  Post Pulse: {len(df_post_pulse)} righe")
        print(f"  Post Ticket: {len(df_post_ticket)} righe")
        print(f"  Note Ticket: {len(df_notes)} righe")

        self._build_post_pulse_lookup(df_post_pulse)
        self._build_post_ticket_lookup(df_post_ticket)
        self._build_notes_lookup(df_notes)

        print(f"  Lookup Post Pulse: {len(self.post_pulse_lookup)} clienti")
        print(f"  Lookup Post Ticket: {len(self.post_ticket_lookup)} ticket")
        print(f"  Lookup Note: {len(self.notes_lookup)} ticket")

        return self

    def _augment_obu_count(self):
        """Aggiunge num_obu_contratto = n° serialnumber distinti per contrattoid.

        Il file non contiene un campo autoritativo "quanti OBU ha il contratto".
        Lo stimiamo contando i serialnumber distinti che compaiono nei ticket per
        lo stesso contratto. È un proxy: dice "quanti OBU di questo contratto
        hanno generato almeno un ticket nel dataset", non "quanti OBU possiede
        davvero il cliente". Per la maggior parte dei casi i due numeri coincidono.
        """
        if 'contrattoid' not in self.df_main.columns or 'serialnumber' not in self.df_main.columns:
            return
        serial_valid = self.df_main['serialnumber'].where(
            self.df_main['serialnumber'].astype(str).str.lower().isin(['nan', 'none', '']) == False
        )
        count_per_contratto = (
            self.df_main.assign(_s=serial_valid)
                        .dropna(subset=['_s'])
                        .groupby('contrattoid')['_s']
                        .nunique()
        )
        self.df_main['num_obu_contratto'] = (
            self.df_main['contrattoid'].map(count_per_contratto).fillna(0).astype(int).astype(str)
        )

    def _read_sheet(self, sheet_name: str) -> pd.DataFrame:
        df = pd.read_excel(self.input_file, sheet_name=sheet_name, dtype=str)
        df.columns = df.columns.map(lambda x: str(x).strip() if x else x)
        return df

    def _build_post_pulse_lookup(self, df: pd.DataFrame):
        for _, row in df.iterrows():
            cid = str(row.get('clienteid', '')).strip()
            post = str(row.get('post', '')).strip()
            if cid and post and post != 'nan':
                self.post_pulse_lookup.setdefault(cid, []).append(post)

    def _build_post_ticket_lookup(self, df: pd.DataFrame):
        for _, row in df.iterrows():
            tid = str(row.get('ticketid', '')).strip()
            post = str(row.get('post', '')).strip()
            if tid and post and post != 'nan':
                self.post_ticket_lookup.setdefault(tid, []).append(post)

    def _build_notes_lookup(self, df: pd.DataFrame):
        for _, row in df.iterrows():
            tid = str(row.get('TicketID', '')).strip()
            if not tid:
                continue

            nota = {
                'nota_cliente': self._clean(row.get('Nota Cliente')),
                'nota_operatore': self._clean(row.get('Nota Operatore')),
                'nota_chiusura': self._clean(row.get('Nota Chiusura')),
            }
            nota = {k: v for k, v in nota.items() if v}
            if nota:
                self.notes_lookup.setdefault(tid, []).append(nota)

    @staticmethod
    def _clean(val) -> str:
        if pd.isna(val):
            return ''
        s = str(val).strip()
        return '' if s in ('.', 'nan', '') else s
