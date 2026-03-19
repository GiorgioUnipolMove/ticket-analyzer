#!/usr/bin/env python3
"""
Ticket Analyzer - Analisi automatizzata ticket restituzione dispositivi.

Uso:
  python main.py --test 20                    # test rule-based (default)
  python main.py                              # run completo rule-based
  python main.py --provider ollama --test 20   # test con LLM
  python main.py --resume
"""

import sys
import argparse
from config import Config
from services.data_loader import DataLoader
from services.excel_writer import ExcelWriter
from utils.progress import load_progress, clear_progress


def parse_args():
    parser = argparse.ArgumentParser(
        description='Analisi ticket restituzione dispositivi UnipolMove',
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        '--provider', type=str,
        default='rules',
        choices=['rules', 'claude', 'gemini', 'ollama'],
        help='Metodo di analisi: rules (default, deterministico) o LLM',
    )
    parser.add_argument('--model', type=str, default=None, help='Modello specifico (solo per LLM)')
    parser.add_argument('--test', type=int, default=None, help='Numero righe per test run')
    parser.add_argument('--start', type=int, default=0, help='Riga di partenza (0-indexed)')
    parser.add_argument('--resume', action='store_true', help='Riprendi da ultimo salvataggio')
    parser.add_argument('--clear', action='store_true', help='Cancella progressi e ricomincia')
    parser.add_argument('--input', type=str, default=Config.INPUT_FILE, help='File input')
    parser.add_argument('--output', type=str, default=Config.OUTPUT_FILE, help='File output')
    return parser.parse_args()


def main():
    args = parse_args()

    # Clear progress se richiesto
    if args.clear:
        clear_progress()

    # Carica dati
    data = DataLoader(args.input).load()

    # Resume o fresh start
    if args.resume:
        last_idx, results, prev_provider = load_progress()
        start_idx = last_idx + 1
        print(f"🔄 Ripresa da riga {start_idx} ({len(results)} analisi già fatte, provider: {prev_provider})")
    else:
        results = {}
        start_idx = args.start

    # Calcola range
    if args.test:
        end_idx = min(start_idx + args.test, len(data.df_main))
        print(f"\n{'=' * 60}")
        print(f"🧪 TEST RUN: righe {start_idx} → {end_idx - 1} ({end_idx - start_idx} righe)")
        print(f"{'=' * 60}\n")
    else:
        end_idx = len(data.df_main)
        print(f"\n{'=' * 60}")
        print(f"🚀 PROCESSAMENTO COMPLETO: {end_idx - start_idx} righe")
        print(f"{'=' * 60}\n")

    # Crea analyzer
    if args.provider == 'rules':
        from services.rule_analyzer import RuleBasedAnalyzer
        print("📋 Modalità: Rule-based (deterministico)")
        analyzer = RuleBasedAnalyzer(data)
    else:
        from providers import create_provider
        from services.analyzer import Analyzer
        try:
            provider = create_provider(args.provider, args.model)
        except (ValueError, ConnectionError) as e:
            print(f"❌ {e}")
            sys.exit(1)
        print(f"🤖 Provider: {provider.name()}")
        print(f"⚡ Rate limit: {Config.get_rate_limit(args.provider)} req/min")
        analyzer = Analyzer(provider, data, args.provider)

    # Analisi
    results = analyzer.run(start_idx, end_idx, results)

    # Scrivi output
    writer = ExcelWriter()
    writer.write(data.df_main, results, args.output)

    print(f"\n{'=' * 60}")
    print(f"✅ COMPLETATO — Output: {args.output}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
