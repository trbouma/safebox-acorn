from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(REPO_ROOT / ".env")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    from tests.helpers import relay_suitability_summary_rows

    rows = relay_suitability_summary_rows()
    if not rows:
        return

    terminalreporter.section("Acorn relay suitability summary")
    for row in rows:
        elapsed = f"{row['elapsed']:.1f}s"
        terminalreporter.write_line(
            f"{row['status']}: {row['relay']} "
            f"({row['scenario']}, {elapsed})"
        )
        terminalreporter.write_line(f"  Observed: {row['observed']}")
        terminalreporter.write_line(
            "  Ledger row: "
            f"| `{row['relay']}` | {row['status']} | {row['observed']} | "
            f"~{elapsed} |  |"
        )
