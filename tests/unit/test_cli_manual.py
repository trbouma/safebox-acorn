"""Keep the published command inventory aligned with the registered CLI."""
import re
from pathlib import Path

import click


def test_cli_manual_covers_registered_commands_and_options(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    from acorn.cli_acorn import cli

    page = (Path(__file__).parents[2] / "website/cli/commands.md").read_text()
    sections = dict(re.findall(
        r"^## ([^\n]+?) \{ #[^}]+ \}\n(.*?)(?=^## |\Z)", page,
        flags=re.MULTILINE | re.DOTALL,
    ))
    seen = set()

    def check(command, path):
        title = "acorn " + path if path else "Global options"
        seen.add(title)
        assert title in sections, f"Missing CLI documentation: {title}"
        section = sections[title]
        assert "Usage: acorn" in section
        for param in command.params:
            if isinstance(param, click.Option):
                for option in param.opts + param.secondary_opts:
                    assert re.search(re.escape(option) + r"(?=[\s,=]|$)", section), (title, option)
            elif isinstance(param, click.Argument):
                assert param.human_readable_name in section, (title, param.name)
        if isinstance(command, click.Group):
            for name, child in command.commands.items():
                check(child, (path + " " + name).strip())

    check(cli, "")
    assert set(sections) == seen, "Manual lists removed or unregistered commands"
