import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment


class ExcelWriter:
    """Genera il file Excel di output con la colonna Analisi formattata."""

    HEADER_FILL = PatternFill('solid', fgColor='4472C4')
    HEADER_FONT = Font(bold=True, color='FFFFFF', name='Arial', size=10)
    ANALISI_FILL = PatternFill('solid', fgColor='FFF2CC')
    BODY_FONT = Font(name='Arial', size=10)

    def write(self, df_main: pd.DataFrame, results: dict, output_file: str):
        print(f"\nGenerazione output: {output_file}")

        df_out = df_main.copy()

        # Inserisci colonna Analisi dopo data_recesso_dispositivo
        col_idx = df_out.columns.get_loc('data_recesso_dispositivo') + 1
        df_out.insert(col_idx, 'Analisi', '')

        # Popola Analisi
        for idx, row in df_out.iterrows():
            tid = str(row.get('id_interaction', '')).strip()
            if tid in results:
                df_out.at[idx, 'Analisi'] = results[tid]

        # Rimuovi ClienteID dall'output
        if 'ClienteID' in df_out.columns:
            df_out = df_out.drop(columns=['ClienteID'])

        # Scrivi Excel
        df_out.to_excel(output_file, index=False, sheet_name='Analisi')

        # Formattazione
        self._format(output_file)

        filled = sum(1 for v in results.values() if v and not v.startswith('ERRORE'))
        print(f"  ✅ {filled} analisi scritte su {len(df_out)} righe")

    def _format(self, output_file: str):
        wb = openpyxl.load_workbook(output_file)
        ws = wb.active

        # Headers
        for cell in ws[1]:
            cell.fill = self.HEADER_FILL
            cell.font = self.HEADER_FONT
            cell.alignment = Alignment(horizontal='center', wrap_text=True)

        # Trova colonna Analisi
        analisi_col = None
        for idx, cell in enumerate(ws[1], 1):
            if cell.value == 'Analisi':
                analisi_col = idx
                break

        # Evidenzia colonna Analisi
        if analisi_col:
            for row in ws.iter_rows(min_row=2, min_col=analisi_col, max_col=analisi_col):
                for cell in row:
                    cell.fill = self.ANALISI_FILL
                    cell.font = self.BODY_FONT

        # Auto-width
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

        wb.save(output_file)
