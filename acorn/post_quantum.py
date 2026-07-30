"""Experimental post-quantum event support.

This module is deliberately outside Acorn's ordinary runtime path. Install the
``post-quantum`` package extra before using ML-DSA signatures.
"""

import importlib
import json
from typing import Any, Union

import secp256k1
from monstr.event.event import Event


class PostQuantumUnavailableError(RuntimeError):
    """Raised when experimental post-quantum support is not installed."""


def _require_oqs() -> Any:
    try:
        return importlib.import_module("oqs")
    except (ImportError, OSError) as exc:
        raise PostQuantumUnavailableError(
            "Post-quantum event support requires the optional dependency. "
            "Install it with 'pip install safebox-acorn[post-quantum]' or "
            "'poetry install -E post-quantum'."
        ) from exc


class PQEvent(Event):
    """Experimental event supporting ML-DSA-44 or classical Schnorr signatures."""

    test: str
    sigalg: str = "ML-DSA-44"

    def sign(self, priv_key):
        if len(priv_key) > 64:
            oqs = _require_oqs()
            signer = oqs.Signature(
                self.sigalg,
                secret_key=bytes.fromhex(priv_key),
            )
            self._get_id()
            signature = signer.sign(bytes.fromhex(self._id))
            self._sig = signature.hex()
            return

        self._get_id()
        signer = secp256k1.PrivateKey()
        signer.deserialize(priv_key)
        signature = signer.schnorr_sign(
            bytes.fromhex(self._id),
            bip340tag="",
            raw=True,
        )
        self._sig = signature.hex()

    def is_valid(self):
        if len(self.pub_key) > 64:
            oqs = _require_oqs()
            try:
                verifier = oqs.Signature(self.sigalg)
                return verifier.verify(
                    bytes.fromhex(self.id),
                    bytes.fromhex(self.sig),
                    bytes.fromhex(self.pub_key),
                )
            except (TypeError, ValueError):
                return False

        try:
            pub_key = secp256k1.PublicKey(
                bytes.fromhex("02" + self._pub_key),
                raw=True,
            )
            return pub_key.schnorr_verify(
                msg=bytes.fromhex(self._id),
                schnorr_sig=bytes.fromhex(self._sig),
                bip340tag="",
                raw=True,
            )
        except (AttributeError, TypeError, ValueError):
            return False

    @staticmethod
    def load(event_data: Union[str, dict], validate=False) -> "PQEvent":
        if isinstance(event_data, str):
            try:
                event_data = json.loads(event_data)
            except json.JSONDecodeError:
                event_data = {}

        event = PQEvent(
            id=event_data.get("id"),
            sig=event_data.get("sig"),
            kind=event_data.get("kind"),
            content=event_data.get("content"),
            tags=event_data.get("tags"),
            pub_key=event_data.get("pubkey"),
            created_at=event_data.get("created_at"),
        )

        if validate and not event.is_valid():
            return None
        return event
