from conftest import REPO


def test_marketing_site_matches_released_navigation_and_doctor():
    html = open(f"{REPO}/index.html", encoding="utf-8").read()
    assert "/tt doctor" in html
    assert "rg</code>/<code>grep</code>/<code>find" in html
    assert "← older" in html and "→ newer" in html and "a live overview" in html
    assert "Math.min(buckets.length - 1, browseIdx + 1)" in html
    assert "browseIdx + 1 >= buckets.length ? null" not in html
