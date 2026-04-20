"""
Rule engine per l'analisi deterministica dei ticket.

CONTESTO UNIVERSALE:
  Tutti i ticket nascono perché il cliente ha RICEVUTO un secondo dispositivo OBU
  (o un dispositivo aggiuntivo), spesso senza averlo esplicitamente richiesto.
  L'analisi deve capire:
    - se il cliente ha effettivamente ricevuto un dispositivo extra
    - se lo aveva richiesto o no
    - se vuole restituirlo / se è già stato restituito
    - se i dati strutturali confermano la presenza del secondo dispositivo
  Anomalia tipica: il cliente lamenta di avere 1 solo OBU (premessa contraddetta),
  oppure dichiara di averne ricevuti 2 aggiuntivi, o di possederne 3.

TIER1: regole basate solo su stati strutturati (no testo).
TIER2: regole basate su keyword nei testi (post/note).
"""

import re


# ═══════════════════════════════════════════════════════════════
# UTILITY
# ═══════════════════════════════════════════════════════════════

def _field(row, name):
    """Estrae un campo dalla riga, normalizzato uppercase. Ritorna '' se nullo."""
    val = row.get(name, '')
    if val is None or str(val).strip().lower() in ('nan', '', 'none', 'null'):
        return ''
    return str(val).strip().upper()


def _contains_any(text, keywords):
    """Controlla se il testo contiene almeno una delle keyword (case-insensitive)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def _contains_none(text, keywords):
    """True se NESSUNA keyword è presente nel testo (filtro negativo)."""
    text_lower = text.lower()
    return not any(kw in text_lower for kw in keywords)


def _word_match(text, patterns):
    """Controlla se il testo contiene una delle parole/frasi come parola intera."""
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(r'\b' + re.escape(pattern) + r'\b', text_lower):
            return True
    return False


def _has_rientro(row):
    """True se data_rientro_in_magazzino è popolato."""
    return _field(row, 'data_rientro_in_magazzino') != ''


def _is_rejected(row):
    """True se pystatuswork contiene REJECTED."""
    return 'REJECTED' in _field(row, 'pystatuswork')


def _fattura_attiva(row):
    """True se STATO FATTURA=OK (processo di fatturazione attivo — NON implica pagamento effettivo).

    ATTENZIONE: FATTURA OK significa solo che il ciclo di fatturazione è in corso,
    NON che il cliente stia effettivamente pagando.
    """
    return _field(row, 'STATO FATTURA') == 'OK'


# ═══════════════════════════════════════════════════════════════
# EXTRACT TEXTS (API invariata)
# ═══════════════════════════════════════════════════════════════

def extract_texts(ticket_id, client_id, post_ticket_lookup, notes_lookup, post_pulse_lookup):
    """Estrae testi separati: post operatore, note cliente, e testo combinato."""
    # Post operatore sul ticket
    post_parts = []
    for post in post_ticket_lookup.get(ticket_id, []):
        post_parts.append(post)

    # Note del ticket (cliente, operatore, chiusura)
    note_parts = []
    note_cliente_parts = []
    for note_dict in notes_lookup.get(ticket_id, []):
        for key, val in note_dict.items():
            if val:
                note_parts.append(val)
                if key == 'nota_cliente':
                    note_cliente_parts.append(val)

    # Testo diretto del ticket (post + note)
    ticket_text = ' '.join(post_parts + note_parts)

    # Solo post operatore (senza note cliente)
    post_text = ' '.join(post_parts)

    # Solo note cliente
    note_cliente_text = ' '.join(note_cliente_parts)

    # Testo cliente: post su anagrafica (possono riguardare altri ticket)
    client_parts = []
    if client_id:
        for post in post_pulse_lookup.get(client_id, []):
            # Priorità ai post che menzionano questo ticket
            if ticket_id in post:
                post_parts.append(post)
            else:
                client_parts.append(post)
    client_text = ' '.join(client_parts)

    # Testo combinato
    all_text = ticket_text + ' ' + client_text
    return ticket_text, client_text, all_text, post_text, note_cliente_text


# ═══════════════════════════════════════════════════════════════
# TIER 1: Regole basate solo su stati strutturati (no testo)
# ═══════════════════════════════════════════════════════════════

# --- Branch F: NOTE pre-emption (prima di tutto) ---

def _t1_50_note_obu_non_presente(row):
    """NOTE = OBU NON PRESENTE."""
    if _field(row, 'NOTE') == 'OBU NON PRESENTE':
        return "OBU non presente sul contratto"
    return None


def _t1_51_note_obu_altro_contratto(row):
    """NOTE = OBU ASSOCIATO AD ALTRO CONTRATTO."""
    if _field(row, 'NOTE') == 'OBU ASSOCIATO AD ALTRO CONTRATTO':
        return "OBU associato ad altro contratto"
    return None


# --- Branch F2: Mismatch numero OBU (TIER1 pre-emption) ---

def _t1_52_un_solo_obu_richiede_recesso_secondo(row):
    """Premessa contraddetta: il ticket riguarda un secondo OBU ma il contratto ne ha uno solo.

    Tutti i ticket partono dall'assunto che il cliente abbia ricevuto un secondo
    dispositivo. Se num_obu=1, la premessa è incongruente con i dati strutturali:
    o il secondo OBU non è mai stato attivato/registrato, o il cliente sta
    chiedendo qualcosa di diverso (recesso totale, reclamo, ecc.).
    """
    num_obu_raw = _field(row, 'num_obu')
    if num_obu_raw == '1':
        return ("ANOMALIA: Il ticket presuppone un secondo dispositivo ma il contratto "
                "ha un solo OBU. Verificare se il secondo OBU non risulta registrato "
                "o se il cliente necessita di recesso totale")
    return None


# --- Branch A: Contratto CESSATO ---

def _t1_01_cess_cess_cess(row):
    """CESS/CESS/CESS."""
    if (_field(row, 'stato_contratto') == 'CESSATO' and
            _field(row, 'stato_dispositivo') == 'CESSATO' and
            _field(row, 'stato_obu') == 'CESSATO'):
        return "Contratto cessato, dispositivo e OBU cessati. Verificare coerenza fatturazione"
    return None


def _t1_02_cess_cess_att(row):
    """CESS/CESS/ATT."""
    if (_field(row, 'stato_contratto') == 'CESSATO' and
            _field(row, 'stato_dispositivo') == 'CESSATO' and
            _field(row, 'stato_obu') == 'ATTIVO'):
        return "Stati discordanti: contratto e dispositivo cessati, OBU ancora attivo. Necessario allineamento IT"
    return None


def _t1_03_cess_riconse(row):
    """CESS/RICONSE/qualsiasi."""
    if (_field(row, 'stato_contratto') == 'CESSATO' and
            _field(row, 'stato_dispositivo') == 'RICONSEGNATO'):
        return "Contratto cessato, dispositivo riconsegnato"
    return None


def _t1_04_cess_sosp(row):
    """CESS/SOSP/qualsiasi."""
    if (_field(row, 'stato_contratto') == 'CESSATO' and
            _field(row, 'stato_dispositivo') == 'SOSPESO'):
        return "Stati discordanti: contratto cessato, dispositivo sospeso. Necessario allineamento IT"
    return None


def _t1_05_cess_att(row):
    """CESS/ATT/qualsiasi."""
    if (_field(row, 'stato_contratto') == 'CESSATO' and
            _field(row, 'stato_dispositivo') == 'ATTIVO'):
        return "Contratto cessato ma dispositivo ancora attivo. Necessario allineamento IT"
    return None


def _t1_06_cess_catchall(row):
    """CESS/catch-all."""
    if _field(row, 'stato_contratto') == 'CESSATO':
        return "Contratto cessato. Verificare stati dispositivo e OBU"
    return None


# --- Branch B: Contratto ATTIVO + flag recesso ---

def _t1_10_recesso_obu(row):
    """flag_recesso_obu=S + OBU CESS."""
    if (_field(row, 'flag_recesso_obu') == 'S' and
            _field(row, 'stato_obu') == 'CESSATO'):
        return "OBU cessati per recesso"
    return None


# --- Branch C: Contratto ATTIVO + Dispositivo CESSATO ---

def _t1_20_att_cess_cess_rientro(row):
    """ATT/CESS/CESS + ha data_rientro."""
    if (_field(row, 'stato_contratto') == 'ATTIVO' and
            _field(row, 'stato_dispositivo') == 'CESSATO' and
            _field(row, 'stato_obu') == 'CESSATO' and
            _has_rientro(row)):
        return "Dispositivo cessato e rientrato a magazzino. Restituzione completata"
    return None


def _t1_21_att_cess_cess_no_rientro(row):
    """ATT/CESS/CESS + no rientro."""
    if (_field(row, 'stato_contratto') == 'ATTIVO' and
            _field(row, 'stato_dispositivo') == 'CESSATO' and
            _field(row, 'stato_obu') == 'CESSATO'):
        return "Dispositivo e OBU cessati. Verificare rientro a magazzino"
    return None


def _t1_22_att_cess_att_fattura(row):
    """ATT/CESS/ATT + FATTURA OK.

    NOTA: FATTURA OK = ciclo di fatturazione attivo, non prova di pagamento.
    """
    if (_field(row, 'stato_contratto') == 'ATTIVO' and
            _field(row, 'stato_dispositivo') == 'CESSATO' and
            _field(row, 'stato_obu') == 'ATTIVO' and
            _field(row, 'STATO FATTURA') == 'OK'):
        return "Dispositivo cessato ma OBU ancora attivo. Fatturazione attiva (verifica allineamento IT)"
    return None


def _t1_23_att_cess_att(row):
    """ATT/CESS/ATT."""
    if (_field(row, 'stato_contratto') == 'ATTIVO' and
            _field(row, 'stato_dispositivo') == 'CESSATO' and
            _field(row, 'stato_obu') == 'ATTIVO'):
        return "Dispositivo cessato ma OBU ancora attivo. Necessario allineamento IT"
    return None


# --- Branch D: Contratto ATTIVO + Dispositivo RICONSEGNATO ---

def _t1_30_att_riconse_cess_rientro(row):
    """ATT/RICONSE/CESS + rientro."""
    if (_field(row, 'stato_contratto') == 'ATTIVO' and
            _field(row, 'stato_dispositivo') == 'RICONSEGNATO' and
            _field(row, 'stato_obu') == 'CESSATO' and
            _has_rientro(row)):
        return "Dispositivo riconsegnato e rientrato a magazzino"
    return None


def _t1_31_att_riconse_att(row):
    """ATT/RICONSE/ATT."""
    if (_field(row, 'stato_contratto') == 'ATTIVO' and
            _field(row, 'stato_dispositivo') == 'RICONSEGNATO' and
            _field(row, 'stato_obu') == 'ATTIVO'):
        return "Dispositivo riconsegnato ma OBU ancora attivo. Necessario allineamento IT"
    return None


def _t1_32_att_riconse_catchall(row):
    """ATT/RICONSE (catch-all)."""
    if (_field(row, 'stato_contratto') == 'ATTIVO' and
            _field(row, 'stato_dispositivo') == 'RICONSEGNATO'):
        return "Dispositivo riconsegnato"
    return None


# --- Branch E: Contratto ATTIVO + Dispositivo ATTIVO → passa a TIER2 ---

def _t1_40_att_att(row):
    """ATT/ATT/qualsiasi → None (serve TIER2)."""
    if (_field(row, 'stato_contratto') == 'ATTIVO' and
            _field(row, 'stato_dispositivo') == 'ATTIVO'):
        return None
    return None


# --- Branch G: Stati speciali ---

def _t1_60_sospeso(row):
    """qualsiasi/SOSPESO/qualsiasi (non cessato)."""
    if (_field(row, 'stato_contratto') != 'CESSATO' and
            _field(row, 'stato_dispositivo') == 'SOSPESO'):
        return "Dispositivo sospeso. Necessario allineamento IT"
    return None


def _t1_61_da_attivare(row):
    """qualsiasi/DA ATTIVARE/qualsiasi."""
    if _field(row, 'stato_dispositivo') == 'DA ATTIVARE':
        return "Dispositivo da attivare, restituzione non applicabile"
    return None


def _t1_62_in_attivazione(row):
    """IN ATTIVAZIONE/qualsiasi."""
    if _field(row, 'stato_contratto') == 'IN ATTIVAZIONE':
        return "Contratto in attivazione"
    return None


TIER1_RULES = [
    # Branch F: NOTE pre-emption
    _t1_50_note_obu_non_presente,
    _t1_51_note_obu_altro_contratto,
    # Branch F2: Mismatch numero OBU
    _t1_52_un_solo_obu_richiede_recesso_secondo,
    # Branch A: Contratto CESSATO (ordine specifico → generico)
    _t1_01_cess_cess_cess,
    _t1_02_cess_cess_att,
    _t1_03_cess_riconse,
    _t1_04_cess_sosp,
    _t1_05_cess_att,
    _t1_06_cess_catchall,
    # Branch B: flag recesso
    _t1_10_recesso_obu,
    # Branch C: ATTIVO + Dispositivo CESSATO
    _t1_20_att_cess_cess_rientro,
    _t1_21_att_cess_cess_no_rientro,
    _t1_22_att_cess_att_fattura,
    _t1_23_att_cess_att,
    # Branch D: ATTIVO + Dispositivo RICONSEGNATO
    _t1_30_att_riconse_cess_rientro,
    _t1_31_att_riconse_att,
    _t1_32_att_riconse_catchall,
    # Branch E: ATTIVO/ATTIVO → None (passa a TIER2, non serve in lista)
    # Branch G: Stati speciali
    _t1_60_sospeso,
    _t1_61_da_attivare,
    _t1_62_in_attivazione,
]


# ═══════════════════════════════════════════════════════════════
# TIER 2: Regole basate su keyword nei testi
# Ordine CRITICO: azioni risolutive PRIMA di contatto ko
# ═══════════════════════════════════════════════════════════════

# --- Keyword sets ---
_OTP_SIGNALS = ['otp ok', 'con otp', 'procedura otp', 'codici otp', 'gestito con otp',
                'inviati otp', 'inviato otp', 'tramite otp', 'otp inviati', 'otp inviato',
                'codice otp', 'inserimento dei due otp', 'inserimento otp',
                'inv.otp', 'invio codice otp', 'gestito ticket con codice otp',
                'gestito ticket con invio codice otp']
_OTP_NEG = ['non poteva', 'errore', 'ko otp', 'non funziona', 'non riesce', 'problema con otp',
            'non riceve otp', 'non riceve codice', 'si rifiuta', 'problemi nell inserire',
            'problemi otp', 'problemi a livello']
_LDV_SIGNALS = ['lettera di vettura', 'ldv']

# --- Gruppo 0: Anomalie conteggio OBU (massima priorità TIER2) ---

# Pattern che indicano che il cliente possiede 3 OBU
_TRE_OBU_PATTERNS = [
    'tre obu', '3 obu', 'tre dispositivi', '3 dispositivi',
    'tre apparati', '3 apparati', 'terzo dispositivo', 'terzo obu',
    'ha tre', 'ha 3 obu', '3 box', 'tre box',
]

# Pattern che indicano che il cliente ha ricevuto 2 OBU aggiuntivi (invece di 1)
_DUE_OBU_AGGIUNTIVI_PATTERNS = [
    'due obu aggiuntivi', '2 obu aggiuntivi', 'due dispositivi aggiuntivi',
    '2 dispositivi aggiuntivi', 'due aggiuntivi', '2 aggiuntivi',
    'ricevuto due', 'ricevuti due obu', 'arrivati due', 'arrivati 2 obu',
    'inviati due obu', 'inviato due obu',
    'due box aggiuntivi', '2 box aggiuntivi',
]


def _t2_00_tre_obu(row, text):
    """Cliente ha 3 OBU: la richiesta di 'secondo dispositivo' è potenzialmente ambigua."""
    if _contains_any(text, _TRE_OBU_PATTERNS):
        return ("ANOMALIA OBU: Testo suggerisce presenza di 3 dispositivi OBU. "
                "Verificare quale dei due dispositivi aggiuntivi si intende restituire")
    return None


def _t2_00b_due_obu_aggiuntivi(row, text):
    """Cliente ha ricevuto 2 OBU aggiuntivi invece di 1: anomalia nella spedizione/attivazione."""
    if _contains_any(text, _DUE_OBU_AGGIUNTIVI_PATTERNS):
        return ("ANOMALIA OBU: Testo indica ricezione di 2 dispositivi aggiuntivi (invece di 1). "
                "Verificare quale restituire e se entrambi sono stati attivati")
    return None


# --- Gruppo 1: Meta-ticket ---

def _t2_01_ticket_doppio(row, text):
    """Ticket duplicato/doppio."""
    if re.search(r'gestito con ticket\s+I-\d+', text, re.IGNORECASE):
        return "Ticket duplicato"
    if re.search(r'già\s+lavorat[ao]\s+con\s+ticket', text, re.IGNORECASE):
        return "Ticket duplicato"
    if _word_match(text, ['ticket doppio', 'tkt doppio', 'tk doppio', 'tt doppio',
                          'duplicato', 'in quanto doppio', 'perché doppio',
                          'perche doppio']):
        return "Ticket duplicato"
    return None


def _t2_02_annullato(row, text):
    """Ticket annullato."""
    # _contains_any instead of _word_match: posts often glue ticket ID to word (e.g. "I-123annullo")
    if _contains_any(text, ['annullo ', 'annullo\n', 'annullato', 'annullata richiesta',
                            'annullare rimozione', 'annullo ticket',
                            'annulla pratica', 'annulla la procedura',
                            'annulliamo', 'annulla la richiesta',
                            'annulla procedura', 'annullare la pratica']):
        return "Ticket annullato"
    # Catch "I-XXXXXXannullo" pattern (ticket ID glued to word)
    if re.search(r'I-\d+\s*annull', text, re.IGNORECASE):
        return "Ticket annullato"
    return None


# --- Gruppo 2: Azioni risolutive ---

def _t2_10_otp_ldv(row, text):
    """OTP + LDV (flusso unico)."""
    has_otp = _contains_any(text, _OTP_SIGNALS) and _contains_none(text, _OTP_NEG)
    has_ldv = _contains_any(text, _LDV_SIGNALS)
    if has_otp and has_ldv:
        return "Eseguita procedura OTP e inviata lettera di vettura"
    return None


def _t2_11_solo_otp(row, text):
    """Solo OTP (senza LDV)."""
    has_otp = _contains_any(text, _OTP_SIGNALS) and _contains_none(text, _OTP_NEG)
    has_ldv = _contains_any(text, _LDV_SIGNALS)
    if has_otp and not has_ldv:
        return "Eseguita procedura OTP"
    return None


def _t2_12_solo_ldv(row, text):
    """Solo LDV (senza OTP)."""
    has_otp = _contains_any(text, _OTP_SIGNALS)
    has_ldv = _contains_any(text, _LDV_SIGNALS)
    if has_ldv and not has_otp:
        return "Inviata lettera di vettura"
    return None


# --- Gruppo 2b: Riconsegna effettuata ---

def _t2_13_riconsegna(row, text):
    """Procedura riconsegna effettuata."""
    if _contains_any(text, ['procedura riconsegna', 'procedura per riconsegna',
                            'effettuata riconsegna', 'riconsegna effettuata',
                            'riconsegna completata']):
        return "Effettuata procedura di riconsegna dispositivo"
    return None


# --- Gruppo 3: Escalation ---

def _t2_20_ahd(row, text):
    """Aperto AHD."""
    if _contains_any(text, ['aperto ahd', 'apertura ahd', 'ahd cs']):
        return "Aperto AHD"
    return None


# --- Gruppo 4: Intento cliente ---

def _t2_30_cambiato_idea(row, text):
    """Cliente ha cambiato idea."""
    if _word_match(text, ['cambiato idea', 'cambia idea', 'ci ho ripensato',
                          'ci ha ripensato', 'ha ripensato',
                          'non intende procedere',
                          'vorrei tenerlo', 'vuole tenerlo',
                          'vuole tenere', 'vuole mantenere',
                          'non vuole rimozione', 'non voleva rimuovere',
                          'non vuole rimuovere',
                          'non vuole più procedere', 'non vuole piu procedere']):
        return "Cliente ha cambiato idea"
    return None


def _t2_31_solo_dispositivo_recesso(row, text):
    """Cliente dichiara di avere 1 solo dispositivo → premessa del ticket contraddetta.

    Contesto: il ticket esiste perché si presume che il cliente abbia ricevuto un
    secondo OBU. Se il cliente stesso dichiara di averne uno solo, la premessa è
    contraddetta: il secondo dispositivo non è mai arrivato, oppure c'è un errore
    nell'apertura del ticket.
    """
    if _word_match(text, ['un solo dispositivo', 'unico dispositivo',
                          'solo dispositivo', 'un solo obu', 'unico obu',
                          'solo un obu', 'solo un dispositivo']):
        return ("ANOMALIA: Cliente dichiara di avere un solo dispositivo — premessa "
                "del ticket contraddetta. Verificare se il secondo OBU è mai stato "
                "consegnato o se è necessario recesso totale")
    return None


def _t2_32_chiede_recesso(row, text):
    """Cliente richiede recesso."""
    if _word_match(text, ['chiede recesso', 'richiesta recesso',
                          'procedura recesso', 'vuole recedere',
                          'deve fare recesso', 'deve recedere']):
        return "Cliente richiede procedura di recesso"
    return None


# --- Gruppo 5: Comunicazioni ---

def _t2_40_mail_primaria(row, text):
    """Mail inviata (solo se non è subordinata a OTP/LDV/AHD)."""
    if _contains_any(text, ['inviata mail', 'invio mail', 'mandata mail', 'inviata email']):
        # Filtro negativo: se ci sono OTP/LDV/AHD la mail è secondaria
        if _contains_none(text, ['otp', 'ldv', 'lettera di vettura', 'ahd']):
            return "Inviata comunicazione mail al cliente"
    return None


def _t2_41_contatto_ko(row, text):
    """Mancato contatto con cliente."""
    if _contains_any(text, ['contatto ko', 'cont ko', 'contatti ko',
                            'mancato contatto', 'non risponde']):
        return "Mancato contatto con cliente"
    return None


# --- Gruppo 6: Safety net — template nota chiusura ---

def _t2_50_nota_provato_contattarti(row, text):
    """Nota chiusura: provato a contattarti."""
    if _contains_any(text, ['provato a contattarti', 'non abbiamo ricevuto risposta']):
        return "Mancato contatto con cliente"
    return None


def _t2_51_nota_finalizzato_rimozione(row, text):
    """Nota chiusura: finalizzato rimozione."""
    if _contains_any(text, ['finalizzato la richiesta di rimozione']):
        return "Rimozione dispositivo completata"
    return None


def _t2_52_nota_puoi_recedere(row, text):
    """Nota chiusura: puoi recedere."""
    if _contains_any(text, ['puoi recedere dal contratto']):
        return "Comunicata procedura di recesso"
    return None


def _t2_53_nota_consegnare_pacco(row, text):
    """Nota chiusura: consegnare pacco."""
    if _contains_any(text, ['consegnare il tuo pacco', 'rete punto poste']):
        return "Inviata lettera di vettura"
    return None


TIER2_RULES = [
    # Gruppo 0: Anomalie conteggio OBU (massima priorità TIER2)
    _t2_00_tre_obu,
    _t2_00b_due_obu_aggiuntivi,
    # Gruppo 1: Meta-ticket
    _t2_01_ticket_doppio,
    _t2_02_annullato,
    # Gruppo 2: Azioni risolutive (priorità massima)
    _t2_10_otp_ldv,
    _t2_11_solo_otp,
    _t2_12_solo_ldv,
    # Gruppo 2b: Riconsegna
    _t2_13_riconsegna,
    # Gruppo 3: Escalation
    _t2_20_ahd,
    # Gruppo 4: Intento cliente
    _t2_30_cambiato_idea,
    _t2_31_solo_dispositivo_recesso,
    _t2_32_chiede_recesso,
    # Gruppo 5: Comunicazioni (solo se primaria)
    _t2_40_mail_primaria,
    _t2_41_contatto_ko,
    # Gruppo 6: Safety net — template nota chiusura
    _t2_50_nota_provato_contattarti,
    _t2_51_nota_finalizzato_rimozione,
    _t2_52_nota_puoi_recedere,
    _t2_53_nota_consegnare_pacco,
]


# ═══════════════════════════════════════════════════════════════
# MODIFIER: fatturazione attiva
# NOTA: FATTURA OK = ciclo di fatturazione attivo, NON prova di pagamento
# ═══════════════════════════════════════════════════════════════

_NO_FATTURA_APPEND_PATTERNS = [
    'cambiato idea',
    'recesso',
    'duplicato',
    'annullato',
    'cessato',
    'rientrato',
    'completata',
    'fatturazione',
]


def _add_fattura_attiva(result, row):
    """Aggiunge nota sulla fatturazione attiva se STATO FATTURA=OK e dispositivo ATTIVO.

    IMPORTANTE: FATTURA OK significa che il ciclo di fatturazione è in corso,
    NON che il cliente stia pagando. Non usare la dicitura "Sta pagando".
    """
    result_lower = result.lower()
    if any(pat in result_lower for pat in _NO_FATTURA_APPEND_PATTERNS):
        return result
    if (_field(row, 'STATO FATTURA') == 'OK' and
            _field(row, 'stato_dispositivo') == 'ATTIVO' and
            'fatturazione' not in result_lower and
            'fattura' not in result_lower):
        result += ". Fatturazione attiva sul dispositivo"
    return result


# ═══════════════════════════════════════════════════════════════
# RULE ENGINE
# ═══════════════════════════════════════════════════════════════

class RuleEngine:
    """Valuta le regole in ordine di priorità e ritorna la prima che matcha."""

    def __init__(self):
        self.tier1_rules = TIER1_RULES
        self.tier2_rules = TIER2_RULES

    def evaluate(self, row, ticket_text, client_text, all_text,
                 post_text='', note_cliente_text=''):
        """
        Valuta tutte le regole in ordine.
        Returns: stringa con l'analisi
        """
        # 1. TIER1 (solo stati) → se matcha, ritorna con modifier
        for rule_fn in self.tier1_rules:
            result = rule_fn(row)
            if result is not None:
                return _add_fattura_attiva(result, row)

        # 2. Pre-check nota_cliente per "cambiato idea"
        if note_cliente_text:
            result = _t2_30_cambiato_idea(row, note_cliente_text)
            if result is not None:
                return _add_fattura_attiva(result, row)

        # 3. TIER2 su post_text (post operatore — fonte più affidabile)
        for rule_fn in self.tier2_rules:
            result = rule_fn(row, post_text)
            if result is not None:
                return _add_fattura_attiva(result, row)

        # 4. TIER2 su ticket_text (post + tutte le note)
        for rule_fn in self.tier2_rules:
            result = rule_fn(row, ticket_text)
            if result is not None:
                return _add_fattura_attiva(result, row)

        # 5. TIER2 su client_text (post anagrafica — ultima spiaggia)
        for rule_fn in self.tier2_rules:
            result = rule_fn(row, client_text)
            if result is not None:
                return _add_fattura_attiva(result, row)

        # 6. Fallback
        return self._fallback(row)

    def _fallback(self, row):
        """Analisi di fallback quando nessuna regola matcha."""
        status = _field(row, 'pystatuswork')
        disp = _field(row, 'stato_dispositivo')
        obu = _field(row, 'stato_obu')

        if 'REJECTED' in status:
            ctx = f" (dispositivo: {disp or '?'}, OBU: {obu or '?'})"
            return "Ticket rifiutato" + ctx

        if 'CANCELLED' in status:
            return "Ticket annullato"

        if 'EXPIRED' in status:
            return "Ticket scaduto"

        if status in ('OPEN', 'NEW') or 'OPEN' in status:
            return "Ticket ancora aperto"

        # Default: descrizione stati
        parts = []
        if disp:
            parts.append(f"Dispositivo {disp}")
        if obu:
            parts.append(f"OBU {obu}")
        if _has_rientro(row):
            parts.append("rientrato a magazzino")

        if parts:
            return '. '.join(parts)
        return "Ticket chiuso"
