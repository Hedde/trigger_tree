#!/usr/bin/env python3
"""trigger-tree HTML report.

Runs tt-stats.py, renders a self-contained HTML page (inline CSS, no external
resources, light+dark) and writes it to $PROJECT/.trigger-tree/report.html.
Prints the absolute path of the written file.
"""

import html
import json
import math
import os
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Website brand ramp; TUI approximations are 75, 80, 114, 214, and 196.
# Neutral untouched state followed by the five shared report/site heat classes.
HEAT = ["#4a5361", "#4775d1", "#38cfd0", "#7cb342", "#ffb300", "#e53935"]

MATURITY_NOTE = {
    "cold-start": "Measurement just started — review candidates are provisional.",
    "warming": "Early signal — review candidates need more sessions before judging.",
    "mature": "Measurement is mature, but low reads can still mean rare-but-critical.",
}

# Keep these variables synchronized with index.html's :root brand block.
CSS = """
:root { --bg:#fff; --fg:#1f2328; --muted:#59636e; --line:#d0d7de; --card:#f6f8fa;
        --cold:#4775d1; --cool:#38cfd0; --active:#7cb342; --warm:#ffb300; --hot:#e53935; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0c1014; --fg:#e6edf3; --muted:#9aa4af; --line:#1f262e; --card:#101418; }
}
:root[data-theme="dark"] { --bg:#0c1014; --fg:#e6edf3; --muted:#9aa4af; --line:#1f262e; --card:#101418; }
:root[data-theme="light"] { --bg:#fff; --fg:#1f2328; --muted:#59636e; --line:#d0d7de; --card:#f6f8fa; }
body { background:var(--bg); color:var(--fg); font:15px/1.55 -apple-system,'Segoe UI',sans-serif;
       max-width:880px; margin:2rem auto; padding:0 1.25rem; }
h1 { font-size:1.7rem; } h2 { font-size:1.2rem; margin-top:2.4rem; border-bottom:1px solid var(--line); padding-bottom:.35rem; }
small, .muted { color:var(--muted); }
table { border-collapse:collapse; width:100%; margin:.75rem 0; font-size:.92em; }
th, td { text-align:left; padding:.35rem .6rem; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); font-weight:600; }
tbody tr:hover, table tr:hover { background:color-mix(in srgb,var(--card) 70%,transparent); }
.bar { display:inline-block; height:.65em; border-radius:3px; vertical-align:baseline; }
.kpi { display:flex; gap:1rem; flex-wrap:wrap; margin:1rem 0; }
.kpi div { background:transparent; border:0; border-top:1px solid var(--line); border-radius:0; padding:.7rem 1rem .7rem 0; min-width:8rem; }
.kpi b { font-size:1.35rem; display:block; }
.note { background:transparent; border:0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); border-radius:0; padding:.7rem 0; margin:1rem 0; }
.grade { display:grid; grid-template-columns:auto 1fr; gap:1.25rem; align-items:center;
         border:0; border-block:1px solid var(--line); border-radius:0; padding:1rem 0; background:transparent; }
.grade-letter { font:700 3.5rem/1 ui-monospace,monospace; }
.untouched { color:var(--muted); }
code { background:var(--card); padding:.1em .35em; border-radius:4px; font-size:.9em; }
.scroll { overflow-x:auto; }
.spark { width:150px; height:46px; display:block; margin-top:.35rem; overflow:visible; }
.chart, .tree-chart { width:100%; height:auto; overflow:visible; font:12px ui-monospace,monospace; }
.chart text, .tree-chart text { fill:var(--fg); }
.chart .grid { stroke:var(--line); stroke-width:1; }
.chart .note-tick { stroke:var(--muted); stroke-width:1; }
.chart-pair { display:grid; gap:1rem; margin:1rem 0; }
.toc { position:sticky; top:0; z-index:2; background:color-mix(in srgb,var(--bg) 94%,transparent);
       border-block:1px solid var(--line); padding:.55rem 0; }
.toc a { display:inline-block; margin:.2rem .8rem .2rem 0; white-space:nowrap; }
footer { border-top:1px solid var(--line); color:var(--muted); margin-top:3rem; padding:1.2rem 0; font-size:.85rem; }
"""


def plugin_version():
    try:
        manifest = os.path.join(SCRIPT_DIR, "..", ".claude-plugin", "plugin.json")
        return json.loads(open(manifest, encoding="utf-8").read())["version"]
    except (OSError, ValueError, KeyError):
        return "unknown"


def heat_color(count, max_count):
    if count <= 0:
        return HEAT[0]
    idx = 1 + int((len(HEAT) - 2) * (math.log1p(count) / math.log1p(max(max_count, 2))) + 1e-9)
    return HEAT[min(idx, len(HEAT) - 1)]


def esc(s):
    return html.escape(str(s if s is not None else "—"))


def agent_label(file_row):
    agents = file_row.get("agents", {})
    main = file_row.get("main_reads", agents.get("main", 0))
    sub = file_row.get("subagent_reads", file_row.get("reads", 0) - main)
    top_subagents = sorted(
        ((name, count) for name, count in agents.items() if name != "main"),
        key=lambda item: (-item[1], item[0]),
    )[:2]
    suffix = ", ".join(f"{esc(name)} {count}" for name, count in top_subagents)
    return f"main {main} · sub {sub}" + (f" ({suffix})" if suffix else "")


def _points(values, width, height, pad=12):
    if not values:
        return []
    high, low = max(values), min(values)
    span = high - low or 1
    step = (width - 2 * pad) / max(1, len(values) - 1)
    return [
        (
            round(pad + index * step, 1),
            round(height - pad - (value - low) * (height - 2 * pad) / span, 1),
        )
        for index, value in enumerate(values)
    ]


def sparkline_svg(values, label):
    if len(values) < 3:
        return ""
    points = _points(values, 150, 46, 8)
    path = " ".join(f"{x},{y}" for x, y in points)
    x, y = points[-1]
    return (
        f"<svg class=spark viewBox='0 0 150 46' role=img aria-label='{esc(label)}'>"
        f"<title>{esc(label)}</title><polyline points='{path}' fill=none stroke='var(--cool)' "
        "stroke-width=2 vector-effect=non-scaling-stroke/>"
        f"<circle cx='{x}' cy='{y}' r=3 fill='var(--cool)'/><text x='{x - 5}' y='{max(9, y - 6)}' "
        f"text-anchor=end>{esc(values[-1])}</text></svg>"
    )


def line_chart_svg(trend, series, title, notes=None):
    if len(trend) < 3:
        return ""
    width, height = 720, 180
    all_values = [float(bucket.get(key) or 0) for key, _, _ in series for bucket in trend]
    high = max(all_values, default=1) or 1
    step = (width - 64) / max(1, len(trend) - 1)
    out = [f"<svg class=chart viewBox='0 0 {width} {height}' role=img><title>{esc(title)}</title>"]
    for grid in range(1, 4):
        y = 16 + grid * 36
        out.append(f"<line class=grid x1=32 y1={y} x2=688 y2={y}/>")
    for key, label, color in series:
        values = [float(bucket.get(key) or 0) for bucket in trend]
        points = [(32 + i * step, 152 - value * 128 / high) for i, value in enumerate(values)]
        for index in range(1, len(points)):
            dashed = trend[index].get("small_n") or trend[index - 1].get("small_n")
            x1, y1 = points[index - 1]
            x2, y2 = points[index]
            dash = " stroke-dasharray='6 5'" if dashed else ""
            out.append(
                f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='{color}' stroke-width=2{dash}/>"
            )
        x, y = points[-1]
        value_label = f"{values[-1]:g}"
        out.append(
            f"<circle cx='{x:.1f}' cy='{y:.1f}' r=3 fill='{color}'/><text x='{x - 7:.1f}' y='{max(12, y - 7):.1f}' text-anchor=end>{esc(label)} {esc(value_label)}</text>"
        )
    for note in notes or []:
        stamp = str(note.get("ts") or "")[:10]
        match = next(
            (
                i
                for i, bucket in enumerate(trend)
                if str(bucket.get("period", "")).startswith(stamp)
            ),
            None,
        )
        if match is not None:
            x = 32 + match * step
            out.append(
                f"<line class=note-tick x1='{x:.1f}' y1=18 x2='{x:.1f}' y2=156><title>{esc(note.get('text'))}</title></line>"
            )
    out.append("</svg>")
    return "".join(out)


def tree_svg(files, maturity, evaluable_files):
    if maturity == "cold-start" or evaluable_files < 5:
        return ""
    current = [row for row in files if row.get("state", "current") == "current"]
    groups = {}
    for row in current:
        groups.setdefault(os.path.dirname(row["path"]), []).append(row)
    ordered = sorted(
        groups.items(), key=lambda item: (-sum(r.get("heat", 0) for r in item[1]), item[0])
    )
    rows = []
    for folder, members in ordered:
        folder_heat = sum(row.get("heat", 0) for row in members)
        rows.append(
            (folder + "/", folder_heat, sum(row.get("reads", 0) for row in members), False, False)
        )
        active = sorted(
            (row for row in members if row.get("reads", 0)),
            key=lambda row: (-row.get("heat", 0), row["path"]),
        )
        rows.extend(
            (
                "  " + os.path.basename(row["path"]),
                row.get("heat", 0),
                row.get("reads", 0),
                True,
                False,
            )
            for row in active
        )
        quiet = len(members) - len(active)
        if quiet:
            rows.append((f"  · {quiet} untouched", 0, 0, True, True))
    high = max((heat for _, heat, _, _, _ in rows), default=1) or 1
    height = 30 + len(rows) * 25
    out = [
        f"<svg class=tree-chart viewBox='0 0 820 {height}' role=img><title>Documentation tree by current heat</title>"
    ]
    for index, (label, heat, reads, nested, quiet) in enumerate(rows):
        y = 23 + index * 25
        shown = label if len(label) <= 48 else label[:47] + "…"
        mark = "·" if quiet else "▸" if not nested else "●"
        color = HEAT[0] if quiet else heat_color(heat, high)
        bar = 0 if quiet else max(3, 280 * math.log1p(heat) / math.log1p(max(high, 2)))
        out.append(
            f"<g><title>{esc(label)} · h{heat:.3f} · {reads} lifetime reads</title><text x=12 y={y} fill='{color}'>{mark}</text><text x=32 y={y}>{esc(shown)}</text><rect x=410 y={y-13} width='{bar:.1f}' height=11 rx=2 fill='{color}'/><text x=705 y={y}>h{heat:.2f} · {reads}×</text></g>"
        )
    out.append("</svg>")
    return "".join(out)


def write_report(content):
    """Atomically write a private report without following project-controlled links."""
    out_dir = os.path.join(ROOT, ".trigger-tree")
    if os.path.lexists(out_dir):
        mode = os.lstat(out_dir).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise RuntimeError("refusing non-directory or symlinked .trigger-tree")
    else:
        os.makedirs(out_dir, mode=0o700)
    out_path = os.path.join(out_dir, "report.html")
    fd, temporary = tempfile.mkstemp(prefix=".report.", dir=out_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.chmod(temporary, 0o600)
        os.replace(temporary, out_path)
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass
    return out_path


def main():
    stats_raw = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "tt-stats.py")] + sys.argv[1:],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    s = json.loads(stats_raw)
    t = s["totals"]
    maturity = s.get("maturity", "cold-start")
    heated_files = sorted(
        (f for f in s["files"] if f.get("state", "current") == "current"),
        key=lambda f: (-f.get("heat", 0), -f["reads"], f["path"]),
    )
    max_heat = max((f.get("heat", 0) for f in heated_files), default=1)
    trend = s.get("trend", [])
    reads_spark = sparkline_svg([bucket.get("reads", 0) for bucket in trend], "Reads by period")
    scans_spark = sparkline_svg([bucket.get("scans", 0) for bucket in trend], "Searches by period")

    parts = [
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>trigger-tree Report</title><style>{CSS}</style></head><body>"
    ]
    parts.append("<h1>🌳 trigger-tree — documentation health</h1>")
    h = s.get("health")
    if h:
        provisional = "" if maturity == "mature" else " · provisional (measurement still young)"
        parts.append(
            "<div class='note grade'>"
            f"<span class=grade-letter>{esc(h['grade'])}</span>"
            f"<span><b>Documentation health · {h['score']}/100</b>{esc(provisional)}<br>"
            "<small class=muted>"
            + " · ".join(esc(d) for d in h["drivers"])
            + "</small></span></div>"
        )
    parts.append(
        f"<p class=muted>Period {esc(s['observed_from'])} → {esc(s['observed_to'])} "
        f"({esc(s.get('observed_days', 0))} days) · maturity: <b>{esc(maturity)}</b></p>"
    )
    parts.append(
        "<div class=kpi>"
        f"<div><b>{t['reads']}</b>reads{reads_spark}</div>"
        f"<div><b>{t['scans']}</b>searches{scans_spark}</div>"
        f"<div><b>{t.get('skill_uses', 0)}</b>skill uses</div>"
        f"<div><b>{s['sessions']}</b>sessions</div>"
        f"<div><b>{t['touched_current_files']}/{t['evaluable_files']}</b>current files touched</div>"
        f"<div><b>{t['untouched_current_files']}</b>current files untouched</div>"
        "</div>"
    )
    parts.append(
        "<p class=muted>Current inventory: "
        f"{t['inventory_files']} files = {t['evaluable_files']} evaluable + "
        f"{t['always_loaded_files']} always loaded. Evaluable coverage reconciles as "
        f"{t['touched_current_files']} touched + {t['untouched_current_files']} untouched = "
        f"{t['evaluable_files']}.</p>"
    )
    parts.append(
        "<p><b>a rule that is never read protects nothing</b> — use the evidence below "
        "to improve routes, not to confuse discovery with understanding. "
        "<a href='https://github.com/Hedde/trigger_tree/blob/main/docs/glossary.md'>Glossary</a>.</p>"
    )
    parts.append(
        "<nav class=toc aria-label='Report sections'><b>Jump to:</b> "
        "<a href='#heat'>heat</a><a href='#folders'>folders</a>"
        "<a href='#untouched'>untouched</a><a href='#trend'>trend</a>"
        "<a href='#routing'>routing</a><a href='#tasks'>tasks</a></nav>"
    )

    heat_model = s.get("heat_model", {})
    half_life = heat_model.get("half_life_days", 30)
    half_life_label = f"{half_life:g}" if isinstance(half_life, (int, float)) else esc(half_life)
    tree = tree_svg(s["files"], maturity, t["evaluable_files"])
    parts.append("<h2 id=heat>Current heat</h2>")
    if tree:
        parts.append(
            "<p class=muted>The same indented tree, heat bars, h values, and lifetime reads "
            "used by the live dashboard. Untouched files collapse to a · summary.</p>" + tree
        )
    parts.append(
        "<p class=muted>Heat is recent attention with a "
        f"{half_life_label}-day half-life; lifetime reads never decay. "
        "Cold means inactive now, not unimportant.</p><div class=scroll><table>"
    )
    visible_windows = [
        days for days in heat_model.get("windows_days", []) if days <= s.get("observed_days", 0)
    ]
    window_headers = "".join(f"<th>{days}d</th>" for days in visible_windows)
    parts.append(
        "<tr><th>Path</th><th>Heat</th><th></th>"
        + window_headers
        + "<th>Lifetime</th><th>Agents</th><th>Last read</th></tr>"
    )
    for f in heated_files[:20]:
        heat = f.get("heat", 0)
        w = max(6, int(120 * heat / max_heat)) if heat else 6
        col = heat_color(heat, max_heat)
        window_cells = "".join(f"<td>{f.get(f'reads_{days}d', 0)}</td>" for days in visible_windows)
        parts.append(
            f"<tr><td><code>{esc(f['path'])}</code></td><td>{heat:.3f}</td>"
            f"<td><span class=bar style='width:{w}px;background:{col}'></span></td>"
            f"{window_cells}<td>{f['reads']}</td><td><small>{agent_label(f)}</small></td>"
            f"<td><small>{esc(f['last_read'])}</small></td></tr>"
        )
    parts.append("</table></div>")

    if s.get("retired_files"):
        parts.append("<h3>Retired paths</h3>")
        parts.append(
            "<p class=muted>These paths have telemetry history but no longer exist. They are "
            "excluded from current heat, health, and coverage.</p><details><summary>"
            f"{len(s['retired_files'])} retired paths</summary><ul>"
        )
        parts.extend(
            f"<li><code>{esc(item['path'])}</code> · {item['reads']} historical reads · "
            f"last {esc(item['last_read'])}</li>"
            for item in s["retired_files"]
        )
        parts.append("</ul></details>")

    if s.get("skills"):
        parts.append("<h2>Skill usage</h2><div class=scroll><table>")
        parts.append("<tr><th>Skill</th><th>Uses</th><th>Sessions</th><th>Last used</th></tr>")
        for sk in s["skills"]:
            parts.append(
                f"<tr><td><code>{esc(sk['name'])}</code></td><td>{sk['uses']}</td>"
                f"<td>{sk['sessions']}</td><td><small>{esc(sk['last_used'])}</small></td></tr>"
            )
        parts.append("</table></div>")

    if s.get("folders"):
        parts.append("<h2 id=folders>Folder heat &amp; cold map</h2>")
        parts.append(
            "<p class=muted>Folder heat sums current decayed file attention. Coverage and lifetime "
            "reads remain separate; cold means inactive now and never proves removal is safe.</p>"
        )
        parts.append("<div class=scroll><table>")
        folder_window = max(visible_windows, default=None)
        folder_window_header = f"<th>{folder_window}d</th>" if folder_window else ""
        parts.append(
            "<tr><th>Folder</th><th>Heat</th><th></th>" + folder_window_header + "<th>Coverage</th>"
            "<th>Lifetime</th><th>Retired read share</th><th>Median file age</th>"
            "<th>Last read</th></tr>"
        )
        max_folder_heat = max((f.get("heat", 0) for f in s["folders"]), default=1)
        visible_folders = [f for f in s["folders"] if f.get("files", 0) or f.get("heat", 0)]
        for fo in sorted(visible_folders, key=lambda f: (-f.get("heat", 0), f["folder"])):
            heat = fo.get("heat", 0)
            w = max(4, int(120 * heat / max_folder_heat)) if heat else 4
            col = heat_color(heat, max_folder_heat)
            no_index = "" if fo.get("has_index") else " <small class=muted>· no index file</small>"
            folder_window_cell = (
                f"<td>{fo.get(f'reads_{folder_window}d', 0)}</td>" if folder_window else ""
            )
            parts.append(
                f"<tr><td><code>{esc(fo['folder'])}/</code>{no_index}</td>"
                f"<td>{heat:.3f}</td>"
                f"<td><span class=bar style='width:{w}px;background:{col}'></span></td>"
                f"{folder_window_cell}"
                f"<td>{fo['touched']}/{fo['files']} ({int(fo['coverage'] * 100)}%)</td>"
                f"<td>{fo['reads']}</td><td>{int(fo.get('retired_read_share', 0) * 100)}%</td>"
                f"<td>{esc(fo.get('median_file_age_days'))} days</td>"
                f"<td><small>{esc(fo.get('last_read'))}</small></td></tr>"
            )
        parts.append("</table></div>")

    parts.append("<h2 id=untouched>Untouched review</h2>")
    parts.append(f"<div class=note>{esc(MATURITY_NOTE[maturity])}</div>")
    candidates = sorted(
        s.get("review_candidates", []),
        key=lambda item: (
            -item.get("inbound_refs", len(item.get("referenced_from", []))),
            item["path"],
        ),
    )
    if candidates:
        parts.append(
            "<p class=muted>Never read during the measurement period. This is a review queue, "
            "not a removal recommendation.</p><div class=scroll><table>"
            "<tr><th>Path</th><th>Inbound refs</th><th>Flags</th></tr>"
        )
        rows = []
        for item in candidates:
            flags = []
            if item.get("is_router"):
                flags.append("unread router")
            if item.get("template"):
                flags.append("template")
            if item.get("classification") == "protected":
                flags.append("protected")
            if not item.get("inbound_refs", len(item.get("referenced_from", []))):
                flags.append("router gap")
            rows.append(
                f"<tr><td><code>{esc(item['path'])}</code></td>"
                f"<td>{item.get('inbound_refs', len(item.get('referenced_from', [])))}</td>"
                f"<td>{esc(', '.join(flags) or 'review')}</td></tr>"
            )
        parts.extend(rows[:20])
        parts.append("</table></div>")
        if len(rows) > 20:
            parts.append(
                f"<details><summary>and {len(rows) - 20} more</summary><div class=scroll><table>"
                "<tr><th>Path</th><th>Inbound refs</th><th>Flags</th></tr>"
                + "".join(rows[20:])
                + "</table></div></details>"
            )
        parts.append(f"<p class=muted><small>{esc(s.get('review_caveat'))}</small></p>")
    else:
        parts.append("<p>None — every inventoried file has been read at least once.</p>")
    always_loaded = s.get("always_loaded_inventory", s.get("always_loaded", []))
    if always_loaded:
        parts.append(
            "<p class=muted><small>Out of scope (always loaded via system prompt / Skill tool): "
            + ", ".join(f"<code>{esc(p)}</code>" for p in always_loaded)
            + "</small></p>"
        )
    if s.get("unread_routers"):
        parts.append(
            "<p class=muted><b>Unread routers:</b> "
            + ", ".join(f"<code>{esc(path)}</code>" for path in s["unread_routers"])
            + ". Router files are never classified as templates.</p>"
        )

    if trend and len(trend) > 1:
        max_bucket = max(b["reads"] + b["scans"] for b in trend) or 1
        parts.append(
            "<h2 id=trend>Trend</h2><p class=muted>Search/read ratio per period. Movement after "
            "a note is correlation, not proof that the recorded edit caused it.</p>"
        )
        counts_chart = line_chart_svg(
            trend,
            (("reads", "reads", "var(--active)"), ("scans", "searches", "var(--cool)")),
            "Reads and searches by period",
            s.get("notes"),
        )
        ratios = [{**bucket, "ratio": bucket.get("search_ratio") or 0} for bucket in trend]
        ratio_chart = line_chart_svg(
            ratios, (("ratio", "search ratio", "var(--warm)"),), "Search ratio by period"
        )
        if counts_chart:
            parts.append("<div class=chart-pair>" + counts_chart + ratio_chart + "</div>")
        parts.append(
            "<p class=muted>Movement after a note is correlation, not proof that the recorded edit caused it.</p>"
            "<div class=scroll><table>"
        )
        parts.append(
            "<tr><th>Period</th><th>Reads</th><th>Searches</th><th></th><th>Search ratio</th></tr>"
        )
        for b in trend:
            w = max(4, int(120 * (b["reads"] + b["scans"]) / max_bucket))
            ratio_value = b.get("search_ratio", b.get("hunting_ratio"))
            ratio = "—" if ratio_value is None else ratio_value
            parts.append(
                f"<tr><td>{esc(b['period'])}</td><td>{b['reads']}</td><td>{b['scans']}</td>"
                f"<td><span class=bar style='width:{w}px;background:{HEAT[2]}'></span></td>"
                f"<td>{esc(ratio)}{' · small n' if b.get('small_n') else ''}</td></tr>"
            )
        parts.append("</table></div>")

    if s.get("notes"):
        parts.append("<h2>Notes (router changes &amp; annotations)</h2><ul>")
        parts.extend(
            f"<li><small class=muted>{esc(n['ts'])}</small> — {esc(n['text'])}</li>"
            for n in s["notes"]
        )
        parts.append("</ul>")

    if s.get("experimental_outcomes"):
        outcomes = s["experimental_outcomes"]
        parts.append(
            "<h2>Experimental outcome correlation</h2>"
            f"<div class=note><b>{esc(outcomes['label'])}</b><br>"
            "This local view does not show that reading a document caused an outcome.</div>"
        )
        parts.append(
            "<div class=scroll><table><tr><th>Bucket</th><th>Sessions</th><th>Docs read</th></tr>"
        )
        for bucket in ("committed", "abandoned"):
            value = outcomes[bucket]
            docs = (
                ", ".join(
                    f"<code>{esc(item['path'])}</code> ×{item['reads']}" for item in value["docs"]
                )
                or "—"
            )
            parts.append(f"<tr><td>{bucket}</td><td>{value['sessions']}</td><td>{docs}</td></tr>")
        parts.append("</table></div>")

    if s.get("router_coverage"):
        parts.append("<h2 id=routing>Folder-router coverage</h2><div class=scroll><table>")
        parts.append("<tr><th>Router</th><th>Listed</th><th>Unlisted direct files</th></tr>")
        for item in s["router_coverage"]:
            missing = "<br>".join("<code>" + esc(path) + "</code>" for path in item["unlisted"])
            parts.append(
                f"<tr><td><code>{esc(item['router'])}</code></td>"
                f"<td>{item['listed']}/{item['files']}</td>"
                f"<td>{missing or '—'}</td></tr>"
            )
        parts.append(
            "</table></div><p class=muted>Unlisted means absent from that folder's existing "
            "README.md, _index.md, index.md, or CLAUDE.md; links elsewhere do not count as "
            "folder-router reachability.</p>"
        )

    search_activity = s.get("search_activity", s.get("hunting", []))
    if search_activity:
        parts.append("<h2>Search activity inside doc folders</h2><div class=scroll><table>")
        parts.append(
            "<tr><th>Folder</th><th>Scans</th><th>Sessions</th><th>Tools</th><th>Pattern</th></tr>"
        )
        parts.extend(
            f"<tr><td><code>{esc(h['path'])}</code></td><td>{h['scans']}</td>"
            f"<td>{h.get('sessions', '—')}/{h.get('total_sessions', '—')}</td>"
            f"<td>{esc(h.get('tools', {}))}</td><td>{esc(h.get('pattern', 'unknown'))}</td></tr>"
            for h in search_activity
        )
        parts.append(
            "</table></div><p class=muted>A scan records explicit search activity, not its "
            "cause. Concentrated bursts may be intentional bulk work; distributed recurrence "
            "can support, but does not prove, a routing hypothesis.</p>"
        )

    if s.get("clusters"):
        parts.append(
            "<h2 id=tasks>Task clusters</h2><p class=muted>Doc-and-skill sets per prompt, grouped "
            "by similarity (Jaccard ≥ 0.6) across sessions.</p><div class=scroll><table>"
        )
        parts.append("<tr><th>×</th><th>Variants</th><th>Example prompt</th><th>Paths</th></tr>")
        for c in s["clusters"]:
            prompt = esc(c["prompts"][0]) if c["prompts"] else "—"
            paths = "<br>".join(f"<code>{esc(p)}</code>" for p in c["paths"])
            parts.append(
                f"<tr><td>{c['count']}</td><td>{c['variants']}</td><td>{prompt}</td><td>{paths}</td></tr>"
            )
        parts.append("</table></div>")

    if s["co_read_top"]:
        parts.append("<h2>Most often read together</h2><div class=scroll><table>")
        parts.append("<tr><th>Pair</th><th>×</th></tr>")
        for c in s["co_read_top"][:10]:
            parts.append(
                f"<tr><td><code>{esc(c['pair'][0])}</code> + <code>{esc(c['pair'][1])}</code></td>"
                f"<td>{c['count']}</td></tr>"
            )
        parts.append("</table></div>")
    skipped_co_reads = s.get("co_read_diagnostics", {}).get("oversized_prompts_skipped", 0)
    if skipped_co_reads:
        limit = s["co_read_diagnostics"]["max_paths_per_prompt"]
        parts.append(
            f"<p class=muted>Co-read pairs skipped for {skipped_co_reads} oversized prompt(s) "
            f"with more than {limit} paths; task clusters and read counts remain complete.</p>"
        )

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts.append(
        f"<footer>Generated {generated} · trigger-tree {esc(plugin_version())}<br>"
        "100% local — this file was generated on your machine and never uploaded.</footer>"
    )
    parts.append("</body></html>")

    out_path = write_report("\n".join(parts))
    print(out_path)


if __name__ == "__main__":
    main()
