from __future__ import annotations

import importlib
from pathlib import Path


def _load_cli(monkeypatch, tmp_path):
    default_oqs_path = Path.home() / "_oqs"
    if default_oqs_path.exists():
        monkeypatch.setenv("OQS_INSTALL_PATH", str(default_oqs_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return importlib.import_module("acorn.cli_acorn")


def test_normalize_relay_adds_wss(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    assert cli._normalize_relay("relay.example.com") == "wss://relay.example.com"
    assert cli._normalize_relay("wss://relay.example.com") == "wss://relay.example.com"
    assert cli._normalize_relay("ws://localhost:7777") == "ws://localhost:7777"


def test_split_csv_trims_spaces(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    assert cli._split_csv("relay.one, relay.two,,relay.three") == [
        "relay.one",
        "relay.two",
        "relay.three",
    ]


def test_format_tx_history_entry_credit(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    rendered = cli._format_tx_history_entry(
        {
            "create_time": "2026-07-29 12:12:22",
            "tx_type": "C",
            "amount": 3,
            "comment": "ecash transfer received",
            "tendered_amount": 3.0,
            "tendered_currency": "SAT",
            "fees": 0,
            "current_balance": 25,
        }
    )

    assert "Credit" in rendered
    assert "+3 sats" in rendered
    assert "balance: 25 sats" in rendered
    assert "ecash transfer received" in rendered


def test_format_tx_history_entry_debit(monkeypatch, tmp_path):
    cli = _load_cli(monkeypatch, tmp_path)

    rendered = cli._format_tx_history_entry(
        {
            "create_time": "2026-07-29 12:04:07",
            "tx_type": "D",
            "amount": 1,
            "comment": "gift wrapped test",
            "tendered_amount": 1.0,
            "tendered_currency": "SAT",
            "fees": 0,
            "current_balance": 20,
        }
    )

    assert "Debit" in rendered
    assert "-1 sats" in rendered
    assert "gift wrapped test" in rendered
