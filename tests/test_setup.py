import json
import os

from conftest import load_script


def test_full_setup_and_idempotency(tmp_path, monkeypatch, capsys):
    mod = load_script("tt-setup.py", tmp_path)
    mod.main([])
    out = capsys.readouterr().out
    assert "updated" in out and "copied" in out and "created" in out

    assert os.path.isfile(tmp_path / ".claude" / "tt-statusline.py")
    assert os.path.isfile(tmp_path / ".trigger-tree" / "config.sh")
    assert "TT_LOG_PROMPTS='truncate'" in (tmp_path / ".trigger-tree" / "config.sh").read_text()
    settings = json.load(open(tmp_path / ".claude" / "settings.json"))
    assert settings["statusLine"]["command"].endswith("tt-statusline.py")
    gitignore = (tmp_path / ".gitignore").read_text()
    assert ".trigger-tree/*" in gitignore and "!.trigger-tree/config.sh" in gitignore

    mod.main([])  # second run: everything skipped, nothing duplicated
    out2 = capsys.readouterr().out
    assert out2.count("skipped") >= 3
    assert (tmp_path / ".gitignore").read_text() == gitignore


def test_setup_explicit_prompt_modes_update_only_prompt_setting(tmp_path, capsys):
    mod = load_script("tt-setup.py", tmp_path)
    mod.main(["--prompt-mode", "hash"])
    config = tmp_path / ".trigger-tree" / "config.sh"
    assert "TT_LOG_PROMPTS='hash'" in config.read_text()
    assert "hashes only" in capsys.readouterr().out

    mod.main(["--prompt-mode", "off"])
    assert "TT_LOG_PROMPTS='off'" in config.read_text()
    assert "markers only" in capsys.readouterr().out

    mod.main(["--prompt-mode", "truncate"])
    assert "TT_LOG_PROMPTS='truncate'" in config.read_text()
    assert "first 200 characters" in capsys.readouterr().out


def test_existing_config_is_preserved_without_explicit_mode(tmp_path, capsys):
    config_dir = tmp_path / ".trigger-tree"
    config_dir.mkdir()
    config = config_dir / "config.sh"
    config.write_text("TT_LOG_PROMPTS='hash'\nTT_ROTATE_BYTES='42'\n")
    mod = load_script("tt-setup.py", tmp_path)
    mod.main([])
    assert "existing prompt setting preserved" in capsys.readouterr().out
    assert config.read_text() == "TT_LOG_PROMPTS='hash'\nTT_ROTATE_BYTES='42'\n"


def test_prompt_assignment_is_appended_when_missing(tmp_path):
    config = tmp_path / "config.sh"
    config.write_text("TT_ROTATE_BYTES='42'\n")
    mod = load_script("tt-setup.py", tmp_path)
    assert mod.write_prompt_mode(config, "off") is True
    assert config.read_text().endswith("TT_LOG_PROMPTS='off'\n")
    assert mod.write_prompt_mode(config, "off") is False


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


def test_gitignore_without_trailing_newline(tmp_path, capsys):
    (tmp_path / ".gitignore").write_text("node_modules")  # no trailing newline
    mod = load_script("tt-setup.py", tmp_path)
    mod.ensure_gitignore()
    content = (tmp_path / ".gitignore").read_text()
    assert "node_modules\n.trigger-tree/*" in content
