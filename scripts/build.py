#!/usr/bin/env python3
"""Build the static Webperf trend dashboard from immutable Core results."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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


def combined_test(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Return Core's canonical multi-test entry, falling back for old runs."""
    tests = raw.get("tests", []) if isinstance(raw, dict) else []
    if not isinstance(tests, list):
        return None
    for test in reversed(tests):
        if isinstance(test, dict) and test.get("type_of_test") == -1:
            return test
    return next((test for test in tests if isinstance(test, dict)), None)


def run_summary(run_file: Path) -> dict[str, Any] | None:
    raw = load_json(run_file, {})
    test = combined_test(raw)
    if test is None:
        return None
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


STATUS = {
    "fel": "error",
    "error": "error",
    "varning": "warning",
    "warning": "warning",
    "löst": "resolved",
    "lost": "resolved",
    "resolved": "resolved",
}
STATUS_LABEL = {
    "error": "Fel",
    "warning": "Varning",
    "resolved": "Godkänd",
    "unknown": "Okänd status",
}


def parse_report_items(body: str) -> list[dict[str, str]]:
    """Turn Core's human-readable bullet list into structured report rows."""
    items: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    heading = re.compile(r"^- (?P<title>.+?) \((?P<status>[^()]+)\)\s*$")
    for line in body.splitlines():
        match = heading.match(line)
        if match:
            if current:
                items.append(current)
            status_word = match.group("status").strip().lower()
            current = {
                "title": match.group("title").strip(),
                "status": STATUS.get(status_word, "unknown"),
                "detail": "",
            }
        elif current and line.strip():
            detail = line.strip()
            current["detail"] = f"{current['detail']}\n{detail}".strip()
    if current:
        items.append(current)
    return items


def detail_markup(value: str) -> str:
    return "<br>".join(html.escape(line) for line in value.splitlines())


def report_key(value: str) -> str:
    """Normalize the visible report heading for joining it to raw findings."""
    first_line = value.splitlines()[0] if value else ""
    return re.sub(r"\s+\((?:fel|error|varning|warning|löst|resolved)\)$", "", first_line, flags=re.I).strip().casefold()


def issue_index(test: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    groups = test.get("data", {}).get("groups", {}) if isinstance(test.get("data"), dict) else {}
    if not isinstance(groups, dict):
        return index
    for group in groups.values():
        if not isinstance(group, dict):
            continue
        for issue in group.get("issues", []):
            if not isinstance(issue, dict):
                continue
            for title in (issue.get("report_title"), issue.get("text")):
                if isinstance(title, str) and report_key(title):
                    index.setdefault(report_key(title), []).append(issue)
                    break
    return index


def safe_href(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value if urlparse(value).scheme in {"http", "https"} else None


def finding_markup(issues: list[dict[str, Any]]) -> str:
    """Render concrete source locations attached by Core, when available."""
    entries: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for issue in issues:
        docs = [safe_href(url) for url in issue.get("resources", [])]
        for sub_issue in issue.get("subIssues", []):
            if not isinstance(sub_issue, dict):
                continue
            evidence = sub_issue.get("evidence", [])
            if not evidence and isinstance(sub_issue.get("extra"), dict):
                evidence = [sub_issue["extra"]]
            evidence = evidence if isinstance(evidence, list) else []
            for node in evidence or [{}]:
                if not isinstance(node, dict):
                    continue
                selector = str(node.get("selector", "")).strip()
                snippet = str(node.get("snippet", "")).strip()
                position = ""
                if sub_issue.get("line") is not None:
                    position = f"Rad {sub_issue['line']}"
                    if sub_issue.get("column") is not None:
                        position += f", kolumn {sub_issue['column']}"
                source = safe_href(sub_issue.get("url"))
                identity = (source or "", selector, snippet)
                if identity in seen or not any(identity) and not position:
                    continue
                seen.add(identity)
                rows = []
                if source:
                    rows.append(f"<dt>Källa</dt><dd><a href=\"{html.escape(source)}\">Öppna berörd resurs</a></dd>")
                if position:
                    rows.append(f"<dt>Position</dt><dd>{html.escape(position)}</dd>")
                if selector:
                    rows.append(f"<dt>CSS-selector</dt><dd><code>{html.escape(selector)}</code></dd>")
                if snippet:
                    rows.append(f"<dt>HTML vid felet</dt><dd><code class=\"html-snippet\">{html.escape(snippet)}</code></dd>")
                explanation = str(node.get("explanation", "")).strip()
                if explanation:
                    rows.append(f"<dt>Förklaring</dt><dd>{html.escape(explanation)}</dd>")
                entries.append(f"<dl class=\"finding-location\">{''.join(rows)}</dl>")
        for doc in docs:
            if doc:
                entries.append(f"<p class=\"finding-doc\"><a href=\"{html.escape(doc)}\">Läs regelns dokumentation</a></p>")
    if not entries:
        return ""
    return "<details class=\"finding-details\"><summary>Hitta felet</summary>" + "".join(entries) + "</details>"


def result_table(items: list[dict[str, str]]) -> str:
    rows = "".join(
        "<tr class=\"result-row result-row--{status}\">"
        "<td class=\"result-status\"><span aria-hidden=\"true\">{icon}</span> "
        "<span class=\"visually-hidden\">Status: </span>{label}</td>"
        "<th scope=\"row\">{title}</th><td>{detail}</td></tr>".format(
            status=item["status"],
            icon={"error": "✕", "warning": "!", "resolved": "✓"}[item["status"]],
            label=STATUS_LABEL[item["status"]],
            title=html.escape(item["title"]),
            detail=(detail_markup(item["detail"]) or "—") + finding_markup(item.get("issues", [])),
        )
        for item in items
    )
    return (
        "<div class=\"result-table-wrap\"><table class=\"result-table\">"
        "<thead><tr><th scope=\"col\">Resultat</th><th scope=\"col\">Kontroll</th>"
        "<th scope=\"col\">Detaljer</th></tr></thead><tbody>"
        f"{rows}</tbody></table></div>"
    )


def report_section(title: str, body: str, findings: dict[str, list[dict[str, Any]]]) -> str:
    items = parse_report_items(body)
    for item in items:
        item["issues"] = findings.get(report_key(item["title"]), [])
    errors = [item for item in items if item["status"] == "error"]
    warnings = [item for item in items if item["status"] == "warning"]
    resolved = [item for item in items if item["status"] == "resolved"]
    unknown = [item for item in items if item["status"] == "unknown"]
    problem_items = [*errors, *warnings, *unknown]
    counts = []
    if errors:
        counts.append(f"<span class=\"count count--error\">✕ {len(errors)} fel</span>")
    if warnings:
        counts.append(f"<span class=\"count count--warning\">! {len(warnings)} varningar</span>")
    if resolved:
        counts.append(f"<span class=\"count count--resolved\">✓ {len(resolved)} godkända</span>")
    if not items:
        content = "<p class=\"no-results\">Inga anmärkningar eller detaljer i denna kategori.</p>"
    else:
        content = result_table(problem_items) if problem_items else "<p class=\"all-clear\">✓ Inga fel eller varningar i denna kategori.</p>"
        if resolved:
            content += (
                "<details class=\"resolved-details\"><summary>"
                f"Visa {len(resolved)} godkända kontroller</summary>{result_table(resolved)}</details>"
            )
    return (
        "<section class=\"report-section\"><header class=\"report-section-heading\">"
        f"<h2>{html.escape(title)}</h2><p class=\"result-counts\">{''.join(counts)}</p>"
        f"</header>{content}</section>"
    )


def report_page(run_file: Path, run: dict[str, Any], site: dict[str, Any]) -> str:
    raw = load_json(run_file, {})
    test = combined_test(raw) or {}
    reports = [
        ("Övergripande", test.get("report", "")),
        ("Tillgänglighet", test.get("report_a11y", "")),
        ("Prestanda", test.get("report_perf", "")),
        ("Integritet & säkerhet", test.get("report_sec", "")),
        ("Webbstandard", test.get("report_stand", "")),
    ]
    findings = issue_index(test)
    sections = "".join(report_section(title, body, findings) for title, body in reports)
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
