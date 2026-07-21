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

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

HEAT = ["#9aa0a6", "#7cb342", "#9ccc65", "#c0ca33", "#fdd835", "#ffb300", "#fb8c00", "#e53935"]

MATURITY_NOTE = {
    "cold-start": "Measurement just started — review candidates are provisional.",
    "warming": "Early signal — review candidates need more sessions before judging.",
    "mature": "Measurement is mature, but low reads can still mean rare-but-critical.",
}

CSS = """
:root { --bg:#fff; --fg:#1f2328; --muted:#6a737d; --line:#e1e4e8; --card:#f6f8fa; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#101418; --fg:#e6edf3; --muted:#8b949e; --line:#30363d; --card:#161b22; }
}
:root[data-theme="dark"] { --bg:#101418; --fg:#e6edf3; --muted:#8b949e; --line:#30363d; --card:#161b22; }
:root[data-theme="light"] { --bg:#fff; --fg:#1f2328; --muted:#6a737d; --line:#e1e4e8; --card:#f6f8fa; }
body { background:var(--bg); color:var(--fg); font:15px/1.55 -apple-system,'Segoe UI',sans-serif;
       max-width:880px; margin:2rem auto; padding:0 1.25rem; }
h1 { font-size:1.5rem; } h2 { font-size:1.1rem; margin-top:2rem; border-bottom:1px solid var(--line); padding-bottom:.3rem; }
small, .muted { color:var(--muted); }
table { border-collapse:collapse; width:100%; margin:.75rem 0; font-size:.92em; }
th, td { text-align:left; padding:.35rem .6rem; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); font-weight:600; }
.bar { display:inline-block; height:.65em; border-radius:3px; vertical-align:baseline; }
.kpi { display:flex; gap:1rem; flex-wrap:wrap; margin:1rem 0; }
.kpi div { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:.6rem 1rem; }
.kpi b { font-size:1.35rem; display:block; }
.note { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:.6rem 1rem; margin:1rem 0; }
.untouched { color:var(--muted); }
code { background:var(--card); padding:.1em .35em; border-radius:4px; font-size:.9em; }
.scroll { overflow-x:auto; }
"""


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

    parts = [f"<title>trigger-tree Report</title><style>{CSS}</style>"]
    parts.append("<h1>🌳 trigger-tree — documentation telemetry</h1>")
    parts.append(
        f"<p class=muted>Period {esc(s['observed_from'])} → {esc(s['observed_to'])} "
        f"({esc(s.get('observed_days', 0))} days) · maturity: <b>{esc(maturity)}</b></p>"
    )
    h = s.get("health")
    if h:
        provisional = "" if maturity == "mature" else " · provisional (measurement still young)"
        parts.append(
            "<div class=note style='display:flex;gap:1.1rem;align-items:center'>"
            f"<span style='font-size:2.4rem;font-weight:700'>{esc(h['grade'])}</span>"
            f"<span><b>Documentation health — {h['score']}/100</b>{esc(provisional)}<br>"
            "<small class=muted>"
            + " · ".join(esc(d) for d in h["drivers"])
            + "</small></span></div>"
        )
    parts.append(
        "<div class=kpi>"
        f"<div><b>{t['reads']}</b>reads</div>"
        f"<div><b>{t['scans']}</b>searches</div>"
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

    heat_model = s.get("heat_model", {})
    half_life = heat_model.get("half_life_days", 30)
    half_life_label = f"{half_life:g}" if isinstance(half_life, (int, float)) else esc(half_life)
    parts.append("<h2>Current heat</h2>")
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
        parts.append("<h2>Folder heat &amp; cold map</h2>")
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

    parts.append("<h2>Untouched review</h2>")
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

    if s.get("trend") and len(s["trend"]) > 1:
        max_bucket = max(b["reads"] + b["scans"] for b in s["trend"]) or 1
        parts.append(
            "<h2>Trend</h2><p class=muted>Search/read ratio per period. Movement after "
            "a note is correlation, not proof that the recorded edit caused it.</p>"
            "<div class=scroll><table>"
        )
        parts.append(
            "<tr><th>Period</th><th>Reads</th><th>Searches</th><th></th><th>Search ratio</th></tr>"
        )
        for b in s["trend"]:
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
        parts.append("<h2>Folder-router coverage</h2><div class=scroll><table>")
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
            "<h2>Task clusters</h2><p class=muted>Doc-and-skill sets per prompt, grouped "
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

    out_path = write_report("\n".join(parts))
    print(out_path)


if __name__ == "__main__":
    main()
