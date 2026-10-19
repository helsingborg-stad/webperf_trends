#!/usr/bin/env python3
"""Build the static Webperf trend dashboard from immutable Core results."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "runs"
REPORTS = ROOT / "reports"
SUMMARY = ROOT / "data" / "summary.json"

SCORE_KEYS = {
    "rating": "Totalt",
    "rating_perf": "Prestanda",
    "rating_a11y": "Tillgänglighet",
    "rating_sec": "Integritet & säkerhet",
    "rating_stand": "Webbstandard",
}
TRACKED_METRICS = {"LCP", "TTFB", "CLS", "FCP", "TBT", "SpeedIndex", "Load"}


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def collect_metrics(value: Any, path: list[str], result: dict[str, float]) -> None:
    """Collect Sitespeed metric objects without depending on extra packages."""
    if isinstance(value, dict):
        metric_name = path[-1] if path else ""
        median = number(value.get("median"))
        mode = value.get("mode")
        if metric_name in TRACKED_METRICS and median is not None and isinstance(mode, str):
            result[f"{mode}:{metric_name}"] = median
        for key, child in value.items():
            collect_metrics(child, [*path, str(key)], result)
    elif isinstance(value, list):
        for child in value:
            collect_metrics(child, path, result)


def human_date(value: str) -> str:
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.astimezone().strftime("%-d %b %Y, %H:%M")
    except ValueError:
        return value.replace("T", " ").replace("Z", "")


def run_summary(run_file: Path) -> dict[str, Any] | None:
    raw = load_json(run_file, {})
    tests = raw.get("tests", []) if isinstance(raw, dict) else []
    if not tests or not isinstance(tests[0], dict):
        return None
    test = tests[0]
    run_id = run_file.stem
    metadata = load_json(RUNS / f"{run_id}.meta.json", {})
    metrics: dict[str, float] = {}
    collect_metrics(test.get("data", {}), [], metrics)
    scores = {key: number(test.get(key)) for key in SCORE_KEYS}
    return {
        "id": run_id,
        "date": test.get("date") or metadata.get("completed_at") or run_id,
        "display_date": human_date(test.get("date") or run_id),
        "url": metadata.get("url", ""),
        "scores": scores,
        "metrics": metrics,
        "meta": metadata,
        "progress": {
            "completed": metadata.get("completed_tests", []),
            "failed": metadata.get("failed_tests", []),
            "total": metadata.get("tests", []),
            "active": metadata.get("active_test", ""),
        },
        "detail": f"reports/{run_id}.html",
    }


def score_markup(scores: dict[str, float | None]) -> str:
    rows = []
    for key, label in SCORE_KEYS.items():
        value = scores.get(key)
        if value is not None:
            rows.append(f"<dt>{html.escape(label)}</dt><dd>{value:.2f} / 5</dd>")
    return "".join(rows) or "<dt>Poäng</dt><dd>Ingen poäng kunde läsas</dd>"


def report_page(run_file: Path, run: dict[str, Any], site: dict[str, Any]) -> str:
    raw = load_json(run_file, {})
    test = raw.get("tests", [{}])[0]
    reports = [
        ("Övergripande", test.get("report", "")),
        ("Tillgänglighet", test.get("report_a11y", "")),
        ("Prestanda", test.get("report_perf", "")),
        ("Integritet & säkerhet", test.get("report_sec", "")),
        ("Webbstandard", test.get("report_stand", "")),
    ]
    sections = "".join(
        f"<section class=\"report-section\"><h2>{html.escape(title)}</h2>"
        f"<pre>{html.escape(body.strip() or 'Inga anmärkningar eller detaljer i denna kategori.')}</pre></section>"
        for title, body in reports
    )
    raw_href = f"../data/runs/{run['id']}.json"
    url = run["url"] or site.get("url", "")
    progress = run["progress"]
    completed = ", ".join(str(test) for test in progress["completed"]) or "inga ännu"
    failed = ", ".join(str(test) for test in progress["failed"])
    total = len(progress["total"])
    progress_text = f"{len(progress['completed'])} av {total} tester klara"
    if progress["active"]:
        progress_text += f" · test {progress['active']} körs"
    if failed:
        progress_text += f" · tester med fel: {failed}"
    return f"""<!doctype html>
<html lang=\"sv\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Detaljrapport · {html.escape(run['display_date'])}</title><link rel=\"stylesheet\" href=\"../assets/site.css\"></head>
<body><a class=\"skip-link\" href=\"#report\">Hoppa till rapporten</a><header class=\"site-header\"><div><a class=\"wordmark\" href=\"../\">Webperf trends</a><p>{html.escape(site.get('name', ''))}</p></div><a href=\"../\">Till översikten</a></header>
<main id=\"report\" class=\"report-page\"><p class=\"eyebrow\">Detaljrapport</p><h1>{html.escape(run['display_date'])}</h1><p class=\"lede\">Mätt URL: <a href=\"{html.escape(url)}\">{html.escape(url)}</a></p>
<p class=\"run-progress\">{html.escape(progress_text)}</p><dl class=\"score-list\">{score_markup(run['scores'])}</dl>{sections}
<details><summary>Tekniskt underlag</summary><p>Core-commit: <code>{html.escape(str(run['meta'].get('core_sha', 'okänd')))}</code></p><p><a href=\"{raw_href}\">Öppna råresultatet (JSON)</a></p></details></main></body></html>"""


def main() -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    site = load_json(ROOT / "data" / "site.json", {})
    entries = [entry for path in RUNS.glob("*.json") if not path.name.endswith(".meta.json") if (entry := run_summary(path))]
    entries.sort(key=lambda item: item["date"])
    SUMMARY.write_text(json.dumps({"site": site, "runs": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for entry in entries:
        run_file = RUNS / f"{entry['id']}.json"
        (REPORTS / f"{entry['id']}.html").write_text(report_page(run_file, entry, site), encoding="utf-8")
    print(f"Built {len(entries)} trend report(s).")


if __name__ == "__main__":
    main()
