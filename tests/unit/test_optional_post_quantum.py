import importlib

import pytest


def test_monstrmore_import_does_not_load_oqs(monkeypatch):
    real_import_module = importlib.import_module

    def guarded_import(name, package=None):
        if name == "oqs":
            raise AssertionError("ordinary Acorn imports must not load oqs")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", guarded_import)
    module = importlib.reload(importlib.import_module("acorn.monstrmore"))

    assert module.KindOtherGiftWrap is not None
    assert module.ExtendedNIP44Encrypt is not None


def test_post_quantum_use_explains_optional_dependency(monkeypatch):
    from acorn import post_quantum

    def missing_oqs(name, package=None):
        if name == "oqs":
            raise ModuleNotFoundError("No module named 'oqs'")
        return importlib.import_module(name, package)

    monkeypatch.setattr(post_quantum.importlib, "import_module", missing_oqs)

    with pytest.raises(
        post_quantum.PostQuantumUnavailableError,
        match=r"safebox-acorn\[post-quantum\]",
    ):
        post_quantum._require_oqs()


def test_historical_pqevent_import_path_is_preserved():
    from acorn.monstrmore import PQEvent
    from acorn.post_quantum import PQEvent as IsolatedPQEvent

    assert PQEvent is IsolatedPQEvent
