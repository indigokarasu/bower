#!/usr/bin/env python3
"""
Bower → Chronicle candidate extraction script.
Extracts meaningful facts about the operator's life from Bower scan data and writes principal-scoped candidate records for sanctioned Chronicle ingestion. It never writes Chronicle directly and never treats file counts or organization patterns as personal facts.
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

_HELP_ARGS = {"--help", "-h"}
if set(sys.argv[1:]) & _HELP_ARGS:
    print((__doc__ or "").strip() or "Usage: python3 bower_mem_ingest.py [no flags]")
    sys.exit(0)

BOWER_DATA = Path(os.path.expanduser("~/.hermes/commons/data/ocas-bower"))
OUTPUT_FILE = BOWER_DATA / "mem_ingest_output.json"

# Keywords that indicate meaningful personal content
MEANINGFUL_SIGNALS = {
    "health": ["fibroscan", "ucsf", "lab result", "blood test", "prescription",
               "diagnosis", "surgery", "mri", "ct scan", "colonoscopy",
               "cholesterol", "a1c", "glucose", "dental", "vision",
               "cardiologist", "dermatologist", "physical exam"],
    "finance": ["mortgage", "401k", "ira", "roth", "rsu", "vesting", "ipo",
                "net worth", "tax return", "w-2", "1099", "budget",
                "investment portfolio", "credit card", "bank account",
                "insurance policy", "refinanc", "capital gains"],
    "home": ["renovation", "contractor", "permit", "inspection", "kitchen remodel",
             "bathroom remodel", "roof", "hvac", "plumbing", "honu hale",
             "shower", "flooring", "landscaping"],
    "travel": ["airbnb", "hotel booking", "flight confirmation", "itinerary",
               "passport", "visa", "reservation", "boarding pass"],
    "career": ["offer letter", "salary negotiation", "promotion", "job description",
               "performance review", "compensation", "equity grant"],
    "social": ["wedding", "birthday", "anniversary", "memorial", "graduation"],
}

def load_json(path):
    with open(path) as f:
        return json.load(f)

def extract_meaningful_facts(content_summaries_file):
    """Extract specific, meaningful facts from content summaries."""
    facts = {"health": [], "finance": [], "home": [], "travel": [], "career": [], "social": []}
    
    with open(content_summaries_file) as f:
        for line in f:
            s = json.loads(line)
            text = (s.get("summary_text", "") + " " + s.get("name", "")).lower()
            
            for category, signals in MEANINGFUL_SIGNALS.items():
                for signal in signals:
                    if signal in text:
                        facts[category].append({
                            "signal": signal,
                            "file": s.get("name", ""),
                            "snippet": s.get("summary_text", "")[:200],
                        })
                        break  # one match per category per file

    # Deduplicate by signal
    for category in facts:
        seen = set()
        deduped = []
        for f in facts[category]:
            if f["signal"] not in seen:
                seen.add(f["signal"])
                deduped.append(f)
        facts[category] = deduped
    
    return facts

def main():
    cs_file = BOWER_DATA / "content_summaries.jsonl"
    facts = extract_meaningful_facts(cs_file)
    
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "facts": facts,
        "memory_candidates": [],
        "review_summary": "",
    }
    
    # Build principal-scoped candidates from specific findings.
    # Candidates remain reviewable proposals until Chronicle accepts them.
    for category, items in facts.items():
        for item in items:
            output["memory_candidates"].append({
                "target_principal": "user",
                "domain": category,
                "claim_kind": "fact",
                "claim_state": "inferred",
                "derivation_type": "normalized",
                "confidence": 0.6,
                "claim": {
                    "signal": item["signal"],
                    "summary": item["snippet"],
                },
                "provenance": {
                    "source_component": "ocas-bower",
                    "source_file": item["file"],
                },
            })

    # Build drawer content — ONLY meaningful facts, NO counts
    lines = [f"## Life Facts Discovered — {output['generated_at'][:10]}"]
    
    for category in ["health", "finance", "home", "travel", "career", "social"]:
        if facts[category]:
            lines.append(f"\n### {category.title()}")
            for f in facts[category]:
                lines.append(f"- {f['signal']}: {f['file']}")
    
    if not any(facts.values()):
        lines.append("\nNo new meaningful facts found in this scan.")
    
    output["review_summary"] = "\n".join(lines)
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Meaningful facts found: {sum(len(v) for v in facts.values())}")
    print(f"Memory candidates: {len(output['memory_candidates'])}")
    for cat, items in facts.items():
        if items:
            print(f"  {cat}: {[f['signal'] for f in items]}")

if __name__ == "__main__":
    main()
