from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

from monstr.encrypt import Keys

from acorn.acorn import Acorn


ACORN_SOURCE = Path(__file__).resolve().parents[2] / "acorn" / "acorn.py"
LOGGER_METHODS = {"debug", "info", "warning", "error", "critical", "exception"}


def _logger_calls() -> list[tuple[int, str]]:
    source = ACORN_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in LOGGER_METHODS:
            continue
        owner = ast.get_source_segment(source, node.func.value) or ""
        if not owner.endswith("logger"):
            continue
        calls.append((node.lineno, ast.get_source_segment(source, node) or ""))
    return calls


def test_runtime_logs_do_not_serialize_sensitive_wallet_material():
    prohibited_patterns = {
        "proof secret": r"\.secret\b",
        "raw wallet metadata": r"\{wallet_config_data\}|,\s*wallet_config_data\b",
        "raw proof collection": (
            r"\{(?:proof_objs|spend_proofs|keep_proofs|proofs_to_use|"
            r"proofs_remaining)\}"
        ),
        "raw melt request": r"\{data_to_send\}|,\s*data_to_send\b",
        "Lightning invoice": r"\{lninvoice\}|\{pr\}|,\s*(?:lninvoice|pr)\b",
        "raw mint response": r"\{response\.json\(\)\}|,\s*response\.json\(\)",
        "raw zap request": r"\{zap_dict\}|,\s*zap_dict\b",
        "raw profile/event content": r"\{(?:profile_str|json_str)\}|,\s*(?:profile_str|json_str)\b",
        "direct message plaintext": r"\{message\}|,\s*message\b",
        "private record label": r"(?:record|label|grant|offer|hash|target_tag)=%s",
        "mint quote identifier": r"quote=%s",
        "payment address": r"lnaddress=%s",
        "token value": r"token=%s",
        "blinding factor": r"\{r\}",
    }

    violations = []
    for line, call_source in _logger_calls():
        for category, pattern in prohibited_patterns.items():
            if re.search(pattern, call_source):
                violations.append(f"line {line}: {category}: {call_source}")

    assert violations == [], "Sensitive logging policy violations:\n" + "\n".join(violations)


def test_wallet_initialization_log_excludes_private_key(caplog):
    secret_nsec = Keys().private_key_bech32()
    secret_hex = Keys(priv_k=secret_nsec).private_key_hex()
    caplog.set_level(logging.DEBUG, logger="Acorn")

    wallet = Acorn(
        nsec=secret_nsec,
        home_relay="wss://relay.example.com",
        relays=["wss://relay.example.com"],
        logging_level=logging.DEBUG,
    )

    assert wallet.pubkey_bech32
    assert secret_nsec not in caplog.text
    assert secret_hex not in caplog.text
