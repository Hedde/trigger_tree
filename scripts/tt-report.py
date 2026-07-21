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
import subprocess
import sys

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
    heated_files = sorted(s["files"], key=lambda f: (-f.get("heat", 0), -f["reads"], f["path"]))
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
        f"<div><b>{len(s['files'])}/{t['inventory_files']}</b>files touched</div>"
        f"<div><b>{len(s['untouched'])}</b>untouched</div>"
        "</div>"
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
    parts.append(
        "<tr><th>Path</th><th>Heat</th><th></th><th>7d</th><th>30d</th><th>90d</th>"
        "<th>Lifetime</th><th>Last read</th></tr>"
    )
    for f in heated_files[:20]:
        heat = f.get("heat", 0)
        w = max(6, int(120 * heat / max_heat)) if heat else 6
        col = heat_color(heat, max_heat)
        parts.append(
            f"<tr><td><code>{esc(f['path'])}</code></td><td>{heat:.3f}</td>"
            f"<td><span class=bar style='width:{w}px;background:{col}'></span></td>"
            f"<td>{f.get('reads_7d', 0)}</td><td>{f.get('reads_30d', 0)}</td>"
            f"<td>{f.get('reads_90d', 0)}</td><td>{f['reads']}</td>"
            f"<td><small>{esc(f['last_read'])}</small></td></tr>"
        )
    parts.append("</table></div>")

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
        parts.append(
            "<tr><th>Folder</th><th>Heat</th><th></th><th>30d</th><th>Coverage</th>"
            "<th>Lifetime</th><th>Last read</th></tr>"
        )
        max_folder_heat = max((f.get("heat", 0) for f in s["folders"]), default=1)
        for fo in sorted(s["folders"], key=lambda f: (-f.get("heat", 0), f["folder"])):
            heat = fo.get("heat", 0)
            w = max(4, int(120 * heat / max_folder_heat)) if heat else 4
            col = heat_color(heat, max_folder_heat)
            no_index = "" if fo.get("has_index") else " <small class=muted>· no index file</small>"
            parts.append(
                f"<tr><td><code>{esc(fo['folder'])}/</code>{no_index}</td>"
                f"<td>{heat:.3f}</td>"
                f"<td><span class=bar style='width:{w}px;background:{col}'></span></td>"
                f"<td>{fo.get('reads_30d', 0)}</td>"
                f"<td>{fo['touched']}/{fo['files']} ({int(fo['coverage'] * 100)}%)</td>"
                f"<td>{fo['reads']}</td><td><small>{esc(fo.get('last_read'))}</small></td></tr>"
            )
        parts.append("</table></div>")

    parts.append("<h2>Review candidates (untouched paths)</h2>")
    parts.append(f"<div class=note>{esc(MATURITY_NOTE[maturity])}</div>")
    if s["untouched"]:
        parts.append(
            "<p class=muted>Never read during the measurement period. This is a review queue, "
            "not a removal recommendation. Low reads can mean rare-but-critical.</p><ul>"
        )
        detail = {d["path"]: d["referenced_from"] for d in s.get("untouched_detail", [])}
        for p in s["untouched"]:
            refs = detail.get(p, [])
            tmpl = {d["path"]: d.get("template") for d in s.get("untouched_detail", [])}
            if tmpl.get(p):
                info = "template — intentional archive"
            elif refs:
                info = "referenced from " + ", ".join(f"<code>{esc(r)}</code>" for r in refs)
            else:
                info = "<b>not referenced by any doc — router gap</b>"
            parts.append(
                f"<li class=untouched><code>{esc(p)}</code>"
                f" <small class=muted>· {info}</small></li>"
            )
        parts.append("</ul>")
    else:
        parts.append("<p>None — every inventoried file has been read at least once.</p>")
    protected = [
        item for item in s.get("review_candidates", []) if item.get("classification") == "protected"
    ]
    if protected:
        parts.append("<h3>Protected — review, likely keep</h3><ul>")
        for item in protected:
            parts.append(
                f"<li><code>{esc(item['path'])}</code> · {esc('; '.join(item['why']))}"
                f"<br><small>{esc(item['caveat'])}</small></li>"
            )
        parts.append("</ul>")
    if s.get("always_loaded"):
        parts.append(
            "<p class=muted><small>Out of scope (always loaded via system prompt / Skill tool): "
            + ", ".join(f"<code>{esc(p)}</code>" for p in s["always_loaded"])
            + "</small></p>"
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
                f"<td>{esc(ratio)}</td></tr>"
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

    out_dir = os.path.join(ROOT, ".trigger-tree")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "report.html")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    print(out_path)


if __name__ == "__main__":
    main()
