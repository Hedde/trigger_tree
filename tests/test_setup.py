import json
import os
import sys

from conftest import load_script


def test_full_setup_and_idempotency(tmp_path, monkeypatch, capsys):
    mod = load_script("tt-setup.py", tmp_path)
    monkeypatch.setattr(sys, "argv", ["tt-setup.py", "--with-config"])
    mod.main()
    out = capsys.readouterr().out
    assert "updated" in out and "copied" in out and "created" in out

    assert os.path.isfile(tmp_path / ".claude" / "tt-statusline.py")
    assert os.path.isfile(tmp_path / ".trigger-tree" / "config.sh")
    settings = json.load(open(tmp_path / ".claude" / "settings.json"))
    assert settings["statusLine"]["command"].endswith("tt-statusline.py")
    gitignore = (tmp_path / ".gitignore").read_text()
    assert ".trigger-tree/*" in gitignore and "!.trigger-tree/config.sh" in gitignore

    mod.main()  # second run: everything skipped, nothing duplicated
    out2 = capsys.readouterr().out
    assert out2.count("skipped") >= 3
    assert (tmp_path / ".gitignore").read_text() == gitignore


def test_existing_statusline_left_untouched(tmp_path, monkeypatch, capsys):
    (tmp_path / ".claude").mkdir()
    original = {"statusLine": {"type": "command", "command": "my-own-line.sh"}}
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(original))
    mod = load_script("tt-setup.py", tmp_path)
    mod.register_statusline()
    assert "left untouched" in capsys.readouterr().out
    assert json.load(open(tmp_path / ".claude" / "settings.json")) == original


def test_unparseable_settings_skipped(tmp_path, capsys):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{broken")
    mod = load_script("tt-setup.py", tmp_path)
    mod.register_statusline()
    assert "unparseable" in capsys.readouterr().out
    assert (tmp_path / ".claude" / "settings.json").read_text() == "{broken"


def test_gitignore_appends_to_existing(tmp_path, capsys):
    (tmp_path / ".gitignore").write_text("node_modules\n")
    mod = load_script("tt-setup.py", tmp_path)
    mod.ensure_gitignore()
    content = (tmp_path / ".gitignore").read_text()
    assert content.startswith("node_modules\n") and ".trigger-tree/*" in content
