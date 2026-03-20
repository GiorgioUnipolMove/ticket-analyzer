#!/usr/bin/env python3
"""
Quality check: confronta output rule-based con analisi manuali e analizza distribuzione.
"""
import pandas as pd
import json
import random
from collections import Counter

# === 1. Carica output rule-based ===
print("=" * 70)
print("QUALITY CHECK - Analisi affidabilità rule-based")
print("=" * 70)

df_output = pd.read_excel("output_analisi.xlsx", dtype=str)
print(f"\nOutput rule-based: {len(df_output)} righe")

# Conta righe con analisi
has_analysis = df_output['Analisi'].notna() & (df_output['Analisi'] != '') & (df_output['Analisi'] != 'nan')
print(f"Righe con analisi: {has_analysis.sum()}")
print(f"Righe senza analisi: {(~has_analysis).sum()}")

# === 2. Distribuzione analisi ===
print(f"\n{'=' * 70}")
print("DISTRIBUZIONE ANALISI (top 20)")
print("=" * 70)

analysis_counts = df_output.loc[has_analysis, 'Analisi'].value_counts()
for i, (text, count) in enumerate(analysis_counts.head(20).items()):
    pct = count / has_analysis.sum() * 100
    print(f"  {i+1:2d}. [{count:5d}] ({pct:5.1f}%) {text[:100]}")

print(f"\n  ... totale categorie distinte: {len(analysis_counts)}")

# === 3. Confronto con file manuale ===
print(f"\n{'=' * 70}")
print("CONFRONTO CON ANALISI MANUALI")
print("=" * 70)

df_manual = pd.read_excel(
    "Copia di Restituzione_device_aggiuntivi_ANALISI OPS.xlsx",
    sheet_name=0, dtype=str
)
print(f"File manuale: {len(df_manual)} righe")

# Trova colonna analisi nel file manuale
manual_analysis_col = None
for col in df_manual.columns:
    if 'analisi' in col.lower() or 'note' in col.lower():
        # Controlla se ha valori non vuoti
        non_null = df_manual[col].dropna()
        non_null = non_null[~non_null.isin(['nan', '', 'NULL'])]
        if len(non_null) > 10:
            print(f"  Colonna candidata: '{col}' ({len(non_null)} valori)")
            if manual_analysis_col is None:
                manual_analysis_col = col

if manual_analysis_col is None:
    # Cerca in tutte le colonne quella con testo di analisi
    print("\n  Cerco colonna con analisi manuali...")
    for col in df_manual.columns:
        sample = df_manual[col].dropna().head(5).tolist()
        sample_str = ' '.join(str(s) for s in sample).lower()
        if any(kw in sample_str for kw in ['cessato', 'dispositivo', 'ticket', 'cliente', 'risolto']):
            non_null = df_manual[col].dropna()
            non_null = non_null[~non_null.isin(['nan', '', 'NULL'])]
            if len(non_null) > 10:
                print(f"  Trovata: '{col}' ({len(non_null)} valori)")
                manual_analysis_col = col
                break

if manual_analysis_col:
    print(f"\n  Usando colonna manuale: '{manual_analysis_col}'")

    # Merge su id_interaction
    id_col = 'id_interaction'
    df_manual_clean = df_manual[[id_col, manual_analysis_col]].copy()
    df_manual_clean = df_manual_clean.rename(columns={manual_analysis_col: 'analisi_manuale'})
    df_manual_clean = df_manual_clean.dropna(subset=['analisi_manuale'])
    df_manual_clean = df_manual_clean[~df_manual_clean['analisi_manuale'].isin(['nan', '', 'NULL'])]

    print(f"  Analisi manuali disponibili: {len(df_manual_clean)}")

    # Merge
    df_compare = df_output[[id_col, 'Analisi']].merge(
        df_manual_clean, on=id_col, how='inner'
    )
    print(f"  Ticket in comune: {len(df_compare)}")

    if len(df_compare) > 0:
        # Confronto
        def normalize(text):
            if pd.isna(text):
                return ''
            return str(text).strip().lower().rstrip('.')

        df_compare['norm_auto'] = df_compare['Analisi'].apply(normalize)
        df_compare['norm_manual'] = df_compare['analisi_manuale'].apply(normalize)

        # Match esatto
        exact = (df_compare['norm_auto'] == df_compare['norm_manual']).sum()
        print(f"\n  Match esatto: {exact}/{len(df_compare)} ({exact/len(df_compare)*100:.1f}%)")

        # Match parziale (contenuto)
        partial = 0
        for _, r in df_compare.iterrows():
            auto = r['norm_auto']
            manual = r['norm_manual']
            if auto == manual:
                partial += 1
            elif auto in manual or manual in auto:
                partial += 1
            elif any(w in auto for w in manual.split() if len(w) > 4):
                partial += 1
        print(f"  Match parziale: {partial}/{len(df_compare)} ({partial/len(df_compare)*100:.1f}%)")

        # Categorizzazione discordanze
        print(f"\n  ANALISI DISCORDANZE (sample di 30 non-match):")
        print(f"  {'-' * 60}")

        mismatches = df_compare[df_compare['norm_auto'] != df_compare['norm_manual']]
        sample_size = min(30, len(mismatches))
        if sample_size > 0:
            sample = mismatches.sample(n=sample_size, random_state=42)
            for _, r in sample.iterrows():
                print(f"\n  Ticket: {r[id_col]}")
                print(f"    AUTO:    {str(r['Analisi'])[:120]}")
                print(f"    MANUALE: {str(r['analisi_manuale'])[:120]}")

        # Categorizza tipo di discordanza
        print(f"\n\n  TIPOLOGIE DISCORDANZE:")
        print(f"  {'-' * 60}")

        categories = Counter()
        for _, r in mismatches.iterrows():
            auto = r['norm_auto']
            manual = r['norm_manual']

            if 'cessato' in manual and 'cessato' not in auto:
                categories['Manual dice cessato, auto no'] += 1
            elif 'risolto' in manual and 'risolto' not in auto:
                categories['Manual dice risolto, auto no'] += 1
            elif 'risolto' in auto and 'risolto' not in manual:
                categories['Auto dice risolto, manual no'] += 1
            elif 'contatto ko' in manual or 'mancato' in manual:
                categories['Manual cita contatto ko'] += 1
            elif 'pagando' in auto and 'pagando' not in manual:
                categories['Auto aggiunge info pagamento'] += 1
            elif 'recesso' in manual and 'recesso' not in auto:
                categories['Manual cita recesso, auto no'] += 1
            elif 'dispositivo attivo' in auto and 'dispositivo attivo' not in manual:
                categories['Auto dice disp attivo (fallback)'] += 1
            else:
                categories['Altro'] += 1

        for cat, count in categories.most_common():
            pct = count / len(mismatches) * 100
            print(f"    [{count:4d}] ({pct:5.1f}%) {cat}")
else:
    print("  ATTENZIONE: colonna analisi manuale non trovata!")
    print(f"  Colonne disponibili: {list(df_manual.columns)}")

# === 4. Analisi coerenza interna ===
print(f"\n{'=' * 70}")
print("COERENZA INTERNA")
print("=" * 70)

# Verifica: se stato_contratto=CESSATO, l'analisi dovrebbe menzionare cessato
if 'stato_contratto' in df_output.columns:
    cessati = df_output[df_output['stato_contratto'].str.upper().str.strip() == 'CESSATO']
    cessati_ok = cessati['Analisi'].str.lower().str.contains('cessat|discordant|recesso', na=False)
    print(f"\n  Contratti CESSATI: {len(cessati)}")
    print(f"    Con analisi coerente: {cessati_ok.sum()} ({cessati_ok.sum()/len(cessati)*100:.1f}%)")
    cessati_ko = cessati[~cessati_ok]
    if len(cessati_ko) > 0:
        print(f"    Incoerenti (sample): ")
        for _, r in cessati_ko.head(5).iterrows():
            print(f"      {r['id_interaction']}: contratto={r['stato_contratto']}, disp={r.get('stato_dispositivo','?')}, obu={r.get('stato_obu','?')} -> {str(r['Analisi'])[:80]}")

# Verifica: se STATO FATTURA=OK e dispositivo ATTIVO, dovrebbe menzionare "pagando"
if 'STATO FATTURA' in df_output.columns and 'stato_dispositivo' in df_output.columns:
    paga_attivo = df_output[
        (df_output['STATO FATTURA'].str.strip().str.upper() == 'OK') &
        (df_output['stato_dispositivo'].str.strip().str.upper() == 'ATTIVO')
    ]
    mentions_paga = paga_attivo['Analisi'].str.lower().str.contains('pagando|paga|fattura', na=False)
    print(f"\n  Fattura OK + Dispositivo ATTIVO: {len(paga_attivo)}")
    print(f"    Menziona pagamento: {mentions_paga.sum()} ({mentions_paga.sum()/max(len(paga_attivo),1)*100:.1f}%)")

# Verifica: contratto ATTIVO, dispositivo CESSATO, obu CESSATO -> "Risolto"
if all(c in df_output.columns for c in ['stato_contratto', 'stato_dispositivo', 'stato_obu']):
    acc = df_output[
        (df_output['stato_contratto'].str.strip().str.upper() == 'ATTIVO') &
        (df_output['stato_dispositivo'].str.strip().str.upper() == 'CESSATO') &
        (df_output['stato_obu'].str.strip().str.upper() == 'CESSATO')
    ]
    risolto = acc['Analisi'].str.lower().str.contains('risolto', na=False)
    print(f"\n  ATTIVO/CESSATO/CESSATO: {len(acc)}")
    print(f"    Dice 'Risolto': {risolto.sum()} ({risolto.sum()/max(len(acc),1)*100:.1f}%)")

# === 5. Sample casuale per review manuale ===
print(f"\n{'=' * 70}")
print("SAMPLE CASUALE PER REVIEW (50 ticket)")
print("=" * 70)

random.seed(123)
sample_indices = random.sample(range(len(df_output)), 50)
for i, idx in enumerate(sample_indices[:50]):
    row = df_output.iloc[idx]
    print(f"\n  [{i+1:2d}] Ticket: {row.get('id_interaction', '?')}")
    print(f"      Contratto: {row.get('stato_contratto', '?')} | Dispositivo: {row.get('stato_dispositivo', '?')} | OBU: {row.get('stato_obu', '?')}")
    print(f"      Fattura: {row.get('STATO FATTURA', '?')} | Status: {row.get('pystatuswork', '?')}")
    print(f"      -> ANALISI: {str(row.get('Analisi', ''))[:120]}")

print(f"\n{'=' * 70}")
print("FINE QUALITY CHECK")
print("=" * 70)
