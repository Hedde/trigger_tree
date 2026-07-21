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
    assert "rg</code>/<code>grep</code>/<code>find" in html
    assert "Claude Code · Codex" in html
    assert "codex plugin marketplace add Hedde/trigger_tree" in html
    assert "OpenAI Curated only after a separate OpenAI submission" in html
    assert "Codex's built-in <code>/statusline</code> is separate" in html
    assert "--cold:#5c8fe6" in html and "--hot:#e53935" in html
    assert 'cold</span> → <span class="cool">cool' in html
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in html
    assert "← older" in html and "→ newer" in html and "a live overview" in html
    assert "Math.min(buckets.length - 1, browseIdx + 1)" in html
    assert "browseIdx + 1 >= buckets.length ? null" not in html
    assert "folderSearches" in html and "unread" in html
