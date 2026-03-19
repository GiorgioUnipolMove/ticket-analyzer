#!/usr/bin/env python3
"""
Ticket Analyzer - Analisi automatizzata ticket restituzione dispositivi.

Uso:
  python main.py --provider gemini --test 20
  python main.py --provider claude
  python main.py --resume
"""

import sys
import argparse
from config import Config
from providers import create_provider
from services.data_loader import DataLoader
from services.analyzer import Analyzer
from services.excel_writer import ExcelWriter
from utils.progress import load_progress, clear_progress


def parse_args():
    parser = argparse.ArgumentParser(
        description='Analisi ticket restituzione dispositivi UnipolMove',
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        '--provider', type=str,
        default=Config.DEFAULT_PROVIDER,
        choices=['claude', 'gemini', 'ollama'],
        help='Provider LLM (default: da .env)',
    )
    parser.add_argument('--model', type=str, default=None, help='Modello specifico')
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

    # Crea provider LLM
    try:
        provider = create_provider(args.provider, args.model)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"🤖 Provider: {provider.name()}")
    print(f"⚡ Rate limit: {Config.get_rate_limit(args.provider)} req/min")

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
        rpm = Config.get_rate_limit(args.provider)
        est_hours = (end_idx - start_idx) / rpm / 60
        print(f"\n{'=' * 60}")
        print(f"🚀 PROCESSAMENTO COMPLETO: {end_idx - start_idx} righe")
        print(f"⏱️  Tempo stimato: ~{est_hours:.1f} ore")
        print(f"{'=' * 60}\n")

    # Analisi
    analyzer = Analyzer(provider, data, args.provider)
    results = analyzer.run(start_idx, end_idx, results)

    # Scrivi output
    writer = ExcelWriter()
    writer.write(data.df_main, results, args.output)

    print(f"\n{'=' * 60}")
    print(f"✅ COMPLETATO — Output: {args.output}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
