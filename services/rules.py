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
    """Estrae testi separati per ticket (diretto) e cliente (indiretto)."""
    # Testo diretto: post e note del ticket specifico
    ticket_parts = []
    for post in post_ticket_lookup.get(ticket_id, []):
        ticket_parts.append(post)
    for note_dict in notes_lookup.get(ticket_id, []):
        for val in note_dict.values():
            if val:
                ticket_parts.append(val)
    ticket_text = ' '.join(ticket_parts)

    # Testo cliente: post su anagrafica (possono riguardare altri ticket)
    client_parts = []
    if client_id:
        for post in post_pulse_lookup.get(client_id, []):
            # Priorità ai post che menzionano questo ticket
            if ticket_id in post:
                ticket_parts.append(post)
            else:
                client_parts.append(post)
    client_text = ' '.join(client_parts)

    # Testo combinato (per backward compat)
    all_text = ticket_text + ' ' + client_text
    return ticket_text, client_text, all_text


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
# Per i casi ATTIVO/ATTIVO/ATTIVO e simili
# ═══════════════════════════════════════════════════════════════

def _r10_contatto_ko(row, text):
    """Mancato contatto con il cliente."""
    if _contains_any(text, ['contatto ko', 'cont ko', 'contatti ko',
                            'non risponde', 'mancato contatto',
                            'cliente non risponde', 'clt non risponde']):
        # Verifica se anche un solo dispositivo → recesso
        if _contains_any(text, ['un solo dispositivo', 'unico dispositivo',
                                'solo dispositivo', 'un dispositivo solo']):
            return "Mancato ricontatto con cliente, ticket chiuso, cliente ha un dispositivo solo"
        return "Mancato ricontatto con cliente, ticket chiuso"
    return None


def _r11_cambiato_idea(row, text):
    """Cliente ha cambiato idea."""
    if _contains_any(text, ['cambiato idea', 'ha cambiato idea',
                            'ripensato', 'ci ho ripensato',
                            'non vuole più', 'non vuole piu',
                            'non intende procedere']):
        return "Cliente ha cambiato idea"
    return None


def _r12_solo_dispositivo(row, text):
    """Cliente ha un solo dispositivo, deve fare recesso."""
    if _contains_any(text, ['un solo dispositivo', 'unico dispositivo',
                            'solo dispositivo', 'un dispositivo solo',
                            'un solo obu']):
        # Verifica se anche "recesso"
        if _contains_any(text, ['recesso']):
            return "Cliente ha un dispositivo solo deve fare recesso"
        return "Cliente ha un dispositivo solo deve fare recesso"
    return None


def _r13_due_contratti_recesso(row, text):
    """Cliente ha due contratti, quello su cui ha chiesto restituzione ha un solo dispositivo."""
    if _contains_any(text, ['due contratti']) and _contains_any(text, ['recesso', 'solo dispositivo']):
        return ("Cliente ha due contratti, quello su cui ha chiesto restituzione "
                "ha un solo dispositivo, deve fare recesso")
    return None


def _r14_ticket_doppio(row, text):
    """Ticket chiuso perché duplicato/doppio."""
    if _contains_any(text, ['doppio', 'duplicato', 'già aperto',
                            'chiuso perché doppio', 'perche doppio']):
        return ("Cliente apre ticket per rimozione secondo dispositivo, "
                "tentativo contatto ko, apertura altro ticket chiuso perché doppio")
    return None


def _r15_lettera_vettura(row, text):
    """Lettera di vettura inviata."""
    if _contains_any(text, ['lettera di vettura', 'ldv']):
        base = "Dispositivo attivo, lettera di vettura inviata, ticket chiuso"
        if _field(row, 'STATO FATTURA') == 'OK':
            base += ". Sta pagando il dispositivo"
        return base
    return None


def _r16_otp(row, text):
    """Procedura OTP eseguita."""
    if _contains_any(text, ['otp ok', 'con otp', 'procedura con otp',
                            'procedura otp']):
        return "Eseguita procedura con OTP, ticket chiuso"
    return None


def _r17_ahd(row, text):
    """Aperto AHD (richiesta help desk)."""
    if _contains_any(text, ['aperto ahd', 'apertura ahd', 'ahd cs']):
        if _field(row, 'STATO FATTURA') == 'OK':
            return ("Dispositivo risulta ancora attivo, lo sta pagando. "
                    "Verificare se rientrato a magazzino. Aperto ahd.")
        return "Aperto ahd per invio lettera di vettura"
    return None


def _r18_mail(row, text):
    """Mandata mail/email al cliente."""
    if _contains_any(text, ['inviata mail', 'invio mail', 'mandata mail',
                            'inviata email', 'invio email', 'mandata email',
                            'inviata e-mail', 'invio e mail']):
        return "Mandata mail a cliente. Ticket chiuso"
    return None


TIER2_RULES = [
    _r10_contatto_ko,
    _r11_cambiato_idea,
    _r12_solo_dispositivo,
    _r13_due_contratti_recesso,
    _r14_ticket_doppio,
    _r15_lettera_vettura,
    _r16_otp,
    _r17_ahd,
    _r18_mail,
]


# ═══════════════════════════════════════════════════════════════
# RULE ENGINE
# ═══════════════════════════════════════════════════════════════

class RuleEngine:
    """Valuta le regole in ordine di priorità e ritorna la prima che matcha."""

    def __init__(self):
        self.tier1_rules = TIER1_RULES
        self.tier2_rules = TIER2_RULES

    def evaluate(self, row, ticket_text, client_text, all_text):
        """
        Valuta tutte le regole in ordine.
        row: pd.Series o dict con i campi strutturati
        ticket_text: testo dei post/note del ticket specifico
        client_text: testo dei post del cliente (altri ticket)
        all_text: concatenazione di entrambi
        Returns: stringa con l'analisi
        """
        # Tier 1: regole deterministiche (non servono i testi)
        for rule_fn in self.tier1_rules:
            result = rule_fn(row, all_text)
            if result is not None:
                return result

        # Tier 2: keyword matching
        # PRIMA cerca nei testi diretti del ticket (più affidabili)
        for rule_fn in self.tier2_rules:
            result = rule_fn(row, ticket_text)
            if result is not None:
                return self._apply_modifiers(result, row)

        # POI cerca nei testi del cliente (possono riguardare altri ticket)
        for rule_fn in self.tier2_rules:
            result = rule_fn(row, client_text)
            if result is not None:
                return self._apply_modifiers(result, row)

        # Fallback
        return self._fallback(row)

    def _apply_modifiers(self, result, row):
        """Applica modificatori trasversali al risultato."""
        # Se sta pagando e non è già menzionato nel risultato
        if (_field(row, 'STATO FATTURA') == 'OK' and
                _field(row, 'stato_dispositivo') == 'ATTIVO' and
                'pagando' not in result.lower()):
            result += ". Sta pagando il dispositivo"
        return result

    def _fallback(self, row):
        """Analisi di fallback quando nessuna regola matcha."""
        status = _field(row, 'pystatuswork')
        disp = _field(row, 'stato_dispositivo')

        if 'REJECTED' in status:
            return "Ticket rifiutato, verificare motivo nei post"

        if disp == 'ATTIVO':
            if _field(row, 'STATO FATTURA') == 'OK':
                return "Dispositivo attivo, ticket chiuso. Sta pagando il dispositivo"
            return "Dispositivo attivo, ticket chiuso"

        return "Ticket chiuso"
