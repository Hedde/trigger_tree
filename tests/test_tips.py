from conftest import load_script


def test_claude_tips_are_client_specific_and_evidence_based(tmp_path):
    mod = load_script("tt-tips.py", tmp_path)
    (tmp_path / "CLAUDE.md").write_text("\n".join(["instruction"] * 201))
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "always.md").write_text("# Always\n")
    (rules / "scoped.md").write_text("---\npaths:\n  - 'src/**'\n---\n# Scoped\n")

    tips = mod.claude_tips(tmp_path)

    assert tips[0].startswith("Run /memory periodically")
    assert any("201 lines" in tip for tip in tips)
    assert any("1 always-loaded rule file" in tip for tip in tips)
    assert all("AGENTS.md" not in tip for tip in tips)


def test_claude_tip_recommends_missing_project_memory(tmp_path):
    mod = load_script("tt-tips.py", tmp_path)
    tips = mod.claude_tips(tmp_path)
    assert any("Add a project CLAUDE.md" in tip for tip in tips)


def test_codex_tips_never_mention_claude_memory(tmp_path):
    mod = load_script("tt-tips.py", tmp_path)
    tips = mod.codex_tips(tmp_path)
    assert tips[0].startswith("Add AGENTS.md")
    assert all("CLAUDE.md" not in tip and "/memory" not in tip for tip in tips)


def test_codex_existing_agents_checks_verification_commands(tmp_path):
    mod = load_script("tt-tips.py", tmp_path)
    (tmp_path / "AGENTS.md").write_text("# Architecture\nUse the service layer.\n")
    tips = mod.codex_tips(tmp_path)
    assert tips[0].startswith("Review AGENTS.md")
    assert any("exact verification commands" in tip for tip in tips)


def test_main_labels_selected_client(tmp_path, capsys):
    mod = load_script("tt-tips.py", tmp_path)
    mod.main(["--client", "codex", "--project", str(tmp_path)])
    out = capsys.readouterr().out
    assert out.startswith("🌳 Codex maintenance tips")
    assert "Claude" not in out


def test_unreadable_markdown_is_handled_conservatively(tmp_path):
    mod = load_script("tt-tips.py", tmp_path)
    broken = tmp_path / "broken.md"
    broken.write_bytes(b"\xff\xfe")
    assert mod.markdown_lines(broken) == 0
    assert mod.has_paths_frontmatter(broken) is True
