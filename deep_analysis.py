#!/usr/bin/env python3
"""
Deep analysis: studia le discordanze per capire come migliorare le regole.
"""
import pandas as pd
import json
from collections import Counter

# Carica dati
df_output = pd.read_excel("output_analisi.xlsx", dtype=str)
df_manual = pd.read_excel(
    "Copia di Restituzione_device_aggiuntivi_ANALISI OPS.xlsx",
    sheet_name=0, dtype=str
)

# Trova analisi manuali
manual_col = 'Analisi '
df_manual_clean = df_manual[['id_interaction', manual_col]].copy()
df_manual_clean = df_manual_clean.rename(columns={manual_col: 'analisi_manuale'})
df_manual_clean = df_manual_clean.dropna(subset=['analisi_manuale'])
df_manual_clean = df_manual_clean[~df_manual_clean['analisi_manuale'].isin(['nan', '', 'NULL'])]

# Merge
df_compare = df_output.merge(df_manual_clean, on='id_interaction', how='inner')

def normalize(text):
    if pd.isna(text):
        return ''
    return str(text).strip().lower().rstrip('.')

df_compare['norm_auto'] = df_compare['Analisi'].apply(normalize)
df_compare['norm_manual'] = df_compare['analisi_manuale'].apply(normalize)
mismatches = df_compare[df_compare['norm_auto'] != df_compare['norm_manual']].copy()

print(f"Totale confronti: {len(df_compare)}")
print(f"Discordanze: {len(mismatches)}")

# === 1. Analisi dettagliata per pattern manuale ===
print(f"\n{'='*70}")
print("PATTERN ANALISI MANUALI NON MATCHATI")
print(f"{'='*70}")

manual_patterns = Counter()
for _, r in mismatches.iterrows():
    manual_patterns[r['norm_manual']] += 1

for pattern, count in manual_patterns.most_common(30):
    print(f"  [{count:3d}] {pattern[:120]}")

# === 2. Per ogni pattern manuale, cosa dice l'auto ===
print(f"\n{'='*70}")
print("PATTERN MANUALI vs AUTO (dettaglio)")
print(f"{'='*70}")

for pattern, count in manual_patterns.most_common(15):
    print(f"\n  MANUALE: '{pattern[:100]}' ({count} casi)")
    auto_vals = mismatches[mismatches['norm_manual'] == pattern]['norm_auto'].value_counts()
    for auto_val, auto_count in auto_vals.head(5).items():
        print(f"    AUTO: [{auto_count}] {auto_val[:100]}")

# === 3. Analisi "sta pagando" - quando è giusto e quando no ===
print(f"\n{'='*70}")
print("ANALISI 'STA PAGANDO' - discordanze")
print(f"{'='*70}")

pagando_mismatches = mismatches[
    mismatches['norm_auto'].str.contains('pagando', na=False) &
    ~mismatches['norm_manual'].str.contains('pagando', na=False)
]
print(f"Auto dice 'pagando', manuale no: {len(pagando_mismatches)}")

# Che dice il manuale in questi casi?
pagando_manual = Counter()
for _, r in pagando_mismatches.iterrows():
    pagando_manual[r['norm_manual']] += 1
print("\nCosa dice il manuale:")
for pattern, count in pagando_manual.most_common(15):
    print(f"  [{count:3d}] {pattern[:120]}")

# Caso opposto
pagando_miss = mismatches[
    ~mismatches['norm_auto'].str.contains('pagando', na=False) &
    mismatches['norm_manual'].str.contains('pagando', na=False)
]
print(f"\nManuale dice 'pagando', auto no: {len(pagando_miss)}")
for _, r in pagando_miss.head(5).iterrows():
    print(f"  AUTO: {r['norm_auto'][:80]}")
    print(f"  MANU: {r['norm_manual'][:80]}")
    print()

# === 4. Analisi "dispositivo cessato" dal manuale ===
print(f"\n{'='*70}")
print("ANALISI 'DISPOSITIVO CESSATO' nel manuale")
print(f"{'='*70}")

cessato_manual = mismatches[mismatches['norm_manual'].str.contains('dispositivo cessato|obu cessat', na=False)]
print(f"Manuale dice 'dispositivo/obu cessato': {len(cessato_manual)}")
print("\nStati reali di questi ticket:")
for _, r in cessato_manual.head(15).iterrows():
    print(f"  {r['id_interaction']}: contratto={r.get('stato_contratto','?')}, "
          f"disp={r.get('stato_dispositivo','?')}, obu={r.get('stato_obu','?')}, "
          f"fattura={r.get('STATO FATTURA','?')}")
    print(f"    AUTO:    {r['norm_auto'][:100]}")
    print(f"    MANUALE: {r['norm_manual'][:100]}")

# === 5. Analisi keyword nei post per i mismatch ===
print(f"\n{'='*70}")
print("ANALISI POST/NOTE DEI TICKET DISCORDANTI")
print(f"{'='*70}")

# Carica i lookup
from services.data_loader import DataLoader
data = DataLoader("Restituzione_device_aggiuntivi_ANALISI OPS_Personale.xlsx").load()

# Per ogni mismatch, mostra i post
print("\nSample di 40 discordanze con post/note:")
for i, (_, r) in enumerate(mismatches.head(40).iterrows()):
    tid = r['id_interaction']
    cid = str(r.get('ClienteID', '')).strip()

    posts = data.post_ticket_lookup.get(tid, [])
    notes = data.notes_lookup.get(tid, [])
    client_posts = data.post_pulse_lookup.get(cid, []) if cid and cid.lower() not in ('nan','','none') else []

    print(f"\n  [{i+1:2d}] Ticket: {tid}")
    print(f"      Stati: contratto={r.get('stato_contratto','?')}, disp={r.get('stato_dispositivo','?')}, "
          f"obu={r.get('stato_obu','?')}, fattura={r.get('STATO FATTURA','?')}, status={r.get('pystatuswork','?')}")
    print(f"      AUTO:    {r['norm_auto'][:120]}")
    print(f"      MANUALE: {r['norm_manual'][:120]}")

    if posts:
        print(f"      POSTS ({len(posts)}):")
        for p in posts[:3]:
            print(f"        - {p[:150]}")
    if notes:
        print(f"      NOTES ({len(notes)}):")
        for n in notes[:2]:
            for k, v in n.items():
                print(f"        {k}: {v[:150]}")
    if client_posts:
        # Solo quelli che menzionano il ticket
        relevant = [p for p in client_posts if tid in p]
        if relevant:
            print(f"      CLIENT_POSTS (relevant {len(relevant)}):")
            for p in relevant[:2]:
                print(f"        - {p[:150]}")

# === 6. Pattern "obu cessato/sospeso" nei post ===
print(f"\n{'='*70}")
print("KEYWORD 'OBU CESSATO/SOSPESO' nei post dei mismatch")
print(f"{'='*70}")

obu_keywords = ['obu cessato', 'obu sospeso', 'obu cessati', 'obu sospesi',
                'cessazione obu', 'cessato obu', 'sospeso obu']
count_obu = 0
for _, r in mismatches.iterrows():
    tid = r['id_interaction']
    cid = str(r.get('ClienteID', '')).strip()
    posts = data.post_ticket_lookup.get(tid, [])
    notes_list = data.notes_lookup.get(tid, [])
    all_text = ' '.join(posts)
    for n in notes_list:
        all_text += ' '.join(n.values())
    if cid and cid.lower() not in ('nan','','none'):
        for p in data.post_pulse_lookup.get(cid, []):
            all_text += ' ' + p

    text_lower = all_text.lower()
    if any(kw in text_lower for kw in obu_keywords):
        count_obu += 1
        if count_obu <= 10:
            print(f"  {r['id_interaction']}: disp={r.get('stato_dispositivo','?')}, obu={r.get('stato_obu','?')}")
            print(f"    AUTO:    {r['norm_auto'][:100]}")
            print(f"    MANUALE: {r['norm_manual'][:100]}")

print(f"\n  Totale con keyword obu cessato/sospeso: {count_obu}")

# === 7. Pattern "rimozione in chiamata" nei post ===
print(f"\n{'='*70}")
print("KEYWORD 'RIMOZIONE' nei post dei mismatch")
print(f"{'='*70}")

rimozione_kw = ['rimozione', 'rimosso', 'rimossa', 'rimuovere', 'rimoz']
count_rim = 0
for _, r in mismatches.iterrows():
    tid = r['id_interaction']
    posts = data.post_ticket_lookup.get(tid, [])
    notes_list = data.notes_lookup.get(tid, [])
    all_text = ' '.join(posts)
    for n in notes_list:
        all_text += ' '.join(n.values())

    text_lower = all_text.lower()
    if any(kw in text_lower for kw in rimozione_kw):
        count_rim += 1
        if count_rim <= 10:
            print(f"  {r['id_interaction']}")
            print(f"    AUTO:    {r['norm_auto'][:100]}")
            print(f"    MANUALE: {r['norm_manual'][:100]}")

print(f"\n  Totale con keyword rimozione: {count_rim}")

# === 8. Analisi "recesso" ===
print(f"\n{'='*70}")
print("KEYWORD 'RECESSO' nei post dei mismatch")
print(f"{'='*70}")

count_rec = 0
for _, r in mismatches.iterrows():
    tid = r['id_interaction']
    cid = str(r.get('ClienteID', '')).strip()
    posts = data.post_ticket_lookup.get(tid, [])
    notes_list = data.notes_lookup.get(tid, [])
    all_text = ' '.join(posts)
    for n in notes_list:
        all_text += ' '.join(n.values())
    if cid and cid.lower() not in ('nan','','none'):
        for p in data.post_pulse_lookup.get(cid, []):
            if tid in p:
                all_text += ' ' + p

    text_lower = all_text.lower()
    if 'recesso' in text_lower:
        count_rec += 1
        if count_rec <= 10:
            print(f"  {r['id_interaction']}: flag_recesso={r.get('flag_recesso_obu','?')}")
            print(f"    AUTO:    {r['norm_auto'][:100]}")
            print(f"    MANUALE: {r['norm_manual'][:100]}")

print(f"\n  Totale con keyword recesso: {count_rec}")

# === 9. Distribuzione stati per i mismatch ===
print(f"\n{'='*70}")
print("DISTRIBUZIONE STATI NEI MISMATCH")
print(f"{'='*70}")

state_combos = Counter()
for _, r in mismatches.iterrows():
    combo = f"{r.get('stato_contratto','?')}/{r.get('stato_dispositivo','?')}/{r.get('stato_obu','?')}"
    state_combos[combo] += 1

for combo, count in state_combos.most_common(10):
    print(f"  [{count:3d}] {combo}")
