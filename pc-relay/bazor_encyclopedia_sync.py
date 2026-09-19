#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENC = ROOT / "BAZOR_ENCYCLOPEDIA.md"
REG = ROOT / "bazor_registry.json"
LOG = ROOT / "pc-relay" / "BAZOR_DATA" / "encyclopedia_version_log.jsonl"

def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")

def main():
    ap = argparse.ArgumentParser(description="Synchronise l'Encyclopédie BAZOR à chaque version générée.")
    ap.add_argument("--component", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--artifact", default="")
    ap.add_argument("--changes", default="")
    ap.add_argument("--tests", default="")
    ap.add_argument("--status", default="GENERATED")
    args = ap.parse_args()

    if not ENC.exists() or not REG.exists():
        raise SystemExit("BAZOR_ENCYCLOPEDIA.md ou bazor_registry.json introuvable")

    stamp = now_iso()
    component = args.component.strip()
    version = args.version.strip()
    key = f"{component}::{version}"

    enc = ENC.read_text(encoding="utf-8")
    marker = f"<!-- BAZOR_VERSION:{key} -->"
    if marker not in enc:
        block = (
            f"\n{marker}\n"
            f"### {component} — {version}\n"
            f"- Généré : {stamp}\n"
            f"- Statut : {args.status.strip() or 'GENERATED'}\n"
            f"- Artefact : {args.artifact.strip() or 'non renseigné'}\n"
            f"- Changements : {args.changes.strip() or 'non renseignés'}\n"
            f"- Tests : {args.tests.strip() or 'non renseignés'}\n"
        )
        header = "## Historique automatique des versions"
        if header not in enc:
            enc += "\n\n" + header + "\n"
        enc += block
        ENC.write_text(enc, encoding="utf-8")

    data = json.loads(REG.read_text(encoding="utf-8"))
    hist = data.setdefault("version_history", [])
    if not any(str(x.get("component")) == component and str(x.get("version")) == version for x in hist if isinstance(x, dict)):
        hist.append({
            "component": component,
            "version": version,
            "generated_at": stamp,
            "artifact": args.artifact.strip() or None,
            "changes": args.changes.strip() or None,
            "tests": args.tests.strip() or None,
            "status": args.status.strip() or "GENERATED",
        })
    data["encyclopedia_updated_at"] = stamp
    data["encyclopedia_sync_required"] = True
    REG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "time": stamp, "event": "VERSION_ENCYCLOPEDIA_SYNC",
            "component": component, "version": version,
            "artifact": args.artifact.strip() or None,
            "status": args.status.strip() or "GENERATED",
        }, ensure_ascii=False) + "\n")

    print(f"BAZOR_ENCYCLOPEDIA_SYNC_OK {component} {version}")

if __name__ == "__main__":
    main()
