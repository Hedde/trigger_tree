import json

from conftest import REPO


def test_marketing_site_matches_released_navigation_and_doctor():
    html = open(f"{REPO}/index.html", encoding="utf-8").read()
    assert html.count('class="card"') == 6
    assert html.count('class="install-card"') == 2
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in html
    assert "grid-template-columns:repeat(auto-fit" not in html
    assert "30-day half-life while lifetime reads stay visible" in html
    assert '█".repeat' in html and '·".repeat' in html
    assert "f focus · h hot · c cold" in html
    assert 'nameDesc ? "Z–A" : "A–Z"' in html and "s settings" in html
    assert 'const sorts = { f: "focus", h: "hot", c: "cold", n: "name" }' in html
    assert "Focused top 10" in html
    assert "/tt doctor" in html
    assert "/tt uninstall" in html
    assert "hook liveness, watch coverage" in html
    assert "native Windows hook launch" in html
    assert "rg</code>/<code>grep</code>/<code>find" in html
    assert "Claude Code · Codex" in html
    assert "codex plugin marketplace add Hedde/trigger_tree" in html
    assert "OpenAI Curated only after a separate OpenAI submission" in html
    assert "Codex's built-in <code>/statusline</code> is separate" in html
    assert "--cold:#4775d1" in html and "--hot:#e53935" in html
    assert 'cold</span> → <span class="cool">cool' in html
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in html
    assert "← older" in html and "→ newer" in html and "a live overview" in html
    assert "Math.min(buckets.length - 1, browseIdx + 1)" in html
    assert "browseIdx + 1 >= buckets.length ? null" not in html
    assert "folderSearches" in html and "unread" in html
    assert (
        'property="og:image" content="https://hedde.github.io/trigger_tree/assets/social-card.png"'
        in html
    )
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert 'property="og:image:width" content="1200"' in html
    assert "current local snapshot · cold-start" in html and "measuring…" in html
    assert "Different evidence, different questions" in html
    assert "Which local project docs did the coding assistant discover?" in html
    assert "/tt badge" in html
    assert "static, dependency-free, and has no analytics" in html
    assert "--muted:#9aa4af" in html
    assert 'src="https://' not in html
    assert '<link rel="canonical" href="https://hedde.github.io/trigger_tree/">' in html
    assert '"@type": "SoftwareApplication"' in html and "application/ld+json" in html
    assert "Common questions" in html
    assert "an unread guardrail fails" in html
    assert "It reports discovery, not understanding." in html
    assert "pipx install trigger-tree" in html
    assert "prompt privacy — stored locally, gitignored" in html
    assert "[s] back" in html and "saved — future prompts use" in html
    assert "injected · always loaded" in html
    assert "RECENT_MS = 8000" in html
    assert "% TIPS.length" in html and "30000" in html
    assert "copyInstall()" in html and 'btn.textContent = "copied ✓"' in html
    assert "uvx --from trigger-tree tt" in html
    assert 'video src="docs/assets/demo.mp4" autoplay loop muted playsinline' in html
    assert "real footage — tt watch --demo" in html


def test_example_report_is_published_and_labeled_synthetic():
    html = open(f"{REPO}/index.html", encoding="utf-8").read()
    assert '<a href="demo-report.html">view an example insights report</a>' in html
    report = open(f"{REPO}/demo-report.html", encoding="utf-8").read()
    assert "<title>trigger-tree Report</title>" in report
    assert "Example report</b> — generated from synthetic demo data" in report
    assert "never leave your machine" in report
    assert 'src="http' not in report and "https://cdn" not in report


def test_ci_gate_section_shows_the_committed_baseline_honestly():
    html = open(f"{REPO}/index.html", encoding="utf-8").read()
    assert "Gate your CI on discoverability" in html
    assert "uses: Hedde/trigger_tree@v" in html
    assert "Discoverable never means discovered" in html
    baseline = json.load(open(f"{REPO}/.trigger-tree/gate.json", encoding="utf-8"))
    assert f'<span class="pill-value">{baseline["score"]}%</span>' in html


def test_search_presence_files_agree_on_the_canonical_url():
    site = "https://hedde.github.io/trigger_tree/"
    sitemap = open(f"{REPO}/sitemap.xml", encoding="utf-8").read()
    robots = open(f"{REPO}/robots.txt", encoding="utf-8").read()
    assert f"<loc>{site}</loc>" in sitemap
    assert f"Sitemap: {site}sitemap.xml" in robots
    assert "User-agent: *" in robots


def test_social_card_has_link_preview_dimensions():
    data = open(f"{REPO}/assets/social-card.png", "rb").read(24)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(data[16:20], "big") == 1200
    assert int.from_bytes(data[20:24], "big") == 630
