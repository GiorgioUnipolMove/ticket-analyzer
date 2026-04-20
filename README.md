# Ticket Analyzer — UnipolMove

Analisi automatizzata di ticket di restituzione dispositivi OBU tramite LLM.

Il tool legge un file Excel con 4 tab (dati ticket, post CRM, note), costruisce il contesto per ogni ticket e chiama un modello LLM per generare un'analisi sintetica (1-2 frasi), evidenziando anomalie e incongruenze operative.

---

## Setup

### 1. Installa le dipendenze

```bash
pip install -r requirements.txt
```

> Installa solo le librerie dei provider che intendi usare (vedi commenti in `requirements.txt`).

### 2. Configura le variabili d'ambiente

```bash
cp .env.example .env
```

Apri `.env` e inserisci la API key del provider scelto:

```env
# Per Gemini (gratis su https://aistudio.google.com/apikey)
GEMINI_API_KEY=AIza...

# Per Claude (https://console.anthropic.com)
ANTHROPIC_API_KEY=sk-ant-...

# Provider di default
DEFAULT_PROVIDER=gemini
```

### 3. Posiziona il file Excel di input

Copia il file Excel nella root del progetto con il nome definito in `INPUT_FILE` (default: `Restituzione_device_aggiuntivi_ANALISI OPS_Personale.xlsx`).

---

## Uso

### Test su un campione

```bash
# Analizza le prime 20 righe con Gemini
python main.py --provider gemini --test 20

# Analizza 50 righe a partire dalla riga 100
python main.py --provider gemini --test 50 --start 100
```

### Run completo

```bash
# Gemini (gratis, ~14 req/min)
python main.py --provider gemini

# Claude (qualita' superiore, ~50 req/min)
python main.py --provider claude

# Ollama (locale, nessun limite di rate)
python main.py --provider ollama --model llama3.1:8b
```

### Resume dopo interruzione

Il tool salva automaticamente il progresso ogni 50 righe in `progress.json`.

```bash
# Riprendi dall'ultimo checkpoint
python main.py --resume

# Cancella il progresso e ricomincia da capo
python main.py --clear
```

### Opzioni complete

```
--provider    Provider LLM: claude | gemini | ollama  (default: da .env)
--model       Override del modello specifico
--test N      Test run: analizza solo N righe
--start N     Parti dalla riga N (0-indexed)
--resume      Riprendi dall'ultimo salvataggio (progress.json)
--clear       Cancella progress.json e ricomincia
--input       Percorso file Excel di input
--output      Percorso file Excel di output
```

---

## Struttura del progetto

```
ticket-analyzer/
├── main.py                  # Entry point CLI e orchestrazione generale
├── config.py                # Configurazione centralizzata (legge da .env)
├── requirements.txt         # Dipendenze Python
├── .env.example             # Template variabili d'ambiente
│
├── providers/               # Implementazioni dei provider LLM
│   ├── __init__.py          # Factory: create_provider(name, model)
│   ├── base.py              # Classe astratta LLMProvider
│   ├── claude.py            # Provider Anthropic Claude
│   ├── gemini.py            # Provider Google Gemini
│   └── ollama.py            # Provider Ollama (locale)
│
├── services/                # Logica di business
│   ├── data_loader.py       # Caricamento Excel (4 tab) e lookup dict
│   ├── analyzer.py          # Orchestratore: itera righe, chiama LLM, retry
│   ├── context_builder.py   # Costruisce il contesto testuale per ogni ticket
│   └── excel_writer.py      # Scrive l'Excel di output con formattazione
│
├── utils/                   # Utility
│   ├── progress.py          # Salvataggio/caricamento checkpoint (progress.json)
│   └── rate_limiter.py      # Sliding window rate limiter per API
│
└── prompts/                 # Prompt per il modello LLM
    ├── __init__.py          # get_system_prompt() assembla system + esempi
    ├── system.py            # System prompt con regole di analisi
    └── examples.py          # 15 esempi few-shot per guidare il modello
```

### Flusso di esecuzione

```
main.py
  └─> DataLoader          legge i 4 tab Excel, costruisce lookup
  └─> create_provider()   istanzia il provider LLM scelto
  └─> Analyzer.run()
        └─> ContextBuilder.build()   assembla contesto per ogni ticket
        └─> RateLimiter              rispetta i limiti API
        └─> provider.call()          chiama il modello LLM
        └─> save_progress()          checkpoint ogni N righe
  └─> ExcelWriter.write()  genera output Excel formattato
```

---

## Confronto provider

| Provider | Costo      | Rate limit | Qualita' | Requisiti           |
|----------|------------|------------|----------|---------------------|
| Gemini   | Gratis     | ~15 req/min| Buona    | GEMINI_API_KEY      |
| Claude   | A pagamento| ~50 req/min| Ottima   | ANTHROPIC_API_KEY   |
| Ollama   | Gratis     | Nessuno    | Variabile| GPU locale, modello scaricato |

**Consiglio**: inizia con Gemini per i test (`--test 20`), poi usa Claude per il run finale se la qualita' lo richiede. Ollama e' utile per uso completamente offline.

---

## Output

Il file Excel di output (`output_analisi.xlsx`) contiene tutte le colonne originali del tab principale, con l'aggiunta della colonna **Analisi** inserita dopo `data_recesso_dispositivo`. La colonna e' evidenziata in giallo per facilitarne la lettura.

