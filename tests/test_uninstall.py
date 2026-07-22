import json

import pytest
from conftest import load_script


def wire(project, command="python3 .claude/tt-statusline.py"):
    claude = project / ".claude"
    claude.mkdir()
    (claude / "tt-statusline.py").write_text("# copied\n")
    (claude / "settings.json").write_text(
        json.dumps({"permissions": {}, "statusLine": {"type": "command", "command": command}})
    )
    (project / ".trigger-tree").mkdir()
    (project / ".trigger-tree" / "history.jsonl").write_text("history\n")
    (project / ".gitignore").write_text(".trigger-tree/*\n")


def test_uninstall_removes_only_owned_statusline_wiring(tmp_path, capsys):
    wire(tmp_path)
    mod = load_script("tt-uninstall.py", tmp_path)
    mod.main()
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert settings == {"permissions": {}}
    assert not (tmp_path / ".claude" / "tt-statusline.py").exists()
    assert (tmp_path / ".trigger-tree" / "history.jsonl").read_text() == "history\n"
    assert (tmp_path / ".gitignore").read_text() == ".trigger-tree/*\n"
    assert "delete them manually" in capsys.readouterr().out

    mod.main()
    assert capsys.readouterr().out.count("skipped") == 2


def test_uninstall_preserves_foreign_statusline_but_removes_copied_script(tmp_path, capsys):
    wire(tmp_path, "my-statusline")
    mod = load_script("tt-uninstall.py", tmp_path)
    mod.main()
    assert (
        json.loads((tmp_path / ".claude" / "settings.json").read_text())["statusLine"]["command"]
        == "my-statusline"
    )
    assert not (tmp_path / ".claude" / "tt-statusline.py").exists()
    assert "foreign statusLine left untouched" in capsys.readouterr().out


def test_uninstall_handles_absent_and_unparseable_settings(tmp_path, capsys):
    mod = load_script("tt-uninstall.py", tmp_path)
    mod.main()
    assert "settings.json (absent)" in capsys.readouterr().out
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text("{broken")
    mod.main()
    assert "unparseable" in capsys.readouterr().out


@pytest.mark.skipif(__import__("os").name == "nt", reason="symlinks need privileges on Windows")
def test_uninstall_refuses_statusline_symlink(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    victim = tmp_path / "victim"
    victim.write_text("safe")
    (claude / "tt-statusline.py").symlink_to(victim)
    mod = load_script("tt-uninstall.py", tmp_path)
    with pytest.raises(RuntimeError, match="symlink"):
        mod.remove_statusline_script()
    assert victim.read_text() == "safe"
