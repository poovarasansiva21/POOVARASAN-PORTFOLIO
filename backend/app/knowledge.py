"""Verified portfolio facts, loaded from data/portfolio.json (the same file the website uses)."""
from __future__ import annotations

import json
from pathlib import Path


def load_portfolio(root: Path) -> dict:
    return json.loads((root / "data" / "portfolio.json").read_text(encoding="utf-8"))


def render_facts(d: dict) -> str:
    ed, out = d["education"], []
    out += [f"Name: {d['name']} ({d['role']}, {d['location']})", f"Summary: {d['summary']}",
            f"Education: {ed['degree']}, {ed['institution']}, {ed['years']}, CGPA {ed['cgpa']}. Coursework: {', '.join(ed['coursework'])}."]
    out += [f"Experience: {e['title']} at {e['org']} ({e['duration']}). {e['summary']}" for e in d["experience"]]
    out += [f"Skills - {k}: {', '.join(v)}" for k, v in d["skills"].items()]
    for p in d["projects"]:
        extra = " ".join(f"{k.title()}: {p[k]}" for k in ("problem", "architecture", "implementation") if p.get(k))
        out.append(f"Project '{p['title']}' ({p['category']}): {p['summary']} {extra} Tech: {', '.join(p['tech'])}. Repo: {p['repo']}")
        if p.get("results"):
            out.append(f"  Verified results: {'; '.join(p['results'])}")
        if p.get("demo"):
            out.append(f"  Live demo: {p['demo']}")
    out += [f"Certification: {c['title']} ({c['note']})" for c in d["certifications"]]
    out += [f"Coding profile - {c['name']}: {c['detail']} ({c['url']})" for c in d["codingProfiles"]]
    c = d["contact"]
    out += [f"Achievements: {d['achievements']}", f"Contact: email {c['email']}, phone {c['phone']}, LinkedIn {c['linkedin']}, GitHub {c['github']}"]
    return "\n".join(out)
