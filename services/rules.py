"""
Rule engine per l'analisi deterministica dei ticket.
Ogni regola ha una priorità: le regole con priorità più bassa vengono valutate prima.
La prima regola che matcha produce l'output.
"""

import re


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


def _word_match(text, patterns):
    """Controlla se il testo contiene una delle parole/frasi come parola intera."""
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(r'\b' + re.escape(pattern) + r'\b', text_lower):
            return True
    return False


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
# TIER 1: Regole deterministiche basate sugli stati
# ═══════════════════════════════════════════════════════════════

TIER1_RULES = []


def _r1_cessato_cessato_cessato(row, text):
    """Contratto CESSATO, Dispositivo CESSATO, OBU CESSATO."""
    if (_field(row, 'stato_contratto') == 'CESSATO' and
            _field(row, 'stato_dispositivo') == 'CESSATO' and
            _field(row, 'stato_obu') == 'CESSATO'):
        return ("Contratto cessato - non necessaria operazione su rimozione "
                "dispositivi aggiuntivi - verificare se fatturazione canoni "
                "coerente con richiesta cliente")
    return None


def _r2_cessato_cessato_attivo(row, text):
    """Contratto CESSATO, Dispositivo CESSATO, OBU ancora ATTIVO."""
    if (_field(row, 'stato_contratto') == 'CESSATO' and
            _field(row, 'stato_dispositivo') == 'CESSATO' and
            _field(row, 'stato_obu') == 'ATTIVO'):
        return "Stati discordanti - conferma lato IT che gli stati siano allineati"
    return None


def _r3_attivo_cessato_cessato(row, text):
    """Contratto ATTIVO, Dispositivo CESSATO, OBU CESSATO → Risolto."""
    if (_field(row, 'stato_contratto') == 'ATTIVO' and
            _field(row, 'stato_dispositivo') == 'CESSATO' and
            _field(row, 'stato_obu') == 'CESSATO'):
        return "Risolto"
    return None


def _r4_cessato_paga_fattura(row, text):
    """Contratto ATTIVO, Dispositivo CESSATO, OBU ATTIVO, STATO FATTURA OK."""
    if (_field(row, 'stato_contratto') == 'ATTIVO' and
            _field(row, 'stato_dispositivo') == 'CESSATO' and
            _field(row, 'stato_obu') == 'ATTIVO' and
            _field(row, 'STATO FATTURA') == 'OK'):
        return "Dispositivo cessato ma lo paga in fattura"
    return None


def _r5_attivo_cessato_attivo(row, text):
    """Contratto ATTIVO, Dispositivo CESSATO, OBU ATTIVO → Risolto."""
    if (_field(row, 'stato_contratto') == 'ATTIVO' and
            _field(row, 'stato_dispositivo') == 'CESSATO' and
            _field(row, 'stato_obu') == 'ATTIVO'):
        return "Risolto"
    return None


def _r6_cessato_sospeso_attivo(row, text):
    """Contratto CESSATO, Dispositivo SOSPESO, OBU ATTIVO."""
    if (_field(row, 'stato_contratto') == 'CESSATO' and
            _field(row, 'stato_dispositivo') == 'SOSPESO' and
            _field(row, 'stato_obu') == 'ATTIVO'):
        return "Stati discordanti - conferma lato IT che gli stati siano allineati"
    return None


def _r7_recesso_obu(row, text):
    """Flag recesso S con OBU cessato."""
    if (_field(row, 'flag_recesso_obu') == 'S' and
            _field(row, 'stato_obu') == 'CESSATO'):
        return "Obu cessati per recesso."
    return None


def _r8_contratto_cessato_generico(row, text):
    """Contratto CESSATO con qualsiasi stato dispositivo/obu non coperto sopra."""
    if _field(row, 'stato_contratto') == 'CESSATO':
        return ("Contratto cessato - non necessaria operazione su rimozione "
                "dispositivi aggiuntivi - verificare se fatturazione canoni "
                "coerente con richiesta cliente")
    return None


TIER1_RULES = [
    _r1_cessato_cessato_cessato,   # priorità 10
    _r2_cessato_cessato_attivo,    # priorità 20
    _r3_attivo_cessato_cessato,    # priorità 30
    _r4_cessato_paga_fattura,      # priorità 40
    _r5_attivo_cessato_attivo,     # priorità 50
    _r6_cessato_sospeso_attivo,    # priorità 55
    _r7_recesso_obu,               # priorità 57
    _r8_contratto_cessato_generico,  # priorità 60
]


# ═══════════════════════════════════════════════════════════════
# TIER 2: Regole basate su keyword nei post/note
# Ordine di priorità CRITICO: regole più specifiche PRIMA
# ═══════════════════════════════════════════════════════════════

# --- PRIORITÀ ALTA: Intento esplicito del cliente (dalle note) ---

def _r20_cambiato_idea(row, text):
    """Cliente ha cambiato idea — rilevato da nota cliente o post."""
    if _contains_any(text, ['cambiato idea', 'ha cambiato idea',
                            'ripensato', 'ci ho ripensato',
                            'non vuole più', 'non vuole piu',
                            'non intende procedere',
                            'vorrei tenerlo', 'vuole tenerlo',
                            'annullare la spedizione',
                            'non ho bisogno', 'non ne ho bisogno',
                            'non mi serve piu', 'non mi serve più']):
        return "Cliente ha cambiato idea"
    return None


def _r21_due_contratti_recesso(row, text):
    """Cliente ha due contratti, quello su cui ha chiesto restituzione ha un solo dispositivo."""
    if _contains_any(text, ['due contratti']) and _contains_any(text, ['recesso', 'solo dispositivo', 'un solo']):
        return ("Cliente ha due contratti, quello su cui ha chiesto restituzione "
                "ha un solo dispositivo, deve fare recesso")
    return None


def _r22_solo_dispositivo_recesso(row, text):
    """Cliente ha un solo dispositivo, deve fare recesso."""
    if _contains_any(text, ['un solo dispositivo', 'unico dispositivo',
                            'solo dispositivo', 'un dispositivo solo',
                            'un solo obu',
                            'associato un solo dispositivo']):
        return "Cliente ha un dispositivo solo deve fare recesso"
    return None


def _r23_chiede_recesso(row, text):
    """Cliente chiede esplicitamente recesso (nei post operatore)."""
    if _contains_any(text, ['clt chiede recesso', 'cliente chiede recesso',
                            'chiede recesso', 'deve fare recesso',
                            'procedura per richiesta recesso']):
        return "Cliente ha un dispositivo solo deve fare recesso"
    return None


# --- PRIORITÀ MEDIA-ALTA: Azione specifica completata ---

def _r30_ticket_doppio(row, text):
    """Ticket chiuso perché duplicato/doppio o già lavorato con altro ticket."""
    # "gestito con ticket I-XXXXXX" o "già lavorata con ticket"
    if re.search(r'gestito con ticket\s+I-\d+', text, re.IGNORECASE):
        return ("Cliente apre ticket per rimozione secondo dispositivo, "
                "tentativo contatto ko, apertura altro ticket chiuso perché doppio")
    if re.search(r'già\s+lavorat[ao]\s+con\s+ticket', text, re.IGNORECASE):
        return ("Cliente apre ticket per rimozione secondo dispositivo, "
                "tentativo contatto ko, apertura altro ticket chiuso perché doppio")
    if _contains_any(text, ['doppio', 'duplicato', 'già aperto',
                            'chiuso perché doppio', 'perche doppio',
                            'ticket doppio']):
        return ("Cliente apre ticket per rimozione secondo dispositivo, "
                "tentativo contatto ko, apertura altro ticket chiuso perché doppio")
    return None


def _r31_otp(row, text):
    """Procedura OTP eseguita."""
    if _contains_any(text, ['otp ok', 'con otp', 'procedura con otp',
                            'procedura otp', 'codici otp']):
        return "Eseguita procedura con OTP, ticket chiuso"
    return None


def _r32_ahd(row, text):
    """Aperto AHD (richiesta help desk)."""
    if _contains_any(text, ['aperto ahd', 'apertura ahd', 'ahd cs']):
        if _field(row, 'STATO FATTURA') == 'OK':
            return ("Dispositivo risulta ancora attivo, lo sta pagando. "
                    "Verificare se rientrato a magazzino. Aperto ahd.")
        return "Aperto ahd per invio lettera di vettura"
    return None


def _r33_lettera_vettura(row, text):
    """Lettera di vettura inviata."""
    if _contains_any(text, ['lettera di vettura', 'ldv']):
        return "Dispositivo attivo, lettera di vettura inviata, ticket chiuso"
    return None


def _r34_mail(row, text):
    """Mandata mail/email al cliente."""
    if _contains_any(text, ['inviata mail', 'invio mail', 'mandata mail',
                            'inviata email', 'invio email', 'mandata email',
                            'inviata e-mail', 'invio e mail']):
        return "Mandata mail a cliente. Ticket chiuso"
    return None


# --- PRIORITÀ BASSA: Contatto ko (generico, cattura molti casi) ---

def _r40_contatto_ko(row, text):
    """Mancato contatto con il cliente."""
    if _contains_any(text, ['contatto ko', 'cont ko', 'contatti ko',
                            'non risponde', 'mancato contatto',
                            'cliente non risponde', 'clt non risponde',
                            'per mancato contatto']):
        return "Mancato ricontatto con cliente, ticket chiuso"
    return None


# Lista ordinata per priorità
# L'ordine rispecchia il comportamento dell'analista manuale:
# 1. Intento esplicito cliente (cambiato idea, recesso)
# 2. Contatto ko (pattern dominante nell'analisi manuale)
# 3. Azioni specifiche (OTP, LDV, AHD, mail)
# 4. Ticket doppio
TIER2_RULES = [
    # Intento cliente (massima priorità)
    _r20_cambiato_idea,
    _r21_due_contratti_recesso,
    _r22_solo_dispositivo_recesso,
    _r23_chiede_recesso,
    # Contatto ko (alta priorità, come usato dall'analista)
    _r40_contatto_ko,
    # Azioni specifiche
    _r30_ticket_doppio,
    _r31_otp,
    _r32_ahd,
    _r33_lettera_vettura,
    _r34_mail,
]


# ═══════════════════════════════════════════════════════════════
# RULE ENGINE
# ═══════════════════════════════════════════════════════════════

# Risultati per cui NON aggiungere "sta pagando"
_NO_PAGANDO_PATTERNS = [
    'cambiato idea',       # il cliente vuole tenerlo, pagare è normale
    'recesso',             # deve cessare il contratto, pagamento non è il punto
    'doppio',              # ticket duplicato, irrilevante
    'due contratti',       # questione contrattuale, non di pagamento
]


class RuleEngine:
    """Valuta le regole in ordine di priorità e ritorna la prima che matcha."""

    def __init__(self):
        self.tier1_rules = TIER1_RULES
        self.tier2_rules = TIER2_RULES

    def evaluate(self, row, ticket_text, client_text, all_text,
                 post_text='', note_cliente_text=''):
        """
        Valuta tutte le regole in ordine.
        row: pd.Series o dict con i campi strutturati
        ticket_text: testo dei post/note del ticket specifico
        client_text: testo dei post del cliente (altri ticket)
        all_text: concatenazione di entrambi
        post_text: solo i post operatore (non usato nel flusso base)
        note_cliente_text: solo le note scritte dal cliente
        Returns: stringa con l'analisi
        """
        # Tier 1: regole deterministiche (non servono i testi)
        for rule_fn in self.tier1_rules:
            result = rule_fn(row, all_text)
            if result is not None:
                return result

        # Pre-check: se la nota cliente indica chiaramente "cambiato idea",
        # dai priorità a questo prima di cercare keyword operatore
        if note_cliente_text:
            result = _r20_cambiato_idea(row, note_cliente_text)
            if result is not None:
                return self._apply_modifiers(result, row)

        # Tier 2: keyword matching sul testo del ticket (post + note)
        for rule_fn in self.tier2_rules:
            result = rule_fn(row, ticket_text)
            if result is not None:
                return self._apply_modifiers(result, row)

        # Poi cerca nei testi del cliente (possono riguardare altri ticket)
        for rule_fn in self.tier2_rules:
            result = rule_fn(row, client_text)
            if result is not None:
                return self._apply_modifiers(result, row)

        # Fallback
        return self._fallback(row, all_text)

    def _apply_modifiers(self, result, row):
        """Applica modificatori trasversali al risultato."""
        result_lower = result.lower()

        # Non aggiungere "sta pagando" se il risultato lo rende irrilevante
        if any(pat in result_lower for pat in _NO_PAGANDO_PATTERNS):
            return result

        # Se sta pagando e non è già menzionato nel risultato
        if (_field(row, 'STATO FATTURA') == 'OK' and
                _field(row, 'stato_dispositivo') == 'ATTIVO' and
                'pagando' not in result_lower and
                'paga' not in result_lower):
            result += ". Sta pagando il dispositivo"
        return result

    def _fallback(self, row, all_text):
        """Analisi di fallback quando nessuna regola matcha."""
        status = _field(row, 'pystatuswork')
        disp = _field(row, 'stato_dispositivo')

        if 'REJECTED' in status:
            # Cerca pattern specifici per ticket rejected
            if _contains_any(all_text, ['recesso', 'deve fare recesso']):
                return "Ticket rifiutato in quanto deve fare recesso"
            if _contains_any(all_text, ['informativo', 'ticket informativo']):
                return "Ticket informativo"
            return "Ticket rifiutato, verificare motivo nei post"

        if disp == 'ATTIVO':
            if _field(row, 'STATO FATTURA') == 'OK':
                return "Dispositivo attivo, ticket chiuso. Sta pagando il dispositivo"
            return "Dispositivo attivo, ticket chiuso"

        return "Ticket chiuso"
