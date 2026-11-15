"""Extraction argument parsing only; no config/provider/data imports."""
import argparse


def parse_extraction_args(argv=None):
    parser = argparse.ArgumentParser(description="Step 3: extract graph triples from DART filings.")
    parser.add_argument("--company", help="single company by stock code or canonical name (smoke test)")
    parser.add_argument("--limit", type=int, help="only the first N companies")
    parser.add_argument("--skip-llm", action="store_true", help="structured OWNS_STAKE backbone only")
    parser.add_argument("--from-cache", action="store_true",
                        help="re-normalize from raw_llm.json (no LLM) — fast filter-tuning loop")
    parser.add_argument("--no-shareholders", action="store_true", help="skip major_shareholders.csv")
    return parser.parse_args(argv)
