from typing import Any, Dict, List, Optional, Union
import asyncio, json, requests
from time import sleep, time, monotonic
import secrets
from datetime import datetime, timedelta
import urllib.parse
import random
from mnemonic import Mnemonic
import bolt11
import aioconsole
import logging
import httpx
import math
from zoneinfo import ZoneInfo
from datetime import timezone
import filetype

from hotel_names import hotel_names
# from coolname import generate, generate_slug
from binascii import unhexlify
import hashlib
import signal, sys, string, cbor2, base64,os
import contextlib
from cryptography.exceptions import InvalidTag



from monstr.encrypt import Keys
from monstr.encrypt import NIP44Encrypt, NIP4Encrypt
from monstr.client.client import Client, ClientPool
from monstr.event.event import Event


from monstr.signing.signing import BasicKeySigner
from monstr.giftwrap import GiftWrap
from monstr.util import util_funcs
from monstr.entities import Entities
from monstr.client.event_handlers import DeduplicateAcceptor

from acorn.monstrmore import KindOtherGiftWrap, ExtendedNIP44Encrypt
from acorn.func_utils import (
    decrypt_and_verify_record_blob,
    decrypt_bytes,
    encrypt_bytes,
    normalize_mint_url,
    npub_to_hex,
)
from acorn.record_transfer import (
    RECORD_PRESENTATION_PREFIX,
    RecordTransferDescriptor,
    RecordTransferEnvelope,
    RecordTransferError,
    decode_record_transfer_descriptor,
    decode_record_presentation_descriptor,
    decrypt_record_transfer_envelope,
    derive_record_transfer_authority_hex,
    encode_record_transfer_descriptor,
    encode_record_presentation_descriptor,
    encrypt_record_transfer_envelope,
    verify_record_transfer_ciphertext,
)
from acorn.record_protection import validate_record_protection_key


tail = util_funcs.str_tails

from acorn.b_dhke import step1_alice, step3_alice, hash_to_curve
from acorn.secp import PrivateKey, PublicKey
from acorn.lightning import lightning_address_pay, lnaddress_to_lnurl, zap_address_pay
from acorn.nostr import bech32_to_hex, hex_to_bech32, nip05_to_npub, create_nembed_compressed,parse_nembed_compressed

from acorn.models import nostrProfile, SafeboxItem, mintRequest, mintQuote, BlindedMessage, Proof, Proofs, proofEvent, proofEvents, KeysetsResponse, PostMeltQuoteResponse, walletQuote, NIP60Proofs
from acorn.models import TokenV3, TokenV3Token, cliQuote, proofsByKeyset, Zevent
from acorn.models import TokenV4, TokenV4Token
from acorn.models import WalletConfig, WalletRecord,WalletReservedRecords
from acorn.models import TxHistory, SafeboxRecord, ParseRecord, EncryptionParms, EncryptionResult, OriginalRecordTransfer

from acorn.func_utils import (
    generate_access_key_from_hex,
    generate_name_from_hex,
    generate_seed_phrase_and_nsec,
    name_to_hex,
    recover_nsec_from_seed,
    seed_phrase_matches_nsec,
    split_proofs_instance,
)

from python_blossom import BlossomClient, Blob as BlossomBlob
from tempfile import NamedTemporaryFile
import mimetypes

RECORD_LIMIT: int = 1024
PROOF_LIMIT: int = 32
ECASH_TRANSFER_KIND: int = 7378
ECASH_TRANSFER_GIFT_WRAP_KIND: int = 1059
ECASH_TRANSFER_CURSOR_LABEL: str = "ecash_transfer_latest"
BURN_DEFAULT_KINDS: List[int] = [0, 5, 37375, 37376, 7375, ECASH_TRANSFER_KIND, 30000, 30001, 30002]
RECEIVE_PROOF_MAINTENANCE_ENABLED: bool = os.getenv(
    "RECEIVE_PROOF_MAINTENANCE_ENABLED",
    "false",
).strip().lower() in ("1", "true", "yes", "on")
RECEIVE_PROOF_MAINTENANCE_TOTAL_LIMIT: int = int(
    os.getenv("RECEIVE_PROOF_MAINTENANCE_TOTAL_LIMIT", str(PROOF_LIMIT))
)
RECEIVE_PROOF_MAINTENANCE_KEYSET_LIMIT: int = int(
    os.getenv("RECEIVE_PROOF_MAINTENANCE_KEYSET_LIMIT", "16")
)
RECEIVE_PROOF_MAINTENANCE_EAGER_TOTAL_LIMIT: int = int(
    os.getenv("RECEIVE_PROOF_MAINTENANCE_EAGER_TOTAL_LIMIT", "12")
)
RECEIVE_PROOF_MAINTENANCE_EAGER_BATCH_LIMIT: int = int(
    os.getenv("RECEIVE_PROOF_MAINTENANCE_EAGER_BATCH_LIMIT", "4")
)
DEFAULT_BLOSSOM_HOME_SERVER: str = "https://blossom.getsafebox.app"
DEFAULT_BLOSSOM_XFER_SERVER: str = "https://blossomx.getsafebox.app"
DEFAULT_HOME_MINT: str = "https://mint.getsafebox.app"
PENDING_MELTS_LABEL: str = "pending_melts"
DEFERRED_RECOVERY_LABEL: str = "deferred_recovery"
RECORD_PROTECTION_STATUS_LABEL: str = "record_protection_status"
MELT_RECOVERY_ATTEMPTS: int = 4
INTERNAL_RECORD_LABELS: frozenset[str] = frozenset(
    {
        "balance",
        "default",
        DEFERRED_RECOVERY_LABEL,
        RECORD_PROTECTION_STATUS_LABEL,
        "ecash_latest",
        "ecash_transfer_latest",
        "home_relay",
        "index",
        "last_dm",
        "lock",
        "mints",
        "payment_request",
        PENDING_MELTS_LABEL,
        "privkey",
        "profile",
        "public_relays",
        "quote",
        "relays",
        "trusted_mints",
        "user_records",
        "wallet",
        "wallet_config",
    }
)


class PaymentOutcomeUnknownError(RuntimeError):
    """The mint may have paid, so retrying the payment is unsafe."""


class PaymentFinalizationError(RuntimeError):
    """The mint paid, but local/relay wallet finalization is incomplete."""


class PaymentFailedError(RuntimeError):
    """The mint definitively reports that the payment was not paid."""

def powers_of_2_sum(amount):
    powers = []
    while amount > 0:
        power = 1
        while power * 2 <= amount:
            power *= 2
        powers.append(power)
        amount -= power
    return sorted(powers)




    return "hello"
class Acorn:
    k: Keys
    nsec: str
    name: str
    handle: str
    unit: str   = "sat" 
    acorn_tags: List = None
    owner: str = None
    proof_event_ids = []
    pubkey_bech32: str
    pubkey_hex: str
    privkey_hex: str
    privkey_bech32: str 
    seed_phrase: str | None = None
    access_key: str =""
    pqc_self_secret: str = None
    home_relay: str
    home_mint: str
    known_mints: dict = {}
    local_currency: str = "SAT"
    latest_ecash: int = 0
    emergency_contacts: List[str] = None
    authorities: List[str] = None
    providers: List[str] = None
    trusted_entities: List[str] = None
    user_records = []
    relays: List[str]
    public_relays: List[str]
    mints: List[str]
    max_proof_event_size: int
    safe_box_items: List[SafeboxItem]
    proofs: List[Proof]
    profile_found_on_home_relay = False
    events: int
    balance: int
    proof_events: proofEvents 
    replicate: bool
    RESERVED_RECORDS: List[str] = sorted(INTERNAL_RECORD_LABELS)
    wallet_reserved_records: object
    logger: logging.Logger
    TZ: str = "America/New_York"

    def _default_blossom_home_server(self) -> str:
        return self.blossom_home_server

    def _default_blossom_xfer_server(self) -> str:
        return self.blossom_xfer_server

    @staticmethod
    def _is_cashu_token(token: str) -> bool:
        return isinstance(token, str) and (token.startswith("cashuA") or token.startswith("cashuB"))

    



    def __init__(   self, 
                    nsec: str, 
                    relays: List[str]|None=None, 
                    public_relays: List[str]|None=None,
                    mints: List[str]|None=None,
                    home_relay:str|None=None, 
                    max_proof_event_size: int = 16384,
                    replicate = False, 
                    logging_level=logging.INFO,
                    blossom_home_server: str | None = None,
                    blossom_xfer_server: str | None = None,
                    blossom_servers: List[str] | None = None) -> None:
        
        self.max_proof_event_size = max_proof_event_size
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging_level)  
        # Configure the logger's handler and format
        if not self.logger.handlers:
            handler = logging.StreamHandler()  # Output to console
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        # This logger owns its console handler. Propagating the same record to
        # the root logger produces duplicate CLI messages under Poetry/pytest.
        self.logger.propagate = False

        
        access_key_digest = hashlib.sha256()    
        
        self.logger.info(f"Wallet initialized: {self.__class__.__name__}")
        self.blossom_home_server = (
            blossom_home_server
            or os.getenv("BLOSSOM_HOME_SERVER")
            or DEFAULT_BLOSSOM_HOME_SERVER
        )
        self.blossom_xfer_server = (
            blossom_xfer_server
            or os.getenv("BLOSSOM_XFER_SERVER")
            or DEFAULT_BLOSSOM_XFER_SERVER
        )
        if blossom_servers:
            self.blossom_servers = blossom_servers
        else:
            env_servers = os.getenv("BLOSSOM_SERVERS", "").strip()
            if env_servers:
                parsed_servers: List[str] = []
                try:
                    loaded = json.loads(env_servers)
                    if isinstance(loaded, list):
                        parsed_servers = [str(s).strip() for s in loaded if str(s).strip()]
                except Exception:
                    parsed_servers = []
                if not parsed_servers:
                    parsed_servers = [s.strip() for s in env_servers.split(",") if s.strip()]
                self.blossom_servers = parsed_servers
            else:
                self.blossom_servers = [self.blossom_home_server]
        if self.blossom_home_server not in self.blossom_servers:
            self.blossom_servers.insert(0, self.blossom_home_server)

        if nsec.startswith('nsec'):
            self.k = Keys(priv_k=nsec)
            self.pubkey_bech32  =   self.k.public_key_bech32()
            self.pubkey_hex     =   self.k.public_key_hex()
            self.privkey_bech32 =   self.k.private_key_bech32()
            self.privkey_hex    =   self.k.private_key_hex()
            self.relays         =   relays
            self.public_relays  =   public_relays or []
            self.mints          =   [normalize_mint_url(each) for each in (mints or [DEFAULT_HOME_MINT])]
            self.home_mint      =   self.mints[0]
            self.safe_box_items = []
            self.proofs: List[Proof] = []
            self.balance: int = 0
            self.proof_events = proofEvents()
            self.proof_event_ids = []
            self.trusted_mints = {}
            self.trusted_entities = []
            self.home_relay = home_relay
            self.replicate = replicate
            self.wallet_config = None
            self.seed_phrase = None
            self.handle = generate_name_from_hex(self.pubkey_hex)
            access_key_digest.update(self.privkey_hex.encode())
            access_key_hash = access_key_digest.hexdigest()
            self.access_key = generate_access_key_from_hex(access_key_hash)

            self.wallet_reserved_records = {}
            self._lock_acquired_at: float | None = None
            self._lock_owner: str | None = None
        else:
            return "Need nsec" 

        
 
        
        # asyncio.run(self._load_proofs())
        

        
        return None

    def _build_discovery_relays(self) -> List[str]:
        relay_pool: List[str] = []
        for each in [self.home_relay] + list(self.relays or []) + list(self.public_relays or []):
            if each and each not in relay_pool:
                relay_pool.append(each)
        return relay_pool

    def _build_zap_request_relays(self) -> List[str]:
        relay_pool: List[str] = []
        for each in [self.home_relay] + list(self.public_relays or []):
            if each and each not in relay_pool:
                relay_pool.append(each)
        return relay_pool

    async def replicate_to_relay(
        self,
        target_relay: str,
        source_relay: str | None = None,
        kinds: List[int] | None = None,
        limit: int = 1024,
    ) -> Dict[str, Any]:
        """Copy this wallet's signed events from one relay to another.

        Replication preserves original event IDs and signatures. It is intended
        for migration or backup when a home relay becomes unreliable,
        unavailable, or adversarial.
        """

        source = self._normalize_relays([source_relay or self.home_relay])
        target = self._normalize_relays([target_relay])
        if not source:
            raise ValueError("source relay is required")
        if not target:
            raise ValueError("target relay is required")

        event_kinds = kinds or [
            0,
            5,
            17375,
            37375,
            37376,
            7375,
            30000,
            30001,
            30002,
        ]
        normalized_kinds = sorted({int(each) for each in event_kinds})
        if not normalized_kinds:
            raise ValueError("at least one event kind is required")

        query_limit = int(limit)
        if query_limit <= 0:
            raise ValueError("limit must be greater than zero")

        query_filter = [{
            "limit": query_limit,
            "authors": [self.pubkey_hex],
            "kinds": normalized_kinds,
        }]

        async with ClientPool(source) as c:
            events: List[Event] = await c.query(query_filter)

        seen_event_ids: set[str] = set()
        unique_events: List[Event] = []
        for event in events:
            event_id = str(event.id)
            if event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)
            unique_events.append(event)

        async with ClientPool(target) as c:
            for event in unique_events:
                c.publish(event)
            await asyncio.sleep(0.3)

        async with ClientPool(target) as c:
            target_events: List[Event] = await c.query(query_filter)
        target_event_ids = {str(each.id) for each in target_events}
        missing_event_ids = [
            str(each.id)
            for each in unique_events
            if str(each.id) not in target_event_ids
        ]
        source_may_be_truncated = len(events) >= query_limit

        by_kind: Dict[str, int] = {}
        for event in unique_events:
            kind_key = str(event.kind)
            by_kind[kind_key] = by_kind.get(kind_key, 0) + 1

        return {
            "status": (
                "OK"
                if not missing_event_ids and not source_may_be_truncated
                else "PARTIAL"
            ),
            "source_relay": source[0],
            "target_relay": target[0],
            "kinds": normalized_kinds,
            "queried": len(events),
            "replicated": len(unique_events),
            "verified": not missing_event_ids,
            "missing_event_ids": missing_event_ids,
            "source_may_be_truncated": source_may_be_truncated,
            "by_kind": by_kind,
            "event_ids": [str(event.id) for event in unique_events],
        }

    async def _query_authored_events_for_burn(
        self,
        relays: List[str],
        kinds: List[int],
        limit: int = RECORD_LIMIT,
    ) -> List[Event]:
        query_filter = [{
            "limit": int(limit),
            "authors": [self.pubkey_hex],
            "kinds": sorted({int(each) for each in kinds}),
        }]
        async with ClientPool(relays) as c:
            events: List[Event] = await c.query(query_filter)

        seen: set[str] = set()
        unique_events: List[Event] = []
        for event in events:
            event_id = str(event.id)
            if event_id in seen:
                continue
            seen.add(event_id)
            unique_events.append(event)
        return unique_events

    async def _max_payable_lightning_amount(
        self,
        lnaddress: str,
        balance: int,
        comment: str,
    ) -> Dict[str, Any]:
        """Return the largest Lightning payment amount that fits mint fees.

        Cashu Lightning payments require paying both the recipient amount and
        the mint's melt fee reserve from one spendable keyset. When a caller
        wants to sweep a wallet, the intuitive request is "send everything",
        but the actual Lightning amount often needs to be reduced by the fee
        reserve. This helper quotes the recipient invoice and mint melt before
        mutating proofs, then returns the largest amount that can be paid.
        """

        if balance <= 0:
            raise ValueError("wallet balance must be positive")

        _keyset_proofs, keyset_amounts = self._proofs_by_keyset()
        if not keyset_amounts:
            raise ValueError("wallet has no spendable keysets")

        headers = {"Content-Type": "application/json"}
        timeout = httpx.Timeout(30.0, connect=5.0)
        candidate = min(int(balance), max(int(each) for each in keyset_amounts.values()))
        last_error: str | None = None

        while candidate > 0:
            try:
                callback, safebox, nonce = lightning_address_pay(candidate, lnaddress, comment=comment)
            except Exception as exc:
                raise RuntimeError(f"Lightning address lookup failed for {lnaddress}: {exc}") from exc

            if not isinstance(callback, dict):
                raise RuntimeError(f"Lightning address callback returned an invalid response for {lnaddress}")
            if callback.get("status") == "ERROR":
                raise RuntimeError(callback.get("reason") or f"Lightning address lookup failed for {lnaddress}")
            if safebox:
                return {
                    "amount": candidate,
                    "fee_reserve": 0,
                    "total": candidate,
                    "mode": "safebox",
                    "nonce": nonce,
                }

            pr = callback.get("pr")
            if not pr:
                raise RuntimeError(f"Lightning address callback did not return an invoice for {lnaddress}")

            next_candidates: List[int] = []
            for keyset, available in sorted(keyset_amounts.items(), key=lambda item: int(item[1]), reverse=True):
                available = int(available)
                if available < candidate:
                    continue
                mint = self.known_mints.get(keyset)
                if not mint:
                    continue

                melt_quote_url = f"{mint}/v1/melt/quote/bolt11"
                data_to_send = {"request": pr, "unit": "sat"}
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(url=melt_quote_url, json=data_to_send, headers=headers)
                        response.raise_for_status()
                        post_melt_response = PostMeltQuoteResponse(**response.json())
                except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
                    last_error = f"{mint}: {exc}"
                    continue

                fee_reserve = int(post_melt_response.fee_reserve)
                total_needed = candidate + fee_reserve
                if total_needed <= available:
                    return {
                        "amount": candidate,
                        "fee_reserve": fee_reserve,
                        "total": total_needed,
                        "mode": "lightning",
                        "keyset": keyset,
                        "mint": mint,
                        "quote": post_melt_response.quote,
                    }
                next_candidates.append(max(0, available - fee_reserve))

            smaller_candidates = [each for each in next_candidates if 0 < each < candidate]
            if smaller_candidates:
                candidate = max(smaller_candidates)
            else:
                candidate -= 1

        detail = f"; last quote error: {last_error}" if last_error else ""
        raise ValueError(
            f"no payable Lightning amount fits wallet balance {balance} sats and mint fee reserve{detail}"
        )

    async def burn_wallet(
        self,
        send_to: str | None = None,
        send_relay: str | None = None,
        pay_to: str | None = None,
        pay_amount: int | None = None,
        relays: List[str] | None = None,
        kinds: List[int] | None = None,
        allow_funded: bool = False,
        limit: int = RECORD_LIMIT,
    ) -> Dict[str, Any]:
        """Burn this wallet's relay-backed data by publishing NIP-09 deletions.

        If `send_to` is provided and the wallet has a spendable balance, the
        balance is first sent as a kind 7378 ecash transfer. If `pay_to` is
        provided, funds are paid to a Lightning address using the wallet's mint
        melt flow. NIP-09 deletion is advisory: relays and clients ultimately
        decide whether matching events are hidden, retained, or
        garbage-collected.
        """

        if send_to and pay_to:
            raise ValueError("provide only one of send_to or pay_to")

        burn_relays = self._normalize_relays(relays or [self.home_relay])
        if not burn_relays:
            raise ValueError("at least one burn relay is required")

        burn_kinds = sorted({int(each) for each in (kinds or BURN_DEFAULT_KINDS)})
        if not burn_kinds:
            raise ValueError("at least one burn kind is required")

        balance_before = int(self.get_balance())
        sweep_result: Dict[str, Any] | None = None
        payment_result: Dict[str, Any] | None = None
        if balance_before > 0:
            if send_to:
                sweep_result = await self.send_ecash_transfer(
                    amount=balance_before,
                    recipient=send_to,
                    relay=send_relay,
                    comment="acorn wallet burn sweep",
                )
                # Refresh local state after issuing the sweep token.
                with contextlib.suppress(Exception):
                    await self.load_data()
            elif pay_to:
                lightning_sweep_quote: Dict[str, Any] | None = None
                if pay_amount is None:
                    lightning_sweep_quote = await self._max_payable_lightning_amount(
                        lnaddress=pay_to,
                        balance=balance_before,
                        comment="acorn wallet burn lightning sweep",
                    )
                    amount_to_pay = int(lightning_sweep_quote["amount"])
                else:
                    amount_to_pay = int(pay_amount)
                if amount_to_pay <= 0:
                    raise ValueError("pay_amount must be positive")
                if amount_to_pay > balance_before:
                    raise ValueError(
                        f"pay_amount exceeds wallet balance: pay_amount={amount_to_pay}, balance={balance_before}"
                    )
                msg_out, fees = await self.pay_multi(
                    amount=amount_to_pay,
                    lnaddress=pay_to,
                    comment="acorn wallet burn lightning sweep",
                )
                payment_result = {
                    "status": "OK",
                    "pay_to": pay_to,
                    "amount": amount_to_pay,
                    "unit": "sat",
                    "fees": fees,
                    "auto_amount": pay_amount is None,
                    "balance_before": balance_before,
                    "message": msg_out,
                }
                if lightning_sweep_quote:
                    payment_result["estimated_fees"] = lightning_sweep_quote.get("fee_reserve")
                    payment_result["estimated_total"] = lightning_sweep_quote.get("total")
                    payment_result["mint"] = lightning_sweep_quote.get("mint")
                    payment_result["mode"] = lightning_sweep_quote.get("mode")
                    payment_result["advisory"] = (
                        "Lightning sweep amount was automatically reduced, if needed, "
                        "so amount plus mint fee reserve fit the wallet's spendable proofs."
                    )
                else:
                    payment_result["advisory"] = (
                        "Explicit Lightning pay amounts can fail if amount plus mint fee reserve "
                        "exceeds the wallet's spendable proofs."
                    )
                with contextlib.suppress(Exception):
                    await self.load_data()
            elif not allow_funded:
                raise ValueError(
                    "wallet has a positive balance; provide send_to, pay_to, or set allow_funded=True"
                )

        events = await self._query_authored_events_for_burn(
            relays=burn_relays,
            kinds=burn_kinds,
            limit=limit,
        )
        event_ids = [str(event.id) for event in events]
        by_kind: Dict[str, int] = {}
        for event in events:
            kind_key = str(event.kind)
            by_kind[kind_key] = by_kind.get(kind_key, 0) + 1

        delete_request: Dict[str, Any] | None = None
        if event_ids:
            delete_request = await self.publish_deletion_request(
                event_ids=event_ids,
                kinds=burn_kinds,
                reason="burn acorn wallet data",
                relays=burn_relays,
            )

        balance_after = int(self.get_balance())
        return {
            "status": "OK",
            "pubkey": self.pubkey_hex,
            "npub": self.pubkey_bech32,
            "relays": burn_relays,
            "kinds": burn_kinds,
            "limit": int(limit),
            "balance_before": balance_before,
            "balance_after": balance_after,
            "sweep": sweep_result,
            "payment": payment_result,
            "matched": len(event_ids),
            "deleted": len(event_ids),
            "by_kind": by_kind,
            "event_ids": event_ids,
            "delete_event_id": delete_request.get("event_id") if delete_request else None,
            "delete_request": delete_request,
            "advisory": "NIP-09 deletion requests are advisory; relay retention behavior can vary.",
        }
   
    async def load_data(self, force_profile_creation: bool=False):
        self.logger.debug(f"load data. Force profile creation {force_profile_creation}")

        try:

          
            # wallet_config= await self.get_wallet_config()
            wallet_config=None
            if wallet_config:
                self.acorn_tags = wallet_config
            else:
                #FIXME get rid of this eventually
                wallet_info = await self.get_wallet_info(label="wallet")
                if wallet_info is None:
                    if force_profile_creation:
                        self.logger.info("op=load_data status=create_profile_on_missing_data relay=%s", self.home_relay)
                        await self.create_instance(keepkey=True)
                        await self._load_proofs()
                        return
                    raise RuntimeError(f"No wallet data found on {self.home_relay}")
                self.acorn_tags = json.loads(wallet_info)


            

            for each in self.acorn_tags:
                if each[0]== "balance":
                    self.balance = int(each[1])
                    self.unit = each[2]
                if each[0] == "mint":
                    self.home_mint = normalize_mint_url(each[1])
                    # print(f"home mint: {self.home_mint}")
                if each[0] == "name":
                    self.name = each[1]
                if each[0] == "local_currency":
                    self.local_currency = each[1]
                    # print(f"name: {self.name}")
                if each[0] == "owner":
                    self.owner = each[1]
                    # print(f"owner: {self.owner}")
                if each[0] == "privkey":                    
                    # print(f"privkey: {each[1]}")
                    # print(f"pubkey: {Keys(priv_k=each[1]).public_key_hex()}")
                    pass
                if each[0] == "seedphrase":
                    candidate_seed_phrase = each[1]
                    if seed_phrase_matches_nsec(candidate_seed_phrase, self.privkey_bech32):
                        self.seed_phrase = candidate_seed_phrase
                    else:
                        self.seed_phrase = None
                        self.logger.warning(
                            "op=load_data status=invalid_recovery_phrase "
                            "reason=phrase_does_not_match_active_key"
                        )
                if each[0] == "local_currency":
                    self.local_currency = each[1]
                if each[0] == "user_record":
                    self.user_records.append(each[1])  
                if each[0] == "latest_ecash":
                    self.latest_ecash = each[1] 

        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            # await self.set_wallet_info(label="wallet",label_info=json.dumps(self.acorn_tags))
            if force_profile_creation:
                self.logger.info("op=load_data status=create_profile_on_missing_data relay=%s", self.home_relay)
                await self.create_instance(keepkey=True)
                
            else:
                self.logger.warning("op=load_data status=failed relay=%s error=%s", self.home_relay, e)
                raise RuntimeError(f"No wallet data found on {self.home_relay}")


        await self._load_proofs()
        
        return
    
    async def set_owner_data(self, npub:str = None, local_currency=None):

        update_tags = []
        if npub ==None and local_currency== None:
            return
        if npub:            
            try:
                npub_obj = Keys(pub_k=npub)
                update_tags.append(["owner",npub])                
            except (ValueError, TypeError) as exc:
                raise ValueError("npub is not a valid format")
        if local_currency:
            update_tags.append(["local_currency",local_currency])
        
        await self.update_tags(update_tags)
        return "OK"

    def __repr__(self):
        out_str = json.dumps(self.wallet_reserved_records)

        return out_str
    
    def powers_of_2_sum(self, amount: int):
        powers = []
        while amount > 0:
            power = 1
            while power * 2 <= amount:
                power *= 2
            powers.append(power)
            amount -= power
        return sorted(powers)
    
    def create_profile(self, nostr_profile_create: bool=False, keepkey:bool=False):
        init_index = {}
        wallet_info = {}
        n_profile = {}
        seed_phrase = self.seed_phrase
        if keepkey==False:
            seed_phrase, generated_nsec = generate_seed_phrase_and_nsec()
            self.k = Keys(priv_k=generated_nsec)
            self.pubkey_bech32 = self.k.public_key_bech32()
            self.privkey_bech32 = self.k.private_key_bech32()
            self.pubkey_hex = self.k.public_key_hex()
            self.privkey_hex = self.k.private_key_hex()
            self.seed_phrase = seed_phrase
            

        
        local_name = generate_name_from_hex(self.pubkey_hex)
        hotel_name = hotel_names.get_hotel_name()
       
        # Create nprofile
        n_profile['pubkey'] = self.k.public_key_hex()
        n_profile['relay'] = [self.home_relay]
        n_profile_str = Entities.encode('nprofile', n_profile)
        self.logger.debug("op=create_profile status=nprofile_created nprofile=%s", n_profile_str)

        nostr_profile = nostrProfile(   name=local_name,
                                        display_name=local_name,
                                        about = f"Resident of {hotel_name}",
                                        picture=f"https://robohash.org/{local_name}/?set=set4",
                                        lud16= f"{local_name}@openbalance.app",
                                        website=f"https://njump.me/{self.pubkey_bech32}",
                                        nprofile=n_profile_str

                                         )
        if nostr_profile_create:
            out = asyncio.run(self._async_create_profile(nostr_profile))
            hello_msg = f"Hello World from {local_name}! #introductions"
            self.logger.info("op=create_profile status=hello_post msg=%s", hello_msg)
            asyncio.run(self._async_send_post(hello_msg))
            self.logger.debug("op=create_profile status=post_result result=%s", out)

        # init_index = "[{\"root\":\"init\"}]"
        init_index["root"] = local_name
        # self.set_index_info(json.dumps(init_index))
        asyncio.run(self.set_wallet_info(label="default", label_info=local_name))
        asyncio.run(self.set_wallet_info(label="profile", label_info=json.dumps(nostr_profile.model_dump())))
        
        self.wallet_config = WalletConfig(  kind_cashu = 7375,
                                            seed_phrase=seed_phrase)                
        asyncio.run(self.set_wallet_info(label="wallet_config", label_info=json.dumps(self.wallet_config.model_dump())))
        asyncio.run(self.set_wallet_info(label="mints", label_info=json.dumps(self.mints)))
        asyncio.run(self.set_wallet_info(label="relays", label_info=json.dumps(self.relays)))
        asyncio.run(self.set_wallet_info(label="quote", label_info='[]'))
        asyncio.run(self.set_wallet_info(label="index", label_info='{}'))
        asyncio.run(self.set_wallet_info(label="last_dm", label_info='0'))
        asyncio.run(self.set_wallet_info(label="user_records", label_info='[]'))
        asyncio.run(self.set_wallet_info(label="payment_request", label_info='[]'))

        self._load_record_events()
        
 
        return self.k.private_key_bech32()

    async def _async_create_profile(self, nostr_profile: nostrProfile, replicate_relays: List[str]=None):
        out_msg = "ok"
        try:
            profile_payload = nostr_profile.model_dump(mode="json")
            await self._publish_kind0_event(profile_payload=profile_payload, relays=replicate_relays)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.logger.warning("op=create_profile status=publish_failed error=%s", exc)
            out_msg = "error"
        return out_msg

    async def _publish_kind0_event(self, profile_payload: Dict[str, Any], relays: List[str] | None = None) -> str:
        if relays:
            write_relays = relays
        else:
            write_relays = []
            for each in [self.home_relay] + list(self.public_relays or []):
                if each and each not in write_relays:
                    write_relays.append(each)
        if not write_relays:
            raise RuntimeError("No relays configured for kind0 publish")

        profile_content = json.dumps(profile_payload)
        async with ClientPool(write_relays) as c:
            n_msg = Event(
                kind=0,
                content=profile_content,
                pub_key=self.pubkey_hex,
            )
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            self.logger.debug("op=publish_kind0 status=published event_id=%s relays=%s", n_msg.id, write_relays)
            return str(n_msg.id)

    async def publish_kind0_metadata(
        self,
        name: str | None = None,
        about: str | None = None,
        picture: str | None = None,
        extra_fields: Dict[str, Any] | None = None,
        relays: List[str] | None = None,
        persist_profile_record: bool = True,
    ) -> Dict[str, Any]:
        profile_payload: Dict[str, Any] = {}
        try:
            profile_raw = await self.get_wallet_info(label="profile")
            if profile_raw:
                profile_payload = json.loads(profile_raw)
        except Exception:
            profile_payload = {}

        if not profile_payload:
            profile_payload = nostrProfile().model_dump(mode="json")

        if name is not None:
            profile_payload["name"] = name
            if not profile_payload.get("display_name"):
                profile_payload["display_name"] = name
        if about is not None:
            profile_payload["about"] = about
        if picture is not None:
            profile_payload["picture"] = picture

        if extra_fields:
            for key, value in extra_fields.items():
                if key:
                    profile_payload[str(key)] = value

        event_id = await self._publish_kind0_event(profile_payload=profile_payload, relays=relays)

        if persist_profile_record:
            await self.set_wallet_info(label="profile", label_info=json.dumps(profile_payload))

        result_relays: List[str] = []
        for each in (relays if relays else [self.home_relay] + list(self.public_relays or [])):
            if each and each not in result_relays:
                result_relays.append(each)

        return {
            "status": "OK",
            "event_id": event_id,
            "profile": profile_payload,
            "relays": result_relays,
        }

    async def create_instance(
        self,
        keepkey: bool = False,
        name: str = "wallet",
        seed_phrase: str | None = None,
        retain_seed_phrase: bool = True,
    ):
        out_msg = "This is another instance"
        access_key_digest = hashlib.sha256()
        if keepkey==False:
            if seed_phrase is None:
                seed_phrase, generated_nsec = generate_seed_phrase_and_nsec()
            else:
                generated_nsec = recover_nsec_from_seed(seed_phrase)
            self.k = Keys(priv_k=generated_nsec)
            self.pubkey_bech32 = self.k.public_key_bech32()
            self.privkey_bech32 = self.k.private_key_bech32()
            self.pubkey_hex = self.k.public_key_hex()
            self.privkey_hex = self.k.private_key_hex()
            
            nut_key = Keys()
            self.seed_phrase = seed_phrase
            self.acorn_tags = [ [ "balance", "0", "sat" ],
                                [ "privkey", nut_key.private_key_hex() ],
                                [ "mint", self.mints[0]],
                                [ "name", name ],
                                ["owner",self.pubkey_bech32],
                                ["local_currency", self.local_currency]
                            ]
            if retain_seed_phrase:
                self.acorn_tags.insert(4, ["seedphrase", seed_phrase])
            
            self.handle = generate_name_from_hex(self.pubkey_hex)
            access_key_digest.update(self.privkey_hex.encode())
            access_key_hash = access_key_digest.hexdigest()
            self.access_key = generate_access_key_from_hex(access_key_hash)
            self.logger.debug("op=create_instance status=wallet_metadata_created npub=%s", self.pubkey_bech32)
            await self.set_wallet_info(label=name,label_info=json.dumps(self.acorn_tags))
            # await self.set_wallet_config()
        else:
            #keepkey = true # we already have a private key
            # need to check if a profile exists, if not create one
            try:
            
                wallet_config= await self.get_wallet_config()
                if  wallet_config:
                    return self.privkey_bech32
                else:
                    nut_key = Keys()
                    self.acorn_tags = [ [ "balance", "0", "sat" ],
                                [ "privkey", nut_key.private_key_hex() ], 
                                [ "mint", self.mints[0]],
                                [ "name", name ],
                                ["owner",self.pubkey_bech32],
                                ["local_currency", self.local_currency]
                            ]
                    self.handle = generate_name_from_hex(self.pubkey_hex)
                    access_key_digest.update(self.privkey_hex.encode())
                    access_key_hash = access_key_digest.hexdigest()
                    self.access_key = generate_access_key_from_hex(access_key_hash)
                    self.seed_phrase = None
                    self.logger.debug(
                        "op=create_instance status=imported_key_metadata_created npub=%s",
                        self.pubkey_bech32,
                    )
                    await self.set_wallet_info(label=name,label_info=json.dumps(self.acorn_tags))
                    


            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
                self.logger.warning("op=create_instance status=no_profile error=%s", e)

            pass
        return self.privkey_bech32

    def get_profile(self, name="wallet"):
        mints = []
        lock_pubkey = None
        try:
            for each in self.acorn_tags:
                if each[0] == "balance":
                    self.balance = int(each[1])
                    self.unit = each[2]
                elif each[0] == "privkey":
                    lock_pubkey = Keys(each[1]).public_key_hex()
                elif each[0] == "mint":
                    mints.append(each[1])
                elif each[0] == "name":
                    name = each[1]

            out_string = f"""   \nnpub: {self.pubkey_bech32}
                                \npubhex: {self.pubkey_hex}  
                                \nhandle: {self.handle}   
                                \nowner: {self.owner}                     
                                \nlock pubkey: {lock_pubkey}
                                \nlocal currency: {self.local_currency}
                                \nhome mints: {mints}
                                \nknown mints: {self.known_mints}
                                \nbalance: {self.balance} {self.unit}
                                \nhome relay: {self.home_relay}
                                \nuser records: {self.user_records}
                                \nname: {name}
                                \n{"*"*75}

            """
        except (ValueError, TypeError, KeyError) as exc:
            self.logger.warning("op=get_profile status=missing_profile error=%s", exc)
            raise RuntimeError("No profile on relay")
        return out_string
    
    def get_instance(self):
        pass
        return "this is the instance"
    
    def get_balance(self):
        
        balance_tally = 0
        for each in self.proofs:                
            balance_tally += each.amount
            self.balance = balance_tally
        return self.balance

    async def get_current_balance(self) -> int:
        await self.load_data()
        return self.get_balance()
    

    async def listen_for_record(self, record_kind:int=37375, since:int = None, reverse: bool=False, relays:List=None):
        # Listen for a record and return it
        self.logger.info("op=listen_for_record status=start kind=%s", record_kind)

        def incoming_handler(the_client: Client, sub_id: str, evt: Event):
            self.logger.debug("op=listen_for_record status=event sub_id=%s event_id=%s", sub_id, evt.id)
            return

        url = relays[0]
        c = ClientPool(url)
        asyncio.create_task(c.run())
   
        await c.wait_connect()

        c.subscribe(
        handlers=incoming_handler,
        filters={
            'limit': 1024,
            'kinds': [record_kind],
            '#p': [self.pubkey_hex]
            
        }
        )
        while True:
            self.logger.debug("op=listen_for_record status=waiting kind=%s relay=%s", record_kind, url)
            await asyncio.sleep(3)
        return

    async def listen_for_record_sub(
    self,
    record_kind: int = 37375,
    since: int | None = None,
    reverse: bool = False,
    relays: List[str] | None = None,
    timeout: int = 60
    ):
        my_gift = KindOtherGiftWrap(BasicKeySigner(self.k), kind_gift_wrap=record_kind)
        self.logger.info("op=listen_for_record_sub status=start kind=%s", record_kind)

        relays_to_use = relays if relays else [self.home_relay]
        if not relays_to_use:
            self.logger.warning("op=listen_for_record_sub status=no_relays kind=%s", record_kind)
            return None, None

        loop = asyncio.get_running_loop()
        record_future = loop.create_future()

        def incoming_handler(the_client: ClientPool, sub_id: str, evt: Event):
            if not record_future.done():
                self.logger.debug("op=listen_for_record_sub status=received event_id=%s", evt.id)
                record_future.set_result(evt)

        client = ClientPool(relays_to_use)

        # Run client in background
        client_task = asyncio.create_task(client.run())
        sub_id = secrets.token_hex(4)
        connect_timeout = max(3, min(timeout, 12))
        try:
            await asyncio.wait_for(client.wait_connect(), timeout=connect_timeout)
        except asyncio.TimeoutError:
            self.logger.warning(
                "op=listen_for_record_sub status=connect_timeout kind=%s timeout=%s relays=%s",
                record_kind,
                connect_timeout,
                relays_to_use,
            )
            return None, None
        except Exception as exc:
            self.logger.warning(
                "op=listen_for_record_sub status=connect_failed kind=%s error=%s relays=%s",
                record_kind,
                exc,
                relays_to_use,
            )
            return None, None

        record_filter = {
            "limit": 1,
            "kinds": [record_kind],
            "#p": [self.pubkey_hex],
        }
        if since is not None:
            record_filter["since"] = since

        client.subscribe(
            sub_id=sub_id,
            handlers=incoming_handler,
            filters=record_filter,
        )

        try:
            # Wait until first record arrives
            evt = await asyncio.wait_for(record_future, timeout=timeout)
            unwrapped_event = await my_gift.unwrap(evt)
            nauth_split = unwrapped_event.content.split(':')
            nauth = nauth_split[0]
            if len(nauth_split)>1:
                nembed = nauth_split[1]
            else:
                nembed = None  
               
            return nauth, nembed
        except (asyncio.TimeoutError, ValueError, TypeError) as exc:
            self.logger.debug("op=listen_for_record_sub status=timeout_or_invalid kind=%s error=%s", record_kind, exc)
            return None, None

        finally:
            # Clean shutdown no matter what
            self.logger.debug("op=listen_for_record_sub status=shutdown")
            # await client.unsubscribe(sub_id=sub_id)
            client_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await client_task
    
    async def get_user_records(self, record_kind:int=37375, since:int = None, reverse: bool=False, relays:List=None)->List[Any]:

        events_out = []
        my_enc = NIP44Encrypt(self.k)
        my_gift = KindOtherGiftWrap(BasicKeySigner(self.k), kind_gift_wrap=record_kind)
        m = hashlib.sha256()
        m.update(self.privkey_hex.encode())
        # m.update(label.encode())
        # label_hash = m.digest().hex()
        decrypt_content = None

        # Normalize relay inputs to avoid runtime failures from malformed config/env values.
        # Accepts:
        # - None -> [home_relay]
        # - "wss://a,wss://b" -> ["wss://a","wss://b"]
        # - ["relay.getsafebox.app", "wss://relay.damus.io"] -> normalized wss urls
        relays_to_use: List[str] = []
        if relays is None:
            relays_to_use = [self.home_relay] if self.home_relay else []
        elif isinstance(relays, str):
            relays_to_use = [each.strip() for each in relays.split(",") if each and each.strip()]
        elif isinstance(relays, (list, tuple, set)):
            relays_to_use = [str(each).strip() for each in relays if each and str(each).strip()]
        else:
            raise ValueError("relays must be None, comma-separated string, or list-like")

        normalized_relays: List[str] = []
        for each in relays_to_use:
            if each.startswith("wss://") or each.startswith("ws://"):
                normalized_relays.append(each)
            else:
                normalized_relays.append(f"wss://{each}")
        relays_to_use = normalized_relays
        if not relays_to_use:
            if self.home_relay:
                relays_to_use = [self.home_relay]
            else:
                raise ValueError("No relays configured for get_user_records")

        # handle records that are coming in via giftwraps
        # 1059 are regular DMs
        # 1060 are health records
        # 1061 are health authentication messages
        # 1062 are shared notes
        # 1063 are official docs and credentials
        # 1400-1499: regular events
        # 21400-21400: emphemeral events

        if record_kind in [1059,1060,1061,1062,1063,21059,21060,21061,21062,21063] or \
            (1400 <= record_kind <= 1499) or (21400 <= record_kind <= 21499):
            
           if since:        
                FILTER = [{
                'limit': RECORD_LIMIT, 
                '#p'  :  [self.pubkey_hex],              
                'kinds': [record_kind],
                'since': since
                
                }]
           else:
                FILTER = [{
                'limit': RECORD_LIMIT, 
                '#p'  :  [self.pubkey_hex],              
                'kinds': [record_kind]
                
                }]
               
        else:
                record_filter = {
                'limit': RECORD_LIMIT,
                'authors': [self.pubkey_hex],
                'kinds': [record_kind]   
                }
                if since is not None:
                    record_filter["since"] = int(since)
                FILTER = [record_filter]

        # print(f"kind: {record_kind} relays to use: {relays_to_use}")
        self.logger.debug(
            "op=get_user_records status=query kind=%s relays=%s filters=%s",
            record_kind,
            len(relays_to_use),
            len(FILTER),
        )
        events = []
        try:
            async with ClientPool(relays_to_use) as c:
                events = await c.query(FILTER)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.logger.warning(
                "op=get_user_records status=query_failed kind=%s relays=%s error=%s",
                record_kind,
                relays_to_use,
                exc,
            )
            return []

        if 30000 <= int(record_kind) < 40000:
            events = self._canonical_record_events(events)
            internal_labels = set(INTERNAL_RECORD_LABELS)
            if getattr(self, "name", None):
                internal_labels.add(str(self.name))
            internal_hashes = {
                self._record_label_hash(label)
                for label in internal_labels
            }
            events = [
                each
                for each in events
                if self._record_event_tag(each, "d") not in internal_hashes
            ]
        else:
            deduplicated: dict[str, Event] = {
                str(each.id): each for each in events
            }
            events = list(deduplicated.values())
            events.sort(
                key=lambda each: (
                    -self._event_timestamp(each),
                    str(each.id),
                )
            )

        each: Event
        for each in events:
            
            # check to see if record originates from elsewhere
            if record_kind in [1059,1060,1061,1062,1063,21059,21060,21061,21062,21063] or \
                (1400 <= record_kind <= 1499) or (21400 <= record_kind <= 21499):
                # print(f"need to  unwrap {type(each.content)} {each.content} ")
                try:
                    pass
                    # print(f"content to decrypt: {each.content}")
                    # decrypt_content = my_enc.decrypt(each.content,self.pubkey_hex)
                    # print(f"decrypt content {decrypt_content}")

                    unwrapped_event = await my_gift.unwrap(each)
                    # print(f"unwrapped event content: {unwrapped_event.content}")
                    try:
                        parsed_record = json.loads(unwrapped_event.content)
                        parsed_record['created_at'] = unwrapped_event.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        parsed_record['id']=unwrapped_event.id
                        parsed_record['sender']=unwrapped_event.pub_key
                        
                        

                    except (json.JSONDecodeError, TypeError) as exc:
                        parsed_record = {   "tag": ["message"],
                                            "type": "dm",
                                            "created_at": unwrapped_event.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                                            "payload":unwrapped_event.content,
                                            "id": unwrapped_event.id,
                                            "timestamp": int(unwrapped_event.created_at.timestamp())
                                            }

                    
                    parsed_record['presenter'] = unwrapped_event.pub_key
                    parsed_record['sender'] = unwrapped_event.pub_key
                    parsed_record['social_name'] = None
                    parsed_record['timestamp'] = int(unwrapped_event.created_at.timestamp())

                except (ValueError, TypeError, RuntimeError) as e:
                    self.logger.warning("op=get_user_records status=unwrap_failed kind=%s event=%s error=%s", record_kind, each.id, e)
                    continue
            
                #Add in sender detais
                if record_kind in [1059]:
                    try:
                        social_profile = await self.get_social_profile(
                            npub=unwrapped_event.pub_key,
                            relays=relays_to_use,
                        )
                        parsed_record['social_name'] = social_profile.get('display_name', None)
                    except Exception as exc:
                        self.logger.debug(
                            "op=get_user_records status=social_profile_lookup_failed sender=%s error=%s",
                            unwrapped_event.pub_key,
                            exc,
                        )
                        parsed_record['social_name'] = None
                else:
                    parsed_record['social_name'] = None


            else: # otherwise record is self-originating
                try:
                    decrypt_content = my_enc.decrypt(each.content, self.pubkey_hex)
                except (ValueError, TypeError, RuntimeError) as exc:
                    # Try Gift Unwrapping
                    try:
                        decrypt_event = my_enc.decrypt_event(each)
                        decrypt_content = decrypt_event.content
                    except Exception as fallback_exc:
                        self.logger.warning(
                            "op=get_user_records status=decrypt_failed "
                            "event=%s error=%s fallback_error=%s",
                            each.id,
                            exc,
                            fallback_exc,
                        )
                        continue
            
                try:
                    parsed_record = json.loads(decrypt_content)
                except (json.JSONDecodeError, TypeError) as exc:
                    #It's just a raw string stored - map into the fields    
                    parsed_record = {}           
                    parsed_record['payload'] = decrypt_content
                    #add the extra fields
                    parsed_record['created_at'] = each.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    parsed_record['id'] = each.id
                    parsed_record['presenter'] = self.pubkey_hex
                    parsed_record['sender'] = each.pub_key
                    parsed_record['timestamp'] = int(each.created_at.timestamp())

                # check for special wallet record which is a list
                if isinstance(parsed_record,list):
                    #FIXME not sure if in a list
                    pass
                else:
                    #FIXME - I think this logic is in the wrong place
                    parsed_record['created_at'] = each.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    parsed_record['id'] = each.id
                    parsed_record['presenter'] = self.pubkey_hex
                    parsed_record['sender'] = each.pub_key
                    parsed_record['timestamp'] = int(each.created_at.timestamp())

            # Normalize structured direct messages that are valid JSON but are not
            # wrapped in the older {"payload": ...} record envelope.
            if isinstance(parsed_record, dict) and "payload" not in parsed_record:
                payload_copy = dict(parsed_record)
                parsed_record["payload"] = payload_copy

            # Convert payload to json
            # See if payload is in stringifed json and convert
                    
            if isinstance(parsed_record, dict) and "payload" in parsed_record:
                try:
                    payload_obj = json.loads(parsed_record["payload"])
                    parsed_record["payload"] = payload_obj
                except (json.JSONDecodeError, TypeError) as exc:
                    self.logger.debug(
                        "Payload is not JSON for event_id=%s",
                        parsed_record.get("id", "unknown"),
                    )
            else:
                self.logger.debug(
                    "Skipping payload JSON parse for record_type=%s",
                    type(parsed_record).__name__,
                )

            #check to see if wallet record and skip
            if isinstance(parsed_record,list):
                pass
            else:
                
                #Inspect Payload and decide what to show
                payload_value = parsed_record.get("payload")
                if isinstance(payload_value, dict):
                    if "content" in payload_value:
                        parsed_record["content"] = payload_value["content"]
                    elif "type" in payload_value:
                        parsed_record["content"] = str(payload_value.get("type") or "structured_dm")
                    else:
                        parsed_record["content"] = json.dumps(payload_value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                else:
                    # string so just show string
                    parsed_record["content"] = payload_value
                    

                
                events_out.append(parsed_record)
              
        
        if events_out:
            events_out.sort(key=lambda r: int(r.get("timestamp", 0)), reverse=reverse)
        return events_out

    async def get_user_record_labels(
        self,
        record_kind: int = 37375,
        since: int = None,
        reverse: bool = False,
        relays: List = None,
    ) -> List[str]:
        """Return only user record labels for the requested record kind."""

        records = await self.get_user_records(
            record_kind=record_kind,
            since=since,
            reverse=reverse,
            relays=relays,
        )
        labels: List[str] = []
        for each in records:
            tag = each.get("tag") if isinstance(each, dict) else None
            if isinstance(tag, list) and tag:
                labels.append(str(tag[0]))
            elif isinstance(tag, str):
                labels.append(tag)
        return labels

    async def set_public_relays(self, relays: List[str]) -> List[str]:
        """Store preferred public relays as an encrypted reserved record."""

        normalized = self._normalize_relays(relays)
        await self.set_wallet_info("public_relays", json.dumps(normalized))
        self.wallet_reserved_records["public_relays"] = json.dumps(normalized)
        self.public_relays = normalized
        return normalized

    async def get_public_relays(self) -> List[str]:
        """Return preferred public relays from reserved record or instance config."""

        configured = self.wallet_reserved_records.get("public_relays")
        if not configured:
            configured = await self.get_wallet_info("public_relays")
            if configured:
                self.wallet_reserved_records["public_relays"] = configured
        if configured:
            try:
                parsed = json.loads(configured)
                if isinstance(parsed, list):
                    return self._normalize_relays(parsed)
            except (json.JSONDecodeError, TypeError):
                if isinstance(configured, str):
                    return self._normalize_relays([each for each in configured.split(",") if each.strip()])
        return self._normalize_relays(self.public_relays or [])

    def _normalize_relays(self, relays: List[str]) -> List[str]:
        normalized: List[str] = []
        for each in relays or []:
            relay = str(each).strip()
            if not relay:
                continue
            if not relay.startswith(("wss://", "ws://")):
                relay = f"wss://{relay}"
            if relay not in normalized:
                normalized.append(relay)
        return normalized


    async def _async_query_client_profile(self, filter: List[dict]): 
    # does a one off query to relay prints the events and exits
        json_obj = {}
        # print("are we here today", self.relays)
        async with ClientPool([self.home_relay]+self.relays) as c:        
            events = await c.query(filter)
        try:    
            json_str = events[0].content
            # print("json_str", json_str)
            # json_obj = json.loads(json_str)
            json_obj = json.loads(json_str)
        except (IndexError, json.JSONDecodeError, TypeError) as exc:
            self.logger.debug("op=query_client_profile status=missing_or_invalid error=%s", exc)
            {"staus": "could not access profile"}
            pass
       
        # print("json_obj", json_obj)
        
        return json_str
        
    def replicate_safebox(self, replicate_relays: List[str] | None = None):
        
        self.logger.info("op=replicate_safebox status=start relays=%s", replicate_relays)

        FILTER = [{
            'limit': 1,
            'authors': [self.pubkey_hex],
            'kinds': [0]
        }]
        
        async def _async_replicate_safebox():
            try:
                profile = await self._async_query_client_profile(FILTER)
                profile_obj = nostrProfile(**json.loads(profile))
                self.logger.debug("op=replicate_safebox status=profile_loaded")
                await self._async_create_profile(profile_obj, replicate_relays=replicate_relays)
            except (ValueError, TypeError, IndexError, json.JSONDecodeError) as exc:
                self.logger.warning("op=replicate_safebox status=no_profile error=%s", exc)
                return "No profile found!"

            await self.set_wallet_info(label="test", label_info="test record booga", replicate_relays=replicate_relays)
            # replicate the reserved records

            profile = await self.get_wallet_info(label="profile")
            self.logger.debug("op=replicate_safebox status=replicate_profile")
            await self.set_wallet_info(label="profile", label_info=profile, replicate_relays=replicate_relays)

            await self.set_wallet_info(label="home_relay", label_info=json.dumps(self.home_relay), replicate_relays=replicate_relays)

            default = await self.get_wallet_info(label="default")
            await self.set_wallet_info(label="default", label_info=default, replicate_relays=replicate_relays)

            wallet_config = await self.get_wallet_info(label="wallet_config")
            await self.set_wallet_info(label="wallet_config", label_info=wallet_config, replicate_relays=replicate_relays)
            
            mints = await self.get_wallet_info(label="mints")
            await self.set_wallet_info(label="mints", label_info=mints,replicate_relays=replicate_relays)
            
            read_relays = await self.get_wallet_info(label="relays")
            await self.set_wallet_info(label="relays", label_info=read_relays, replicate_relays=replicate_relays)
            
            trusted_mints = await self.get_wallet_info(label="trusted_mints")
            self.logger.debug("op=replicate_safebox status=trusted_mints")
            await self.set_wallet_info(label="trusted_mints", label_info=json.dumps(self.trusted_mints), replicate_relays=replicate_relays)
            
            quote = await self.get_wallet_info(label="quote")
            self.logger.debug("op=replicate_safebox status=quote")
            await self.set_wallet_info(label="quote", label_info=quote,replicate_relays=replicate_relays)
            
            index = await self.get_wallet_info(label="index")
            self.logger.debug("op=replicate_safebox status=index")
            await self.set_wallet_info(label="index", label_info=index, replicate_relays=replicate_relays)
            
            last_dm = await self.get_wallet_info(label="last_dm")
            self.logger.debug("op=replicate_safebox status=last_dm")
            await self.set_wallet_info(label="last_dm", label_info=last_dm, replicate_relays=replicate_relays)
            
            self.logger.debug("op=replicate_safebox status=proofs count=%s", len(self.proofs))
            await self.add_proofs_obj(self.proofs, replicate_relays=replicate_relays)
            return profile

        return asyncio.run(_async_replicate_safebox())
    
    async def _async_store_event(self, event_content_str:str, event_kind: int, relays: List[str]):

        async with ClientPool(relays) as c:
      
            self.logger.debug("op=store_event status=publish kind=%s", event_kind)
      
            n_msg = Event(kind=event_kind,
                        content=event_content_str,
                        pub_key=self.pubkey_hex)
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
        return "ok"

    def get_post(self):
        if not self.profile_found_on_home_relay:
            return f"No profile found on {self.home_relay}"
        
        
        FILTER = [{
            'authors': "78733951a0435da2644aa5dbe6230cc0624844132a6fe213e59170bcc7dd3870",
            'limit': RECORD_LIMIT,
            'authors': [self.pubkey_hex],
            'kinds': [1]
        }]
        content =asyncio.run(self.query_client_post(FILTER))
        
        return content
    
    async def query_client_post(self, filter: List[dict]):
    # does a one off query to relay prints the events and exits
        posts = ""
        async with ClientPool([self.home_relay]+self.relays) as c:
        # async with Client(relay) as c:
            events = await c.query(filter)
            
            for each in events:
                posts += str(each.content) +"\n"
                
           
            return posts

    async def send_ecash_dm(self,amount: int, nrecipient: str, ecash_relays:List[str], comment: str ="Sent!"):
        #FIXME Deprecate this function
        relays = []
        try:
            if '@' in nrecipient:
                npub_hex, relays = nip05_to_npub(nrecipient)
                npub = hex_to_bech32(npub_hex)
                self.logger.debug("op=send_ecash_dm status=resolved_npub npub=%s", npub)
            else:
                npub = nrecipient
        except (ValueError, TypeError) as exc:
            self.logger.warning("op=send_ecash_dm status=invalid_recipient recipient=%s error=%s", nrecipient, exc)
            return "error"
        try:
            token_amount = await self.issue_token(amount=amount)
            token_msg = comment +"\n\n" + token_amount
        except (RuntimeError, ValueError, TypeError) as exc:
            self.logger.warning("op=send_ecash_dm status=issue_failed amount=%s error=%s", amount, exc)
            return "insufficient funds"
        
        self.logger.debug("op=send_ecash_dm status=sending relays=%s", ecash_relays)
        out_msg = await self.secure_dm(nrecipient=npub,message=token_msg,dm_relays=ecash_relays)
        # out_msg= asyncio.run(self._async_send_ecash_dm(token_msg,npub, ecash_relays+relays ))
        return out_msg

    async def send_ecash(self,amount: int, nrecipient: str, ecash_relays:List[str], comment: str ="Sent!"):
        #FIXME Deprecate this function
        relays = []
        try:
            if '@' in nrecipient:
                npub_hex, relays = nip05_to_npub(nrecipient)
                npub = hex_to_bech32(npub_hex)
                self.logger.debug("op=send_ecash status=resolved_npub npub=%s", npub)
            else:
                npub = nrecipient
        except (ValueError, TypeError) as exc:
            self.logger.warning("op=send_ecash status=invalid_recipient recipient=%s error=%s", nrecipient, exc)
            return "error"
        try:
            token_msg = await self.issue_token(amount=amount)
            # token_msg = comment +"\n\n" + token_amount
        except (RuntimeError, ValueError, TypeError) as exc:
            self.logger.warning("op=send_ecash status=issue_failed amount=%s error=%s", amount, exc)
            return "insufficient funds"
        
        self.logger.debug("op=send_ecash status=sending relays=%s", ecash_relays)
        out_msg = await self.secure_transmittal(nrecipient=npub,message=token_msg,dm_relays=ecash_relays,kind=21401)
        
        return f" {amount} {out_msg}"    

    async def _async_send_ecash_dm(self,token_message: str, npub: str, ecash_relays:List[str]):
        self.logger.debug("op=send_ecash_dm status=npub npub=%s", npub)
        
        my_enc = NIP4Encrypt(self.k)
        k_to_send = Keys(pub_k=npub)
        k_to_send_pubkey_hex = k_to_send.public_key_hex()
        self.logger.debug("op=send_ecash_dm status=to_pubkey pubkey=%s", k_to_send_pubkey_hex)
        ecash_msg = token_message
        # ecash_info_encrypt = my_enc.encrypt(ecash_msg,to_pub_k=k_to_send_pubkey_hex)

        self.logger.debug("op=send_ecash_dm status=relays relays=%s", ecash_relays)
        async with ClientPool(ecash_relays) as c:
            n_msg = Event(kind=Event.KIND_ENCRYPT,
                      content=ecash_msg,
                      pub_key=k_to_send_pubkey_hex)

            # print("are we here_async?", ecash_relays)
            # returns event we to_p_tag and content encrypted
            n_msg = my_enc.encrypt_event(evt=n_msg,
                                    to_pub_k=k_to_send_pubkey_hex)

            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
        
        return f"{token_message} {ecash_msg} to {npub} {ecash_relays}"    
    
    
    async def get_ecash_dm(self):
        
        
        tags = ["#p", self.pubkey_hex]
        # last_dm = float(self.get_wallet_info("last_dm"))
        try:
            last_dm = float(self.wallet_reserved_records['last_dm'])
        except (KeyError, TypeError, ValueError) as exc:
            last_dm = 0

        # last_dm = 0
        self.logger.debug("op=get_ecash_dm status=last_dm last_dm=%s", last_dm)
        #TODO need to figure out why the kind is not 1059
        dm_filter = [{
            
            'limit': RECORD_LIMIT, 
            '#p'  :  [self.pubkey_hex],
            'since': int(last_dm +1)
            
        }]
        final_dm, tokens =await self._async_query_ecash_dm(dm_filter)
        # final_dm, tokens =asyncio.run(self._async_query_secure_ecash_dm(dm_filter))
        self.logger.debug("op=get_ecash_dm status=tokens_found count=%s", len(tokens))
        for each in  tokens:
            self.accept_token(each)
        
        self.logger.debug("op=get_ecash_dm status=final_dm final_dm=%s", final_dm)
        await self.set_wallet_info("last_dm", str(final_dm))
        # self.swap_multi_each()
        
        return final_dm
    
    async def _async_query_ecash_dm(self, filter: List[dict]):
    # does a one off query to relay prints the events and exits
        my_enc = NIP4Encrypt(self.k)
        posts = ""
        tags = []
        tokens =[]
        try:
            last_dm = self.wallet_reserved_records['last_dm']
        except (KeyError, TypeError, ValueError) as exc:
            last_dm = 0
        
        final_dm = int(last_dm)
        self.logger.debug("op=query_ecash_dm status=filter filter=%s", filter)
        relay_pool = [self.home_relay] + self.relays
        self.logger.debug("op=query_ecash_dm status=relays relays=%s", relay_pool)
        async with ClientPool(relay_pool) as c:
        # async with Client(relay) as c:
            events: List[Event] = await c.query(filter)
            self.logger.debug("op=query_ecash_dm status=events count=%s", len(events))
            if events:
                self.logger.debug("op=query_ecash_dm status=events_present")
                for each in events:
                    try:
                        decrypt_content = my_enc.decrypt_event(each)
                    except (InvalidTag, ValueError, TypeError) as exc:
                        self.logger.debug("op=query_ecash_dm status=decrypt_skip")
                        self.logger.debug("op=query_ecash_dm status=decrypt_failed event=%s error=%s", each.id, exc)
                        continue
                    
                    self.logger.debug("op=query_ecash_dm status=message event_id=%s kind=%s", each.id, each.kind)
                    # last_dm = each.created_at.timestamp() if each.created_at.timestamp() > last_dm else last_dm
                    # print("last event update", datetime.fromtimestamp(last_dm),)

                    dm_timestamp = int(each.created_at.timestamp())
                    print ("final_dm, dm_timestamp:",final_dm, dm_timestamp)
                    final_dm = dm_timestamp if dm_timestamp > final_dm else final_dm
                    print ("final_dm, dm_timestamp:",final_dm, dm_timestamp)
                    array_token = decrypt_content.content.splitlines()
                    self.logger.debug("op=query_ecash_dm status=token_lines count=%s", len(array_token))
                    
                    for each in array_token:
                        if self._is_cashu_token(each):
                            self.logger.debug("op=query_ecash_dm status=token_found")
                            token = each
                            tokens.append(token)
                            break
            else:
                self.logger.debug("op=query_ecash_dm status=no_events")
                
                
        self.logger.debug("op=query_ecash_dm status=complete last_dm=%s", last_dm)
        return final_dm, tokens          

    async def _async_query_secure_ecash_dm(self, filter: List[dict]):
    # does a one off query to relay prints the events and exits
        my_enc = NIP4Encrypt(self.k)
        posts = ""
        tags = []
        tokens =[]
        
        last_dm = self.wallet_reserved_records['last_dm']
        final_dm = int(last_dm)
        self.logger.debug("op=query_secure_ecash_dm status=filter filter=%s", filter)
        relay_pool = [self.home_relay]+self.relays
        self.logger.debug("op=query_secure_ecash_dm status=relays relays=%s", relay_pool)
        async with ClientPool(relay_pool) as c:
        # async with Client(relay) as c:
            events: List[Event] = await c.query(filter)
            self.logger.debug("op=query_secure_ecash_dm status=events count=%s", len(events))
            if events:
                self.logger.debug("op=query_secure_ecash_dm status=events_present")
                for each in events:
                   
                    
                    self.logger.debug("op=query_secure_ecash_dm status=message event_id=%s kind=%s", each.id, each.kind)
                   
            else:
                self.logger.debug("op=query_secure_ecash_dm status=no_events")
                
                
        self.logger.debug("op=query_secure_ecash_dm status=complete last_dm=%s", last_dm)
        return final_dm, tokens               
       
    async def delete_dms(self, tags):
         async with ClientPool([self.home_relay]+self.relays) as c:
            self.logger.debug("op=delete_dms status=start")
            n_msg = Event(kind=Event.KIND_DELETE,
                        content=None,
                        pub_key=self.pubkey_hex,
                        tags=tags)
            self.logger.debug("op=delete_dms status=prepared tags=%s", len(tags))
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            self.logger.debug("op=delete_dms status=published")

            
    async def secure_dm(self,nrecipient:str, message: str, dm_relays: List[str]):
        try:
            npub_hex = self._resolve_pubkey_identifier(nrecipient)
        except (ValueError, TypeError) as exc:
            raise RuntimeError(f"Could not resolve {nrecipient}") from exc
        
        npub = hex_to_bech32(npub_hex)
        self.logger.debug("op=secure_dm status=resolved recipient=%s npub=%s relays=%s", nrecipient, npub, dm_relays)

        await self._async_secure_dm(npub_hex=npub_hex, message=message,dm_relays=dm_relays) 
        return "message sent" 
    
    async def _async_secure_dm(self, npub_hex, message:str, dm_relays: List[str]):
       
        # my_gift = GiftWrap(BasicKeySigner(self.k))
        
        my_gift = KindOtherGiftWrap(BasicKeySigner(self.k), kind_gift_wrap=1059)
        # relays = [self.home_relay]
        relays = dm_relays

        async with ClientPool(relays) as c:


            send_evt = Event(content=message,
                         tags=[
                             ['p', npub_hex]
                         ])
           
            self.logger.debug(f"sending dm to {npub_hex} via {dm_relays}")
            wrapped_evt, trans_k = await my_gift.wrap(send_evt,
                                                  to_pub_k=npub_hex)
            # wrapped_evt.sign(self.privkey_hex)
            c.publish(wrapped_evt)
            await asyncio.sleep(0.2)
                
    async def secure_transmittal(   self,
                                    nrecipient:str, 
                                    message: str,  
                                    dm_relays: List[str],
                                    kind: int=1060, ):
        try:
            if '@' in nrecipient:
                npub_hex, relays = nip05_to_npub(nrecipient)
                npub = hex_to_bech32(npub_hex)
                self.logger.debug("op=share_record status=resolved_npub npub=%s", npub)
                dm_relays = dm_relays
            else:
                npub_hex = bech32_to_hex(nrecipient)
        except (ValueError, TypeError) as exc:
            self.logger.warning("Invalid transmittal recipient=%s error=%s", nrecipient, exc)
            raise ValueError("invalid transmittal recipient") from exc
        self.logger.debug(
            "op=secure_transmittal status=prepared relays=%s message_bytes=%s",
            len(dm_relays),
            len(message.encode("utf-8")),
        )

        await self._async_secure_transmittal(npub_hex=npub_hex, message=message, dm_relays=dm_relays, kind=kind) 
        return "message sent" 
    
    async def _async_secure_transmittal(self, npub_hex, message:str,  dm_relays: List[str],kind):
       
        my_gift = KindOtherGiftWrap(BasicKeySigner(self.k),kind_gift_wrap=kind)
        
        # relays = [self.home_relay]
        relays = dm_relays

        async with ClientPool(relays) as c:


            send_evt = Event(content=message,
                         tags=[
                             ['p', npub_hex]
                         ],
                         created_at=int(datetime.now(timezone.utc).timestamp()))
           
            self.logger.debug(f"sending dm to {npub_hex} via {dm_relays}")
            wrapped_evt, trans_k = await my_gift.wrap(send_evt,
                                                  to_pub_k=npub_hex)
            # wrapped_evt.sign(self.privkey_hex)
            c.publish(wrapped_evt)
            await asyncio.sleep(0.2)                


    def send_post(self,text):
        asyncio.run(self._async_send_post(text))  
    
    def _build_kind1_publish_relays(self, relays: List[str] | None = None) -> List[str]:
        relay_pool: List[str] = []
        candidates = relays if relays else [self.home_relay] + list(self.public_relays or []) + list(self.relays or [])
        for each in candidates:
            if each and each not in relay_pool:
                relay_pool.append(each)
        return relay_pool

    async def _async_send_post(self, text:str, relays: List[str] | None = None):
        """Publish a kind-1 text note."""
        publish_relays = self._build_kind1_publish_relays(relays=relays)
        if not publish_relays:
            raise RuntimeError("No relays configured for kind1 publish")

        async with ClientPool(publish_relays) as c:
            n_msg = Event(
                kind=Event.KIND_TEXT_NOTE,
                content=text,
                pub_key=self.pubkey_hex
            )
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            self.logger.debug("op=publish_kind1 status=published event_id=%s relays=%s", n_msg.id, publish_relays)
            return str(n_msg.id)

    async def publish_kind1_post(self, content: str, relays: List[str] | None = None) -> Dict[str, Any]:
        if not content or not str(content).strip():
            raise ValueError("Content is required")
        event_id = await self._async_send_post(str(content), relays=relays)
        return {
            "status": "OK",
            "event_id": event_id,
            "content": str(content),
            "relays": self._build_kind1_publish_relays(relays=relays),
        }

    async def publish_event(
        self,
        content: str,
        tags: List[List[str]] | None = None,
        kind: int = Event.KIND_TEXT_NOTE,
        relays: List[str] | None = None,
    ) -> Dict[str, Any]:
        body = str(content or "").strip()
        if not body:
            raise ValueError("content is required")

        try:
            event_kind = int(kind)
        except Exception as exc:
            raise ValueError("kind must be integer") from exc
        if event_kind < 0:
            raise ValueError("kind must be >= 0")

        normalized_tags: List[List[str]] = []
        for each in tags or []:
            if not each or not isinstance(each, list):
                continue
            normalized_tags.append([str(x) for x in each if x is not None])

        publish_relays = self._build_kind1_publish_relays(relays=relays)
        if not publish_relays:
            raise RuntimeError("No relays configured for event publish")

        async with ClientPool(publish_relays) as c:
            n_msg = Event(
                kind=event_kind,
                content=body,
                tags=normalized_tags,
                pub_key=self.pubkey_hex,
            )
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            self.logger.debug(
                "op=publish_event status=published event_id=%s kind=%s relays=%s",
                n_msg.id,
                event_kind,
                publish_relays,
            )

        return {
            "status": "OK",
            "event_id": str(n_msg.id),
            "kind": event_kind,
            "content": body,
            "tags": normalized_tags,
            "relays": publish_relays,
        }

    @staticmethod



    @staticmethod

    @staticmethod

    @staticmethod

    @staticmethod




    @staticmethod

    @staticmethod

    @staticmethod

    @staticmethod



    async def publish_reply(
        self,
        target_event_id: str,
        content: str,
        target_pubkey: str | None = None,
        target_kind: int | None = None,
        relay_hint: str | None = None,
        extra_tags: List[List[str]] | None = None,
        relays: List[str] | None = None,
    ) -> Dict[str, Any]:
        target_id = (target_event_id or "").strip()
        if not target_id:
            raise ValueError("target_event_id is required")
        if target_id.startswith("note"):
            target_id = bech32_to_hex(target_id)
        if len(target_id) != 64 or not all(ch in string.hexdigits for ch in target_id):
            raise ValueError("target_event_id must be note1... or 64-char hex id")
        target_id = target_id.lower()
        reply_content = (content or "").strip()
        if not reply_content:
            raise ValueError("content is required")

        resolved_pubkey = target_pubkey
        resolved_kind = target_kind
        if resolved_pubkey and resolved_pubkey.startswith("npub"):
            resolved_pubkey = bech32_to_hex(resolved_pubkey)
        if resolved_pubkey and (len(resolved_pubkey) != 64 or not all(ch in string.hexdigits for ch in resolved_pubkey)):
            raise ValueError("target_pubkey must be npub or 64-char hex")
        if resolved_pubkey:
            resolved_pubkey = resolved_pubkey.lower()

        # Optional lookup so caller can provide event id only.
        if resolved_pubkey is None or resolved_kind is None:
            lookup_relays = relays if relays else self._build_discovery_relays()
            if lookup_relays:
                query_filter = [{
                    "limit": 1,
                    "ids": [target_id],
                }]
                try:
                    async with ClientPool(lookup_relays) as c:
                        lookup_events: List[Event] = await c.query(query_filter)
                    if lookup_events:
                        target_evt = lookup_events[0]
                        if resolved_pubkey is None:
                            resolved_pubkey = str(target_evt.pub_key).lower()
                        if resolved_kind is None:
                            resolved_kind = int(target_evt.kind)
                except Exception as exc:
                    self.logger.debug("op=publish_reply status=lookup_failed error=%s", exc)

        tags: List[List[str]] = []
        # Reply marker included for client interoperability.
        e_tag: List[str] = ["e", target_id]
        if relay_hint:
            e_tag.append(relay_hint)
        e_tag.append("reply")
        if resolved_pubkey:
            e_tag.append(resolved_pubkey)
        tags.append(e_tag)

        if resolved_pubkey:
            p_tag: List[str] = ["p", resolved_pubkey]
            if relay_hint:
                p_tag.append(relay_hint)
            tags.append(p_tag)

        if resolved_kind is not None:
            tags.append(["k", str(resolved_kind)])

        if extra_tags:
            for each in extra_tags:
                if each and isinstance(each, list):
                    tags.append([str(x) for x in each])

        publish_relays = self._build_kind1_publish_relays(relays=relays)
        if not publish_relays:
            raise RuntimeError("No relays configured for reply publish")

        async with ClientPool(publish_relays) as c:
            n_msg = Event(
                kind=Event.KIND_TEXT_NOTE,
                content=reply_content,
                tags=tags,
                pub_key=self.pubkey_hex,
            )
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            self.logger.debug("op=publish_reply status=published event_id=%s relays=%s", n_msg.id, publish_relays)

        return {
            "status": "OK",
            "event_id": str(n_msg.id),
            "target_event_id": target_id,
            "content": reply_content,
            "tags": tags,
            "relays": publish_relays,
        }

    async def publish_reaction(
        self,
        target_event_id: str,
        content: str = "❤️",
        reacted_pubkey: str | None = None,
        reacted_kind: int | None = None,
        relay_hint: str | None = None,
        a_tag: str | None = None,
        extra_tags: List[List[str]] | None = None,
        relays: List[str] | None = None,
    ) -> Dict[str, Any]:
        target_id = (target_event_id or "").strip()
        if not target_id:
            raise ValueError("target_event_id is required")
        if target_id.startswith("note"):
            target_id = bech32_to_hex(target_id)
        if len(target_id) != 64 or not all(ch in string.hexdigits for ch in target_id):
            raise ValueError("target_event_id must be note1... or 64-char hex id")
        target_id = target_id.lower()

        target_pubhex = reacted_pubkey
        target_kind = reacted_kind
        if target_pubhex and target_pubhex.startswith("npub"):
            target_pubhex = bech32_to_hex(target_pubhex)
        if target_pubhex and (len(target_pubhex) != 64 or not all(ch in string.hexdigits for ch in target_pubhex)):
            raise ValueError("reacted_pubkey must be npub or 64-char hex pubkey")
        if target_pubhex:
            target_pubhex = target_pubhex.lower()

        # Optional lookup so callers can provide only event id.
        if target_pubhex is None or target_kind is None:
            lookup_relays = relays if relays else self._build_discovery_relays()
            if lookup_relays:
                query_filter = [{
                    "limit": 1,
                    "ids": [target_id],
                }]
                try:
                    async with ClientPool(lookup_relays) as c:
                        lookup_events: List[Event] = await c.query(query_filter)
                    if lookup_events:
                        target_evt = lookup_events[0]
                        if target_pubhex is None:
                            target_pubhex = str(target_evt.pub_key).lower()
                        if target_kind is None:
                            target_kind = int(target_evt.kind)
                except Exception as exc:
                    self.logger.debug("op=publish_reaction status=lookup_failed error=%s", exc)

        tags: List[List[str]] = []
        prefix_tags: List[List[str]] = []
        if extra_tags:
            for each in extra_tags:
                if each and isinstance(each, list):
                    prefix_tags.append([str(x) for x in each])
        # Preserve NIP-25 recommendation that target e/p tags are last when
        # additional e/p tags exist.
        if prefix_tags:
            tags.extend(prefix_tags)

        e_tag: List[str] = ["e", target_id]
        if relay_hint:
            e_tag.append(relay_hint)
        if target_pubhex:
            if not relay_hint:
                e_tag.append("")
            e_tag.append(target_pubhex)
        tags.append(e_tag)

        if target_pubhex:
            p_tag: List[str] = ["p", target_pubhex]
            if relay_hint:
                p_tag.append(relay_hint)
            tags.append(p_tag)

        if target_kind is not None:
            tags.append(["k", str(target_kind)])

        if a_tag:
            tags.append(["a", a_tag])

        publish_relays = self._build_kind1_publish_relays(relays=relays)
        if not publish_relays:
            raise RuntimeError("No relays configured for reaction publish")

        reaction_content = "❤️" if content is None else str(content)
        async with ClientPool(publish_relays) as c:
            n_msg = Event(
                kind=7,
                content=reaction_content,
                tags=tags,
                pub_key=self.pubkey_hex,
            )
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            self.logger.debug("op=publish_reaction status=published event_id=%s relays=%s", n_msg.id, publish_relays)

        return {
            "status": "OK",
            "event_id": str(n_msg.id),
            "target_event_id": target_id,
            "content": reaction_content,
            "tags": tags,
            "relays": publish_relays,
        }

    async def publish_external_reaction(
        self,
        content: str,
        external_tags: List[List[str]],
        extra_tags: List[List[str]] | None = None,
        relays: List[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Publish external-content reaction event (NIP-25 kind 17).

        Requires external content tags (`k` + `i` pairs per NIP-73 pattern).
        """
        reaction_content = "" if content is None else str(content)

        tags: List[List[str]] = []
        has_k = False
        has_i = False
        for each in external_tags or []:
            if not each or not isinstance(each, list):
                continue
            normalized = [str(x) for x in each if x is not None]
            if not normalized:
                continue
            if normalized[0] == "k":
                has_k = True
            if normalized[0] == "i":
                has_i = True
            tags.append(normalized)

        if not has_k or not has_i:
            raise ValueError("external_tags must include at least one 'k' and one 'i' tag")

        if extra_tags:
            for each in extra_tags:
                if each and isinstance(each, list):
                    tags.append([str(x) for x in each if x is not None])

        publish_relays = self._build_kind1_publish_relays(relays=relays)
        if not publish_relays:
            raise RuntimeError("No relays configured for external reaction publish")

        async with ClientPool(publish_relays) as c:
            n_msg = Event(
                kind=17,
                content=reaction_content,
                tags=tags,
                pub_key=self.pubkey_hex,
            )
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            self.logger.debug("op=publish_external_reaction status=published event_id=%s relays=%s", n_msg.id, publish_relays)

        return {
            "status": "OK",
            "event_id": str(n_msg.id),
            "kind": 17,
            "content": reaction_content,
            "tags": tags,
            "relays": publish_relays,
        }

    async def publish_deletion_request(
        self,
        event_ids: List[str] | None = None,
        a_tags: List[str] | None = None,
        kinds: List[int | str] | None = None,
        reason: str | None = None,
        relays: List[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Publish a NIP-09 deletion request (kind 5).

        Notes:
        - Clients/relays ultimately decide deletion visibility semantics.
        - Callers SHOULD include `k` tags for referenced event kinds when known.
        """
        normalized_event_ids: List[str] = []
        for each_id in event_ids or []:
            value = str(each_id or "").strip()
            if not value:
                continue
            if value.startswith("note"):
                value = bech32_to_hex(value)
            if len(value) != 64 or not all(ch in string.hexdigits for ch in value):
                raise ValueError("event_ids must be note1... or 64-char hex ids")
            normalized = value.lower()
            if normalized not in normalized_event_ids:
                normalized_event_ids.append(normalized)

        normalized_a_tags: List[str] = []
        for each_a in a_tags or []:
            value = str(each_a or "").strip()
            if not value:
                continue
            # NIP-09 `a` tag is <kind>:<pubkey>:<d-identifier>.
            if value.count(":") < 2:
                raise ValueError("a_tags must be NIP-01 coordinates: <kind>:<pubkey>:<d-identifier>")
            if value not in normalized_a_tags:
                normalized_a_tags.append(value)

        if not normalized_event_ids and not normalized_a_tags:
            raise ValueError("at least one event id or a-tag is required")

        tags: List[List[str]] = []
        for each_id in normalized_event_ids:
            tags.append(["e", each_id])
        for each_a in normalized_a_tags:
            tags.append(["a", each_a])

        normalized_kinds: List[str] = []
        for each_kind in kinds or []:
            try:
                kind_value = str(int(each_kind))
            except Exception as exc:
                raise ValueError("kinds must be integers") from exc
            if kind_value not in normalized_kinds:
                normalized_kinds.append(kind_value)
        for each_kind in normalized_kinds:
            tags.append(["k", each_kind])

        publish_relays = self._build_kind1_publish_relays(relays=relays)
        if not publish_relays:
            raise RuntimeError("No relays configured for delete request publish")

        delete_reason = str(reason or "").strip()
        async with ClientPool(publish_relays) as c:
            n_msg = Event(
                kind=Event.KIND_DELETE,
                content=delete_reason,
                tags=tags,
                pub_key=self.pubkey_hex,
            )
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            self.logger.debug("op=publish_delete_request status=published event_id=%s relays=%s", n_msg.id, publish_relays)

        return {
            "status": "OK",
            "event_id": str(n_msg.id),
            "kind": Event.KIND_DELETE,
            "content": delete_reason,
            "tags": tags,
            "event_ids": normalized_event_ids,
            "a_tags": normalized_a_tags,
            "kinds": [int(each) for each in normalized_kinds],
            "relays": publish_relays,
        }

    async def add_tx_history(   self, 
                                tx_type:str, 
                                amount:int, 
                                comment:str = "", 
                                tendered_amount: float=None,
                                tendered_currency: str = "SAT",
                                fees: int =0,
                                invoice:str=None,
                                payment_preimage: str = None,
                                payment_hash: str = None,
                                description_hash: str = None
                                ):
        self.logger.debug("Add tx history")
        my_enc = NIP44Encrypt(self.k)
        if comment == None: #sometimes none get passed in
            comment = ""

        if tendered_amount == None:
            tendered_amount = amount
        created_at = int(datetime.now().timestamp())

        # Calculate current balance - need to refresh data

        # await self.load_data()
        

       
        tx_history = TxHistory( create_time=created_at,
                                tx_type=tx_type,
                                amount= amount,
                                comment= comment,
                                tendered_amount=tendered_amount,
                                tendered_currency=tendered_currency,
                                fees=fees,
                                current_balance=self.balance,
                                invoice=invoice,
                                payment_hash=payment_hash,
                                preimage=payment_preimage,
                                description_hash=description_hash
                               
                                 
                                )
        tx_history_str = json.dumps(tx_history.model_dump())
        tx_history_encrypt = my_enc.encrypt(tx_history_str,to_pub_k=self.pubkey_hex)
        async with ClientPool([self.home_relay]) as c:
       
            n_msg = Event(                        
                        kind=7377,
                        content=tx_history_encrypt,
                        pub_key=self.pubkey_hex)
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            await asyncio.sleep(0.2)
            


    async def get_tx_history(self):
        self.logger.debug("Get tx history")
        tx_history = []
        my_enc = NIP44Encrypt(self.k)
        decrypt_content = None

        filter = [{
            'limit': RECORD_LIMIT,
            'authors': [self.pubkey_hex],
            'kinds': [7377] 
            
        }]

        async with ClientPool([self.home_relay]) as c:  
            events = await c.query(filter) 
            for each in events:
                decrypt_content = my_enc.decrypt(each.content, self.pubkey_hex)
                
                json_obj = json.loads(decrypt_content) 
                # Convert create_time to datetime
                json_obj['create_time'] = datetime.fromtimestamp(json_obj['create_time']).strftime('%Y-%m-%d %H:%M:%S')
               
                tx_history.append(json_obj)         
           
        return tx_history


    async def set_wallet_config(self):
        # this function will eventually get rid of set_wallet_info_wallet("wallet")     
        m = hashlib.sha256()
        m.update(self.privkey_hex.encode())
        wallet_config_data = json.dumps(self.acorn_tags)
        m.update(wallet_config_data.encode())
                 
        label_name_hash = m.digest().hex()
        
        # print(label, label_info)
        my_enc = NIP44Encrypt(self.k)
        wallet_config_data_encrypt = my_enc.encrypt(wallet_config_data,to_pub_k=self.pubkey_hex) 
        write_relays = [self.home_relay]
        async with ClientPool(write_relays) as c:
        # async with Client(relay) as c:
            n_msg = Event(kind=17375,
                        content=wallet_config_data_encrypt,
                        pub_key=self.pubkey_hex
                        )
            
            # n_msg = my_enc.encrypt_event(evt=n_msg,
            #                         to_pub_k=self.pubkey_hex)
            
            n_msg.sign(self.privkey_hex)
            # print("label, event id:", label, n_msg.id)
            c.publish(n_msg)
            await asyncio.sleep(0.2)
            self.logger.debug(
                "op=set_wallet_config status=published event_id=%s relays=%s fields=%s",
                n_msg.id,
                len(write_relays),
                len(self.acorn_tags),
            )

    async def get_wallet_config(self):  
        wallet_config_info = None
        events = None  
        my_enc = NIP44Encrypt(self.k)
        decrypt_content = None
        FILTER = [{
            'limit': 1,
            'authors': [self.pubkey_hex],
            'kinds': [17375] 
        }]
        async with ClientPool([self.home_relay]) as c:       
            
            events = await c.query(FILTER)
            
            self.logger.debug(f"get wallet info no of events: {len(events)}")

        if events:
            wallet_config_info = json.loads(my_enc.decrypt(events[0].content, self.pubkey_hex))
       
        
        return wallet_config_info

       

    @staticmethod
    def _record_event_tag(event: Event, tag_name: str) -> str:
        for tag in event.tags:
            if len(tag) > 1 and tag[0] == tag_name:
                return str(tag[1])
        return ""

    def _canonical_record_events(self, events: List[Event]) -> List[Event]:
        """Return one canonical event for each addressable record coordinate."""
        unique: dict[str, Event] = {}
        for event in events:
            unique[str(event.id)] = event

        grouped: dict[tuple, List[Event]] = {}
        for event in unique.values():
            d_tag = self._record_event_tag(event, "d")
            if 30000 <= int(event.kind) < 40000 and d_tag:
                coordinate = (int(event.kind), str(event.pub_key), d_tag)
            else:
                coordinate = ("event", str(event.id))
            grouped.setdefault(coordinate, []).append(event)

        canonical: List[Event] = []
        for candidates in grouped.values():
            candidates.sort(
                key=lambda each: (-self._event_timestamp(each), str(each.id))
            )
            canonical.append(candidates[0])
        canonical.sort(
            key=lambda each: (-self._event_timestamp(each), str(each.id))
        )
        return canonical

    def _record_relay_pool(self, relays: List[str] | str | None = None) -> List[str]:
        if relays is None:
            candidates = [self.home_relay]
        elif isinstance(relays, str):
            candidates = [
                each.strip() for each in relays.split(",") if each.strip()
            ]
        else:
            candidates = [
                str(each).strip() for each in relays if str(each).strip()
            ]
        normalized = self._normalize_relays(candidates)
        if not normalized:
            raise ValueError("at least one record relay is required")
        return normalized

    def _record_label_hash(self, label: str) -> str:
        """Return the legacy-compatible private record lookup tag."""
        if not isinstance(label, str) or not label:
            raise ValueError("record label must be a non-empty string")
        digest = hashlib.sha256()
        digest.update(self.privkey_hex.encode())
        digest.update(label.encode())
        return digest.hexdigest()

    async def set_wallet_info(
        self,
        label: str,
        label_info: str,
        replicate_relays: List[str] = None,
        record_kind: int = 37375,
        verify: bool = False,
        verify_timeout: float = 8.0,
    ) -> dict:
        return await self._async_set_wallet_info(
            label,
            label_info,
            replicate_relays=replicate_relays,
            record_kind=record_kind,
            verify=verify,
            verify_timeout=verify_timeout,
        )

    async def _async_set_wallet_info(
        self,
        label: str,
        label_info: str,
        replicate_relays: List[str] = None,
        record_kind: int = 37375,
        verify: bool = False,
        verify_timeout: float = 8.0,
    ) -> dict:
        label_name_hash = self._record_label_hash(label)

        my_enc = NIP44Encrypt(self.k)
        wallet_info_encrypt = my_enc.encrypt(
            label_info,
            to_pub_k=self.pubkey_hex,
        )
        tags = [["d", label_name_hash]]
        write_relays = self._record_relay_pool(
            replicate_relays if replicate_relays else [self.home_relay]
        )

        created_at = int(datetime.now().timestamp())
        if verify:
            existing_filter = [{
                "limit": RECORD_LIMIT,
                "authors": [self.pubkey_hex],
                "kinds": [record_kind],
                "#d": [label_name_hash],
            }]
            async with ClientPool(write_relays) as c:
                existing = await c.query(existing_filter)
            canonical_existing = self._canonical_record_events(existing)
            if canonical_existing:
                created_at = max(
                    created_at,
                    self._event_timestamp(canonical_existing[0]) + 1,
                )

        async with ClientPool(write_relays) as c:
            n_msg = Event(
                kind=record_kind,
                content=wallet_info_encrypt,
                pub_key=self.pubkey_hex,
                tags=tags,
                created_at=created_at,
            )
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            await asyncio.sleep(0.2)
            self.logger.debug(
                "op=set_wallet_info status=published event_id=%s kind=%s relays=%s",
                n_msg.id,
                record_kind,
                len(write_relays),
            )

        verification = {
            relay: {"readable": False, "canonical": False}
            for relay in write_relays
        }
        if verify:
            deadline = monotonic() + max(0.5, float(verify_timeout))
            verify_filter = [{
                "limit": RECORD_LIMIT,
                "authors": [self.pubkey_hex],
                "kinds": [record_kind],
                "#d": [label_name_hash],
            }]
            while monotonic() < deadline:
                for relay in write_relays:
                    if verification[relay]["canonical"]:
                        continue
                    try:
                        async with ClientPool([relay]) as c:
                            observed = await c.query(verify_filter)
                        canonical = self._canonical_record_events(observed)
                        verification[relay]["readable"] = any(
                            str(each.id) == str(n_msg.id)
                            for each in observed
                        )
                        verification[relay]["canonical"] = bool(
                            canonical
                            and str(canonical[0].id) == str(n_msg.id)
                        )
                    except Exception as exc:
                        verification[relay]["error"] = str(exc)
                if all(
                    each["canonical"] for each in verification.values()
                ):
                    break
                await asyncio.sleep(0.4)

            failed = [
                relay for relay, state in verification.items()
                if not state["canonical"]
            ]
            if failed:
                raise RuntimeError(
                    "Record publish could not be verified as canonical on: "
                    + ", ".join(failed)
                )

        return {
            "status": "OK",
            "event_id": str(n_msg.id),
            "kind": int(record_kind),
            "label_hash": label_name_hash,
            "relays": write_relays,
            "verified": bool(verify),
            "verification": verification,
        }

    async def get_label_hash(self, label:str=None):
        """get label hash used for d tag"""
        return self._record_label_hash(label)

    async def get_wallet_info(
        self,
        label: str = None,
        record_kind: int = 37375,
        record_by_hash: str = None,
        record_origin: str = None,
        relays: List[str] | str | None = None,
    ):
        my_enc = NIP44Encrypt(self.k)

        if record_origin:
            label = ':'.join([record_origin,label])

        if record_by_hash:
            label_hash = record_by_hash
        else:
            label_hash = self._record_label_hash(label)
        
        decrypt_content = None
        
        # d_tag_encrypt = my_enc.encrypt(d_tag,to_pub_k=self.pubkey_hex)
        # a_tag = ["a", label_hash]
        # print("a_tag:",a_tag)
       
        self.logger.debug("op=get_wallet_info status=query kind=%s", record_kind)
        
        # DEFAULT_RELAY = self.relays[0]
        FILTER = [{
            'limit': RECORD_LIMIT,
            'authors': [self.pubkey_hex],
            'kinds': [record_kind],
            '#d': [label_hash]   
            
            
        }]

        # print("are we here?", label_hash)
        event = await self._async_get_wallet_info(
            FILTER,
            label_hash,
            relays=relays,
        )
        if not event:
            self.logger.debug(
                "op=get_wallet_info status=missing kind=%s",
                record_kind,
            )
            return None
        
        # print(event.data())
        try:
            decrypt_content = my_enc.decrypt(event.content, self.pubkey_hex)
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            self.logger.warning(
                "op=get_wallet_info status=decrypt_failed kind=%s error=%s",
                record_kind,
                exc,
            )
            return None
        
        

        return decrypt_content

    async def store_deferred_recovery(
        self,
        *,
        verify_timeout: float = 8.0,
    ) -> dict:
        """Persist only the non-secret state of a deferred backup ceremony."""

        payload = {
            "version": 1,
            "status": "pending",
            "created_at": int(time()),
        }
        result = await self.set_wallet_info(
            DEFERRED_RECOVERY_LABEL,
            json.dumps(payload, separators=(",", ":"), sort_keys=True),
            verify=True,
            verify_timeout=verify_timeout,
        )
        return {
            "status": "PENDING",
            "pending": True,
            "created_at": payload["created_at"],
            "event_id": result.get("event_id"),
            "verified": bool(result.get("verified")),
        }

    async def get_deferred_recovery(self) -> dict:
        """Return validated deferred recovery state for the active Acorn."""

        raw = await self.get_wallet_info(DEFERRED_RECOVERY_LABEL)
        if raw is None:
            return {"status": "ABSENT", "pending": False}
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("deferred recovery state is malformed") from exc
        if payload.get("version") != 1:
            raise ValueError("deferred recovery state is not supported")
        status = str(payload.get("status", "")).lower()
        if status == "complete":
            return {
                "status": "COMPLETE",
                "pending": False,
                "completed_at": int(payload.get("completed_at", 0)),
            }
        if status == "pending":
            return {
                "status": "PENDING",
                "pending": True,
                "created_at": int(payload.get("created_at", 0)),
            }
        raise ValueError("deferred recovery state is not supported")

    async def get_deferred_recovery_status(self) -> dict:
        """Return the persistent recovery state without returning secrets."""

        raw = await self.get_wallet_info(DEFERRED_RECOVERY_LABEL)
        if raw is None:
            return {"status": "ABSENT", "pending": False}
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("deferred recovery state is malformed") from exc
        if payload.get("version") != 1:
            raise ValueError("deferred recovery state is not supported")
        status = str(payload.get("status", "")).lower()
        if status == "pending":
            return {
                "status": "PENDING",
                "pending": True,
                "created_at": int(payload.get("created_at", 0)),
            }
        if status == "complete":
            return {
                "status": "COMPLETE",
                "pending": False,
                "completed_at": int(payload.get("completed_at", 0)),
            }
        raise ValueError("deferred recovery state is not supported")

    async def activate_record_protection(
        self,
        *,
        record_protection_key: str,
        verify_timeout: float = 8.0,
    ) -> dict:
        """Publish non-secret state indicating that an RPK has been activated."""

        canonical_key = validate_record_protection_key(record_protection_key)
        activated_at = int(time())
        fingerprint = hashlib.sha256(bytes.fromhex(canonical_key)).hexdigest()[:16]
        payload = {
            "version": 1,
            "status": "active",
            "activated_at": activated_at,
            "key_fingerprint": fingerprint,
        }
        result = await self.set_wallet_info(
            RECORD_PROTECTION_STATUS_LABEL,
            json.dumps(payload, separators=(",", ":"), sort_keys=True),
            verify=True,
            verify_timeout=verify_timeout,
        )
        return {
            "status": "ACTIVE",
            "active": True,
            "activated_at": activated_at,
            "key_fingerprint": fingerprint,
            "event_id": result.get("event_id"),
            "verified": bool(result.get("verified")),
        }

    async def get_record_protection_status(self) -> dict:
        """Read record-protection capability state without returning the RPK."""

        raw = await self.get_wallet_info(RECORD_PROTECTION_STATUS_LABEL)
        if raw is None:
            return {"status": "DISABLED", "active": False}
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("record protection status is malformed") from exc
        if payload.get("version") != 1 or payload.get("status") != "active":
            raise ValueError("record protection status is not supported")
        return {
            "status": "ACTIVE",
            "active": True,
            "activated_at": int(payload.get("activated_at", 0)),
            "key_fingerprint": str(payload.get("key_fingerprint", "")),
        }

    async def complete_deferred_recovery(
        self,
        *,
        verify_timeout: float = 8.0,
    ) -> dict:
        """Remove current recovery secrets after the user confirms backup."""

        recovery = await self.get_deferred_recovery()
        if not recovery.get("pending"):
            return {
                "status": recovery.get("status", "ABSENT"),
                "pending": False,
                "completed": recovery.get("status") == "COMPLETE",
            }

        current_tags = list(getattr(self, "acorn_tags", []) or [])
        scrubbed_tags = [
            tag
            for tag in current_tags
            if not (
                isinstance(tag, list)
                and len(tag) > 0
                and tag[0] == "seedphrase"
            )
        ]
        self.acorn_tags = scrubbed_tags
        self.seed_phrase = None
        wallet_label = str(getattr(self, "name", "") or "wallet")
        await self.set_wallet_info(
            wallet_label,
            json.dumps(scrubbed_tags),
            verify=True,
            verify_timeout=verify_timeout,
        )
        await self.set_wallet_config()

        deletion = await self.delete_record(
            DEFERRED_RECOVERY_LABEL,
            relays=[self.home_relay],
        )
        completed_at = int(time())
        marker = await self.set_wallet_info(
            DEFERRED_RECOVERY_LABEL,
            json.dumps(
                {
                    "version": 1,
                    "status": "complete",
                    "completed_at": completed_at,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            verify=True,
            verify_timeout=verify_timeout,
        )
        return {
            "status": "COMPLETE",
            "pending": False,
            "completed": True,
            "completed_at": completed_at,
            "delete_request": deletion,
            "marker_event_id": marker.get("event_id"),
            "advisory": (
                "Recovery secrets were removed from current Acorn state. "
                "NIP-09 deletion is advisory; relays or replicas may retain "
                "historical encrypted events."
            ),
        }
    
    async def delete_record(
        self,
        label: str = None,
        record_kind: int = 37375,
        record_origin: str = None,
        relays: List[str] | str | None = None,
        delete_blob: bool = False,
    ):
        if record_origin:
            label = ":".join([record_origin, label])

        label_hash = self._record_label_hash(label)
        delete_relays = self._record_relay_pool(relays)
        FILTER = [{
            'limit': RECORD_LIMIT,
            'authors': [self.pubkey_hex],
            'kinds': [record_kind],
            '#d': [label_hash]   
            
            
        }]

        # print("are we here?", label_hash)
        event = await self._async_get_wallet_info(
            FILTER,
            label_hash,
            relays=delete_relays,
        )
        if not event:
            return {
                "status": "NOT_FOUND",
                "label": label,
                "kind": int(record_kind),
                "relays": delete_relays,
                "message": f"{label} not found.",
            }

        blob_cleanup = None
        if delete_blob:
            try:
                record = await self.get_record_safebox(
                    record_name=label,
                    record_kind=record_kind,
                    relays=delete_relays,
                )
                if record.blobsha256:
                    blob_cleanup = {
                        "requested": True,
                        "sha256": record.blobsha256,
                        "deleted": False,
                        "servers": [],
                    }
                    client = BlossomClient(
                        nsec=self.privkey_bech32,
                        default_servers=self.blossom_servers,
                    )
                    for server in self.blossom_servers:
                        try:
                            client.delete_blob(
                                server=server,
                                sha256=record.blobsha256,
                            )
                            blob_cleanup["servers"].append(
                                {"server": server, "deleted": True}
                            )
                            blob_cleanup["deleted"] = True
                        except Exception as exc:
                            blob_cleanup["servers"].append(
                                {
                                    "server": server,
                                    "deleted": False,
                                    "error": str(exc),
                                }
                            )
            except Exception as exc:
                blob_cleanup = {
                    "requested": True,
                    "deleted": False,
                    "error": str(exc),
                }
        
        tags = [
            ["e", str(event.id)],
            ["a", f"{int(record_kind)}:{self.pubkey_hex}:{label_hash}"],
            ["k", str(int(record_kind))],
        ]
        self.logger.debug("op=delete_record status=prepared kind=%s tags=%s", record_kind, len(tags))
        async with ClientPool(delete_relays) as c:
        
            n_msg = Event(kind=Event.KIND_DELETE,
                        content=f"Delete Acorn record {label_hash}",
                        pub_key=self.pubkey_hex,
                        tags=tags)
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            # added a delay here so the delete event get published
            await asyncio.sleep(1)
        
        hidden_on: List[str] = []
        for relay in delete_relays:
            try:
                async with ClientPool([relay]) as c:
                    remaining = await c.query(FILTER)
                if not remaining:
                    hidden_on.append(relay)
            except Exception:
                continue

        index_updated = False
        index_error = None
        if isinstance(getattr(self, "acorn_tags", None), list):
            original_tags = list(self.acorn_tags)
            self.acorn_tags = [
                tag
                for tag in self.acorn_tags
                if not (
                    isinstance(tag, list)
                    and len(tag) > 1
                    and tag[0] == "user_record"
                    and tag[1] == label
                )
            ]
            if self.acorn_tags != original_tags:
                try:
                    await self.set_wallet_info(
                        label=self.name,
                        label_info=json.dumps(self.acorn_tags),
                    )
                    await self.set_wallet_config()
                    index_updated = True
                except Exception as exc:
                    index_error = str(exc)

        return {
            "status": "DELETE_REQUESTED",
            "label": label,
            "kind": int(record_kind),
            "event_id": str(event.id),
            "delete_event_id": str(n_msg.id),
            "relays": delete_relays,
            "hidden_on": hidden_on,
            "advisory": (
                "NIP-09 deletion is advisory; relays and clients may retain "
                "the original event."
            ),
            "blob_cleanup": blob_cleanup,
            "index_updated": index_updated,
            "index_error": index_error,
            "message": f"{label} deletion requested.",
        }
    
    async def _async_get_wallet_info(
        self,
        filter: List[dict],
        label_hash,
        relays: List[str] | str | None = None,
    ):
    # does a one off query to relay prints the events and exits
        self.logger.debug("op=get_wallet_info status=query_prepared filters=%s", len(filter))
        # my_enc = NIP44Encrypt(self.k)
        # target_tag = filter[0]['d']
        target_tag = label_hash
        events = []
        
        relay_pool = self._record_relay_pool(relays)
        async with ClientPool(relay_pool) as c:
        
            
            events = await c.query(filter)
            
            self.logger.debug(f"no of events: {len(events)}")
            
            # print(f"_async event xoxoxo: type: {type(events[0])} data: {events[0].data()}")

        if not events:
            self.logger.debug("op=get_wallet_info status=no_events")
            return None

        canonical = self._canonical_record_events(events)
        return canonical[0] if canonical else None


    async def set_lock(self, lock: bool):
        pass

    def _lock_actor(self) -> str:
        task = asyncio.current_task()
        if task is None:
            return "sync"
        try:
            task_name = task.get_name()
        except Exception:
            task_name = None
        return task_name or f"task-{id(task)}"

    async def check_lock(self):
        lock_value = "FALSE"
        try:
            lock_value = await self.get_wallet_info("lock")
            # print(lock_value)
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as e:
            self.logger.debug("Check lock fallback; lock record unavailable: %s", e)
        if lock_value is None:
            self.logger.debug("op=check_lock status=missing_lock_record")
            lock_value = "FALSE"
        
        return str(lock_value).upper().strip() == "TRUE"

    async def acquire_lock(self, attempts=10):
        start_wait = monotonic()
        actor = self._lock_actor()
        current_depth = getattr(self, "_lock_depth", 0)
        loop_count = 0

        # Re-entrant acquire for the same in-process actor.
        # This avoids false lock contention when a locked flow calls another
        # method that also acquires the wallet lock.
        if self._lock_owner == actor and current_depth > 0:
            self._lock_depth = current_depth + 1
            self.logger.debug(
                "op=acquire_lock status=reentrant handle=%s actor=%s depth=%s",
                self.handle,
                actor,
                self._lock_depth,
            )
            return

        self.logger.debug(
            "op=acquire_lock status=start handle=%s actor=%s attempts=%s",
            self.handle,
            actor,
            attempts,
        )
        try:
            lock_value = await self.get_wallet_info(label="lock")
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as e:
            self.logger.debug("Lock record missing/unreadable; defaulting to unlocked: %s", e)
            lock_value = "FALSE"
        if lock_value is None:
            self.logger.debug("op=acquire_lock status=missing_lock_record")
            lock_value = "FALSE"

        
        if str(lock_value).upper().strip() == "TRUE":
            
            self.logger.debug("op=acquire_lock status=already_locked handle=%s actor=%s", self.handle, actor)
            
            
            
            while True:                
                await asyncio.sleep(1)
                loop_count +=1
                if loop_count > attempts:
                    wait_ms = int((monotonic() - start_wait) * 1000)
                    self.logger.info(
                        "op=acquire_lock status=seizing_lock handle=%s actor=%s attempts=%s wait_ms=%s previous_owner=%s",
                        self.handle,
                        actor,
                        attempts,
                        wait_ms,
                        self._lock_owner,
                    )
                    await self.set_wallet_info(label="lock",label_info="FALSE")
                    break
                    # raise RuntimeError(f"Could not acquire lock after {timeout} attempts")
                try:
                    lock_value = await self.get_wallet_info(label="lock")
                except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as e:
                    self.logger.debug("Lock poll failed; assuming unlocked for recovery: %s", e)
                    lock_value = "FALSE"
                if lock_value is None:
                    self.logger.debug("op=acquire_lock status=missing_lock_record_during_poll")
                    lock_value = "FALSE"
                self.logger.debug(
                    "op=acquire_lock status=poll lock_value=%s attempt=%s max_attempts=%s handle=%s",
                    lock_value,
                    loop_count,
                    attempts,
                    self.handle,
                )
                if str(lock_value).upper().strip() != 'TRUE':
                    await self.set_wallet_info(label="lock",label_info="TRUE")
                    self._lock_acquired_at = monotonic()
                    self._lock_owner = actor
                    self._lock_depth = 1
                    wait_ms = int((self._lock_acquired_at - start_wait) * 1000)
                    level = self.logger.warning if wait_ms >= 1500 else self.logger.info
                    level(
                        "op=acquire_lock status=acquired_after_wait handle=%s actor=%s wait_ms=%s attempts_used=%s",
                        self.handle,
                        actor,
                        wait_ms,
                        loop_count,
                    )
                    break
        else:
            self.logger.debug("op=acquire_lock status=acquired_immediately handle=%s actor=%s", self.handle, actor)
            await self.set_wallet_info(label="lock",label_info="TRUE")
            self._lock_acquired_at = monotonic()
            self._lock_owner = actor
            self._lock_depth = 1
       

    async def release_lock(self):
        actor = self._lock_actor()
        current_depth = getattr(self, "_lock_depth", 0)

        if self._lock_owner == actor and current_depth > 1:
            self._lock_depth = current_depth - 1
            self.logger.debug(
                "op=release_lock status=reentrant_decrement handle=%s actor=%s depth=%s",
                self.handle,
                actor,
                self._lock_depth,
            )
            return

        held_ms = None
        if self._lock_acquired_at is not None:
            held_ms = int((monotonic() - self._lock_acquired_at) * 1000)
        if held_ms is None:
            self.logger.debug(
                "op=release_lock status=releasing handle=%s actor=%s owner=%s held_ms=unknown",
                self.handle,
                actor,
                self._lock_owner,
            )
        else:
            self.logger.info(
                "op=release_lock status=releasing handle=%s actor=%s owner=%s held_ms=%s",
                self.handle,
                actor,
                self._lock_owner,
                held_ms,
            )
        await self.set_wallet_info(label="lock",label_info="FALSE")
        self._lock_acquired_at = None
        self._lock_owner = None
        self._lock_depth = 0
        
        pass  

        
    async def get_record(
        self,
        record_name: str = None,
        record_kind: int = 37375,
        record_by_hash=None,
        record_origin: str = None,
        relays: List[str] | str | None = None,
    ):
        #FIXME - not sure if this function is used - get_wallet_info is doing is
        
        record_out = await self.get_wallet_info(
            label=record_name,
            record_kind=record_kind,
            record_by_hash=record_by_hash,
            record_origin=record_origin,
            relays=relays,
        )
        if record_out is None:
            return None
        try:
            record_obj = json.loads(record_out)
            
        except (json.JSONDecodeError, TypeError):
            record_obj = record_out

        return record_obj

    async def get_record_safebox(
        self,
        record_name: str = None,
        record_kind: int = 37375,
        record_by_hash: str = None,
        record_origin: str = None,
        relays: List[str] | str | None = None,
    ) -> SafeboxRecord:
        my_enc = NIP44Encrypt(self.k)

        if record_origin:
            record_name = ':'.join([record_origin,record_name])

        if record_by_hash:
            label_hash = record_by_hash
        else:
            label_hash = self._record_label_hash(record_name)
        
        decrypt_content = None
        
        # d_tag_encrypt = my_enc.encrypt(d_tag,to_pub_k=self.pubkey_hex)
        # a_tag = ["a", label_hash]
        # print("a_tag:",a_tag)
       
        self.logger.debug("op=get_record_safebox status=query kind=%s", record_kind)
        
        # DEFAULT_RELAY = self.relays[0]
        FILTER = [{
            'limit': RECORD_LIMIT,
            'authors': [self.pubkey_hex],
            'kinds': [record_kind],
            '#d': [label_hash]   
            
            
        }]

        # print("are we here?", label_hash)
        event = await self._async_get_wallet_info(
            FILTER,
            label_hash,
            relays=relays,
        )
        if not event:
            self.logger.warning(
                "op=get_record_safebox status=missing kind=%s",
                record_kind,
            )
            raise ValueError(f"No event found for {record_kind} {record_name}")

        try:
            decrypt_content = my_enc.decrypt(event.content, self.pubkey_hex)
        except (ValueError, TypeError) as exc:
            self.logger.warning("op=get_record_safebox status=decrypt_failed kind=%s error=%s", record_kind, exc)
            raise ValueError(f"Could not decrypt info for: {record_name}. Does a record exist?") from exc
        
        try:
            safebox_record: SafeboxRecord = SafeboxRecord(**json.loads(decrypt_content))
            self.logger.debug(
                "op=get_record_safebox status=ok kind=%s has_blob=%s",
                record_kind,
                bool(safebox_record.blobref),
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.logger.warning("op=get_record_safebox status=parse_failed kind=%s error=%s", record_kind, exc)
            raise ValueError(f"Could create safebox record: {record_name}. Does a record exist?") from exc

        return safebox_record
    
    async def get_original_blob(
        self,
        orginal_record: OriginalRecordTransfer,
        delete: bool = True,
        blossom_xfer_server: str | None = None,
        blossom_home_server: str | None = None,
    ):

        blob_data: bytes = None
        blob_type:  str = None
        self.logger.debug("op=get_original_blob status=start")
        fallback_xfer = blossom_xfer_server or self._default_blossom_xfer_server()
        fallback_home = blossom_home_server or self._default_blossom_home_server()
        source_servers: List[str] = []
        for server in [fallback_xfer, fallback_home]:
            if server and server not in source_servers:
                source_servers.append(server)

        client = BlossomClient(nsec=orginal_record.blobnsec, default_servers=source_servers)
        blob_retrieve: BlossomBlob | None = None
        source_server_used: str | None = None
        last_fetch_error: str | None = None
        for source_server in source_servers:
            try:
                blob_retrieve = client.get_blob(
                    server=source_server,
                    sha256=orginal_record.blobsha256,
                )
                source_server_used = source_server
                break
            except Exception as exc:
                last_fetch_error = str(exc)
                if exc.__class__.__name__ == "BlobNotFound":
                    self.logger.info(
                        "op=get_original_blob status=source_missing server=%s sha256=%s",
                        source_server,
                        orginal_record.blobsha256,
                    )
                else:
                    self.logger.warning(
                        "op=get_original_blob status=fetch_failed server=%s sha256=%s error=%s",
                        source_server,
                        orginal_record.blobsha256,
                        exc,
                    )

        if not blob_retrieve:
            self.logger.warning(
                "op=get_original_blob status=not_available sha256=%s tried=%s error=%s",
                orginal_record.blobsha256,
                source_servers,
                last_fetch_error,
            )
            return None, None

        self.logger.debug("op=get_original_blob status=mime mime=%s", blob_retrieve.mime_type)
        if blob_retrieve.mime_type == "application/octet-stream":
            self.logger.debug("op=get_original_blob status=decrypting")
            try:
                blob_data = decrypt_bytes(    cipherbytes=blob_retrieve.get_bytes(),
                                                        
                                                        key=bytes.fromhex(orginal_record.encryptparms.key),
                                                        iv = bytes.fromhex(orginal_record.encryptparms.iv)
                                                    )
                blob_type = filetype.guess_mime(blob_data)
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as e:
                self.logger.warning("op=get_original_blob status=decrypt_failed error=%s", e)
            if delete and blob_data:
                try:
                    delete_result = client.delete_blob(server=source_server_used,sha256=orginal_record.blobsha256)
                    self.logger.debug("op=get_original_blob status=deleted delete=%s result=%s", delete, delete_result)
                except Exception as exc:
                    self.logger.warning(
                        "op=get_original_blob status=delete_failed server=%s sha256=%s error=%s",
                        source_server_used,
                        orginal_record.blobsha256,
                        exc,
                    )
        else:
            self.logger.debug("op=get_original_blob status=no_decrypt_needed")
            blob_data = blob_retrieve.get_bytes()


        return blob_data, blob_type
    
    async def get_record_blobdata(
        self,
        record_name: str = None,
        record_kind: int = 37375,
        record_by_hash: str = None,
        record_origin: str = None,
        relays: List[str] | str | None = None,
    ) -> tuple[str | None, bytes | None]:
        blob_data: bytes = None
        blob_type:  str = None
        guessed_blob_type: str = None
        my_enc = NIP44Encrypt(self.k)

        blossom_servers = self.blossom_servers
        client = BlossomClient(nsec=None, default_servers=blossom_servers)

        
        if record_origin:
            record_name = ':'.join([record_origin,record_name])

        self.logger.debug("op=get_record_blobdata status=start kind=%s", record_kind)

        if record_by_hash:
            label_hash = record_by_hash
        else:
            label_hash = self._record_label_hash(record_name)
        
        decrypt_content = None
        
        # d_tag_encrypt = my_enc.encrypt(d_tag,to_pub_k=self.pubkey_hex)
        # a_tag = ["a", label_hash]
        # print("a_tag:",a_tag)
       
        self.logger.debug("op=get_record_blobdata status=query kind=%s", record_kind)
        
        # DEFAULT_RELAY = self.relays[0]
        FILTER = [{
            'limit': RECORD_LIMIT,
            'authors': [self.pubkey_hex],
            'kinds': [record_kind],
            '#d': [label_hash]   
            
            
        }]

        event = await self._async_get_wallet_info(
            FILTER,
            label_hash,
            relays=relays,
        )
        if not event:
            self.logger.warning(
                "op=get_record_blobdata status=missing kind=%s",
                record_kind,
            )
            return None, None
        
        # print(event.data())
        try:
            decrypt_content = my_enc.decrypt(event.content, self.pubkey_hex)
        except (ValueError, TypeError) as exc:
            self.logger.warning("op=get_record_blobdata status=decrypt_failed kind=%s error=%s", record_kind, exc)
            return None, None

        try:
            safebox_record: SafeboxRecord = SafeboxRecord(**json.loads(decrypt_content))
            blob_sha256 = safebox_record.blobsha256
            blob_type = safebox_record.blobtype
            if blob_sha256:
                blob_retrieve: BlossomBlob | None = None
                last_blob_error: Exception | None = None
                for server in blossom_servers:
                    try:
                        blob_retrieve = client.get_blob(
                            server=server,
                            sha256=blob_sha256,
                        )
                        break
                    except Exception as exc:
                        last_blob_error = exc
                if blob_retrieve is None:
                    raise RuntimeError(
                        f"Blob {blob_sha256} was not available from configured "
                        f"servers: {last_blob_error}"
                    )
                
                retrieved_bytes = blob_retrieve.get_bytes()
                if safebox_record.encryptparms is not None:
                    try:
                        blob_data = decrypt_and_verify_record_blob(
                            cipherbytes=retrieved_bytes,
                            encryptparms=safebox_record.encryptparms,
                            blobsha256=blob_sha256,
                            origsha256=safebox_record.origsha256,
                        )
                    except (ValueError, TypeError) as exc:
                        self.logger.warning(
                            "op=get_record_blobdata status=blob_integrity_failed kind=%s",
                            record_kind,
                        )
                        raise RuntimeError(
                            "Encrypted blob integrity verification failed"
                        ) from exc
                else:
                    # Compatibility path for records created before Acorn's
                    # encrypted blob metadata was introduced.
                    blob_data = retrieved_bytes
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.logger.warning("op=get_record_blobdata status=parse_failed kind=%s error=%s", record_kind, exc)
            return None, None

        if blob_data:
            guessed_blob_type = filetype.guess_mime(blob_data)
            # with NamedTemporaryFile(
            #   mode="wb",
            #    suffix=guessed_extension,
            #    dir = './tmp',
            #    delete=False
            #) as tmp:
            #    tmp.write(blob_data)
            #    tmp_path = tmp.name
            self.logger.debug(
                "op=get_record_blobdata status=ok kind=%s mime=%s",
                record_kind,
                guessed_blob_type,
            )

        return guessed_blob_type, blob_data

   
    def get_proofs(self):
        #TODO add in a group by keyset

        
        return self.proofs

    def _event_timestamp(self, event: Event) -> int:
        created_at = event.created_at
        if hasattr(created_at, "timestamp"):
            return int(created_at.timestamp())
        return int(created_at)

    async def _resolve_receive_relays_from_kind0(
        self,
        receive_pubkey: str,
        lookup_relays: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Find NIP-05 relay hints for a receiving pubkey via its kind 0 event."""

        relay_pool = self._normalize_relays(lookup_relays or self._build_discovery_relays())
        if not relay_pool:
            return {
                "receive_pubkey": receive_pubkey,
                "lookup_relays": [],
                "nip05": None,
                "relays": [],
                "verified": False,
                "reason": "no_lookup_relays",
            }

        query_filter = [{
            "limit": 1,
            "authors": [receive_pubkey],
            "kinds": [0],
        }]

        async with ClientPool(relay_pool) as c:
            events: List[Event] = await c.query(query_filter)

        if not events:
            return {
                "receive_pubkey": receive_pubkey,
                "lookup_relays": relay_pool,
                "nip05": None,
                "relays": [],
                "verified": False,
                "reason": "kind0_not_found",
            }

        event = sorted(events, key=self._event_timestamp, reverse=True)[0]
        try:
            profile = json.loads(event.content)
        except (json.JSONDecodeError, TypeError) as exc:
            return {
                "receive_pubkey": receive_pubkey,
                "lookup_relays": relay_pool,
                "kind0_event_id": str(event.id),
                "nip05": None,
                "relays": [],
                "verified": False,
                "reason": f"kind0_invalid_json: {exc}",
            }

        nip05 = profile.get("nip05") or profile.get("NIP05")
        if not nip05:
            return {
                "receive_pubkey": receive_pubkey,
                "lookup_relays": relay_pool,
                "kind0_event_id": str(event.id),
                "nip05": None,
                "relays": [],
                "verified": False,
                "reason": "nip05_not_found",
            }

        resolved_pubkey, resolved_relays = nip05_to_npub(str(nip05))
        if not resolved_pubkey or str(resolved_pubkey).lower() != str(receive_pubkey).lower():
            return {
                "receive_pubkey": receive_pubkey,
                "lookup_relays": relay_pool,
                "kind0_event_id": str(event.id),
                "nip05": str(nip05),
                "relays": [],
                "verified": False,
                "reason": "nip05_pubkey_mismatch",
                "resolved_pubkey": str(resolved_pubkey).lower() if resolved_pubkey else None,
            }

        return {
            "receive_pubkey": receive_pubkey,
            "lookup_relays": relay_pool,
            "kind0_event_id": str(event.id),
            "nip05": str(nip05),
            "relays": self._normalize_relays(resolved_relays),
            "verified": True,
        }

    async def send_ecash_transfer(
        self,
        amount: int,
        recipient: str,
        relay: str | None = None,
        comment: str = "ecash transfer",
        nonce: str | None = None,
        direct: bool = False,
        expiration: int | None = None,
    ) -> Dict[str, Any]:
        """Send ecash to another Acorn via encrypted relay event.

        Direct/debug mode publishes sender-authored kind 7378. Default
        gift-wrapped mode publishes a NIP-59 kind 1059 outer event containing
        an inner Acorn kind 7378 transfer.
        """

        if int(amount) <= 0:
            raise ValueError("amount must be positive")
        if expiration is not None:
            expiration = int(expiration)
            if expiration <= int(time()):
                raise ValueError("expiration must be a future Unix timestamp")

        recipient_pubkey, recipient_relays = self._resolve_pubkey_and_relays(recipient)
        transfer_relay_candidates = [relay] if relay else (recipient_relays or [self.home_relay])
        transfer_relays = self._normalize_relays(transfer_relay_candidates)
        if not transfer_relays:
            raise ValueError("No relay available for ecash transfer")
        nonce = nonce or secrets.token_hex(16)

        token = await self.issue_token(int(amount), comment=comment)

        payload = {
            "version": 1,
            "type": "cashu-token",
            "token": token,
            "mint": self.home_mint,
            "amount": int(amount),
            "unit": "sat",
            "comment": comment,
            "nonce": nonce,
        }

        async with ClientPool(transfer_relays) as c:
            if direct:
                my_enc = NIP44Encrypt(self.k)
                encrypted_payload = my_enc.encrypt(json.dumps(payload), to_pub_k=recipient_pubkey)
                tags = [
                    ["p", recipient_pubkey],
                    ["protocol", "acorn-ecash-transfer"],
                    ["v", "1"],
                    ["mint", self.home_mint],
                    ["amount", str(int(amount))],
                    ["unit", "sat"],
                    ["nonce", nonce],
                ]
                if expiration is not None:
                    tags.append(["expiration", str(expiration)])
                n_msg = Event(
                    kind=ECASH_TRANSFER_KIND,
                    content=encrypted_payload,
                    pub_key=self.pubkey_hex,
                    tags=tags,
                )
                n_msg.sign(self.privkey_hex)
                transient_pubkey = None
            else:
                my_gift = KindOtherGiftWrap(
                    BasicKeySigner(self.k),
                    kind_gift_wrap=ECASH_TRANSFER_GIFT_WRAP_KIND,
                    preserve_rumour_kind=True,
                )
                inner_evt = Event(
                    kind=ECASH_TRANSFER_KIND,
                    content=json.dumps(payload),
                    pub_key=self.pubkey_hex,
                    tags=[
                        ["p", recipient_pubkey],
                        ["protocol", "acorn-ecash-transfer"],
                        ["v", "1"],
                    ],
                )
                n_msg, transient_key = await my_gift.wrap(
                    inner_evt,
                    to_pub_k=recipient_pubkey,
                    expiration=expiration,
                )
                transient_pubkey = transient_key.public_key_hex()
            c.publish(n_msg)
            await asyncio.sleep(0.2)

        return {
            "status": "OK",
            "kind": n_msg.kind,
            "transfer_kind": ECASH_TRANSFER_KIND,
            "gift_wrap_kind": ECASH_TRANSFER_GIFT_WRAP_KIND if not direct else None,
            "event_id": n_msg.id,
            "recipient_pubkey": recipient_pubkey,
            "relays": transfer_relays,
            "recipient_relays": recipient_relays,
            "mode": "direct" if direct else "gift-wrapped",
            "transient_pubkey": transient_pubkey,
            "deletable_by_sender": bool(direct),
            "expiration": expiration,
            "amount": int(amount),
            "unit": "sat",
            "mint": self.home_mint,
            "nonce": nonce,
        }

    async def sweep_ecash_transfers(
        self,
        since: int | None = None,
        relays: List[str] | None = None,
        limit: int = RECORD_LIMIT,
        advance_cursor: bool = True,
        receive_nsec: str | None = None,
        event_id: str | None = None,
    ) -> Dict[str, Any]:
        """Accept Acorn ecash transfers addressed to this wallet.

        Receives standard NIP-59 kind 1059 gift wraps containing inner kind
        7378 transfers, legacy kind 7378 gift wraps, and direct sender-authored
        kind 7378 events.
        """

        receive_key = Keys(priv_k=receive_nsec) if receive_nsec else self.k
        receive_pubkey = receive_key.public_key_hex()
        target_event_id = str(event_id or "").strip()
        if target_event_id.startswith("note"):
            target_event_id = bech32_to_hex(target_event_id)
        if target_event_id:
            target_event_id = target_event_id.lower()
            if len(target_event_id) != 64 or not all(ch in string.hexdigits for ch in target_event_id):
                raise ValueError("event_id must be note1... or 64-char hex")
        relay_discovery: Dict[str, Any] | None = None
        if relays:
            relay_pool = self._normalize_relays(relays)
        elif receive_nsec:
            relay_discovery = await self._resolve_receive_relays_from_kind0(receive_pubkey)
            relay_pool = relay_discovery.get("relays") or self._normalize_relays([self.home_relay])
        else:
            relay_pool = self._normalize_relays([self.home_relay])
        cursor_label = (
            ECASH_TRANSFER_CURSOR_LABEL
            if receive_pubkey == self.pubkey_hex
            else f"{ECASH_TRANSFER_CURSOR_LABEL}:{receive_pubkey}"
        )
        cursor_from_record = False
        cursor = int(since or 0)
        if since is None:
            cursor_from_record = True
            try:
                cursor_raw = await self.get_wallet_info(cursor_label, record_kind=37376)
                cursor = int(cursor_raw) if cursor_raw else 0
            except (RuntimeError, ValueError, TypeError, KeyError, json.JSONDecodeError, httpx.HTTPError) as exc:
                self.logger.debug("op=sweep_ecash_transfers status=no_cursor error=%s", exc)
                cursor = 0

        if target_event_id:
            query_filter = [{
                "limit": 1,
                "ids": [target_event_id],
                "kinds": [ECASH_TRANSFER_GIFT_WRAP_KIND, ECASH_TRANSFER_KIND],
            }]
        else:
            query_filter = [{
                "limit": int(limit),
                "kinds": [ECASH_TRANSFER_GIFT_WRAP_KIND, ECASH_TRANSFER_KIND],
                "#p": [receive_pubkey],
            }]
        if cursor > 0 and not target_event_id:
            query_filter[0]["since"] = cursor + 1

        async with ClientPool(relay_pool) as c:
            events: List[Event] = await c.query(query_filter)

        events_sorted = sorted(events, key=self._event_timestamp)
        receive_enc = NIP44Encrypt(receive_key)
        receive_gift = KindOtherGiftWrap(BasicKeySigner(receive_key), kind_gift_wrap=ECASH_TRANSFER_GIFT_WRAP_KIND)
        legacy_receive_gift = KindOtherGiftWrap(BasicKeySigner(receive_key), kind_gift_wrap=ECASH_TRANSFER_KIND)
        accepted: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []
        latest_processed = cursor

        for each_event in events_sorted:
            event_ts = self._event_timestamp(each_event)
            try:
                sender_pubkey = each_event.pub_key
                mode = "direct"
                try:
                    gift_unwrapper = receive_gift
                    if getattr(each_event, "kind", None) == ECASH_TRANSFER_KIND:
                        gift_unwrapper = legacy_receive_gift
                    unwrapped_event = await gift_unwrapper.unwrap(each_event)
                    decrypted = unwrapped_event.content
                    sender_pubkey = unwrapped_event.pub_key
                    mode = "gift-wrapped"
                except Exception as unwrap_exc:
                    self.logger.debug(
                        "op=sweep_ecash_transfers status=unwrap_fallback event_id=%s error=%s",
                        each_event.id,
                        unwrap_exc,
                    )
                    if getattr(each_event, "kind", None) == ECASH_TRANSFER_GIFT_WRAP_KIND:
                        skipped.append({
                            "event_id": each_event.id,
                            "reason": "gift_wrap_not_addressed_to_receive_key",
                            "timestamp": event_ts,
                            "error": str(unwrap_exc),
                        })
                        latest_processed = max(latest_processed, event_ts)
                        continue
                    try:
                        decrypted = receive_enc.decrypt(each_event.content, each_event.pub_key)
                    except Exception as decrypt_exc:
                        failed.append({
                            "event_id": each_event.id,
                            "reason": "decrypt_failed",
                            "timestamp": event_ts,
                            "error": str(decrypt_exc),
                        })
                        latest_processed = max(latest_processed, event_ts)
                        continue
                payload = json.loads(decrypted)
                if payload.get("type") != "cashu-token":
                    skipped.append({
                        "event_id": each_event.id,
                        "reason": "unsupported_payload_type",
                        "timestamp": event_ts,
                    })
                    latest_processed = max(latest_processed, event_ts)
                    continue

                token = payload.get("token")
                if not token:
                    skipped.append({
                        "event_id": each_event.id,
                        "reason": "missing_token",
                        "timestamp": event_ts,
                    })
                    latest_processed = max(latest_processed, event_ts)
                    continue

                comment = payload.get("comment") or "ecash transfer received"
                history_comment = f"ecash transfer received from {sender_pubkey[:12]}: {comment}"
                msg_out, token_amount = await self.accept_token(
                    cashu_token=token,
                    comment=history_comment,
                    tendered_amount=payload.get("amount"),
                    tendered_currency=payload.get("unit", "SAT").upper(),
                )
                accepted.append({
                    "event_id": each_event.id,
                    "outer_kind": each_event.kind,
                    "inner_kind": getattr(unwrapped_event, "kind", None) if mode == "gift-wrapped" else None,
                    "sender_pubkey": sender_pubkey,
                    "outer_pubkey": each_event.pub_key,
                    "mode": mode,
                    "timestamp": event_ts,
                    "amount": token_amount,
                    "unit": "sat",
                    "message": msg_out,
                    "nonce": payload.get("nonce"),
                })
                latest_processed = max(latest_processed, event_ts)
            except (RuntimeError, ValueError, TypeError, KeyError, json.JSONDecodeError, httpx.HTTPError) as exc:
                failed.append({
                    "event_id": each_event.id,
                    "sender_pubkey": each_event.pub_key,
                    "timestamp": event_ts,
                    "reason": str(exc),
                })
                self.logger.warning(
                    "op=sweep_ecash_transfers status=failed event_id=%s error=%s",
                    each_event.id,
                    exc,
                )
                break

        if advance_cursor and latest_processed > cursor:
            await self.set_wallet_info(cursor_label, str(latest_processed), record_kind=37376)

        return {
            "status": "OK" if not failed else "PARTIAL",
            "kind": ECASH_TRANSFER_KIND,
            "relays": relay_pool,
            "relay_discovery": relay_discovery,
            "cursor_label": cursor_label,
            "query_filter": query_filter,
            "event_id": target_event_id or None,
            "receive_pubkey": receive_pubkey,
            "wallet_pubkey": self.pubkey_hex,
            "used_transient_receive_key": bool(receive_nsec),
            "since": cursor,
            "cursor_from_record": cursor_from_record,
            "latest_processed": latest_processed,
            "queried": len(events_sorted),
            "accepted": accepted,
            "skipped": skipped,
            "failed": failed,
            "accepted_count": len(accepted),
            "accepted_amount": sum(each["amount"] for each in accepted),
        }

    async def delete_ecash_transfer_events(
        self,
        relays: List[str] | None = None,
        recipient: str | None = None,
        since: int | None = None,
        until: int | None = None,
        limit: int = RECORD_LIMIT,
    ) -> Dict[str, Any]:
        """Delete kind 7378 transfer events authored by this wallet."""

        relay_pool = self._normalize_relays(relays or [self.home_relay])
        recipient_pubkey = self._resolve_pubkey_identifier(recipient) if recipient else None
        query_filter: Dict[str, Any] = {
            "limit": int(limit),
            "authors": [self.pubkey_hex],
            "kinds": [ECASH_TRANSFER_KIND],
        }
        if recipient_pubkey:
            query_filter["#p"] = [recipient_pubkey]
        if since is not None:
            query_filter["since"] = int(since)
        if until is not None:
            query_filter["until"] = int(until)

        async with ClientPool(relay_pool) as c:
            events: List[Event] = await c.query([query_filter])

        events_sorted = sorted(events, key=self._event_timestamp, reverse=True)
        event_ids: List[str] = []
        for each_event in events_sorted:
            event_id = str(each_event.id)
            if event_id not in event_ids:
                event_ids.append(event_id)

        if not event_ids:
            return {
                "status": "OK",
                "kind": ECASH_TRANSFER_KIND,
                "relays": relay_pool,
                "recipient_pubkey": recipient_pubkey,
                "matched": 0,
                "deleted": 0,
                "event_ids": [],
                "delete_event_id": None,
            }

        delete_result = await self.publish_deletion_request(
            event_ids=event_ids,
            kinds=[ECASH_TRANSFER_KIND],
            reason="delete acorn ecash transfer events",
            relays=relay_pool,
        )

        return {
            "status": "OK",
            "kind": ECASH_TRANSFER_KIND,
            "relays": relay_pool,
            "recipient_pubkey": recipient_pubkey,
            "matched": len(event_ids),
            "deleted": len(event_ids),
            "event_ids": event_ids,
            "delete_event_id": delete_result.get("event_id"),
            "delete_request": delete_result,
        }
            
    async def get_ecash_latest(self,since: int|None = None, relays: List[str]|None=None, nonce:str = None):
        ecash_out = []
        ecash_record = {}
        latest_dm = 0
        since_now = int(datetime.now(timezone.utc).timestamp())
      
        if not relays:
                relays = self.relays
        try:
            ecash_latest_raw = await self.get_wallet_info("ecash_latest", record_kind=37376)
            ecash_latest = int(ecash_latest_raw) if ecash_latest_raw is not None else 0
            
            self.logger.debug("op=get_ecash_latest status=start ecash_latest=%s relays=%s", ecash_latest, relays)
           
            
            user_records = await self.get_user_records(record_kind=21401, relays=relays, since=ecash_latest+1, reverse=True)
            
           

            for each in user_records:
                ecash_record["ecash"] = each["payload"]
                ecash_record["timestamp"] = each["timestamp"]
               
                # ecash_out.append(ecash_record)
                latest_dm = each["timestamp"] 
                self.logger.debug(
                    "op=get_ecash_latest status=processing age_seconds=%s timestamp=%s",
                    since_now - latest_dm,
                    latest_dm,
                )
                try:
                    ecash_nembed = parse_nembed_compressed(each["payload"])                    
                    token_to_redeem = ecash_nembed["token"]
                    receive_nonce = ecash_nembed.get("nonce", None)
                    tendered_amount = ecash_nembed.get("tendered_amount", None)
                    tendered_currency = ecash_nembed.get("tendered_currency", "SAT")
                    self.logger.debug(
                        "op=get_ecash_latest status=parsed_token nonce_match=%s",
                        bool(nonce and receive_nonce == nonce),
                    )
                    if nonce and receive_nonce == nonce:
                        self.logger.debug("op=get_ecash_latest status=matching_nonce")
                    else:
                        self.logger.debug("op=get_ecash_latest status=different_nonce")

                    msg_out, token_amount = await self.accept_token(
                        cashu_token=token_to_redeem,
                        comment=ecash_nembed["comment"],
                        tendered_amount=tendered_amount,
                        tendered_currency=tendered_currency,
                    )

                    if token_to_redeem == "nsf":
                        pass
                        self.logger.info("op=get_ecash_latest status=nsf_token")
                        # tendered_amount = ecash_nembed.get("tendered_amount", None)
                        # tendered_currency = ecash_nembed.get("tendered_currency", "SAT")
                        # ecash_out.append(("ERROR", 0,"SAT"))
                        # await self.add_tx_history(tx_type='X',amount=0, comment="PAYMENT UNSUCCESSFUL", tendered_amount=0, tendered_currency="NSF" )
                        ecash_out.append(("ADVISORY", 0, "SAT", "NSF", nonce, 0))
                    else:
                        self.logger.info("op=get_ecash_latest status=redeemed_ok")
                        self.logger.debug("op=get_ecash_latest status=record_payment tendered_currency=%s", tendered_currency)
                        # await self.add_tx_history(tx_type='C',amount=token_amount, comment=ecash_nembed["comment"], tendered_amount=tendered_amount, tendered_currency=tendered_currency )
                        ecash_out.append(("OK", tendered_amount, tendered_currency, "Payment OK", nonce, token_amount))
                    
                    
                except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                    ecash_out.append(("ERROR", 0,"SAT", "Redemption"))
                    pass
                
                   
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            self.logger.debug("op=get_ecash_latest status=init_latest_record error=%s", exc)
            await self.set_wallet_info("ecash_latest", "0", record_kind=37376)
            
        self.logger.debug("op=get_ecash_latest status=complete latest_dm=%s", latest_dm)
        if latest_dm > 0:
            await self.set_wallet_info("ecash_latest", str(latest_dm), record_kind=37376)
        # print(f"since now: {since_now} {latest_dm} {since_now-latest_dm}")
        # print(f"total messages: {len(ecash_out)} received for {self.handle}")
        

        return ecash_out

        
        
    def set_index_info(self,index_info: str):
        asyncio.run(self._async_set_index_info(index_info))  
    
    async def _async_set_index_info(self, index_info: str):
        
        self.logger.debug("op=set_index_info status=update")
        my_enc = NIP44Encrypt(self.k)
        index_info_encrypt = my_enc.encrypt(index_info,to_pub_k=self.pubkey_hex)
    

        async with ClientPool([self.home_relay]) as c:
        # async with Client(relay) as c:
            n_msg = Event(kind=17375,
                        content=index_info_encrypt,
                        pub_key=self.pubkey_hex
                        )
            
            # n_msg = my_enc.encrypt_event(evt=n_msg,
            #                         to_pub_k=self.pubkey_hex)
            
            n_msg.sign(self.privkey_hex)
            self.logger.debug("op=set_index_info status=published event_id=%s", n_msg.id)
            c.publish(n_msg)
            # await asyncio.sleep(1)

    def get_index_info(self):
        my_enc = NIP44Encrypt(self.k)
        
        DEFAULT_RELAY = self.relays[0]
        FILTER = [{
            'limit': RECORD_LIMIT,
            'authors': [self.pubkey_hex],
            'kinds': [17375]
            
        }]
        try:
            event =asyncio.run(self._async_get_index_info(FILTER))
        
            # print(event.data())
            decrypt_content = my_enc.decrypt(event.content, self.pubkey_hex)

            index_obj = json.loads(decrypt_content)

            return index_obj
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            return None
    
    async def _async_get_index_info(self, filter: List[dict]):
    # does a one off query to relay prints the events and exits
        # print("filter", filter[0]['d'])
        my_enc = NIP44Encrypt(self.k)
        
        event_select = None
        async with ClientPool([self.home_relay]) as c:
        # async with Client(relay) as c:
            
            events = await c.query(filter)
            
            # print(f"{filter} events: {len(events)}")
  
            
            return events[0]
        
    async def transfer_blob(
        self,
        record_name,
        record_kind: int = 37375,
        record_origin: str = None,
        blobxfer: str = None,
        blossom_xfer_server: str | None = None,
        blossom_home_server: str | None = None,
    ) -> Dict[str, Any]:
        """Transfer source blob to wallet blob store and attach metadata to record."""
        self.logger.debug("op=transfer_blob status=start kind=%s", record_kind)
        blossom_server = self._default_blossom_home_server()
        default_xfer_server = self._default_blossom_xfer_server()
        source_xfer = blossom_xfer_server or default_xfer_server
        source_home = blossom_home_server or blossom_server
        source_servers: List[str] = []
        for server in [source_xfer, source_home]:
            if server and server not in source_servers:
                source_servers.append(server)

        if record_origin:
            record_name = ':'.join([record_origin, record_name])

        if not blobxfer:
            return {"status": "SKIPPED", "reason": "no_blobxfer"}

        try:
            blobxfer_obj: OriginalRecordTransfer = OriginalRecordTransfer.model_validate_json(blobxfer)
        except (ValueError, TypeError) as exc:
            self.logger.warning(
                "op=transfer_blob status=invalid_blobxfer kind=%s error=%s",
                record_kind,
                exc,
            )
            return {"status": "INVALID_BLOBXFER", "reason": str(exc)}

        self.logger.debug("op=transfer_blob status=validated kind=%s", record_kind)
        try:
            client_xfer = BlossomClient(nsec=blobxfer_obj.blobnsec, default_servers=source_servers)
            blob_retrieve: BlossomBlob | None = None
            source_server_used: str | None = None
            last_fetch_error: str | None = None
            for source_server in source_servers:
                try:
                    blob_retrieve = client_xfer.get_blob(
                        server=source_server,
                        sha256=blobxfer_obj.blobsha256,
                    )
                    source_server_used = source_server
                    break
                except Exception as exc:
                    last_fetch_error = str(exc)
                    if exc.__class__.__name__ == "BlobNotFound":
                        self.logger.info(
                            "op=transfer_blob status=source_missing kind=%s sha256=%s server=%s",
                            record_kind,
                            blobxfer_obj.blobsha256,
                            source_server,
                        )
                    else:
                        self.logger.warning(
                            "op=transfer_blob status=fetch_failed kind=%s server=%s error=%s",
                            record_kind,
                            source_server,
                            exc,
                        )

            if not blob_retrieve:
                self.logger.warning(
                    "op=transfer_blob status=not_available kind=%s sha256=%s tried=%s error=%s",
                    record_kind,
                    blobxfer_obj.blobsha256,
                    source_servers,
                    last_fetch_error,
                )
                return {"status": "NOT_FOUND", "reason": "original_record_not_available"}

            try:
                delete_result = client_xfer.delete_blob(
                    server=source_server_used,
                    sha256=blobxfer_obj.blobsha256,
                )
                self.logger.debug("op=transfer_blob status=source_deleted success=%s", bool(delete_result))
            except Exception as exc:
                self.logger.warning(
                    "op=transfer_blob status=source_delete_failed kind=%s error=%s",
                    record_kind,
                    exc,
                )

            if blob_retrieve.mime_type != "application/octet-stream":
                return {"status": "INVALID_SOURCE_MIME", "reason": blob_retrieve.mime_type}

            try:
                blob_data = decrypt_bytes(
                    cipherbytes=blob_retrieve.get_bytes(),
                    key=bytes.fromhex(blobxfer_obj.encryptparms.key),
                    iv=bytes.fromhex(blobxfer_obj.encryptparms.iv),
                )
            except (ValueError, TypeError) as exc:
                self.logger.warning("op=transfer_blob status=decrypt_failed error=%s", exc)
                return {"status": "DECRYPT_FAILED", "reason": str(exc)}

            resultsha256 = hashlib.sha256(blob_data).hexdigest()
            if resultsha256 != blobxfer_obj.origsha256:
                self.logger.warning(
                    "op=transfer_blob status=hash_mismatch expected=%s got=%s",
                    blobxfer_obj.origsha256,
                    resultsha256,
                )
                return {"status": "HASH_MISMATCH", "reason": "transferred_hash_mismatch"}

            guessed_blob_type = filetype.guess_mime(blob_data) or "application/octet-stream"
            self.logger.debug("op=transfer_blob status=decrypted mime=%s", guessed_blob_type)

            safebox_record = await self.get_record_safebox(record_name=record_name, record_kind=record_kind)
            self.logger.debug("op=transfer_blob status=loaded_record")

            blob_key = os.urandom(32)
            encrypt_result: EncryptionResult = encrypt_bytes(blob_data, blob_key)
            encrypt_parms = EncryptionParms(
                alg=encrypt_result.alg,
                key=blob_key.hex(),
                iv=encrypt_result.iv.hex(),
            )

            final_blob_data = encrypt_result.cipherbytes
            client = BlossomClient(nsec=self.privkey_bech32, default_servers=[blossom_server])
            upload_result = client.upload_blob(
                blossom_server,
                data=final_blob_data,
                description='Blob to server',
            )
            sha256 = upload_result['sha256']
            blob_ref = upload_result.get('url', f"{blossom_server}/{sha256}")

            self.logger.debug("op=transfer_blob status=uploaded sha256=%s", sha256)
            updated_safebox_record = SafeboxRecord(
                tag=safebox_record.tag,
                type=safebox_record.type,
                payload=safebox_record.payload,
                blobref=blob_ref,
                blobtype=guessed_blob_type,
                blobsha256=sha256,
                origsha256=blobxfer_obj.origsha256,
                encryptparms=encrypt_parms,
            )
            record_json_str = updated_safebox_record.model_dump_json()

            await self.update_tags([["user_record", record_name, "generic"]])
            await self.set_wallet_info(record_name, record_json_str, record_kind=record_kind)
            await self.set_wallet_config()
            return {"status": "OK", "blobref": blob_ref, "blobsha256": sha256}

        except (ValueError, TypeError, RuntimeError, KeyError) as exc:
            self.logger.warning(
                "op=transfer_blob status=processing_failed kind=%s error=%s",
                record_kind,
                exc,
            )
            return {"status": "PROCESSING_FAILED", "reason": str(exc)}

    @staticmethod
    def _record_transfer_server_allowed(
        server: str,
        allowed_servers: List[str] | None,
    ) -> bool:
        if not allowed_servers:
            return True
        normalized = server.rstrip("/").lower()
        return normalized in {
            str(candidate).rstrip("/").lower() for candidate in allowed_servers
        }

    def _read_record_transfer(
        self,
        descriptor_value: str,
        *,
        allowed_servers: List[str] | None = None,
        presentation: bool = False,
    ) -> tuple[RecordTransferDescriptor, RecordTransferEnvelope, BlossomClient]:
        descriptor = (
            decode_record_presentation_descriptor(descriptor_value)
            if presentation
            else decode_record_transfer_descriptor(descriptor_value)
        )
        if not self._record_transfer_server_allowed(
            descriptor.server,
            allowed_servers,
        ):
            raise RecordTransferError(
                "Record transfer server is not allowed by this application"
            )
        authority_nsec = Keys(
            priv_k=derive_record_transfer_authority_hex(descriptor.secret)
        ).private_key_bech32()
        client = BlossomClient(
            nsec=authority_nsec,
            default_servers=[descriptor.server],
        )
        try:
            retrieved = client.get_blob(
                server=descriptor.server,
                sha256=descriptor.ciphertext_sha256,
            )
        except Exception as exc:
            raise RecordTransferError(
                "Temporary record transfer is not available"
            ) from exc
        ciphertext = retrieved.get_bytes()
        verify_record_transfer_ciphertext(ciphertext, descriptor)
        envelope = decrypt_record_transfer_envelope(
            ciphertext,
            secret=descriptor.secret,
        )
        expected_capability = "presentation" if presentation else "transfer"
        if envelope.capability != expected_capability:
            raise RecordTransferError(
                f"Record capability is {envelope.capability}, not {expected_capability}"
            )
        return descriptor, envelope, client

    async def create_record_transfer(
        self,
        record_name: str,
        *,
        expires_in: int = 3600,
        blossom_transfer_server: str | None = None,
        _capability: str = "transfer",
    ) -> Dict[str, Any]:
        """Create a short-lived encrypted bearer transfer for one record."""

        if not isinstance(expires_in, int) or not 60 <= expires_in <= 30 * 24 * 60 * 60:
            raise ValueError("Record transfer lifetime must be between 60 seconds and 30 days")
        record = await self.get_record_safebox(record_name=record_name)
        blob_type = None
        blob_data = None
        if record.blobref:
            blob_type, blob_data = await self.get_record_blobdata(record_name=record_name)
            if blob_data is None:
                raise RuntimeError("Original Record could not be loaded for sharing")
        ciphertext, secret = encrypt_record_transfer_envelope(
            RecordTransferEnvelope(
                label=record_name,
                record_type=str(record.type),
                payload=record.payload,
                blob_data=blob_data,
                blob_type=blob_type or record.blobtype,
                capability=_capability,
            )
        )
        server = (blossom_transfer_server or self._default_blossom_xfer_server()).rstrip("/")
        authority_nsec = Keys(
            priv_k=derive_record_transfer_authority_hex(secret)
        ).private_key_bech32()
        client = BlossomClient(nsec=authority_nsec, default_servers=[server])
        upload = client.upload_blob(
            server,
            data=ciphertext,
            description=f"Temporary Acorn record {_capability}",
        )
        ciphertext_sha256 = hashlib.sha256(ciphertext).hexdigest()
        uploaded_sha256 = str(upload.get("sha256", "")).lower()
        if uploaded_sha256 != ciphertext_sha256:
            raise RuntimeError("Transfer server returned an unexpected ciphertext hash")
        blob_url = upload.get("url") or f"{server}/{ciphertext_sha256}"
        expires_at = int(time()) + expires_in
        descriptor_value = RecordTransferDescriptor(
                blob_url=str(blob_url),
                ciphertext_sha256=ciphertext_sha256,
                secret=secret,
                expires_at=expires_at,
            )
        descriptor = (
            encode_record_presentation_descriptor(descriptor_value)
            if _capability == "presentation"
            else encode_record_transfer_descriptor(descriptor_value)
        )
        return {
            "descriptor": descriptor,
            "expires_at": expires_at,
            "label": record_name,
            "has_original": blob_data is not None,
            "server": server,
            "ciphertext_sha256": ciphertext_sha256,
        }

    async def create_record_presentation(
        self,
        record_name: str,
        *,
        expires_in: int = 3600,
        blossom_transfer_server: str | None = None,
    ) -> Dict[str, Any]:
        """Create a view-only record presentation bearer capability."""

        return await self.create_record_transfer(
            record_name,
            expires_in=expires_in,
            blossom_transfer_server=blossom_transfer_server,
            _capability="presentation",
        )

    async def inspect_record_transfer(
        self,
        descriptor_value: str,
        *,
        allowed_servers: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Validate and decrypt transfer metadata without storing the record."""

        descriptor, envelope, _ = self._read_record_transfer(
            descriptor_value,
            allowed_servers=allowed_servers,
        )
        return {
            "label": envelope.label,
            "record_type": envelope.record_type,
            "has_original": envelope.blob_data is not None,
            "blob_type": envelope.blob_type,
            "expires_at": descriptor.expires_at,
            "server": descriptor.server,
        }

    async def inspect_record_presentation(
        self,
        descriptor_value: str,
        *,
        allowed_servers: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Decrypt presentation content for display without storing it."""

        descriptor, envelope, _ = self._read_record_transfer(
            descriptor_value,
            allowed_servers=allowed_servers,
            presentation=True,
        )
        return {
            "label": envelope.label,
            "record_type": envelope.record_type,
            "payload": envelope.payload,
            "has_original": envelope.blob_data is not None,
            "blob_data": envelope.blob_data,
            "blob_type": envelope.blob_type,
            "blob_sha256": (
                hashlib.sha256(envelope.blob_data).hexdigest()
                if envelope.blob_data is not None
                else None
            ),
            "expires_at": descriptor.expires_at,
            "server": descriptor.server,
        }

    async def delete_record_transfer(
        self,
        descriptor_value: str,
        *,
        allowed_servers: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Delete a temporary transfer using its transfer-scoped authority."""

        normalized_descriptor = str(descriptor_value or "").strip()
        descriptor = (
            decode_record_presentation_descriptor(
                normalized_descriptor,
                require_unexpired=False,
            )
            if normalized_descriptor.lower().startswith(RECORD_PRESENTATION_PREFIX)
            else decode_record_transfer_descriptor(
                normalized_descriptor,
                require_unexpired=False,
            )
        )
        if not self._record_transfer_server_allowed(
            descriptor.server,
            allowed_servers,
        ):
            raise RecordTransferError(
                "Record transfer server is not allowed by this application"
            )
        authority_nsec = Keys(
            priv_k=derive_record_transfer_authority_hex(descriptor.secret)
        ).private_key_bech32()
        client = BlossomClient(
            nsec=authority_nsec,
            default_servers=[descriptor.server],
        )
        try:
            client.delete_blob(
                server=descriptor.server,
                sha256=descriptor.ciphertext_sha256,
            )
        except Exception as exc:
            self.logger.warning(
                "op=delete_record_transfer status=failed error_type=%s",
                type(exc).__name__,
            )
            raise RecordTransferError(
                "Temporary record transfer deletion could not be confirmed"
            ) from exc
        return {
            "status": "DELETED",
            "transfer_deleted": True,
            "server": descriptor.server,
            "ciphertext_sha256": descriptor.ciphertext_sha256,
        }

    async def accept_record_transfer(
        self,
        descriptor_value: str,
        *,
        record_name: str | None = None,
        allowed_servers: List[str] | None = None,
        delete_transfer: bool = True,
    ) -> Dict[str, Any]:
        """Import a transfer and delete its temporary ciphertext after storage."""

        descriptor, envelope, client = self._read_record_transfer(
            descriptor_value,
            allowed_servers=allowed_servers,
        )
        destination_label = str(record_name or envelope.label).strip()
        if not destination_label:
            raise RecordTransferError("Record transfer destination label is required")
        await self.put_record(
            destination_label,
            envelope.payload,
            record_type=envelope.record_type,
            blob_data=envelope.blob_data,
        )
        deleted = False
        delete_error = None
        if delete_transfer:
            try:
                client.delete_blob(
                    server=descriptor.server,
                    sha256=descriptor.ciphertext_sha256,
                )
                deleted = True
            except Exception as exc:
                delete_error = str(exc)
                self.logger.warning(
                    "op=accept_record_transfer status=cleanup_failed error_type=%s",
                    type(exc).__name__,
                )
        return {
            "status": "OK",
            "label": destination_label,
            "has_original": envelope.blob_data is not None,
            "transfer_deleted": deleted,
            "cleanup_error": delete_error,
        }

    async def put_record(
        self,
        record_name,
        record_value,
        record_type="generic",
        record_kind: int = 37375,
        record_origin: str = None,
        blob_data: bytes = None,
        relays: List[str] | str | None = None,
        verify_timeout: float = 8.0,
        return_result: bool = False,
        preserve_existing_blob: bool = False,
    ):
        if record_origin:
            record_name = ':'.join([record_origin,record_name])

        self.logger.debug("op=put_record status=start kind=%s", record_kind)
        base_label = record_name.split(":", 1)[-1] if record_origin else record_name
        if (
            record_name in INTERNAL_RECORD_LABELS
            or base_label in INTERNAL_RECORD_LABELS
            or str(record_name).startswith("__acorn_")
        ):
            raise ValueError(
                f"{record_name!r} is reserved for Acorn internal state"
            )

        blossom_server = self._default_blossom_home_server()
        mime_type_guess = None
        origsha256 = None
        encrypt_parms = None
        blob_ref = None
        sha256 = None
        existing_blob = None
        if preserve_existing_blob:
            try:
                candidate = await self.get_record_safebox(
                    record_name=record_name,
                    record_kind=record_kind,
                    relays=relays,
                )
            except ValueError as exc:
                if "No event found" not in str(exc):
                    raise
            else:
                if candidate.blobref:
                    existing_blob = candidate

        if blob_data:
            self.logger.debug("op=put_record status=blob_upload_start")
            origsha256 = hashlib.sha256(blob_data).hexdigest()
            guessed = filetype.guess(blob_data)
            mime_type_guess = (
                guessed.mime if guessed else "application/octet-stream"
            )
            blob_key = os.urandom(32)
            encrypt_result: EncryptionResult = encrypt_bytes(blob_data, blob_key)
            encrypt_parms = EncryptionParms(
                alg=encrypt_result.alg,
                key=blob_key.hex(),
                iv=encrypt_result.iv.hex(),
            )
            client = BlossomClient(
                nsec=self.privkey_bech32,
                default_servers=[blossom_server],
            )
            upload_result = client.upload_blob(
                blossom_server,
                data=encrypt_result.cipherbytes,
                description="Blob to server",
            )
            sha256 = upload_result["sha256"]
            blob_ref = upload_result.get(
                "url",
                f"{blossom_server}/{sha256}",
            )
            self.logger.debug(
                "op=put_record status=blob_uploaded sha256=%s",
                sha256,
            )
        elif existing_blob is not None:
            # Updating a record's payload must not silently detach its existing
            # encrypted attachment. The relay record remains authoritative for
            # the attachment metadata and decryption material.
            blob_ref = existing_blob.blobref
            mime_type_guess = existing_blob.blobtype
            sha256 = existing_blob.blobsha256
            origsha256 = existing_blob.origsha256
            encrypt_parms = existing_blob.encryptparms

        record_obj = SafeboxRecord(
            tag=[record_name],
            type=record_type,
            payload=record_value,
            blobref=blob_ref,
            blobtype=mime_type_guess,
            blobsha256=sha256,
            origsha256=origsha256,
            encryptparms=encrypt_parms,
        )
        record_json_str = record_obj.model_dump_json()
        write_relays = self._record_relay_pool(relays)

        try:
            publish_result = await self.set_wallet_info(
                record_name,
                record_json_str,
                replicate_relays=write_relays,
                record_kind=record_kind,
                verify=True,
                verify_timeout=verify_timeout,
            )
        except Exception:
            if sha256:
                with contextlib.suppress(Exception):
                    BlossomClient(
                        nsec=self.privkey_bech32,
                        default_servers=[blossom_server],
                    ).delete_blob(server=blossom_server, sha256=sha256)
            raise

        # The encrypted event is authoritative. The legacy wallet index is a
        # rebuildable compatibility cache and is updated only after readback.
        await self.update_tags([["user_record", record_name, record_type]])
        await self.set_wallet_config()

        replaced_blob_cleanup = None
        if (
            existing_blob is not None
            and blob_data
            and existing_blob.blobsha256
            and existing_blob.blobsha256 != sha256
        ):
            replaced_blob_cleanup = {
                "sha256": existing_blob.blobsha256,
                "deleted": False,
                "servers": [],
            }
            client = BlossomClient(
                nsec=self.privkey_bech32,
                default_servers=self.blossom_servers,
            )
            for server in self.blossom_servers:
                try:
                    client.delete_blob(server=server, sha256=existing_blob.blobsha256)
                    replaced_blob_cleanup["servers"].append(
                        {"server": server, "deleted": True}
                    )
                    replaced_blob_cleanup["deleted"] = True
                except Exception as exc:
                    replaced_blob_cleanup["servers"].append(
                        {"server": server, "deleted": False, "error": str(exc)}
                    )
        if return_result:
            return {
                "status": "OK",
                "label": record_name,
                "kind": int(record_kind),
                "event_id": publish_result["event_id"],
                "relays": publish_result["relays"],
                "verified": publish_result["verified"],
                "verification": publish_result["verification"],
                "blobref": blob_ref,
                "blobsha256": sha256,
                "replaced_blob_cleanup": replaced_blob_cleanup,
            }
        return record_name
    
    async def update_tags(self,tag_values):
        
        for tag_value in tag_values:
            if tag_value[0]=="user_record":
                if tag_value in self.acorn_tags:
                    self.logger.debug("op=update_tags status=user_record_exists")
                else:
                    self.acorn_tags.append(tag_value)
            elif tag_value[0]=="balance":
                for index, each in enumerate(self.acorn_tags):
                    if each[0]=="balance":
                        self.acorn_tags[index]=tag_value
            elif tag_value[0] == "owner":
                for index, each in enumerate(self.acorn_tags):
                    if each[0]=="owner":
                        self.acorn_tags[index]=tag_value
            elif tag_value[0] == "local_currency":
                for index, each in enumerate(self.acorn_tags):
                    if each[0]=="local_currency":
                        self.acorn_tags[index]=tag_value
            elif tag_value[0] == "ecash_latest":
                for index, each in enumerate(self.acorn_tags):
                    if each[0]=="ecash_latest":
                        self.acorn_tags[index]=tag_value
            
        
        # print(f"update tags: {self.acorn_tags}")
        await self.set_wallet_info(label=self.name,label_info=json.dumps(self.acorn_tags))

    async def _mint_proofs(self, quote:str, amount:int, mint:str=None):
        # print("mint proofs")
        lock_acquired = False
        try:
            await self.acquire_lock()
            lock_acquired = True
            headers = { "Content-Type": "application/json"}
            timeout = httpx.Timeout(20.0, connect=5.0)
            mint_base_url = normalize_mint_url(mint or self.home_mint)
            keyset_url = f"{mint_base_url}/v1/keysets"

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(keyset_url, headers=headers)
                response.raise_for_status()
                keysets_json = response.json()

                keyset = keysets_json['keysets'][0]['id']
                keysets_obj = KeysetsResponse(**keysets_json)

            self.known_mints[keysets_obj.keysets[0].id] = mint_base_url

            # print("id:", keysets_obj.keysets[0].id)

            blinded_messages=[]
            blinded_values =[]
            powers_of_2 = powers_of_2_sum(int(amount))
            
            
            for each in powers_of_2:
                secret = secrets.token_hex(32)
                B_, r, Y = step1_alice(secret)
                blinded_values.append((B_,r, secret, Y))
                
                blinded_messages.append(    BlindedMessage( amount=each,
                                                            id=keyset,
                                                            B_=B_.serialize().hex(),
                                                            Y = Y.serialize().hex(),
                                                            ).model_dump()
                                                            
                                        )
            # print("blinded values, blinded messages:", blinded_values, blinded_messages)
            mint_url = f"{mint_base_url}/v1/mint/bolt11"


            # blinded_message = BlindedMessage(amount=amount,id=keyset,B_=B_.serialize().hex())
            # print(blinded_message)
            request_body = {
                                "quote"     : quote,
                                "outputs"   : blinded_messages
                            }
            # print(request_body)
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(mint_url, json=request_body, headers=headers)
                response.raise_for_status()
                promises = response.json()['signatures']
                # print("promises:", promises)
           

            
            mint_key_url = f"{mint_base_url}/v1/keys/{keyset}"

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(mint_key_url, headers=headers)
                response.raise_for_status()
                keys = response.json()["keysets"][0]["keys"]

            proof_objs = []
            i = 0
            
            for each in promises:
                pub_key_c = PublicKey()
                # print("each:", each['C_'])
                pub_key_c.deserialize(unhexlify(each['C_']))
                promise_amount = each['amount']
                A = keys[str(int(promise_amount))]
                # A = keys[str(j)]
                pub_key_a = PublicKey()
                pub_key_a.deserialize(unhexlify(A))
                r = blinded_values[i][1]
                # print(pub_key_c, promise_amount,A, r)
                C = step3_alice(pub_key_c,r,pub_key_a)
                
                proof = Proof ( amount= promise_amount,
                            id = keyset,
                            secret=blinded_values[i][2],
                            C=C.serialize().hex(),
                            Y=blinded_values[i][3].serialize().hex()
                )

                proof_objs.append(proof)
                
                i+=1
            
            self.logger.debug(
                "op=mint_proofs status=received proofs=%s amount=%s",
                len(proof_objs),
                sum(each.amount for each in proof_objs),
            )

            # Persist and verify the newly minted bearer proofs before exposing
            # them through the in-memory wallet state. Callers such as the CLI
            # and Safebox Web write transaction history immediately after this
            # method returns, so self.balance must represent the post-deposit
            # balance rather than the state loaded before minting.
            await self.add_proofs_obj(proof_objs, verify=True)
            self.proofs = self._deduplicate_proofs([*self.proofs, *proof_objs])
            self.balance = sum(each.amount for each in self.proofs)
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
            self.logger.error(
                "op=mint_proofs status=failed amount=%s mint=%s error=%s",
                amount,
                mint,
                e,
            )
            raise RuntimeError(f"Error in mint_proofs ({type(e).__name__}): {e}") from e
        
        finally:
            if lock_acquired:
                await self.release_lock()

        return True

    async def check_quote(self, quote:str, amount:int, mint:str = None):
        self.logger.debug("op=check_quote status=start amount=%s mint=%s", amount, mint)
        
        

        success_mint = True  
        lninvoice = None  
          
        mint_base_url = normalize_mint_url(mint or self.home_mint)
        url = f"{mint_base_url}/v1/mint/quote/bolt11/{quote}"

        self.logger.debug("op=check_quote status=request mint=%s", mint or self.home_mint)

        headers = { "Content-Type": "application/json"}
        timeout = httpx.Timeout(10.0, connect=5.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                mint_quote = mintQuote(**response.json())
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            self.logger.warning(
                "op=check_quote status=failed amount=%s mint=%s error=%s",
                amount,
                mint,
                exc,
            )
            return False, None

        if mint_quote.paid == True:
            self.logger.debug("op=check_quote status=paid amount=%s", amount)
            try:
                success_mint = await self._mint_proofs(mint_quote.quote, amount, mint_base_url)
            except (RuntimeError, httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
                # Treat minting failures as transient so polling can continue and/or timeout cleanly.
                self.logger.warning(
                    "op=check_quote status=mint_failed amount=%s mint=%s error=%s",
                    amount,
                    mint,
                    exc,
                )
                return False, None
            lninvoice = mint_quote.request
        else:
            success_mint = False
      

        return success_mint, lninvoice
        
       
        # return await self._check_quote(quote, amount,mint)
    
    async def async_deposit(self, amount:int, mint:str = None)->cliQuote:
        mint_base_url = normalize_mint_url(mint or self.home_mint)
        url = f"{mint_base_url}/v1/mint/quote/bolt11"
       
        headers = { "Content-Type": "application/json"}
        mint_request = mintRequest(amount=amount)
        payload_json = mint_request.model_dump_json()
        timeout = httpx.Timeout(10.0, connect=5.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, data=payload_json, headers=headers)
                response.raise_for_status()
                response_json = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            self.logger.error(
                "op=async_deposit amount=%s mint=%s url=%s error=%s",
                amount,
                mint,
                url,
                exc,
            )
            raise RuntimeError(f"Deposit quote request failed: {exc}") from exc

        mint_quote = mintQuote(**response_json)
        invoice = response_json['request']
        quote = response_json['quote']
        self.logger.debug("op=async_deposit quote_received amount=%s mint_url=%s", amount, url)
        # print(self.powers_of_2_sum(int(amount)))
        # add quote as a replaceable event

        wallet_quote_list =[]
        
        success, lninvoice = await self.poll_for_payment(
            quote=quote,
            amount=amount,
            mint=mint_base_url,
        )

        return success, lninvoice 
        
       
    
    def deposit(self, amount:int, mint:str = None)->cliQuote:
        mint_base_url = normalize_mint_url(mint or self.home_mint)
        url = f"{mint_base_url}/v1/mint/quote/bolt11"
        try:
            headers = { "Content-Type": "application/json"}
            mint_request = mintRequest(amount=amount)
            mint_request_dump = mint_request.model_dump()
            payload_json = mint_request.model_dump_json()
            # Retry transient DNS/connect/read failures common on high-latency links.
            attempts = 4
            connect_timeout = 4.0
            read_timeout = 8.0
            last_error = None
            response = None
            for attempt in range(1, attempts + 1):
                try:
                    response = requests.post(
                        url,
                        data=payload_json,
                        headers=headers,
                        timeout=(connect_timeout, read_timeout),
                    )
                    status_code = getattr(response, "status_code", 200)
                    if 400 <= status_code < 500 and status_code not in (408, 429):
                        raise RuntimeError(
                            f"Mint quote request was rejected with HTTP {status_code} at {url}"
                        )
                    response.raise_for_status()
                    break
                except requests.exceptions.RequestException as exc:
                    last_error = exc
                    self.logger.warning(
                        "op=deposit status=quote_retry_failed attempt=%s/%s url=%s error=%s",
                        attempt,
                        attempts,
                        url,
                        exc,
                    )
                    if attempt < attempts:
                        sleep(0.4 * attempt)
                        continue
                    status_code = getattr(getattr(exc, "response", None), "status_code", None)
                    if status_code is not None:
                        raise RuntimeError(
                            f"Mint quote request failed after {attempts} attempts with HTTP "
                            f"{status_code} at {url}"
                        ) from exc
                    raise RuntimeError(
                        f"Mint quote endpoint was unreachable or timed out after {attempts} "
                        f"attempts at {url}"
                    ) from exc

            if response is None:
                raise RuntimeError(f"Mint quote endpoint unavailable at {url}: {last_error}")

            mint_quote = mintQuote(**response.json())
            # print(mint_quote)
            invoice = response.json()['request']
            quote = response.json()['quote']
            self.logger.debug("op=deposit status=invoice_received")
            # print(self.powers_of_2_sum(int(amount)))
            # add quote as a replaceable event

            wallet_quote_list =[]
            

        except RuntimeError:
            raise
        except (
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
            httpx.HTTPError,
            requests.exceptions.RequestException,
        ) as e:
            raise RuntimeError(f"Deposit failed for mint {mint_base_url}: {e}") from e
         
        return cliQuote(invoice=invoice, quote=quote, mint_url=url)
        # return f"Please pay invoice \n{invoice} \nfor quote: \n{quote}."
    
    async def poll_for_payment(self, quote:str, amount: int, mint:str=None):
        start_time = time()  # Record the start time
        end_time = start_time + 120  # Set the loop to run for 120 seconds
        success = False
        lninvoice = None
        mint_base_url = normalize_mint_url(mint or self.home_mint)

        while time() < end_time:
            self.logger.debug("op=poll_for_payment status=checking amount=%s mint=%s", amount, mint_base_url)
            success, lninvoice = await self.check_quote(
                quote=quote,
                amount=amount,
                mint=mint_base_url,
            )
            if success:
                self.logger.info("op=poll_for_payment status=paid amount=%s", amount)
                break
            elapsed = time() - start_time
            # Faster polling in the early window for better UX, then taper.
            if elapsed < 20:
                await asyncio.sleep(1)
            elif elapsed < 60:
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(3)

        self.logger.debug("op=poll_for_payment status=done amount=%s", amount)
        if not success:
            self.logger.warning("op=poll_for_payment status=timeout amount=%s", amount)
            raise TimeoutError("Polling has timed out.")
        return success, lninvoice
        
    
    def withdraw(self, lninvoice:str):

        msg_out = asyncio.run(self.pay_multi_invoice(lninvoice=lninvoice))
        
        return msg_out

    async def add_proofs_obj(
        self,
        proofs_arg: List[Proof],
        replicate_relays: List[str] = None,
        verify: bool = False,
        verify_timeout: float = 8.0,
    ):
        
        records_to_write = []
        # my_enc = NIP44Encrypt(self.k)
        my_enc = ExtendedNIP44Encrypt(self.k)

        if not proofs_arg:
            self.logger.info("op=add_proofs_obj status=skip_empty_batch")
            return

        if replicate_relays:
            write_relays = replicate_relays
            
        else:
            write_relays = [self.home_relay]

        # Create the format for NIP 60 proofs
        #FIXME This is where the swap error handling needs to be fixed
        # proofs_arg[0].id - is null sometimes
        published_events: List[Event] = []
        try:
            nip60_proofs = NIP60Proofs(mint=self.known_mints[proofs_arg[0].id])
            for each in proofs_arg:
                nip60_proofs.proofs.append(each)
    
            #TODO Do some error checking on size of record

            record = nip60_proofs.model_dump_json()
            self.logger.debug("op=add_proofs_obj status=record_length length=%s proofs=%s", len(record), len(nip60_proofs.proofs))

            if len(record) > self.max_proof_event_size:
                self.logger.warning("Record length %s is greater than max, splitting proofs", len(record))
                split_proofs = split_proofs_instance(original=nip60_proofs, num_splits=math.ceil(len(record)/self.max_proof_event_size))
                
                for each in split_proofs:
                    records_to_write.append(each.model_dump_json())
            else:
                records_to_write =[record]
            

            for each in records_to_write:
                payload_encrypt = my_enc.encrypt(each,to_pub_k=self.pubkey_hex)
            
                async with ClientPool(write_relays) as c:
                    
                    #FIXME kind
                    n_msg = Event(kind=7375,
                                content=payload_encrypt,
                                pub_key=self.pubkey_hex)
                    n_msg.sign(self.privkey_hex)
                    published_events.append(n_msg)
                    self.logger.debug(
                        "op=add_proofs_obj status=published event_id=%s kind=%s payload_bytes=%s",
                        n_msg.id,
                        n_msg.kind,
                        len(record),
                    )
                    c.publish(n_msg)
                    await asyncio.sleep(0.2)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            self.logger.error("op=add_proofs_obj status=failed proofs=%s error=%s", len(proofs_arg), e)
            raise RuntimeError(f"Error writing proofs: {e}") from e
        
        event_ids = [str(event.id) for event in published_events]
        verification = {
            relay: {"readable": False, "missing_event_ids": list(event_ids)}
            for relay in write_relays
        }
        if verify:
            deadline = monotonic() + max(0.5, float(verify_timeout))
            verify_filter = [{
                "limit": max(1, len(event_ids)),
                "authors": [self.pubkey_hex],
                "kinds": [7375],
                "ids": event_ids,
            }]
            while monotonic() < deadline:
                for relay in write_relays:
                    if verification[relay]["readable"]:
                        continue
                    try:
                        async with ClientPool([relay]) as c:
                            observed = await c.query(verify_filter)
                        observed_ids = {str(event.id) for event in observed}
                        missing = [
                            event_id for event_id in event_ids
                            if event_id not in observed_ids
                        ]
                        verification[relay]["missing_event_ids"] = missing
                        verification[relay]["readable"] = not missing
                        verification[relay].pop("error", None)
                    except Exception as exc:
                        verification[relay]["error"] = str(exc)

                if all(state["readable"] for state in verification.values()):
                    break

                # Re-publishing the same signed event is idempotent and helps
                # when a relay connection closed before its first write was
                # durably accepted.
                for relay, state in verification.items():
                    if state["readable"]:
                        continue
                    try:
                        async with ClientPool([relay]) as c:
                            for event in published_events:
                                if str(event.id) in state["missing_event_ids"]:
                                    c.publish(event)
                    except Exception as exc:
                        state["error"] = str(exc)
                await asyncio.sleep(0.4)

            failed = [
                relay for relay, state in verification.items()
                if not state["readable"]
            ]
            if failed:
                raise RuntimeError(
                    "Proof publish could not be verified on: "
                    + ", ".join(failed)
                )

        return {
            "status": "OK",
            "event_ids": event_ids,
            "relays": write_relays,
            "verified": bool(verify),
            "verification": verification,
        }



    async def write_proofs(self, replicate_relays: List[str]=None):
        # make sure have latest kind
        #TODO Need to add some error checking


        self.logger.debug("op=write_proofs status=start proofs=%s", len(self.proofs))
        try:
            expected_proofs = list(self.proofs)
            expected_balance = sum(each.amount for each in expected_proofs)
            expected_count = len(expected_proofs)
            old_filter = [{
                'limit': RECORD_LIMIT,
                'authors': [self.pubkey_hex],
                'kinds': [7375]
            }]
            old_proof_event_ids: List[str] = []
            async with ClientPool([self.home_relay]) as c:
                existing_events = await c.query(old_filter)
                old_proof_event_ids = [event.id for event in existing_events]

            # get proofs by keyset
            all_proofs, _amount = self._proofs_by_keyset()
            
            for key, value in all_proofs.items():
                await self.add_proofs_obj(value, verify=True)

            if old_proof_event_ids:
                await self._async_delete_events_by_ids(old_proof_event_ids, record_kind=7375)

            # Confirm relay state after old-proof deletion. High-latency relays can briefly
            # surface an empty/partial view; retry before accepting the write as successful.
            loaded_ok = False
            loaded_balance = 0
            loaded_count = 0
            verify_attempts = 5
            for attempt in range(1, verify_attempts + 1):
                await self._load_proofs()
                loaded_balance = sum(each.amount for each in self.proofs)
                loaded_count = len(self.proofs)
                if loaded_balance >= expected_balance and loaded_count >= expected_count:
                    loaded_ok = True
                    break
                await asyncio.sleep(0.4 * attempt)

            if not loaded_ok:
                self.logger.critical(
                    "op=write_proofs status=verify_failed expected_balance=%s expected_count=%s loaded_balance=%s loaded_count=%s",
                    expected_balance,
                    expected_count,
                    loaded_balance,
                    loaded_count,
                )
                # Emergency restore path: republish expected proofs and re-load.
                if expected_proofs:
                    restore_by_keyset = {}
                    for each in expected_proofs:
                        restore_by_keyset.setdefault(each.id, []).append(each)
                    for _, proof_group in restore_by_keyset.items():
                        await self.add_proofs_obj(proof_group)
                    await asyncio.sleep(1)
                    await self._load_proofs()
                    loaded_balance = sum(each.amount for each in self.proofs)
                    loaded_count = len(self.proofs)
                    if loaded_balance < expected_balance or loaded_count < expected_count:
                        # Keep local state conservative for caller-side recovery decisions.
                        self.proofs = expected_proofs
                        self.balance = expected_balance
                        raise RuntimeError(
                            "Proof persistence verification failed after restore attempt"
                        )
                elif loaded_balance != 0 or loaded_count != 0:
                    raise RuntimeError("Unexpected proof state after writing empty proof set")
        except (ValueError, TypeError, RuntimeError, httpx.HTTPError) as e:
            self.logger.error("op=write_proofs status=failed error=%s", e)
            raise RuntimeError(f"error writing proofs: {e}") from e

        
        return

    async def _async_add_proofs_obj(self,proofs_arg: List[Proofs], replicate_relays: List[str]=None):
        # make sure have latest kind
        #TODO this is a workaround



        proofs_to_store = json.dump
        for each in proofs_arg:
            pass
            proof_to_store = [each.model_dump()]
            text = json.dumps(proof_to_store)
            await self._async_add_proofs(text, replicate_relays)
        
        return

    
    async def _async_add_proofs(self, text:str, replicate_relays: List[str]=None):
        """
            Example showing how to post a text note (Kind 1) to relay
        """
        self.logger.debug("op=add_proofs status=text_length length=%s", len(text))
        my_enc = NIP44Encrypt(self.k)
        payload_encrypt = my_enc.encrypt(text,to_pub_k=self.pubkey_hex)
        
        if replicate_relays:
            write_relays = replicate_relays
            
        else:
            write_relays = [self.home_relay]


        async with ClientPool(write_relays) as c:
            
            #FIXME kind
            n_msg = Event(kind=7375,
                        content=payload_encrypt,
                        pub_key=self.pubkey_hex)
            n_msg.sign(self.privkey_hex)
            self.logger.debug(
                "op=add_proofs status=published event_id=%s kind=%s payload_bytes=%s",
                n_msg.id,
                n_msg.kind,
                len(text),
            )
            c.publish(n_msg)
            await asyncio.sleep(0.2)



    async def add_proof_event(self, proofs:List[Proof]):
        await self._async_add_proof_event(proofs)  
    
    async def _async_add_proof_event(self, proofs: List[Proof]):
        """
            Example showing how to post a text note (Kind 1) to relay
        """
        proofs_for_event = []
        
        for proof in proofs:
            proofs_for_event.append(proof.model_dump())
        
        text = json.dumps(proofs_for_event)

        my_enc = NIP44Encrypt(self.k)
        payload_encrypt = my_enc.encrypt(text,to_pub_k=self.pubkey_hex)
        
        async with ClientPool([self.home_relay]) as c:
        # async with Client(relay) as c:
        #FIXME KIND
            n_msg = Event(kind=7375,
                        content=payload_encrypt,
                        pub_key=self.pubkey_hex)
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            # await asyncio.sleep(1) 
    
    def _load_record_events(self):
        exists = False
        FILTER = [{
            'limit': RECORD_LIMIT,
            'authors': [self.pubkey_hex],
            'kinds': [37375]
        }]
        exists =asyncio.run(self._async_load_record_events(FILTER))
        self.profile_found_on_home_relay = exists
        return exists
    
    async def _async_load_record_events(self, filter: List[dict]):
    # does a query for record events, does not decrypt
        exists = False
       
        async with ClientPool([self.home_relay]) as c:
            record_events =[]
            my_enc = NIP44Encrypt(self.k)
            # get reserved records  
            reverse_hash = {}        
            record_events = await c.query(filter)
            if len(record_events) == 0:
                # raise ValueError(f"There is no profile on home relay: {self.home_relay}")
                return False
            
            self.logger.debug(f"Load record events: {len(record_events)}")
            for each in self.RESERVED_RECORDS:
                m = hashlib.sha256()
                m.update(self.privkey_hex.encode())
                m.update(each.encode())
                label_hash = m.digest().hex()
                # print(each, label_hash)
                reverse_hash[label_hash]=each

                for each_record in record_events:                
                    for each_tag in each_record.tags:            
                        if each_tag[0] == 'd':
                            
                            try:
                                decrypt_content = my_enc.decrypt(each_record.content, self.pubkey_hex)
                            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                                decrypt_content = "could not decrpyt"
                                                        
                            reserved_record_label = reverse_hash.get(each_tag[1])
                            
                            if reverse_hash.get(each_tag[1]):
                                self.wallet_reserved_records[reserved_record_label]=decrypt_content
                                
                
                    
        self.logger.debug(f"Finished loading reserved records of {len(record_events)} events")   
        return True
    
    async def _load_proofs(self):
        
        
        FILTER = [{
            'limit': RECORD_LIMIT,
            'authors': [self.pubkey_hex],
            'kinds': [7375]
        }]
       
        content = await self._async_load_proofs(FILTER)

        
        
        return content
    


    async def _async_load_proofs(self, filter: List[dict]):
    # does a one off query to relay prints the events and exits
        my_enc = NIP44Encrypt(self.k)
        proofs = ""
        self.proofs = []
        self.proof_event_ids = []
        async with ClientPool([self.home_relay]) as c:
        # async with Client(relay) as c:
            events = await c.query(filter)
            deletion_filter = [{
                'limit': RECORD_LIMIT,
                'authors': [self.pubkey_hex],
                'kinds': [Event.KIND_DELETE],
            }]
            deletion_events = await c.query(deletion_filter)

            deleted_event_ids = {
                str(tag[1])
                for deletion_event in deletion_events
                for tag in (deletion_event.tags or [])
                if len(tag) >= 2 and tag[0] == "e"
            }
            events = [
                event for event in events
                if str(event.id) not in deleted_event_ids
            ]
            self.events = len(events)
            if deleted_event_ids:
                self.logger.debug(
                    "op=load_proofs status=deletion_filter "
                    "deletion_events=%s deleted_ids=%s current_events=%s",
                    len(deletion_events),
                    len(deleted_event_ids),
                    len(events),
                )
            
            for each_event in events:
                # print(type(each_event.id), each_event.id)
                self.proof_event_ids.append(each_event.id)
                proof_event = proofEvent(id=each_event.id)
                try:
                    content = my_enc.decrypt(each_event.content, self.pubkey_hex)
                    content_json = json.loads(content)
                    # print("event_id:", each_event.id)
                    
                    
                        
                    # proof = Proof(**each_content)
                    nip60_proofs = NIP60Proofs(**content_json)
                    # self.logger.debug(f"load nip60 proofs")
                    self.known_mints[nip60_proofs.proofs[0]['id']]= nip60_proofs.mint
                    for each in nip60_proofs.proofs:
                        self.proofs.append(each)
                        proof_event.proofs.append(each)
                        # print(proof.amount, proof.secret)
                    # self.proof_events.proof_events.append(proof_event)          
                except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                    content = each.content

                
                proofs += str(content) +"\n\n"

            
            balance = 0
            for each in self.proofs:
                # print(each.amount, each.secret)
                balance += each.amount
            self.balance = balance
            # self.logger.debug(f"balance from loaded proofs: {balance}")
            # print("proofs:", len(self.proofs))

                
            # Relay queries can return the same proof event more than once.
            # Pydantic Proof objects are mutable and therefore unhashable, so
            # deduplicate on the Cashu proof identity instead of using set().
            self.proofs = self._deduplicate_proofs(self.proofs)
            self.balance = sum(each.amount for each in self.proofs)
           
            
            return proofs
    


    async def delete_proof_events(self):
        await self._async_delete_proof_events()

    @staticmethod
    def _deduplicate_proofs(proofs: List[Proof]) -> List[Proof]:
        unique: dict[tuple[str, str], Proof] = {}
        for proof in proofs:
            proof_key = (str(proof.id), str(proof.secret))
            unique.setdefault(proof_key, proof)
        return list(unique.values())

    def _proofs_by_keyset(self):
        all_proofs = {}
        keyset_amounts = {}
        for each in self.proofs:
            # print(each.id)
            if each.id not in all_proofs:                
                all_proofs[each.id] = [each]
            else:
                all_proofs[each.id].append(each)  
        
        # calculate amounts for each keyset
        for key in all_proofs: 
            amount=0
            for each in all_proofs[key]:
                amount +=each.amount        
            keyset_amounts[key]=amount
        # print(keyset_amounts)
        return all_proofs, keyset_amounts

    async def proof_safety_audit(self, check_relay: bool = False) -> dict:
        """
        Preflight integrity checks before destructive proof operations.
        Returns a structured report and never mutates wallet state permanently.
        """
        report: dict = {
            "safe_to_swap": True,
            "reason": "ok",
            "proof_count": 0,
            "proof_amount": 0,
            "keyset_count": 0,
            "unknown_keysets": [],
            "invalid_proofs": 0,
            "duplicate_proofs": 0,
            "relay_check": None,
        }

        invalid = 0
        unknown_keysets: set[str] = set()
        seen: set[tuple[str, str]] = set()
        duplicate_count = 0
        amount_sum = 0

        for each in self.proofs:
            try:
                pid = str(each.id)
                psecret = str(each.secret)
                pamount = int(each.amount)
                if pamount <= 0:
                    invalid += 1
                    continue
                amount_sum += pamount
                if pid not in self.known_mints:
                    unknown_keysets.add(pid)
                key = (pid, psecret)
                if key in seen:
                    duplicate_count += 1
                else:
                    seen.add(key)
            except Exception:
                invalid += 1

        keyset_proofs, _ = self._proofs_by_keyset() if self.proofs else ({}, {})
        report["proof_count"] = len(self.proofs)
        report["proof_amount"] = amount_sum
        report["keyset_count"] = len(keyset_proofs)
        report["unknown_keysets"] = sorted(unknown_keysets)
        report["invalid_proofs"] = invalid
        report["duplicate_proofs"] = duplicate_count

        if invalid > 0:
            report["safe_to_swap"] = False
            report["reason"] = "invalid_proofs"
        elif duplicate_count > 0:
            report["safe_to_swap"] = False
            report["reason"] = "duplicate_proofs"
        elif amount_sum <= 0 and len(self.proofs) > 0:
            report["safe_to_swap"] = False
            report["reason"] = "non_positive_total"
        elif unknown_keysets:
            report["safe_to_swap"] = False
            report["reason"] = "unknown_keyset_mapping"
        elif len(self.proofs) == 0:
            report["safe_to_swap"] = False
            report["reason"] = "no_proofs"

        if check_relay:
            snapshot_proofs = list(self.proofs)
            snapshot_balance = self.balance
            snapshot_events = self.events
            snapshot_event_ids = list(self.proof_event_ids)
            snapshot_known_mints = dict(self.known_mints)
            relay_result = {
                "ok": True,
                "proof_count": None,
                "proof_amount": None,
                "error": None,
            }
            try:
                await self._load_proofs()
                relay_result["proof_count"] = len(self.proofs)
                relay_result["proof_amount"] = sum(each.amount for each in self.proofs)
            except Exception as exc:
                relay_result["ok"] = False
                relay_result["error"] = str(exc)
            finally:
                self.proofs = snapshot_proofs
                self.balance = snapshot_balance
                self.events = snapshot_events
                self.proof_event_ids = snapshot_event_ids
                self.known_mints = snapshot_known_mints

            report["relay_check"] = relay_result

        return report

    async def check_proofs(self) -> dict:
        """
        Inspect the wallet's currently loaded proofs against their mints.

        This is a read-only preflight. It does not acquire the wallet lock,
        reload relay state, swap proofs, write proof events, or update wallet
        attributes. Duplicate proof copies are checked only once so the
        mint-confirmed amount is not overstated.
        """
        state_names = ("UNSPENT", "SPENT", "PENDING", "UNKNOWN")

        def empty_state_totals() -> dict:
            return {
                state: {"proof_count": 0, "amount": 0}
                for state in state_names
            }

        structural = await self.proof_safety_audit(check_relay=False)
        report: dict = {
            "read_only": True,
            "status": "clean",
            "requires_repair": False,
            "wallet": {
                "proof_count": len(self.proofs),
                "amount": sum(
                    int(each.amount)
                    for each in self.proofs
                    if isinstance(getattr(each, "amount", None), int)
                ),
            },
            "checked": {"proof_count": 0, "amount": 0},
            "mint_confirmed_unspent": {"proof_count": 0, "amount": 0},
            "states": empty_state_totals(),
            "keysets": [],
            "structural": structural,
            "errors": [],
            "recommendation": "No repair indicated.",
        }

        unique_by_keyset: dict[str, list[tuple[Proof, str]]] = {}
        seen: set[tuple[str, str]] = set()

        for proof in self.proofs:
            try:
                keyset = str(proof.id)
                secret = str(proof.secret)
                amount = int(proof.amount)
                if not keyset or not secret or amount <= 0:
                    continue
                proof_key = (keyset, secret)
                if proof_key in seen:
                    continue
                seen.add(proof_key)
                proof_y = str(proof.Y or "")
                if not proof_y:
                    proof_y = hash_to_curve(secret.encode("utf-8")).serialize().hex()
                unique_by_keyset.setdefault(keyset, []).append((proof, proof_y))
            except Exception:
                # The structural audit reports malformed proofs. Do not mutate
                # or attempt to manufacture a state for one here.
                continue

        headers = {"Content-Type": "application/json"}
        timeout = httpx.Timeout(30.0, connect=5.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for keyset, proof_rows in unique_by_keyset.items():
                mint_url = self.known_mints.get(keyset)
                keyset_states = empty_state_totals()
                keyset_amount = sum(int(proof.amount) for proof, _ in proof_rows)
                keyset_report = {
                    "keyset": keyset,
                    "mint": mint_url,
                    "proof_count": len(proof_rows),
                    "amount": keyset_amount,
                    "states": keyset_states,
                    "error": None,
                }
                report["keysets"].append(keyset_report)

                if not mint_url:
                    error = f"No mint mapping for keyset {keyset}"
                    keyset_report["error"] = error
                    report["errors"].append(error)
                    keyset_states["UNKNOWN"]["proof_count"] = len(proof_rows)
                    keyset_states["UNKNOWN"]["amount"] = keyset_amount
                    report["states"]["UNKNOWN"]["proof_count"] += len(proof_rows)
                    report["states"]["UNKNOWN"]["amount"] += keyset_amount
                    continue

                try:
                    response = await client.post(
                        url=f"{mint_url.rstrip('/')}/v1/checkstate",
                        json={"Ys": [proof_y for _, proof_y in proof_rows]},
                        headers=headers,
                    )
                    response.raise_for_status()
                    response_body = response.json()
                    states = (
                        response_body.get("states", [])
                        if isinstance(response_body, dict)
                        else []
                    )
                    if len(states) != len(proof_rows):
                        raise RuntimeError(
                            f"checkstate returned {len(states)} states for "
                            f"{len(proof_rows)} proofs"
                        )
                except Exception as exc:
                    error = f"Unable to check keyset {keyset} at {mint_url}: {exc}"
                    keyset_report["error"] = error
                    report["errors"].append(error)
                    keyset_states["UNKNOWN"]["proof_count"] = len(proof_rows)
                    keyset_states["UNKNOWN"]["amount"] = keyset_amount
                    report["states"]["UNKNOWN"]["proof_count"] += len(proof_rows)
                    report["states"]["UNKNOWN"]["amount"] += keyset_amount
                    continue

                for (proof, _proof_y), state_obj in zip(proof_rows, states):
                    state = (
                        str(state_obj.get("state", "")).upper()
                        if isinstance(state_obj, dict)
                        else ""
                    )
                    if state not in state_names:
                        state = "UNKNOWN"
                    amount = int(proof.amount)
                    keyset_states[state]["proof_count"] += 1
                    keyset_states[state]["amount"] += amount
                    report["states"][state]["proof_count"] += 1
                    report["states"][state]["amount"] += amount
                    report["checked"]["proof_count"] += 1
                    report["checked"]["amount"] += amount

        unspent = report["states"]["UNSPENT"]
        report["mint_confirmed_unspent"] = dict(unspent)

        structural_problem = not structural["safe_to_swap"] and structural["reason"] != "no_proofs"
        spent_found = report["states"]["SPENT"]["proof_count"] > 0
        inconclusive = bool(
            report["errors"]
            or report["states"]["PENDING"]["proof_count"]
            or report["states"]["UNKNOWN"]["proof_count"]
        )
        report["requires_repair"] = bool(structural_problem or spent_found)

        if inconclusive:
            report["status"] = "inconclusive"
            report["recommendation"] = (
                "Recheck before repairing; pending, unknown, or unreachable "
                "proof state requires investigation."
            )
        elif report["requires_repair"]:
            report["status"] = "repair-recommended"
            report["recommendation"] = (
                "Review this report, then run 'acorn repair-proofs' if the "
                "spent or structurally invalid state is expected."
            )
        elif not self.proofs:
            report["status"] = "empty"
            report["recommendation"] = "No proofs are present."

        return report

    async def repair_proofs(self, force_prune_stale: bool = False) -> str:
        """
        Reconcile local/relay-backed proof state against mint state and
        rewrite the wallet to contain only currently usable proofs.

        Strategy:
        - drop local duplicates first
        - consult checkstate
        - for proofs still reported UNSPENT, perform an individual swap into a fresh proof
        - if the mint rejects an individual proof as already spent, drop it
        """
        headers = {"Content-Type": "application/json"}
        timeout = httpx.Timeout(30.0, connect=5.0)
        lock_acquired = False
        rebuilt_proofs: list[Proof] = []
        dropped_counts: dict[str, int] = {}
        duplicate_dropped = 0

        try:
            await self.acquire_lock()
            lock_acquired = True
            await self._load_proofs()
            source_event_ids = list(self.proof_event_ids)
            await self._require_resolved_pending_melts()

            keyset_proofs, _keyset_amounts = self._proofs_by_keyset()
            if not keyset_proofs:
                return "repair-proofs skipped (no proofs)"

            original_count = len(self.proofs)
            original_balance = sum(each.amount for each in self.proofs)

            for each_keyset, proofs in keyset_proofs.items():
                mint_url = self.known_mints.get(each_keyset)
                if not mint_url:
                    raise RuntimeError(f"Cannot repair proofs for unknown keyset mapping: {each_keyset}")

                unique_proofs: list[Proof] = []
                seen_proofs: set[tuple[str, str]] = set()
                for proof in proofs:
                    proof_key = (str(proof.id), str(proof.secret))
                    if proof_key in seen_proofs:
                        duplicate_dropped += 1
                        continue
                    seen_proofs.add(proof_key)
                    unique_proofs.append(proof)

                checkstate_url = f"{mint_url}/v1/checkstate"
                ys = [each.Y for each in unique_proofs]
                payload = {"Ys": ys}

                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url=checkstate_url, json=payload, headers=headers)
                    response.raise_for_status()
                    checkstate_response = response.json()

                states = checkstate_response.get("states", []) if isinstance(checkstate_response, dict) else []
                if len(states) != len(unique_proofs):
                    raise RuntimeError(
                        f"Repair checkstate length mismatch for keyset {each_keyset}: "
                        f"{len(states)} states for {len(unique_proofs)} proofs"
                    )

                dropped = 0
                candidate_proofs: list[Proof] = []
                for proof, state_obj in zip(unique_proofs, states):
                    state_value = state_obj.get("state") if isinstance(state_obj, dict) else None
                    if state_value == "UNSPENT":
                        candidate_proofs.append(proof)
                    else:
                        dropped += 1

                if dropped:
                    dropped_counts[each_keyset] = dropped
                    self.logger.warning(
                        "op=repair_proofs status=dropped keyset=%s mint=%s dropped=%s",
                        each_keyset,
                        mint_url,
                        dropped,
                    )

                if not candidate_proofs:
                    continue

                mint_key_url = f"{mint_url}/v1/keys/{each_keyset}"
                swap_url = f"{mint_url}/v1/swap"

                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(mint_key_url, headers=headers)
                    response.raise_for_status()
                    keys = response.json()["keysets"][0]["keys"]

                    for each_proof in candidate_proofs:
                        blinded_values = []
                        secret = secrets.token_hex(32)
                        B_, r, Y = step1_alice(secret)
                        blinded_values.append((B_, r, secret, Y))
                        blinded_messages = [
                            BlindedMessage(
                                amount=each_proof.amount,
                                id=each_keyset,
                                B_=B_.serialize().hex(),
                                Y=Y.serialize().hex(),
                            ).model_dump()
                        ]
                        data_to_send = {
                            "inputs": [each_proof.to_dict()],
                            "outputs": blinded_messages,
                        }

                        response = await client.post(url=swap_url, json=data_to_send, headers=headers)
                        if response.is_error:
                            response_text = response.text.strip()
                            stale_proof_error = False
                            try:
                                response_json = response.json()
                                stale_proof_error = (
                                    response_json.get("code") == 11001
                                    or "Token already spent" in str(response_json.get("detail", ""))
                                )
                            except Exception:
                                stale_proof_error = "Token already spent" in response_text

                            if stale_proof_error:
                                dropped_counts[each_keyset] = dropped_counts.get(each_keyset, 0) + 1
                                self.logger.warning(
                                    "op=repair_proofs status=drop_on_swap keyset=%s mint=%s amount=%s reason=already_spent",
                                    each_keyset,
                                    mint_url,
                                    each_proof.amount,
                                )
                                continue

                            raise RuntimeError(
                                f"repair-proofs swap probe failed for keyset {each_keyset} at mint {mint_url} "
                                f"with status {response.status_code}: {response_text or '<empty body>'}"
                            )

                        promises = response.json()["signatures"]
                        if len(promises) != 1:
                            raise RuntimeError(
                                f"repair-proofs expected exactly one replacement proof for keyset {each_keyset}, "
                                f"got {len(promises)}"
                            )

                        each = promises[0]
                        pub_key_c = PublicKey()
                        pub_key_c.deserialize(unhexlify(each["C_"]))
                        promise_amount = each["amount"]
                        A = keys[str(int(promise_amount))]
                        pub_key_a = PublicKey()
                        pub_key_a.deserialize(unhexlify(A))
                        r = blinded_values[0][1]
                        Y = blinded_values[0][3]
                        C = step3_alice(pub_key_c, r, pub_key_a)
                        replacement = Proof(
                            amount=promise_amount,
                            id=each_keyset,
                            secret=blinded_values[0][2],
                            C=C.serialize().hex(),
                            Y=Y.serialize().hex(),
                        )
                        # The input was consumed by the successful swap. Keep
                        # its replacement durable even if a later repair step
                        # fails before the final compact rewrite.
                        await self.add_proofs_obj([replacement], verify=True)
                        rebuilt_proofs.append(replacement)

            repaired_balance = sum(each.amount for each in rebuilt_proofs)
            repaired_count = len(rebuilt_proofs)
            total_spent_dropped = sum(dropped_counts.values())

            if repaired_count == 0 and original_count > 0:
                if not force_prune_stale:
                    raise RuntimeError(
                        "repair-proofs found zero usable replacement proofs and refused to overwrite the wallet. "
                        "If you want to discard all stale proofs, rerun with force enabled."
                    )
                self.logger.warning(
                    "op=repair_proofs status=force_prune_empty_wallet original_count=%s original_balance=%s",
                    original_count,
                    original_balance,
                )

            if source_event_ids:
                await self._async_delete_events_by_ids(
                    source_event_ids,
                    record_kind=7375,
                )
            await self._load_proofs()

            if repaired_count == original_count and duplicate_dropped == 0 and total_spent_dropped == 0:
                return (
                    "repair-proofs refreshed all proofs successfully "
                    f"({repaired_balance} sats across {repaired_count} proofs). "
                    "No stale proofs were removed."
                )

            return (
                "repair-proofs completed: "
                f"dropped {total_spent_dropped} spent proofs, "
                f"dropped {duplicate_dropped} duplicate proofs, "
                f"kept {repaired_count} proofs, "
                f"balance {original_balance} -> {repaired_balance} sats"
            )
        finally:
            if lock_acquired:
                await self.release_lock()

    async def _maybe_maintain_received_proofs(self, reason: str, added_proof_count: int = 0) -> None:
        """
        Best-effort receive-side proof maintenance.

        This keeps long-lived wallets from accumulating large fragmented proof
        sets until the next spend path has to pay the cleanup cost.
        """
        try:
            if not RECEIVE_PROOF_MAINTENANCE_ENABLED:
                self.logger.debug(
                    "op=receive_maintenance status=skip reason=disabled trigger=%s",
                    reason,
                )
                return

            await self._load_proofs()
            proof_count = len(self.proofs)
            keyset_proofs, _keyset_amounts = self._proofs_by_keyset() if self.proofs else ({}, {})
            largest_keyset_count = max((len(value) for value in keyset_proofs.values()), default=0)

            total_triggered = proof_count > RECEIVE_PROOF_MAINTENANCE_TOTAL_LIMIT
            keyset_triggered = largest_keyset_count > RECEIVE_PROOF_MAINTENANCE_KEYSET_LIMIT
            eager_batch_triggered = (
                added_proof_count >= RECEIVE_PROOF_MAINTENANCE_EAGER_BATCH_LIMIT
                and proof_count >= RECEIVE_PROOF_MAINTENANCE_EAGER_TOTAL_LIMIT
            )

            if not total_triggered and not keyset_triggered and not eager_batch_triggered:
                self.logger.debug(
                    "op=receive_maintenance status=skip reason=under_limit trigger=%s proofs=%s total_limit=%s largest_keyset=%s keyset_limit=%s added_proofs=%s eager_total_limit=%s eager_batch_limit=%s",
                    reason,
                    proof_count,
                    RECEIVE_PROOF_MAINTENANCE_TOTAL_LIMIT,
                    largest_keyset_count,
                    RECEIVE_PROOF_MAINTENANCE_KEYSET_LIMIT,
                    added_proof_count,
                    RECEIVE_PROOF_MAINTENANCE_EAGER_TOTAL_LIMIT,
                    RECEIVE_PROOF_MAINTENANCE_EAGER_BATCH_LIMIT,
                )
                return

            self.logger.info(
                "op=receive_maintenance status=start trigger=%s proofs=%s total_limit=%s largest_keyset=%s keyset_limit=%s added_proofs=%s eager_total_limit=%s eager_batch_limit=%s total_triggered=%s keyset_triggered=%s eager_batch_triggered=%s",
                reason,
                proof_count,
                RECEIVE_PROOF_MAINTENANCE_TOTAL_LIMIT,
                largest_keyset_count,
                RECEIVE_PROOF_MAINTENANCE_KEYSET_LIMIT,
                added_proof_count,
                RECEIVE_PROOF_MAINTENANCE_EAGER_TOTAL_LIMIT,
                RECEIVE_PROOF_MAINTENANCE_EAGER_BATCH_LIMIT,
                total_triggered,
                keyset_triggered,
                eager_batch_triggered,
            )
            await self.swap_multi_each()
            await self.swap_multi_consolidate()
            self.logger.info(
                "op=receive_maintenance status=done trigger=%s proofs=%s",
                reason,
                len(self.proofs),
            )
        except Exception as exc:
            self.logger.warning(
                "op=receive_maintenance status=failed trigger=%s error=%s",
                reason,
                exc,
            )



    @staticmethod
    def _melt_state(payload: dict | None) -> str:
        if not isinstance(payload, dict):
            return "UNKNOWN"
        state = str(payload.get("state") or "").upper()
        if state in {"PAID", "UNPAID", "PENDING"}:
            return state
        if payload.get("paid") is True:
            return "PAID"
        return "UNKNOWN"

    async def _load_pending_melts(self) -> List[dict]:
        raw = await self.get_wallet_info(label=PENDING_MELTS_LABEL)
        if not raw:
            return []
        try:
            loaded = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PaymentFinalizationError(
                "Pending Lightning payment journal is unreadable; refusing to spend."
            ) from exc
        if not isinstance(loaded, list) or not all(isinstance(each, dict) for each in loaded):
            raise PaymentFinalizationError(
                "Pending Lightning payment journal has an invalid format; refusing to spend."
            )
        return loaded

    async def _save_pending_melts(self, entries: List[dict]) -> None:
        await self.set_wallet_info(
            label=PENDING_MELTS_LABEL,
            label_info=json.dumps(entries, sort_keys=True),
        )
        # A recovery journal is useful only if it is readable after a process
        # exit. Verify relay readback before allowing a melt submission.
        for attempt in range(1, 6):
            try:
                observed = await self._load_pending_melts()
                if observed == entries:
                    return
            except PaymentFinalizationError:
                pass
            await asyncio.sleep(0.4 * attempt)
        raise PaymentFinalizationError(
            "Pending Lightning payment journal could not be read back from "
            "the home relay. No new melt should be submitted."
        )

    async def _upsert_pending_melt(self, entry: dict) -> None:
        pending = await self._load_pending_melts()
        pending = [
            each for each in pending
            if str(each.get("quote")) != str(entry.get("quote"))
        ]
        pending.append(entry)
        await self._save_pending_melts(pending)

    async def _remove_pending_melt(self, quote: str) -> None:
        pending = await self._load_pending_melts()
        remaining = [
            each for each in pending
            if str(each.get("quote")) != str(quote)
        ]
        await self._save_pending_melts(remaining)

    async def _query_melt_quote(
        self,
        mint: str,
        quote: str,
        timeout: httpx.Timeout | None = None,
    ) -> dict:
        quote_url = f"{mint.rstrip('/')}/v1/melt/quote/bolt11/{quote}"
        async with httpx.AsyncClient(
            timeout=timeout or httpx.Timeout(30.0, connect=5.0)
        ) as client:
            response = await client.get(quote_url)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("mint returned a non-object melt quote response")
        return payload

    async def _resolve_melt_submission(
        self,
        *,
        melt_url: str,
        mint: str,
        quote: str,
        request_payload: dict,
        headers: dict,
        timeout: httpx.Timeout,
        attempts: int = MELT_RECOVERY_ATTEMPTS,
    ) -> dict:
        """
        Submit a melt once, then resolve ambiguous responses by quote lookup.

        The melt POST is never repeated. A timeout, disconnect, HTTP error, or
        non-terminal response is followed only by idempotent quote queries.
        """
        post_error: Exception | None = None
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url=melt_url,
                    json=request_payload,
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
            state = self._melt_state(payload)
            if state in {"PAID", "UNPAID"}:
                return {"state": state, "payload": payload, "source": "melt-response"}
        except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError) as exc:
            post_error = exc

        last_payload: dict | None = None
        last_error: Exception | None = post_error
        for attempt in range(max(1, int(attempts))):
            if attempt:
                await asyncio.sleep(0.5 * attempt)
            try:
                last_payload = await self._query_melt_quote(
                    mint=mint,
                    quote=quote,
                    timeout=timeout,
                )
                state = self._melt_state(last_payload)
                if state in {"PAID", "UNPAID"}:
                    return {
                        "state": state,
                        "payload": last_payload,
                        "source": "quote-query",
                    }
            except (httpx.HTTPError, RuntimeError, ValueError, TypeError) as exc:
                last_error = exc

        detail = str(last_error) if last_error else self._melt_state(last_payload)
        raise PaymentOutcomeUnknownError(
            f"Lightning payment outcome is unresolved for quote {quote}. "
            "Do not retry the payment. Acorn retained a pending recovery "
            f"record and will query the mint again. Last result: {detail}"
        )

    async def _finalize_paid_melt(self, entry: dict, payload: dict) -> None:
        quote = str(entry["quote"])
        spend_ys = {str(each) for each in entry.get("spend_ys", [])}
        retained: List[Proof] = []
        for proof in self.proofs:
            proof_y = str(proof.Y or "")
            if not proof_y:
                proof_y = hash_to_curve(
                    str(proof.secret).encode("utf-8")
                ).serialize().hex()
            if proof_y not in spend_ys:
                retained.append(proof)

        self.proofs = retained
        self.balance = sum(each.amount for each in retained)
        try:
            await self.write_proofs()
        except Exception as exc:
            raise PaymentFinalizationError(
                f"Mint confirmed Lightning payment for quote {quote}, but "
                "the remaining proofs could not be persisted. Do not retry; "
                "restart Acorn to resume finalization."
            ) from exc

        history_marker = f"cashu-melt:{quote}"
        try:
            history = await self.get_tx_history()
        except Exception as exc:
            raise PaymentFinalizationError(
                f"Mint confirmed Lightning payment for quote {quote}, but "
                "transaction-history reconciliation could not be completed. "
                "Do not retry; restart Acorn to resume finalization."
            ) from exc

        if not any(each.get("description_hash") == history_marker for each in history):
            try:
                await self.add_tx_history(
                    tx_type="D",
                    amount=int(entry["amount"]),
                    comment=str(entry.get("comment") or ""),
                    tendered_amount=entry.get("tendered_amount"),
                    tendered_currency=str(entry.get("tendered_currency") or "SAT"),
                    fees=int(entry.get("fee_reserve") or 0),
                    invoice=entry.get("invoice"),
                    payment_preimage=payload.get("payment_preimage"),
                    payment_hash=entry.get("payment_hash"),
                    description_hash=history_marker,
                )
            except Exception as exc:
                raise PaymentFinalizationError(
                    f"Mint confirmed Lightning payment for quote {quote}, but "
                    "transaction history could not be persisted. Do not retry; "
                    "restart Acorn to resume finalization."
                ) from exc

        await self._remove_pending_melt(quote)

    async def reconcile_pending_melts(self) -> dict:
        """
        Resume pending Lightning melts after a timeout or process restart.

        PAID entries are finalized, UNPAID entries are released, and
        PENDING/UNKNOWN entries remain journaled and block another payment.
        """
        pending = await self._load_pending_melts()
        result = {"paid": 0, "unpaid": 0, "unresolved": 0, "quotes": []}
        timeout = httpx.Timeout(30.0, connect=5.0)

        for entry in list(pending):
            quote = str(entry.get("quote") or "")
            mint = str(entry.get("mint") or "")
            if not quote or not mint:
                result["unresolved"] += 1
                result["quotes"].append(
                    {"quote": quote or None, "state": "UNKNOWN", "error": "invalid journal entry"}
                )
                continue
            try:
                payload = await self._query_melt_quote(mint, quote, timeout)
                state = self._melt_state(payload)
            except Exception as exc:
                state = "UNKNOWN"
                payload = {}
                error = str(exc)
            else:
                error = None

            result["quotes"].append(
                {"quote": quote, "state": state, "error": error}
            )
            if state == "PAID":
                await self._finalize_paid_melt(entry, payload)
                result["paid"] += 1
            elif state == "UNPAID":
                await self._remove_pending_melt(quote)
                result["unpaid"] += 1
            else:
                result["unresolved"] += 1

        return result

    async def _require_resolved_pending_melts(self) -> dict:
        result = await self.reconcile_pending_melts()
        if result["unresolved"]:
            unresolved_quotes = [
                str(each.get("quote"))
                for each in result["quotes"]
                if each.get("state") not in {"PAID", "UNPAID"}
            ]
            raise PaymentOutcomeUnknownError(
                "A previous Lightning payment is still unresolved "
                f"(quotes: {', '.join(unresolved_quotes)}). Do not spend or "
                "submit another payment until the mint reports a terminal state."
            )
        return result


    async def pay_multi(  self, 
                    amount:int, 
                    lnaddress: str, 
                    comment: str = "Paid!",
                    tendered_amount: float = None,
                    tendered_currency: str = "SAT"
                    ): 
        # print("pay from multiple mints")
        available_amount = 0
        chosen_keyset = None
        chosen_keysets = [] # This is for multipath payments
        multi_path = False
        keyset_proofs,keyset_amounts = self._proofs_by_keyset()
        headers = { "Content-Type": "application/json"}
        msg_out = "Paid"
        final_fees = 0
        melt_attempted = False

        try:
            timeout = httpx.Timeout(30.0, connect=5.0)
            await self.acquire_lock()
            await self._require_resolved_pending_melts()
            callback, safebox, nonce = lightning_address_pay(amount, lnaddress,comment=comment)         
            pr = callback['pr'] 
            self.logger.debug("op=pay_multi status=lookup has_safebox=%s", bool(safebox))

            if safebox:
                self.logger.info("op=pay_multi status=direct_safebox nonce=%s", nonce)
                ln_parts = lnaddress.split('@')
                local_part = ln_parts[0]
                safebox_to_call = f"https://{ln_parts[1]}/.well-known/safebox.json/{ln_parts[0].lower()}"
                self.logger.debug("op=pay_multi status=resolve_safebox url=%s", safebox_to_call)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(safebox_to_call)
                    response.raise_for_status()
                    response = response.json()
                pubkey = response.get("pubkey",None)
                nrecipient = hex_to_bech32(pubkey)
                relays = response.get("relays", None)
                ecash_relays = response.get("ecash_relays", relays)
                self.logger.debug("op=pay_multi status=transmit_ecash relays=%s", ecash_relays)
                cashu_token = await self.issue_token(amount=amount, comment=comment)
                pay_obj =   {"token": cashu_token,
                             "amount": amount, 
                             "comment": comment,
                             "tendered_amount": tendered_amount,
                             "tendered_currency": tendered_currency,
                             "nonce": nonce}
                nembed_to_send = create_nembed_compressed(pay_obj)
                self.logger.debug("op=pay_multi status=nembed_created")
                
                

                await self.secure_transmittal(nrecipient=nrecipient,message=nembed_to_send,dm_relays=ecash_relays,kind=21401)
                # await self.add_tx_history(tx_type='D', amount=amount, comment=comment,
                # tendered_amount=tendered_amount, tendered_currency=tendered_currency, fees=final_fees)
            else: #     return f"Payment in ecash of {amount} sats", 0


                for each in keyset_amounts:
                    available_amount += keyset_amounts[each]
                
                
                # print("available amount:", available_amount)
                if available_amount < amount:
                    msg_out = f"Insufficient balance to pay {amount} sats. You need more funds!"
                    raise RuntimeError(msg_out)
                
                
                for key in sorted(keyset_amounts, key=lambda k: keyset_amounts[k]):
                    # print(key, keyset_amounts[key])
                    if keyset_amounts[key] >= amount:
                        chosen_keyset = key
                        break
                if not chosen_keyset:
                    # print("insufficient balance in any one keyset, you need to swap or do mpp!") 
                    multi_path = True
                    
                
                if multi_path:
                    raise RuntimeError("Multipath payments are not implemented yet!")
                    #TODO the remaining code is for multipath
                    amount_multi =0
                    keysets_to_use_for_multi = []
                    for key in sorted(keyset_amounts, key=lambda k: keyset_amounts[k],reverse=True):
                        
                        # print(key, keyset_amounts[key])
                        amount_multi += keyset_amounts[key]
                        chosen_keysets.append(key)
                        # just do all the keysets for now
                        # if amount_multi >= amount:
                        #     print(f"got enough!")
                        #     break
                    
                    self.logger.debug("op=pay_multi status=mpp_choose amount=%s keysets=%s", amount, chosen_keysets)
                    amount_remaining = amount
                    total_fees = 0
                    total_melt_amount = 0
                    for each_keyset in chosen_keysets:
                        self.logger.debug("op=pay_multi status=mpp_remaining amount_remaining=%s", amount_remaining)
                        # There are three possible use cases
                        if amount_remaining <= 0:
                            self.logger.debug("op=pay_multi status=mpp_done")
                            break
                        elif amount_remaining > keyset_amounts[each_keyset]:
                            self.logger.debug("op=pay_multi status=mpp_use_full_keyset keyset=%s", each_keyset)
                            amount_to_use = keyset_amounts[each_keyset]
                        else:
                            amount_to_use = amount_remaining
                        
                        
                        melt_quote_url = f"{self.known_mints[each_keyset]}/v1/melt/quote/bolt11"
                        melt_url = f"{self.known_mints[each_keyset]}/v1/melt/bolt11"
                        
                        data_to_send = {    "request": pr,
                                            "unit": "sat",
                                            "options": {"mpp": {"amount": amount_to_use}}
                                    }
                        # print(f"{melt_quote_url, melt_url} {data_to_send}")
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            response = await client.post(url=melt_quote_url, json=data_to_send, headers=headers)
                            response.raise_for_status()
                            post_melt_response = PostMeltQuoteResponse(**response.json())
                        self.logger.debug("op=pay_multi status=mpp_melt_quote keyset=%s", each_keyset)

                        # Now need to figure out how much can be paid based on case
                        if amount_remaining > keyset_amounts[each_keyset]:
                            pass
                            amount_to_pay = amount_to_use - post_melt_response.fee_reserve
                            melt_amount = amount_to_use
                        else:
                            pass
                            amount_to_pay = amount_to_use
                            melt_amount = amount_to_use + post_melt_response.fee_reserve
                            if melt_amount >= keyset_amounts[each_keyset]:
                                self.logger.warning("op=pay_multi status=mpp_melt_warning keyset=%s", each_keyset)
                            else:
                                self.logger.debug("op=pay_multi status=mpp_melt_amount_ok keyset=%s", each_keyset)

                        total_melt_amount += melt_amount
                        total_fees += post_melt_response.fee_reserve
                        # amount_paid_by_keyset = amount_to_use - post_melt_response.fee_reserve
                        self.logger.debug(
                            "op=pay_multi status=mpp_amount_calc keyset=%s amount_to_pay=%s keyset_total=%s fee_reserve=%s melt_amount=%s",
                            each_keyset,
                            amount_to_pay,
                            keyset_amounts[each_keyset],
                            post_melt_response.fee_reserve,
                            melt_amount,
                        )
                        # Redo the melt request
                        data_to_send = {    "request": pr,
                                        "unit": "sat",
                                        "options": {"mpp": {"amount": amount_to_pay}}
                                }
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            response = await client.post(url=melt_quote_url, json=data_to_send, headers=headers)
                            response.raise_for_status()
                            post_melt_response = PostMeltQuoteResponse(**response.json())
                        self.logger.debug("op=pay_multi status=mpp_adjusted_quote keyset=%s", each_keyset)
                        amount_remaining = amount_remaining - amount_to_pay   
                        self.logger.debug("op=pay_multi status=mpp_adjusted_remaining amount_remaining=%s", amount_remaining)
                        keysets_to_use_for_multi.append((each_keyset,melt_amount,amount_to_pay,post_melt_response))

                    if amount_remaining > 0:
                        raise ValueError(f"There are not sufficient mints to support multipath payments. Try smaller amounts?")

                    # Now we have the meltquotes
                    self.logger.debug(
                        "op=pay_multi status=mpp_requests count=%s keysets=%s",
                        len(keysets_to_use_for_multi),
                        [each[0] for each in keysets_to_use_for_multi],
                    )
                    self.logger.info("op=pay_multi status=mpp_summary amount=%s fees=%s melt_amount=%s", amount, total_fees, total_melt_amount)
                    
                    self._multi_melt(keysets_to_use_for_multi) 
                    
                    # self.write_proofs()

                    msg_out = f"pay amount with mpp {amount} total fees: {total_fees}, total melt amount {total_melt_amount}"
                    return msg_out, total_fees
                    # raise ValueError(f"Need to implement multipath payment for {amount} with {available_amount} available")

                else: # Can pay with a single keyset
                    
                    self.logger.debug(f"chosen keyset for payment {chosen_keyset}")
                
                    # Now do the pay routine
                    melt_quote_url = f"{self.known_mints[chosen_keyset]}/v1/melt/quote/bolt11"
                    melt_url = f"{self.known_mints[chosen_keyset]}/v1/melt/bolt11"

                    self.logger.debug("op=pay_multi status=single_keyset amount=%s", amount)
                    data_to_send = {    "request": pr,
                                        "unit": "sat"

                                    }
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(url=melt_quote_url, json=data_to_send, headers=headers)
                        response.raise_for_status()
                    

                    # print("post melt response:", response.json())
                    post_melt_response = PostMeltQuoteResponse(**response.json())
                    # print("mint response:", post_melt_response)
                    proofs_to_use = []
                    proof_amount = 0
                    amount_needed = amount + post_melt_response.fee_reserve
                    self.logger.debug(f"amount needed: {amount_needed}")
                    if amount_needed > keyset_amounts[chosen_keyset]:
                        self.logger.warning("op=pay_multi status=single_keyset_insufficient_switching")
                        chosen_keyset = None
                        for key in sorted(keyset_amounts, key=lambda k: keyset_amounts[k]):
                            # print(key, keyset_amounts[key])
                            if keyset_amounts[key] >= amount_needed:
                                chosen_keyset = key
                                self.logger.debug(f"new chosen keyset: {key}")
                                break
                        if not chosen_keyset:
                            msg_out = "you don't have a sufficient balance in a keyset, you need to swap"
                            raise ValueError(msg_out)

                        # Adding in some additional error handling to head off a random fatal error    
                        
                        # Set to new mints and redo the calls
                        melt_quote_url = f"{self.known_mints[chosen_keyset]}/v1/melt/quote/bolt11"
                        melt_url = f"{self.known_mints[chosen_keyset]}/v1/melt/bolt11"
                        # print(melt_quote_url,melt_url)
                        # callback = lightning_address_pay(amount, lnaddress,comment=comment)
                        # pr = callback['pr']        
                        # print(pr)
                        self.logger.debug("op=pay_multi status=retry_quote amount=%s", amount)
                        data_to_send = {    "request": pr,
                                        "unit": "sat"

                                    }
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            response = await client.post(url=melt_quote_url, json=data_to_send, headers=headers)
                            response.raise_for_status()
                        # print("post melt response:", response.json())
                        post_melt_response = PostMeltQuoteResponse(**response.json())
                        # print("mint response:", post_melt_response)
                        
                        
                        
                        if not chosen_keyset:
                            msg_out ="insufficient balance in any one keyset, you need to swap!"
                            raise ValueError(msg_out) 
                        
                    # Print now we should be all set to go
                    
                    self.logger.debug("---we have a sufficient mint balance---")
                    
                    # This is the part that needs to be added in multi
                    proofs_to_use = []
                    proof_amount = 0
                    proofs_from_keyset = list(keyset_proofs[chosen_keyset])
                    while proof_amount < amount_needed:
                        pay_proof = proofs_from_keyset.pop()
                        proofs_to_use.append(pay_proof)
                        proof_amount += pay_proof.amount
                        # print("pop", pay_proof.amount)
                        

                    
                    #FIXME this is the critical error!!!
                    try: 
                        proofs_remaining = await self.swap_for_payment_multi(chosen_keyset,proofs_to_use, amount_needed)
                    except (ValueError, RuntimeError) as e:
                        error_text = str(e)
                        if (
                            "Token already spent" in error_text
                            or "11001" in error_text
                            or "Local wallet proof state is stale" in error_text
                        ):
                            raise RuntimeError(
                                "Payment could not proceed because the wallet contains stale proofs."
                            ) from e
                        raise RuntimeError(f"ERROR Swap for Payment: {e}. You may need to try the payment again.") from e
                        

                    # print("proofs remaining:", proofs_remaining)
                    # print(f"amount needed: {amount_needed}")
                    # Implement from line 824
                    sum_proofs =0
                    spend_proofs = []
                    keep_proofs = []
                    
                    for each in proofs_remaining:
                        
                        sum_proofs += each.amount
                        if sum_proofs <= amount_needed:
                            spend_proofs.append(each)
                            self.logger.debug("op=pay_multi status=select_proof amount=%s", each.amount)
                        else:
                            keep_proofs.append(each)
                            self.logger.debug("op=pay_multi status=retain_proof amount=%s", each.amount)
                    
                    self.logger.debug(
                        "op=pay_multi status=proof_selection spend_count=%s spend_amount=%s keep_count=%s keep_amount=%s",
                        len(spend_proofs),
                        sum(each.amount for each in spend_proofs),
                        len(keep_proofs),
                        sum(each.amount for each in keep_proofs),
                    )
                    melt_proofs = []
                    for each_proof in spend_proofs:
                            melt_proofs.append(each_proof.to_dict())

                    data_to_send = {"quote": post_melt_response.quote,
                                "inputs": melt_proofs }
                    self.logger.debug("op=pay_multi status=checkpoint_before_melt amount=%s", amount)

                    # Persist all post-swap proofs before submitting the melt.
                    # If the process exits after submission, the journal and
                    # these proof Ys are sufficient to resume safely.
                    keyset_proofs[chosen_keyset] = (
                        proofs_from_keyset + spend_proofs + keep_proofs
                    )
                    checkpoint_proofs: List[Proof] = []
                    for key in keyset_proofs:
                        checkpoint_proofs.extend(keyset_proofs[key])
                    self.proofs = checkpoint_proofs
                    self.balance = sum(each.amount for each in checkpoint_proofs)
                    await self.write_proofs()

                    pending_entry = {
                        "quote": post_melt_response.quote,
                        "mint": self.known_mints[chosen_keyset],
                        "keyset": chosen_keyset,
                        "spend_ys": [
                            str(each.Y or hash_to_curve(
                                str(each.secret).encode("utf-8")
                            ).serialize().hex())
                            for each in spend_proofs
                        ],
                        "amount": int(amount),
                        "fee_reserve": int(amount_needed - amount),
                        "lnaddress": lnaddress,
                        "comment": comment,
                        "tendered_amount": tendered_amount,
                        "tendered_currency": tendered_currency,
                        "invoice": pr,
                        "created_at": int(datetime.now().timestamp()),
                    }
                    await self._upsert_pending_melt(pending_entry)

                    melt_attempted = True
                    outcome = await self._resolve_melt_submission(
                        melt_url=melt_url,
                        mint=self.known_mints[chosen_keyset],
                        quote=post_melt_response.quote,
                        request_payload=data_to_send,
                        headers=headers,
                        timeout=timeout,
                    )
                    if outcome["state"] == "UNPAID":
                        await self._remove_pending_melt(post_melt_response.quote)
                        raise PaymentFailedError(
                            f"Lightning payment to {lnaddress} of {amount} sats "
                            "was not paid. The mint reports UNPAID; the "
                            "post-swap proofs remain in the wallet."
                        )

                    await self._finalize_paid_melt(
                        pending_entry,
                        outcome["payload"],
                    )
                    final_fees = amount_needed - amount
                    msg_out = (
                        f"Payment of {amount} sats with fee {final_fees} sats "
                        f"to {lnaddress} successful!"
                    )
                    self.logger.info(
                        "op=pay_multi status=complete amount=%s source=%s",
                        amount,
                        outcome["source"],
                    )
                    return msg_out, final_fees
                
                
                
                final_fees = amount_needed - amount
                msg_out = f"Payment of {amount} sats with fee {final_fees} sats to {lnaddress} successful!"
                self.logger.info("op=pay_multi status=complete amount=%s fees=%s", amount, final_fees)
                await self.write_proofs()
                self.logger.debug("op=pay_multi status=complete amount=%s", amount)
                self.logger.debug(
                    "op=pay_multi status=tx_history amount=%s tendered_amount=%s tendered_currency=%s",
                    amount,
                    tendered_amount,
                    tendered_currency,
                )
                await self.add_tx_history(tx_type='D', amount=amount, comment=comment, tendered_amount=tendered_amount, tendered_currency=tendered_currency, fees=final_fees)
        except (PaymentOutcomeUnknownError, PaymentFinalizationError, PaymentFailedError):
            raise
        except (ValueError, RuntimeError, httpx.HTTPError) as e:
            final_fees = 0
            if (
                "Token already spent" in str(e)
                or "11001" in str(e)
                or "stale proofs" in str(e).lower()
            ):
                msg_out = "Payment could not proceed because the wallet contains stale proofs."
            elif melt_attempted:
                msg_out = (
                    "Lightning payment outcome may be unresolved. Do not retry "
                    "until 'acorn reconcile-payments' reports PAID or UNPAID."
                )
            else:
                msg_out = f"Payment was not submitted to the mint: {e}"
            self.logger.error("%s original_error=%s", msg_out, e)
            raise RuntimeError(msg_out) from e
        finally:
            await self.release_lock()
    
        
        return msg_out, final_fees

    async def _multi_melt(self, keysets_to_use):

        
        headers = { "Content-Type": "application/json"}
        
        mpp_mint_melt_request = []
        
        for each in keysets_to_use:
            keyset_proofs,keyset_amounts = self._proofs_by_keyset()
            chosen_keyset = each[0]
            proofs_to_use = []
            proof_amount = 0
            proofs_from_keyset = keyset_proofs[each[0]]
            amount_needed = each[1]
            amount_to_pay = each[2]
            post_melt_response = each[3]
            melt_url = f"{self.known_mints[chosen_keyset]}/v1/melt/bolt11"
            self.logger.debug("op=multi_melt status=request amount_needed=%s keyset=%s", amount_needed, chosen_keyset)
            while proof_amount < amount_needed:
                pay_proof = proofs_from_keyset.pop()
                proofs_to_use.append(pay_proof)
                proof_amount += pay_proof.amount
            
            proofs_remaining = await self.swap_for_payment_multi(chosen_keyset,proofs_to_use, amount_needed)
            # proofs_remaining = proofs_to_use
            sum_proofs =0
            spend_proofs = []
            keep_proofs = []
            for each_proof in proofs_remaining:
                
                sum_proofs += each_proof.amount
                if sum_proofs <= amount_needed:
                    spend_proofs.append(each_proof)
                    self.logger.debug("op=multi_melt status=select_proof amount=%s", each_proof.amount)
                else:
                    keep_proofs.append(each_proof)
                    self.logger.debug("op=multi_melt status=retain_proof amount=%s", each_proof.amount)
            
            self.logger.debug(
                "op=multi_melt status=proof_selection spend_count=%s spend_amount=%s keep_count=%s keep_amount=%s",
                len(spend_proofs),
                sum(each.amount for each in spend_proofs),
                len(keep_proofs),
                sum(each.amount for each in keep_proofs),
            )
            melt_proofs = []
            for each_spend_proof in spend_proofs:
                    melt_proofs.append(each_spend_proof.to_dict())

            data_to_send = {"quote": post_melt_response.quote,
                        "inputs": melt_proofs }
            
        
            
            self.logger.debug(
                "op=multi_melt status=request_prepared amount=%s proofs=%s",
                amount_to_pay,
                len(melt_proofs),
            )
            mpp_mint_melt_request.append((melt_url,data_to_send))
            
        # print(mpp_mint_melt_request)
        await self._do_mpp_requests(mpp_mint_melt_request)
        self.logger.debug("op=multi_melt status=requests_complete")




            
        return 
           
    async def _do_mpp_requests(self, mpp_requests):
        tasks = []
        for each_request in mpp_requests:
            self.logger.debug("op=multi_melt status=queue_request request=%s", each_request[0])
            tasks.append(asyncio.create_task(self._post_request(each_request)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self.logger.debug("op=multi_melt status=tasks_completed")
    
    async def _post_request(self,request_item):
        timeout = httpx.Timeout(30.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            self.logger.debug("op=multi_melt status=post_request url=%s", request_item[0])
            response = await client.post(url=request_item[0], json=request_item[1])
            response.raise_for_status()
        return

            

    async def pay_multi_invoice(  self, 
                     
                    lninvoice: str, 
                    comment: str = "Paid!",
                    tendered_amount: float=None,
                    tendered_currency: str = "SAT",
                    fees: int =0,                             
                    payment_preimage: str = None,
                    payment_hash: str = None,
                    description_hash: str = None): 
        def _mint_error_with_body(action: str, response: httpx.Response) -> RuntimeError:
            body_text = response.text.strip()
            try:
                body_text = json.dumps(response.json())
            except Exception:
                pass
            return RuntimeError(
                f"{action} failed with HTTP {response.status_code}: {body_text or '<empty body>'}"
            )

        # decode amount from invoice
        melt_attempted = False
        try:
            await self.acquire_lock()
            await self._require_resolved_pending_melts()
            timeout = httpx.Timeout(30.0, connect=5.0)
            decoded_invoice = bolt11.decode(lninvoice)
            if decoded_invoice.amount_msat is None:
                raise ValueError("Amountless invoices are not supported.")
            ln_amount = int(decoded_invoice.amount_msat // 1e3)
            payment_hash = decoded_invoice.payment_hash
            description_hash = decoded_invoice.description_hash

            self.logger.debug("pay from multiple mints")
            available_amount = 0
            chosen_keyset = None
            keyset_proofs,keyset_amounts = self._proofs_by_keyset()
            for each in keyset_amounts:
                available_amount += keyset_amounts[each]
            
            
            self.logger.debug(f"available amount: {available_amount}")
            if available_amount < ln_amount:
                msg_out ="insufficient balance. you need more funds!"
                raise ValueError(msg_out)
                
            
            for key in sorted(keyset_amounts, key=lambda k: keyset_amounts[k]):
                self.logger.debug(f"{key}, {keyset_amounts[key]}")
                if keyset_amounts[key] >= ln_amount:
                    chosen_keyset = key
                    break
            if not chosen_keyset:
                self.logger.error("insufficient balance in any one keyset, you need to swap!") 
                raise ValueError("insufficient balance in any one keyset")
               
        
            self.logger.debug(f"chosen keyset: {chosen_keyset}")
            # Now do the pay routine
            melt_quote_url = f"{self.known_mints[chosen_keyset]}/v1/melt/quote/bolt11"
            melt_url = f"{self.known_mints[chosen_keyset]}/v1/melt/bolt11"
            self.logger.debug("op=pay_multi_invoice status=endpoints_ready")
            headers = { "Content-Type": "application/json"}
            # callback = lightning_address_pay(amount, lnaddress,comment=comment)
            pr = lninvoice        
            self.logger.debug("op=pay_multi_invoice status=quote_request amount=%s", ln_amount)
            data_to_send = {    "request": pr,
                                "unit": "sat"

                            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url=melt_quote_url, json=data_to_send, headers=headers)
                if response.is_error:
                    raise _mint_error_with_body("melt quote request", response)
            # check reponse for error
            # print(f"mint response: {response.json()}")
            response_json = response.json()
            if response_json.get('code', None) == 11000:
                raise RuntimeError("mint quote already paid!")
            post_melt_response = PostMeltQuoteResponse(**response.json())
            self.logger.debug(
                "op=pay_multi_invoice status=quote_received fee_reserve=%s",
                post_melt_response.fee_reserve,
            )
            proofs_to_use = []
            proof_amount = 0
            amount_needed = ln_amount + post_melt_response.fee_reserve
            self.logger.debug(f"amount needed: {amount_needed}")
            #FIXME There is something wrong with the logic here for chosen keysets
            # This is paying via invoice not lnadress so need to fix 1775
            if amount_needed > keyset_amounts[chosen_keyset]:
                self.logger.debug("insufficient balance in keyset. you need to swap, or use another keyset")
                chosen_keyset = None
                for key in sorted(keyset_amounts, key=lambda k: keyset_amounts[k]):
                    self.logger.debug(f"{key}, {keyset_amounts[key]}")
                    if keyset_amounts[key] >= amount_needed:
                        chosen_keyset = key
                        self.logger.debug(f"new chosen keyset: {key}")
                        break
                if not chosen_keyset:
                    msg_out="you don't have a sufficient balance in a keyset, you need to swap"
                    raise ValueError(msg_out)
                
                # Set to new mints and redo the calls
                melt_quote_url = f"{self.known_mints[chosen_keyset]}/v1/melt/quote/bolt11"
                melt_url = f"{self.known_mints[chosen_keyset]}/v1/melt/bolt11"
                self.logger.debug("op=pay_multi_invoice status=alternate_endpoints_ready")
                # We already have the invoice in this function
                # callback = lightning_address_pay(ln_amount, lninvoice,comment=comment)
                # pr = callback['pr']   
                pr = lninvoice     
                self.logger.debug("op=pay_multi_invoice status=alternate_quote_request amount=%s", ln_amount)
                data_to_send = {    "request": pr,
                                "unit": "sat"

                            }
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url=melt_quote_url, json=data_to_send, headers=headers)
                    if response.is_error:
                        raise _mint_error_with_body("melt quote request", response)
                post_melt_response = PostMeltQuoteResponse(**response.json())
                self.logger.debug(
                    "op=pay_multi_invoice status=alternate_quote_received fee_reserve=%s",
                    post_melt_response.fee_reserve,
                )

                if not chosen_keyset:
                    msg_out ="insufficient balance in any one keyset, you need to swap!"
                    raise ValueError(msg_out) 
                
            # Print now we should be all set to go
        
            self.logger.debug("---we have a sufficient mint---")
            self.logger.debug("op=pay_multi_invoice status=mint_ready fee_reserve=%s", post_melt_response.fee_reserve)
            proofs_to_use = []
            proof_amount = 0
            proofs_from_keyset = list(keyset_proofs[chosen_keyset])
            while proof_amount < amount_needed:
                pay_proof = proofs_from_keyset.pop()
                proofs_to_use.append(pay_proof)
                proof_amount += pay_proof.amount
                self.logger.debug(f"pop {pay_proof.amount}")
                
            self.logger.debug(
                "op=pay_multi_invoice status=input_selection selected=%s selected_amount=%s remaining=%s",
                len(proofs_to_use),
                sum(each.amount for each in proofs_to_use),
                len(proofs_from_keyset),
            )
            # Continue implementing from line 818 swap_for_payment may need a parameter
            # Now need to do the melt
            proofs_remaining = await self.swap_for_payment_multi(chosen_keyset,proofs_to_use, amount_needed)
            

            self.logger.debug("op=pay_multi_invoice status=swap_complete proofs=%s", len(proofs_remaining))
            self.logger.debug(f"amount needed: {amount_needed}")
            # Implement from line 824
            sum_proofs =0
            spend_proofs = []
            keep_proofs = []
            for each in proofs_remaining:
                
                sum_proofs += each.amount
                if sum_proofs <= amount_needed:
                    spend_proofs.append(each)
                    self.logger.debug("op=pay_multi_invoice status=select_proof amount=%s", each.amount)
                else:
                    keep_proofs.append(each)
                    self.logger.debug("op=pay_multi_invoice status=retain_proof amount=%s", each.amount)
            self.logger.debug(
                "op=pay_multi_invoice status=proof_selection spend_count=%s spend_amount=%s keep_count=%s keep_amount=%s",
                len(spend_proofs),
                sum(each.amount for each in spend_proofs),
                len(keep_proofs),
                sum(each.amount for each in keep_proofs),
            )
            melt_proofs = []
            for each_proof in spend_proofs:
                    melt_proofs.append(each_proof.to_dict())

            data_to_send = {"quote": post_melt_response.quote,
                        "inputs": melt_proofs }

            keyset_proofs[chosen_keyset] = (
                proofs_from_keyset + spend_proofs + keep_proofs
            )
            checkpoint_proofs: List[Proof] = []
            for key in keyset_proofs:
                checkpoint_proofs.extend(keyset_proofs[key])
            self.proofs = checkpoint_proofs
            self.balance = sum(each.amount for each in checkpoint_proofs)
            await self.write_proofs()

            pending_entry = {
                "quote": post_melt_response.quote,
                "mint": self.known_mints[chosen_keyset],
                "keyset": chosen_keyset,
                "spend_ys": [
                    str(each.Y or hash_to_curve(
                        str(each.secret).encode("utf-8")
                    ).serialize().hex())
                    for each in spend_proofs
                ],
                "amount": int(ln_amount),
                "fee_reserve": int(amount_needed - ln_amount),
                "comment": comment,
                "tendered_amount": tendered_amount,
                "tendered_currency": tendered_currency,
                "invoice": lninvoice,
                "payment_hash": payment_hash,
                "invoice_description_hash": description_hash,
                "created_at": int(datetime.now().timestamp()),
            }
            await self._upsert_pending_melt(pending_entry)

            melt_attempted = True
            outcome = await self._resolve_melt_submission(
                melt_url=melt_url,
                mint=self.known_mints[chosen_keyset],
                quote=post_melt_response.quote,
                request_payload=data_to_send,
                headers=headers,
                timeout=timeout,
            )
            if outcome["state"] == "UNPAID":
                await self._remove_pending_melt(post_melt_response.quote)
                raise PaymentFailedError(
                    f"Lightning invoice payment of {ln_amount} sats was not "
                    "paid. The mint reports UNPAID; the post-swap proofs "
                    "remain in the wallet."
                )

            await self._finalize_paid_melt(pending_entry, outcome["payload"])
            payment_preimage = outcome["payload"].get("payment_preimage")
            final_fees = amount_needed - ln_amount
            msg_out = f"Paid {ln_amount} sats with fees {final_fees} sats successful!"
            self.logger.info(
                    "op=pay_multi_invoice status=complete source=%s",
                    outcome["source"],
            )
            return msg_out, final_fees, payment_hash, payment_preimage, description_hash
        except (PaymentOutcomeUnknownError, PaymentFinalizationError, PaymentFailedError):
            raise
        except (ValueError, RuntimeError, httpx.HTTPError) as e:
            self.logger.error("Error in pay_multi_invoice: %s", e)
            if melt_attempted:
                msg_out = (
                    "Lightning invoice outcome may be unresolved. Do not retry "
                    "until 'acorn reconcile-payments' reports PAID or UNPAID."
                )
            else:
                msg_out = f"Invoice payment was not submitted to the mint: {e}"
            raise RuntimeError(msg_out) from e
        finally:
            await self.release_lock()
            self.logger.debug("op=pay_multi_invoice status=complete")

    async def delete_kind_events(self, record_kind:int):
        """
            Delete kind events
        """
        # first, get all of the events for the kind

        FILTER = [{
                'limit': RECORD_LIMIT, 
                '#p'  :  [self.pubkey_hex],              
                'kinds': [record_kind]
                
                }]
  

        async with ClientPool([self.home_relay]) as c:  
            events = await c.query(FILTER) 
        
        self.logger.debug("op=delete_kind_events status=events_found count=%s kind=%s", len(events), record_kind)
        for each in events:
            self.logger.debug("op=delete_kind_events status=event_id event_id=%s", each.id)
        
        tags = []
        for each_event in events:
            tags.append(["e",each_event.id])
            
        tags.append(["k",str(record_kind)])
        self.logger.debug("op=delete_kind_events status=tags count=%s", len(tags))
        
        
        try:

            async with ClientPool([self.home_relay]) as c:
            
                n_msg = Event(kind=Event.KIND_DELETE,
                            content=None,
                            pub_key=self.pubkey_hex,
                            tags=tags)
                n_msg.sign(self.privkey_hex)
                c.publish(n_msg)
                # added a delay here so the delete event get published
                await asyncio.sleep(1)
                self.logger.debug("op=delete_kind_events status=published")
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            raise RuntimeError("error deleting proof events")  
        
        return f"events of kind {record_kind} deleted on {self.home_relay}" 


    async def _async_delete_proof_events(self):
        """
            Delete proof events
        """
        #FIXME I don't this code does anything
        backup_proof_events = self.proof_events
        try:
            tags = []
            for each_event in self.proof_events.proof_events:
                tags.append(["e",each_event.id])
                self.logger.debug(f"proof to delete: {each_event.id}")
                # print(each_event.id)
                for each_proof in each_event.proofs:
                    # self.logger.debug(f"{each_proof.id}, {each_proof.amount}")
                    pass
            #FIXME end of fix me
            for each in self.proof_event_ids:
                tags.append(["e",each])
            tags.append(["k","7375"])
            self.logger.debug("op=delete_proof_events status=prepared tags=%s", len(tags))
            # print(f"tags for proof events to delete {tags}")
            
            async with ClientPool([self.home_relay]) as c:
            
                n_msg = Event(kind=Event.KIND_DELETE,
                            content=None,
                            pub_key=self.pubkey_hex,
                            tags=tags)
                n_msg.sign(self.privkey_hex)
                c.publish(n_msg)
                # added a delay here so the delete event get published
                await asyncio.sleep(1)
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            raise RuntimeError("error deleting proof events")    

    async def _async_delete_events_by_ids(
        self,
        event_ids: List[str],
        record_kind: int,
        verify: bool = True,
        verify_timeout: float = 8.0,
    ):
        if not event_ids:
            return {"status": "OK", "event_id": None, "verified": True}

        tags = []
        for event_id in event_ids:
            tags.append(["e", event_id])
        tags.append(["k", str(record_kind)])
        self.logger.debug(f"deleting {len(event_ids)} events for kind {record_kind}")

        async with ClientPool([self.home_relay]) as c:
            n_msg = Event(
                kind=Event.KIND_DELETE,
                content=None,
                pub_key=self.pubkey_hex,
                tags=tags,
            )
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            await asyncio.sleep(1)

        if verify:
            verify_filter = [{
                "limit": 1,
                "authors": [self.pubkey_hex],
                "kinds": [Event.KIND_DELETE],
                "ids": [str(n_msg.id)],
            }]
            deadline = monotonic() + max(0.5, float(verify_timeout))
            observed = False
            while monotonic() < deadline:
                async with ClientPool([self.home_relay]) as c:
                    readback = await c.query(verify_filter)
                    observed = any(str(event.id) == str(n_msg.id) for event in readback)
                    if not observed:
                        c.publish(n_msg)
                if observed:
                    break
                await asyncio.sleep(0.4)
            if not observed:
                raise RuntimeError(
                    "Proof deletion request could not be verified on "
                    f"{self.home_relay}"
                )

        return {
            "status": "OK",
            "event_id": str(n_msg.id),
            "verified": bool(verify),
        }

    async def swap_proofs(self, incoming_swap_proofs: List[Proof]):
        '''This function swaps proofs'''
        self.logger.debug("Swap proofs")
        if not incoming_swap_proofs:
            raise RuntimeError("No proofs supplied for swap")

        swap_amount =0
        count = 0
        
        headers = { "Content-Type": "application/json"}
        timeout = httpx.Timeout(30.0, connect=5.0)
        
        #keyset_url = f"{self.mints[0]}/v1/keysets"
        proof_keyset = incoming_swap_proofs[0].id
        mint_base = self.known_mints.get(proof_keyset)
        if not mint_base:
            raise RuntimeError(f"Unknown mint for keyset id: {proof_keyset}")

        keyset_url = f"{mint_base}/v1/keysets"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(keyset_url, headers=headers)
            response.raise_for_status()
            keyset = response.json()['keysets'][0]['id']

        swap_url = f"{mint_base}/v1/swap"
        swap_proofs = []
        blinded_swap_proofs = []
        blinded_values =[]
        blinded_messages = []
        new_proofs = []
        for each_proof in incoming_swap_proofs:
            swap_amount+=each_proof.amount        
            swap_proofs.append(each_proof.to_dict())                    
            count +=1
        
        r = PrivateKey()
        powers_of_2 = self.powers_of_2_sum(swap_amount)
        self.logger.debug("op=swap_proofs status=decompose total=%s proofs=%s", swap_amount, count)
        for each in powers_of_2:
                secret = secrets.token_hex(32)
                B_, r, Y = step1_alice(secret)
                blinded_values.append((B_,r, secret,Y))
                
                blinded_messages.append(    BlindedMessage( amount=each,
                                                            id=keyset,
                                                            B_=B_.serialize().hex(),
                                                            Y = Y.serialize().hex(),
                                                            ).model_dump()
                                        )
            
        data_to_send = {
                            "inputs":   swap_proofs,
                            "outputs": blinded_messages
                            
            } 
        
        try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url=swap_url, json=data_to_send, headers=headers)
                    if response.status_code >= 400:
                        body = response.text[:500]
                        self.logger.error(
                            "op=swap_proofs status=swap_http_error mint=%s keyset=%s code=%s body=%s",
                            mint_base,
                            proof_keyset,
                            response.status_code,
                            body,
                        )
                    response.raise_for_status()
                    promises = response.json()['signatures']

                    mint_key_url = f"{mint_base}/v1/keys/{keyset}"
                    response = await client.get(mint_key_url, headers=headers)
                    if response.status_code >= 400:
                        body = response.text[:500]
                        self.logger.error(
                            "op=swap_proofs status=keys_http_error mint=%s keyset=%s code=%s body=%s",
                            mint_base,
                            keyset,
                            response.status_code,
                            body,
                        )
                    response.raise_for_status()
                    keys = response.json()["keysets"][0]["keys"]
                # print(keys)
                new_proofs = []
                i = 0
            
                for each in promises:
                    pub_key_c = PublicKey()
                    # print("each:", each['C_'])
                    pub_key_c.deserialize(unhexlify(each['C_']))
                    promise_amount = each['amount']
                    A = keys[str(int(promise_amount))]
                    # A = keys[str(j)]
                    pub_key_a = PublicKey()
                    pub_key_a.deserialize(unhexlify(A))
                    r = blinded_values[i][1]
                    Y = blinded_values[i][3]
                    # print(pub_key_c, promise_amount,A, r)
                    C = step3_alice(pub_key_c,r,pub_key_a)
                    proof = {   "amount": promise_amount,
                            "id": keyset,
                            "secret": blinded_values[i][2],
                            "C":    C.serialize().hex(),
                            "Y":    Y.serialize().hex()
                            }
                    new_proofs.append(proof)
                    # print(proofs)
                    i+=1
        except httpx.HTTPStatusError as e:
                response_text = ""
                try:
                    response_text = (e.response.text or "")[:500]
                except Exception:
                    response_text = ""
                raise RuntimeError(
                    f"Problem with swap HTTP {e.response.status_code} on {swap_url}: {response_text}"
                ) from e
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as e:
                raise RuntimeError(f"Problem with swap {e}")

        # need to convert new_proofs into objects
        new_proof_obj_list = []
        for each in new_proofs:
            new_proof_obj_list.append(Proof(**each))

        return new_proof_obj_list
    
    async def swap_multi_consolidate(self):
        #TODO run swap_multi_each first to get rid of any potential doublespends
        #TODO figure out how to catch doublespends in this routine
        headers = { "Content-Type": "application/json"}
        timeout = httpx.Timeout(30.0, connect=5.0)
        lock_acquired = False
        combined_proofs = []
        combined_proof_objs =[]
        proof_objs = []
        
        # Let's check all the proofs before we do anything
        try:
            await self.acquire_lock()
            lock_acquired = True
            await self._load_proofs()
            source_event_ids = list(self.proof_event_ids)
            await self._require_resolved_pending_melts()
            keyset_proofs,keyset_amounts = self._proofs_by_keyset()
            if not keyset_proofs:
                self.logger.info("op=swap_multi_consolidate status=skip reason=no_proofs")
                return "multi swap skipped (no proofs)"
            audit_report = await self.proof_safety_audit(check_relay=False)
            if not audit_report.get("safe_to_swap", False):
                raise RuntimeError(
                    f"Proof safety audit failed before consolidate: {audit_report.get('reason')}"
                )

            for each_keyset in keyset_proofs:
                check = []
                mint_verify_url = f"{self.known_mints[each_keyset]}/v1/checkstate"
                for each_proof in keyset_proofs[each_keyset]:
                    check.append(each_proof.Y)

                # print(mint_verify_url, check)
                Ys = {"Ys": check}
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url=mint_verify_url, headers=headers, json=Ys)
                    response.raise_for_status()
                    check_response = response.json()
                proofs_to_check = check_response['states']
                for each_proof in proofs_to_check:
                    assert each_proof['state'] == "UNSPENT"
                    # print(each_proof['state'])
                
                    
            # return
            # All the proofs are verified, we are good to go for the swap    

 
            for each_keyset in keyset_proofs:
                
                each_keyset_url = self.known_mints[each_keyset]
                # print(each_keyset,each_keyset_url)
                swap_url = f"{self.known_mints[each_keyset]}/v1/swap"
                # print(swap_url)
                swap_proofs = []
                blinded_swap_proofs = []
                blinded_values =[]
                blinded_messages = []
                swap_amount =0
                count = 0
                for each_proof in keyset_proofs[each_keyset]:
                    # print(each_proof.amount)
                    swap_amount+=each_proof.amount
                    swap_proofs.append(each_proof.to_dict())                    
                    count +=1
                    # print("swap proofs:", swap_proofs)
                r = PrivateKey()

                # print("create blinded swap proofs")
                powers_of_2 = self.powers_of_2_sum(swap_amount)
                # print("total:", swap_amount,count, powers_of_2)
                for each in powers_of_2:
                    secret = secrets.token_hex(32)
                    B_, r, Y = step1_alice(secret)
                    blinded_values.append((B_,r, secret,Y))
                    
                    blinded_messages.append(    BlindedMessage( amount=each,
                                                                id=each_keyset,
                                                                B_=B_.serialize().hex(),
                                                                Y = Y.serialize().hex(),
                                                                ).model_dump()
                                            )
                data_to_send = {
                                "inputs":   swap_proofs,
                                "outputs": blinded_messages
                                
                }
            
                # print(data_to_send)
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(url=swap_url, json=data_to_send, headers=headers)
                        if response.is_error:
                            response_text = response.text.strip()
                            raise RuntimeError(
                                "Mint rejected consolidation swap for keyset "
                                f"{each_keyset} at mint {self.known_mints.get(each_keyset)} "
                                f"with status {response.status_code}: {response_text or '<empty body>'}"
                            )
                        promises = response.json()['signatures']

                        mint_key_url = f"{self.known_mints[each_keyset]}/v1/keys/{each_keyset}"
                        response = await client.get(mint_key_url, headers=headers)
                        response.raise_for_status()
                        keys = response.json()["keysets"][0]["keys"]
                    # print(keys)
                    proofs = []
                    proof_objs = []
                    i = 0
                
                    for each in promises:
                        pub_key_c = PublicKey()
                        # print("each:", each['C_'])
                        pub_key_c.deserialize(unhexlify(each['C_']))
                        promise_amount = each['amount']
                        A = keys[str(int(promise_amount))]
                        # A = keys[str(j)]
                        pub_key_a = PublicKey()
                        pub_key_a.deserialize(unhexlify(A))
                        r = blinded_values[i][1]
                        Y = blinded_values[i][3]
                        # print(pub_key_c, promise_amount,A, r)
                        C = step3_alice(pub_key_c,r,pub_key_a)
                        proof = {   "amount": promise_amount,
                                "id": each_keyset,
                                "secret": blinded_values[i][2],
                                "C":    C.serialize().hex(),
                                "Y":    Y.serialize().hex()
                                }
                        proofs.append(proof)
                        proof_obj = Proof(amount=promise_amount,
                                            id=each_keyset,
                                            secret=blinded_values[i][2],
                                            C=C.serialize().hex(),
                                            Y = Y.serialize().hex()
                                            )
                        proof_objs.append(proof_obj)

                        # print(proofs)
                        i+=1

                    # A successful keyset consolidation has consumed all of
                    # that keyset's inputs. Make its replacements durable
                    # before processing another keyset.
                    await self.add_proofs_obj(proof_objs, verify=True)
                except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                    raise RuntimeError(
                        f"Consolidation failed for keyset {each_keyset} at mint {self.known_mints.get(each_keyset)}: {exc}"
                    ) from exc

                combined_proofs = combined_proofs + proofs
                combined_proof_objs = combined_proof_objs + proof_objs
            # print(request_body) 
            # refresh balance
            
            swap_balance = 0
            for each in self.proofs:
                swap_balance += each.amount
            # print(len(self.proofs))
            if not combined_proof_objs:
                raise RuntimeError("Consolidation produced zero proofs; refusing to overwrite existing proofs")

            if source_event_ids:
                await self._async_delete_events_by_ids(
                    source_event_ids,
                    record_kind=7375,
                )
            await self._load_proofs()
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError):
            raise
        
        finally:
            if lock_acquired:
                await self.release_lock()
    
        
        return f"multi swap ok  {len(self.proofs)} proofs in {self.events} proof events"

    async def swap_multi_each(self):
        #FIXME this is used before consolidate to throw out any dups or doublespend. Fix events
        headers = { "Content-Type": "application/json"}
        timeout = httpx.Timeout(30.0, connect=5.0)
        combined_proofs = []
        combined_proof_objs =[]
        lock_acquired = False
        duplicate_dropped = 0
        stale_dropped = 0
        
        # Let's check all the proofs before we do anything
        try:
            await self.acquire_lock()
            lock_acquired = True
            await self._load_proofs()
            source_event_ids = list(self.proof_event_ids)
            await self._require_resolved_pending_melts()
            keyset_proofs,_keyset_amounts = self._proofs_by_keyset()
            if not keyset_proofs:
                self.logger.info("op=swap_multi_each status=skip reason=no_proofs")
                return "multi swap skipped (no proofs)"
            audit_report = await self.proof_safety_audit(check_relay=False)
            if not audit_report.get("safe_to_swap", False):
                raise RuntimeError(
                    f"Proof safety audit failed before swap_each: {audit_report.get('reason')}"
                )

            candidate_keyset_proofs = {}

            for each_keyset, proofs_for_keyset in keyset_proofs.items():
                unique_proofs = []
                seen_proofs = set()
                for each_proof in proofs_for_keyset:
                    proof_key = (str(each_proof.id), str(each_proof.secret))
                    if proof_key in seen_proofs:
                        duplicate_dropped += 1
                        continue
                    seen_proofs.add(proof_key)
                    unique_proofs.append(each_proof)

                if not unique_proofs:
                    continue

                check = [each_proof.Y for each_proof in unique_proofs]
                mint_verify_url = f"{self.known_mints[each_keyset]}/v1/checkstate"
                Ys = {"Ys": check}
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url=mint_verify_url, headers=headers, json=Ys)
                    response.raise_for_status()
                    check_response = response.json()
                proofs_to_check = check_response.get("states", []) if isinstance(check_response, dict) else []
                if len(proofs_to_check) != len(unique_proofs):
                    raise RuntimeError(
                        f"Swap-each checkstate length mismatch for keyset {each_keyset}: "
                        f"{len(proofs_to_check)} states for {len(unique_proofs)} proofs"
                    )

                surviving_proofs = []
                invalid_states = []
                for each_proof, state_obj in zip(unique_proofs, proofs_to_check):
                    state_value = state_obj.get("state") if isinstance(state_obj, dict) else None
                    if state_value == "UNSPENT":
                        surviving_proofs.append(each_proof)
                    else:
                        stale_dropped += 1
                        invalid_states.append(state_value or "<missing>")

                if invalid_states:
                    self.logger.warning(
                        "op=swap_multi_each status=drop_invalid_checkstate keyset=%s mint=%s dropped=%s states=%s",
                        each_keyset,
                        self.known_mints.get(each_keyset),
                        len(invalid_states),
                        ",".join(invalid_states),
                    )

                if surviving_proofs:
                    candidate_keyset_proofs[each_keyset] = surviving_proofs
                
            # return
            # All the proofs are verified, we are good to go for the swap   
            # In multi_each we are going to swap for each proof 
            

            for each_keyset, proofs_for_keyset in candidate_keyset_proofs.items():
                mint_key_url = f"{self.known_mints[each_keyset]}/v1/keys/{each_keyset}"
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(mint_key_url, headers=headers)
                    response.raise_for_status()
                    keys = response.json()["keysets"][0]["keys"]
                # print(each_keyset,each_keyset_url)
                swap_url = f"{self.known_mints[each_keyset]}/v1/swap"
                
                for each_proof in proofs_for_keyset:
                    # print(each_proof.amount)
                    blinded_values =[]
                    blinded_messages = []
                    secret = secrets.token_hex(32)
                    B_, r, Y = step1_alice(secret)
                    blinded_values.append((B_,r, secret,Y))
                    
                    blinded_messages.append(    BlindedMessage( amount=each_proof.amount,
                                                                id=each_keyset,
                                                                B_=B_.serialize().hex(),
                                                                Y = Y.serialize().hex(),
                                                                ).model_dump()
                                            )
                    data_to_send = {
                                "inputs":   [each_proof.to_dict()],
                                "outputs": blinded_messages
                                
                    }
                    proofs = []
                    proof_objs = []
                    
                    try:
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            response = await client.post(url=swap_url, json=data_to_send, headers=headers)
                            if response.is_error:
                                response_text = response.text.strip()
                                stale_proof_error = False
                                try:
                                    response_json = response.json()
                                    stale_proof_error = (
                                        response_json.get("code") == 11001
                                        or "Token already spent" in str(response_json.get("detail", ""))
                                    )
                                except Exception:
                                    stale_proof_error = "Token already spent" in response_text

                                if stale_proof_error:
                                    stale_dropped += 1
                                    self.logger.warning(
                                        "op=swap_multi_each status=drop_on_swap keyset=%s mint=%s amount=%s reason=already_spent",
                                        each_keyset,
                                        self.known_mints.get(each_keyset),
                                        each_proof.amount,
                                    )
                                    continue
                                raise RuntimeError(
                                    "Mint rejected swap-each for keyset "
                                    f"{each_keyset} at mint {self.known_mints.get(each_keyset)} "
                                    f"with status {response.status_code}: {response_text or '<empty body>'}"
                                )
                            promises = response.json()['signatures']
                        # print("promises:", promises)
                        
                        i = 0
                
                        for each in promises:
                            pub_key_c = PublicKey()
                            # print("each:", each['C_'])
                            pub_key_c.deserialize(unhexlify(each['C_']))
                            promise_amount = each['amount']
                            A = keys[str(int(promise_amount))]
                            # A = keys[str(j)]
                            pub_key_a = PublicKey()
                            pub_key_a.deserialize(unhexlify(A))
                            r = blinded_values[i][1]
                            Y = blinded_values[i][3]
                            # print(pub_key_c, promise_amount,A, r)
                            C = step3_alice(pub_key_c,r,pub_key_a)
                            proof = {   "amount": promise_amount,
                                "id": each_keyset,
                                "secret": blinded_values[i][2],
                                "C":    C.serialize().hex(),
                                "Y":    Y.serialize().hex()
                                }
                            proofs.append(proof)
                            # print(proofs)
                            proof_obj = Proof(amount=promise_amount,
                                            id=each_keyset,
                                            secret=blinded_values[i][2],
                                            C=C.serialize().hex(),
                                            Y = Y.serialize().hex()
                                            )
                            proof_objs.append(proof_obj)
                            i+=1

                        # Each successful mint swap has already consumed its
                        # input. Persist and verify the replacements before
                        # another input can be touched so a later failure
                        # cannot strand bearer proofs in process memory.
                        await self.add_proofs_obj(proof_objs, verify=True)
                    except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                        raise RuntimeError(
                            f"Swap-each failed for keyset {each_keyset} at mint {self.known_mints.get(each_keyset)}: {exc}"
                        ) from exc

                    combined_proofs = combined_proofs + proofs
                    combined_proof_objs = combined_proof_objs + proof_objs

            if not combined_proof_objs:
                raise RuntimeError(
                    "swap-each found zero usable replacement proofs and refused to overwrite the wallet. "
                    "Run repair-proofs only after confirming the mint state is stable."
                )

            if source_event_ids:
                await self._async_delete_events_by_ids(
                    source_event_ids,
                    record_kind=7375,
                )
            await self._load_proofs()

        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError):
            raise
        
        finally:
            if lock_acquired:
                await self.release_lock()
                   
        
        return (
            "multi swap ok"
            if duplicate_dropped == 0 and stale_dropped == 0
            else f"multi swap ok (dropped {stale_dropped} stale proofs, {duplicate_dropped} duplicates)"
        )
    async def _async_swap(self):
        # This is the async version of swap
        headers = { "Content-Type": "application/json"}
        timeout = httpx.Timeout(30.0, connect=5.0)
        keyset_proofs,keyset_amounts = self._proofs_by_keyset()
        combined_proofs = []
        combined_proof_objs =[]
        
        # Let's check all the proofs before we do anything

        async with httpx.AsyncClient(timeout=timeout) as client:
            for each_keyset in keyset_proofs:
                check = []
                mint_verify_url = f"{self.known_mints[each_keyset]}/v1/checkstate"
                for each_proof in keyset_proofs[each_keyset]:
                    check.append(each_proof.Y)

                Ys = {"Ys": check}
                try:
                    response = await client.post(url=mint_verify_url, headers=headers, json=Ys)
                    response.raise_for_status()
                    check_response = response.json()
                    proofs_to_check = check_response["states"]
                    for each_proof in proofs_to_check:
                        if each_proof.get("state") != "UNSPENT":
                            raise ValueError(f"Proof state not spendable: {each_proof.get('state')}")
                except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
                    self.logger.warning(
                        "op=async_swap status=checkstate_failed mint=%s keyset=%s error=%s",
                        self.known_mints.get(each_keyset),
                        each_keyset,
                        exc,
                    )
                    return f"there is a problem with the mint {self.known_mints[each_keyset]}"
                
            # return
            # All the proofs are verified, we are good to go for the swap
            # In multi_each we are going to swap for each proof
            for each_keyset in keyset_proofs:
                mint_key_url = f"{self.known_mints[each_keyset]}/v1/keys/{each_keyset}"
                try:
                    response = await client.get(mint_key_url, headers=headers)
                    response.raise_for_status()
                    keys = response.json()["keysets"][0]["keys"]
                except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
                    self.logger.error(
                        "op=async_swap status=key_fetch_failed keyset=%s mint=%s error=%s",
                        each_keyset,
                        self.known_mints.get(each_keyset),
                        exc,
                    )
                    raise RuntimeError(f"Unable to fetch keys for keyset {each_keyset}") from exc

                swap_url = f"{self.known_mints[each_keyset]}/v1/swap"
                
                for each_proof in keyset_proofs[each_keyset]:
                    blinded_values =[]
                    blinded_messages = []
                    secret = secrets.token_hex(32)
                    B_, r, Y = step1_alice(secret)
                    blinded_values.append((B_,r, secret,Y))
                    
                    blinded_messages.append(    BlindedMessage( amount=each_proof.amount,
                                                                id=each_keyset,
                                                                B_=B_.serialize().hex(),
                                                                Y = Y.serialize().hex(),
                                                                ).model_dump()
                                            )
                    data_to_send = {
                                "inputs":   [each_proof.to_dict()],
                                "outputs": blinded_messages
                                
                    }
                    proofs = []
                    proof_objs = []
                    try:
                        response = await client.post(url=swap_url, json=data_to_send, headers=headers)
                        response.raise_for_status()
                        promises = response.json()['signatures']
                        
                        i = 0
                
                        for each in promises:
                            pub_key_c = PublicKey()
                            pub_key_c.deserialize(unhexlify(each['C_']))
                            promise_amount = each['amount']
                            A = keys[str(int(promise_amount))]
                            pub_key_a = PublicKey()
                            pub_key_a.deserialize(unhexlify(A))
                            r = blinded_values[i][1]
                            Y = blinded_values[i][3]
                            C = step3_alice(pub_key_c,r,pub_key_a)
                            proof = {   "amount": promise_amount,
                                "id": each_keyset,
                                "secret": blinded_values[i][2],
                                "C":    C.serialize().hex(),
                                "Y":    Y.serialize().hex()
                                }
                            proofs.append(proof)
                            proof_obj = Proof(amount=promise_amount,
                                          id=each_keyset,
                                          secret=blinded_values[i][2],
                                          C=C.serialize().hex(),
                                          Y = Y.serialize().hex()
                                          )
                            proof_objs.append(proof_obj)
                            i+=1
                    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
                        self.logger.warning(
                            "op=async_swap status=swap_step_failed keyset=%s mint=%s error=%s",
                            each_keyset,
                            self.known_mints.get(each_keyset),
                            exc,
                        )
                        continue

                    combined_proofs = combined_proofs + proofs
                    combined_proof_objs = combined_proof_objs + proof_objs

        if not combined_proof_objs:
            raise RuntimeError("Async swap produced zero proofs; refusing destructive proof replacement")

        self.logger.debug("op=async_swap status=write_proofs proofs=%s", len(combined_proof_objs))
        self.proofs = combined_proof_objs
        await self.write_proofs()
        
        # self._load_proofs()
        FILTER = [{
            'limit': RECORD_LIMIT,
            'authors': [self.pubkey_hex],
            'kinds': [7375]
        }]
        await self._async_load_proofs(FILTER)

        return     
    def swap_for_payment(self, proofs_to_use: List[Proof], payment_amount: int)->List[Proof]:
        # create proofs to melt, and proofs_remaining

        swap_amount =0
        count = 0
        
        headers = { "Content-Type": "application/json"}
        keyset_url = f"{self.mints[0]}/v1/keysets"
        response = requests.get(keyset_url, headers=headers)
        keyset = response.json()['keysets'][0]['id']

        swap_url = f"{self.mints[0]}/v1/swap"

        swap_proofs = []
        blinded_values =[]
        blinded_messages = []
        proofs = []
        proofs_to_melt = []
        proofs_remaing = []
        # Figure out proofs_to_use_amount
        proofs_to_use_amount = 0
        for each in proofs_to_use:
            proofs_to_use_amount += each.amount
       
        powers_of_2_payment = self.powers_of_2_sum(payment_amount)
        

        for each in powers_of_2_payment:
            secret = secrets.token_hex(32)
            B_, r, Y = step1_alice(secret)
            blinded_values.append((B_,r, secret))
            
            blinded_messages.append(    BlindedMessage( amount=each,
                                                        id=keyset,
                                                        B_=B_.serialize().hex(),
                                                        Y = Y.serialize().hex(),
                                                        ).model_dump()
                                    )
        if proofs_to_use_amount > payment_amount:
            powers_of_2_leftover = self.powers_of_2_sum(proofs_to_use_amount- payment_amount)
            for each in powers_of_2_leftover:
                secret = secrets.token_hex(32)
                B_, r, Y = step1_alice(secret)
                blinded_values.append((B_,r, secret))
            
                blinded_messages.append(    BlindedMessage( amount=each,
                                                        id=keyset,
                                                        B_=B_.serialize().hex(),
                                                        Y = Y.serialize().hex(),
                                                        ).model_dump()
                                    )

        proofs_to_send =[]
        for each in proofs_to_use:
            proofs_to_send.append(each.to_dict())

        data_to_send = {
                        "inputs":  proofs_to_send,
                        "outputs": blinded_messages
                        
        }

        # print(powers_of_2_payment, powers_of_2_leftover)
        # print(proofs_to_use)
        # print(blinded_messages)
        # print(data_to_send)

        try:
            # print("are we here?")
            response = requests.post(url=swap_url, json=data_to_send, headers=headers)
            
            self.logger.debug("op=swap_for_payment status=response_received")
            promises = response.json()['signatures']
            self.logger.debug("op=swap_for_payment status=promises count=%s", len(promises))

        
            mint_key_url = f"{self.mints[0]}/v1/keys/{keyset}"
            response = requests.get(mint_key_url, headers=headers)
            keys = response.json()["keysets"][0]["keys"]
            # print(keys)
            
            i = 0
        
            for each in promises:
                pub_key_c = PublicKey()
                self.logger.debug("op=swap_for_payment status=promise amount=%s", each.get("amount"))
                pub_key_c.deserialize(unhexlify(each['C_']))
                promise_amount = each['amount']
                A = keys[str(int(promise_amount))]
                # A = keys[str(j)]
                pub_key_a = PublicKey()
                pub_key_a.deserialize(unhexlify(A))
                r = blinded_values[i][1]
                self.logger.debug("op=swap_for_payment status=unblind amount=%s", promise_amount)
                C = step3_alice(pub_key_c,r,pub_key_a)
                
                proof = Proof(  amount=promise_amount,
                                id=keyset,
                                secret=blinded_values[i][2],
                                C=C.serialize().hex() )
                
                proofs.append(proof)
                # print(proofs)
                i+=1
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            raise RuntimeError(f"swap_for_payment failed: {exc}") from exc
        
        for each in proofs:
            self.logger.debug("op=swap_for_payment status=proof amount=%s", each.amount)
        # now need break out proofs for payment and proofs remaining

        return proofs

    async def swap_for_payment_multi(self, keyset_to_use:str, proofs_to_use: List[Proof], payment_amount: int)->List[Proof]:
        # create proofs to melt, and proofs_remaining

        swap_amount =0
        count = 0
        
        headers = { "Content-Type": "application/json"}
        timeout = httpx.Timeout(30.0, connect=5.0)
        keyset_url = f"{self.known_mints[keyset_to_use]}/v1/keysets"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(keyset_url, headers=headers)
            response.raise_for_status()
            keyset = response.json()['keysets'][0]['id']

        swap_url = f"{self.known_mints[keyset_to_use]}/v1/swap"
        checkstate_url = f"{self.known_mints[keyset_to_use]}/v1/checkstate"

        swap_proofs = []
        blinded_values =[]
        blinded_messages = []
        proofs = []
        checkstate_ys = []

        self.logger.debug("op=swap_for_payment_multi status=checkstate_start")
        for each in proofs_to_use:
            self.logger.debug("op=swap_for_payment_multi status=checkstate_y")
            checkstate_ys.append(each.Y)

        data_to_send = {"Ys": checkstate_ys}  
        self.logger.debug("op=swap_for_payment_multi status=checkstate_payload")
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url=checkstate_url, json=data_to_send, headers=headers)
            response.raise_for_status()
            checkstate_response = response.json()
            self.logger.debug("op=swap_for_payment_multi status=checkstate_response")

        states = checkstate_response.get("states", []) if isinstance(checkstate_response, dict) else []
        invalid_states = []
        for idx, state_obj in enumerate(states):
            state_value = None
            if isinstance(state_obj, dict):
                state_value = state_obj.get("state")
            # Only UNSPENT proofs are safe to pass into /swap.
            if state_value not in ("UNSPENT",):
                invalid_states.append((idx, state_value))

        if invalid_states:
            invalid_summary = ", ".join([f"{idx}:{state}" for idx, state in invalid_states])
            self.logger.warning(
                "op=swap_for_payment_multi status=invalid_checkstate keyset=%s details=%s",
                keyset_to_use,
                invalid_summary,
            )
            raise RuntimeError(
                f"mint rejected one or more proofs before swap (states: {invalid_summary}). "
                "Retry payment after wallet state refresh."
            )

        # Figure out proofs_to_use_amount
        proofs_to_use_amount = 0
        for each in proofs_to_use:
            proofs_to_use_amount += each.amount
       
        powers_of_2_payment = self.powers_of_2_sum(payment_amount)
        

        for each in powers_of_2_payment:
            secret = secrets.token_hex(32)
            B_, r, Y = step1_alice(secret)
            blinded_values.append((B_,r, secret))
            
            blinded_messages.append(    BlindedMessage( amount=each,
                                                        id=keyset,
                                                        B_=B_.serialize().hex(),
                                                        Y = Y.serialize().hex(),
                                                        ).model_dump()
                                    )
        if proofs_to_use_amount > payment_amount:
            powers_of_2_leftover = self.powers_of_2_sum(proofs_to_use_amount- payment_amount)
            for each in powers_of_2_leftover:
                secret = secrets.token_hex(32)
                B_, r, Y = step1_alice(secret)
                blinded_values.append((B_,r, secret))
            
                blinded_messages.append(    BlindedMessage( amount=each,
                                                        id=keyset,
                                                        B_=B_.serialize().hex(),
                                                        Y = Y.serialize().hex(),
                                                        ).model_dump()
                                    )

        proofs_to_send =[]
        for each in proofs_to_use:
            proofs_to_send.append(each.to_dict())

        data_to_send = {
                        "inputs":  proofs_to_send,
                        "outputs": blinded_messages
                        
        }

        # print(powers_of_2_payment, powers_of_2_leftover)
        # print(proofs_to_use)
        # print(blinded_messages)
        # print(data_to_send)

        try:
            self.logger.debug("are we here?")
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url=swap_url, json=data_to_send, headers=headers)
                if response.status_code >= 400:
                    response_text = response.text
                    stale_proof_error = False
                    try:
                        response_json = response.json()
                        stale_proof_error = (
                            response_json.get("code") == 11001
                            or "Token already spent" in str(response_json.get("detail", ""))
                        )
                    except Exception:
                        stale_proof_error = "Token already spent" in response_text
                    self.logger.warning(
                        "op=swap_for_payment_multi status=swap_http_error keyset=%s code=%s body=%s",
                        keyset_to_use,
                        response.status_code,
                        response_text,
                    )
                    if stale_proof_error:
                        raise RuntimeError(
                            "swap rejected because one or more selected proofs were already spent "
                            f"(keyset {keyset_to_use}, mint {self.known_mints.get(keyset_to_use)}). "
                            "Local wallet proof state is stale. Refresh/reconcile proofs before retrying payment."
                        )
                    raise RuntimeError(
                        f"swap failed with HTTP {response.status_code}: {response_text}"
                    )
                promises = response.json()['signatures']

                mint_key_url = f"{self.known_mints[keyset_to_use]}/v1/keys/{keyset}"
                response = await client.get(mint_key_url, headers=headers)
                response.raise_for_status()
                keys = response.json()["keysets"][0]["keys"]
            # print(keys)
            
            i = 0
        
            for each in promises:
                pub_key_c = PublicKey()
                # print("each:", each['C_'])
                pub_key_c.deserialize(unhexlify(each['C_']))
                promise_amount = each['amount']
                A = keys[str(int(promise_amount))]
                # A = keys[str(j)]
                pub_key_a = PublicKey()
                pub_key_a.deserialize(unhexlify(A))
                r = blinded_values[i][1]
                secret_msg = blinded_values[i][2]
                Y: PublicKey = hash_to_curve(secret_msg.encode("utf-8"))
                self.logger.debug(
                    "op=swap_for_payment_multi status=unblind amount=%s",
                    promise_amount,
                )
                C = step3_alice(pub_key_c,r,pub_key_a)
                
                proof = Proof(  amount=promise_amount,
                                id=keyset,
                                secret=secret_msg,
                                C=C.serialize().hex(),
                                Y = Y.serialize().hex()
                              
                                 
                                )
                
                proofs.append(proof)
                # print(proofs)
                i+=1
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as e:
            self.logger.warning("op=swap_for_payment_multi status=failed error=%s", e)
            raise RuntimeError(f"ERROR {e}")
        
        for each in proofs:
            pass
            # print(each.amount)
        # now need break out proofs for payment and proofs remaining

        return proofs

    def swap_for_payment_inputs(self, keyset_to_use:str, proofs_to_use: List[Proof], payment_amount: int)->List[Proof]:
        # create proofs to melt, and proofs_remaining

        swap_amount =0
        count = 0
        
        headers = { "Content-Type": "application/json"}
        keyset_url = f"{self.known_mints[keyset_to_use]}/v1/keysets"
        response = requests.get(keyset_url, headers=headers)
        keyset = response.json()['keysets'][0]['id']

        swap_url = f"{self.known_mints[keyset_to_use]}/v1/swap"

        swap_proofs = []
        blinded_values =[]
        blinded_messages = []
        proofs = []
        
        # Figure out proofs_to_use_amount
        proofs_to_use_amount = 0
        for each in proofs_to_use:
            proofs_to_use_amount += each.amount
       
        powers_of_2_payment = self.powers_of_2_sum(payment_amount)
        

        for each in powers_of_2_payment:
            secret = secrets.token_hex(32)
            B_, r, Y = step1_alice(secret)
            blinded_values.append((B_,r, secret))
            
            blinded_messages.append(    BlindedMessage( amount=each,
                                                        id=keyset,
                                                        B_=B_.serialize().hex(),
                                                        Y = Y.serialize().hex(),
                                                        ).model_dump()
                                    )
        if proofs_to_use_amount > payment_amount:
            powers_of_2_leftover = self.powers_of_2_sum(proofs_to_use_amount- payment_amount)
            for each in powers_of_2_leftover:
                secret = secrets.token_hex(32)
                B_, r, Y = step1_alice(secret)
                blinded_values.append((B_,r, secret))
            
                blinded_messages.append(    BlindedMessage( amount=each,
                                                        id=keyset,
                                                        B_=B_.serialize().hex(),
                                                        Y = Y.serialize().hex(),
                                                        ).model_dump()
                                    )

        proofs_to_send =[]
        for each in proofs_to_use:
            proofs_to_send.append(each.to_dict())

        data_to_send = {
                        "inputs":  proofs_to_send,
                        "outputs": blinded_messages
                        
        }



        try:
            self.logger.debug("are we here?")
            response = requests.post(url=swap_url, json=data_to_send, headers=headers)
            
            # print(response.json())
            promises = response.json()['signatures']
            # print("promises:", promises)

        
            mint_key_url = f"{self.known_mints[keyset_to_use]}/v1/keys/{keyset}"
            response = requests.get(mint_key_url, headers=headers)
            keys = response.json()["keysets"][0]["keys"]
            # print(keys)
            
            i = 0
        
            for each in promises:
                pub_key_c = PublicKey()
                # print("each:", each['C_'])
                pub_key_c.deserialize(unhexlify(each['C_']))
                promise_amount = each['amount']
                A = keys[str(int(promise_amount))]
                # A = keys[str(j)]
                pub_key_a = PublicKey()
                pub_key_a.deserialize(unhexlify(A))
                r = blinded_values[i][1]
                secret_msg = blinded_values[i][2]
                Y: PublicKey = hash_to_curve(secret_msg.encode("utf-8"))
                self.logger.debug(
                    "op=swap_for_payment_inputs status=unblind amount=%s",
                    promise_amount,
                )
                C = step3_alice(pub_key_c,r,pub_key_a)
                
                proof = Proof(  amount=promise_amount,
                                id=keyset,
                                secret=secret_msg,
                                C=C.serialize().hex(),
                                Y = Y.serialize().hex()
                              
                                 
                                )
                
                proofs.append(proof)
                # print(proofs)
                i+=1
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as e:
            self.logger.warning("op=swap_for_payment_inputs status=failed error=%s", e)
        
        for each in proofs:
            pass
            # print(each.amount)
        # now need break out proofs for payment and proofs remaining

        return proofs
            
    async def accept_token(
        self,
        cashu_token: str,
        comment: str = "ecash deposit",
        tendered_amount: float | None = None,
        tendered_currency: str = "SAT",
    ):
        self.logger.debug("op=accept_token status=start token_bytes=%s", len(cashu_token))
        # asyncio.run(self.nip17_accept(cashu_token))
        # msg_out, token_accepted_amount = await self._async_token_accept(cashu_token)
        # self.set_wallet_info(label="trusted_mints", label_info=json.dumps(self.trusted_mints))

        
        
        # return f'Not implemented', 0
        
        lock_acquired = False
        try:

            
            token_amount =0

            token_mints: set[str] = set()

            if cashu_token[:6] == "cashuA":

                
                token_obj = TokenV3.deserialize(cashu_token)
                
                
                        # need to inspect if a new mint

                proofs=[]
                proof_obj_list: List[Proof] = []
                for each in token_obj.token: 
                    # print(each.mint)
                    for each_proof in each.proofs:
                        
                        proofs.append(each_proof.model_dump())
                        proof_obj_list.append(each_proof)
                        id = each_proof.id
                        self.known_mints[id]=each.mint
                        if each.mint:
                            token_mints.add(each.mint)
                        token_amount += each_proof.amount
                        # print(id, each.mint)

            


            elif cashu_token[:6] == "cashuB":
                    token_obj = TokenV4.deserialize(cashu_token)
                    # print(token_obj)
                    proofs=[]
                    proof_obj_list: List[Proof] = []
                    for each_proof in token_obj.proofs:
                        proofs.append(each_proof.model_dump())
                        proof_obj_list.append(each_proof)
                        id = each_proof.id
                        self.known_mints[id] = token_obj.mint
                        token_amount += each_proof.amount
                    if token_obj.mint:
                        token_mints.add(token_obj.mint)
            else:
                raise ValueError("Not a valid cashu token format")

            if len(token_mints) != 1:
                raise ValueError(
                    "Cashu token must identify exactly one issuing mint"
                )
            token_mint = next(iter(token_mints))
              
            swap_proofs = await self.swap_proofs(proof_obj_list)
            if not swap_proofs:
                raise RuntimeError("Mint swap returned no refreshed proofs")
            for proof in swap_proofs:
                # A mint may rotate its active keyset. The received token can
                # therefore use one keyset while /swap returns another.
                self.known_mints[proof.id] = token_mint
            self.logger.debug(
                "op=accept_token status=swapped token_amount=%s input_proofs=%s output_proofs=%s",
                token_amount,
                len(proof_obj_list),
                len(swap_proofs),
            )
            
            await self.acquire_lock()
            lock_acquired = True
            await self.add_proofs_obj(swap_proofs, verify=True)

            self.proofs = self._deduplicate_proofs([*self.proofs, *swap_proofs])
            self.balance = sum(proof.amount for proof in self.proofs)

        
            
            self.logger.info("op=accept_token status=success token_amount=%s", token_amount)
        except (ValueError, TypeError, RuntimeError, httpx.HTTPError) as e:
            self.logger.error("op=accept_token status=failed error=%s", e)
            raise RuntimeError(f"Unable to accept token safely: {e}") from e
            
        
        finally:
            if lock_acquired:
                await self.release_lock()
        await self.add_tx_history(
            tx_type='C',
            amount=token_amount,
            comment=comment,
            tendered_amount=tendered_amount,
            tendered_currency=tendered_currency,
        )
        return f'Successfully accepted {token_amount} sats!', token_amount


       

        


    async def issue_token(self, amount:int, comment:str = "ecash withdrawal"):

        lock_acquired = False
        token_serialized = None
        try:
            await self.acquire_lock()
            lock_acquired = True
            await self._require_resolved_pending_melts()
            # print("issue token")
            available_amount = 0
            chosen_keyset = None
            keyset_proofs,keyset_amounts = self._proofs_by_keyset()
            for each in keyset_amounts:
                available_amount += keyset_amounts[each]
            
            
            
            self.logger.debug("op=issue_token status=balance amount=%s available=%s", amount, available_amount)
            if available_amount < amount:                
                raise ValueError("Insufficient balance.")
                # msg_out = "insufficient balance. you need more funds!"
                # return msg_out
            
            for key in sorted(keyset_amounts, key=lambda k: keyset_amounts[k]):
                
                self.logger.debug(f"{key} {keyset_amounts[key]}")
                if keyset_amounts[key] >= amount:
                    chosen_keyset = key
                    break
            if not chosen_keyset:
               
                self.logger.error("op=issue_token status=no_single_keyset amount=%s", amount)
                raise ValueError("Insufficient balance in a single keyset; swap required.")

            mint_for_keyset = self.known_mints.get(chosen_keyset)
            if not mint_for_keyset:
                raise RuntimeError(f"Missing mint mapping for keyset {chosen_keyset}")
            
            proofs_to_use = []
            proof_amount = 0
            proofs_from_keyset = keyset_proofs[chosen_keyset]
            while proof_amount < amount:
                pay_proof = proofs_from_keyset.pop()
                proofs_to_use.append(pay_proof)
                proof_amount += pay_proof.amount
                self.logger.debug("op=issue_token selecting_proof keyset=%s amount=%s", chosen_keyset, pay_proof.amount)
                
            self.logger.debug(
                "op=issue_token status=prepared keyset=%s proofs_to_use=%s",
                chosen_keyset,
                len(proofs_to_use),
            )
            
            proofs_remaining = await self.swap_for_payment_multi(chosen_keyset,proofs_to_use, amount)
            

            self.logger.debug("op=issue_token status=swap_complete amount=%s proofs_remaining=%s", amount, len(proofs_remaining))
            # Implement from line 824
            sum_proofs =0
            spend_proofs = []
            keep_proofs = []
            for each in proofs_remaining:
                
                sum_proofs += each.amount
                if sum_proofs <= amount:
                    spend_proofs.append(each)
                    self.logger.debug("op=issue_token status=select_proof amount=%s", each.amount)
                else:
                    keep_proofs.append(each)
                    self.logger.debug("op=issue_token status=retain_proof amount=%s", each.amount)
            self.logger.debug(
                "op=issue_token status=proof_selection spend_count=%s spend_amount=%s keep_count=%s keep_amount=%s",
                len(spend_proofs),
                sum(each.amount for each in spend_proofs),
                len(keep_proofs),
                sum(each.amount for each in keep_proofs),
            )

            for each in keep_proofs:
                proofs_from_keyset.append(each)
            # print("self proofs", self.proofs)
            # need to reassign back into 
            keyset_proofs[chosen_keyset]= proofs_from_keyset
            # OK - now need to put proofs back into a flat lish
            post_payment_proofs = []
            for key in keyset_proofs:
                each_proofs = keyset_proofs[key]
                for each_proof in each_proofs:
                    post_payment_proofs.append(each_proof)
            self.proofs = post_payment_proofs
            
            #TODO change this to write_proof
            await self.write_proofs()
            # await self.add_proofs_obj(post_payment_proofs)
            
            # await self._load_proofs()


            
            tokens = TokenV3Token(mint=mint_for_keyset,
                                            proofs=spend_proofs)
            
            v3_token = TokenV3(token=[tokens], memo=comment, unit="sat")
            v4_token = TokenV4.from_tokenv3(v3_token)
            token_serialized = v4_token.serialize()
            # print("proofs remaining:", proofs_remaining)
        except (ValueError, TypeError, RuntimeError, httpx.HTTPError) as e:
            self.logger.error("op=issue_token status=failed amount=%s error=%s", amount, e)
            raise RuntimeError(f"Error issuing token: {e}") from e
        finally:
            if lock_acquired:
                await self.release_lock()

        if token_serialized is None:
            raise RuntimeError("Error issuing token: token serialization failed")

        # write_proofs() reloads the authoritative relay-backed proof set and
        # recomputes self.balance. Derive the balance from the retained proofs
        # instead of subtracting again, which produced negative balances when
        # the issued token emptied the wallet.
        self.balance = sum(each.amount for each in self.proofs)
        try:
            await self.add_tx_history(tx_type='D',amount=amount,comment=comment)
        except Exception as exc:
            # Issuance is already committed once proofs are persisted.
            self.logger.warning("op=issue_token status=tx_history_failed amount=%s error=%s", amount, exc)
        
        return token_serialized   

    async def zap(self, amount:int, event_id, comment, relays: List[str] | None = None): 
        out_msg = ""
        prs = []
        skipped_invoice_requests = 0
        last_invoice_error: str | None = None
        orig_address = event_id

        try:
            if '.' in event_id:
                if '@' in event_id:
                    pass
                else:
                    event_id = "_@" + event_id
            
                npub_hex, relays = nip05_to_npub(event_id)
                npub = hex_to_bech32(npub_hex)
                self.logger.debug(f"npub: {npub}")
                event_id = npub
            
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            raise ValueError(f"could not resolve nip05")
            

        if isinstance(event_id, str) and len(event_id) == 64 and all(ch in string.hexdigits for ch in event_id):
            event_id = event_id.lower()

        if event_id.startswith("note"):
            try:
                event_id = bech32_to_hex(event_id)
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                return "Note id format is invalid. Please check and try again."
            zap_filter = [{  
            'ids'  :  [event_id]          
            
            }]
            prs = await self._async_query_zap(amount, comment,zap_filter, relays=relays)
             

        elif event_id.startswith("npub"):  
            pub_hex = bech32_to_hex(event_id)
            profile_filter =  [{
                'limit': 1,
                'authors': [pub_hex],
                'kinds': [0]
            }]
            prs = await self._async_query_npub(amount, comment, profile_filter)
            self.logger.debug(f"Filter: {profile_filter}")
            # raise ValueError(f"You are zapping to a npub {event_id}") 
            out_msg = f"You are zapping {amount} to {orig_address} with {prs}"
        elif len(event_id) == 64 and all(ch in string.hexdigits for ch in event_id):
            zap_filter = [{
                'ids': [event_id.lower()]
            }]
            prs = await self._async_query_zap(amount, comment, zap_filter, relays=relays)
        else:
            raise ValueError(f"need a note or npub") 

        try:
            for each_pr in prs:
                await self.pay_multi_invoice(each_pr)
                out_msg+=f"\nZapped {amount} to destination: {orig_address}."
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as e:
            out_msg = f"Error {e}"
        
        return out_msg   
    
    async def _async_query_zap(self, amount:int, comment:str, filter: List[dict], relays: List[str] | None = None): 
    # does a one off query to relay prints the events and exits
        zaps_to_send = []
        event = None
        skipped_profiles = 0
        skipped_invoice_requests = 0
        last_invoice_error: str | None = None
        query_relays = relays if relays else (await self.get_public_relays()) or self._build_discovery_relays()
        # print("are we here today", self.relays)
        async with ClientPool(query_relays) as c:        
            events = await c.query(filter)
        try:
            event = events[0]  
            self.logger.debug(
                "op=zap status=target_event event_id=%s kind=%s tags=%s",
                event.id,
                event.kind,
                len(event.tags),
            )
            # json_obj = json.loads(json_str)
            # json_obj = json.loads(json_str)
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            {"status": "could not access profile"}
            pass
       
        if event == None:
            raise RuntimeError(f"no event; searched relays: {', '.join(query_relays)}")
        
        for each in event.tags:
            if not each or each[0] != "zap":
                continue
            if len(each) < 2 or not each[1]:
                self.logger.warning("op=zap status=skip_invalid_zap_tag")
                continue
            relay_hint = each[2] if len(each) > 2 else None
            weight_str = each[3] if len(each) > 3 else "1"
            zaps_to_send.append((each[1], relay_hint, weight_str))
        if zaps_to_send == []:
            zaps_to_send =[(event.pub_key,None,1)]

        normalized_targets: List[tuple[str, str | None, float]] = []
        total_weight = 0.0
        for target_pubkey, relay_hint, weight_value in zaps_to_send:
            try:
                parsed_weight = float(weight_value)
            except (TypeError, ValueError):
                self.logger.warning("op=zap status=invalid_split default=1 value=%s", weight_value)
                parsed_weight = 1.0
            if parsed_weight <= 0:
                self.logger.warning("op=zap status=nonpositive_split default=1 value=%s", weight_value)
                parsed_weight = 1.0
            normalized_targets.append((target_pubkey, relay_hint, parsed_weight))
            total_weight += parsed_weight
        if total_weight <= 0:
            raise RuntimeError("Invalid zap split weights")

        allocated_sats: List[int] = []
        remainders: List[tuple[float, int]] = []
        used_sats = 0
        for idx, (_, _, target_weight) in enumerate(normalized_targets):
            raw_allocation = (amount * target_weight) / total_weight
            sat_allocation = int(raw_allocation)
            allocated_sats.append(sat_allocation)
            used_sats += sat_allocation
            remainders.append((raw_allocation - sat_allocation, idx))
        remaining_sats = int(amount) - used_sats
        if remaining_sats > 0:
            remainders.sort(reverse=True)
            for _, target_idx in remainders[:remaining_sats]:
                allocated_sats[target_idx] += 1
        
        self.logger.debug("zaps to send normalized=%s allocated_sats=%s", normalized_targets, allocated_sats)

        prs = []
        for idx, each_zap in enumerate(normalized_targets):
            zap_amount = allocated_sats[idx]
            if zap_amount <= 0:
                self.logger.debug("op=zap status=skip_zero_split target=%s", each_zap[0])
                continue
            profile_filter =  [{
                'limit': 1,
                'authors': [each_zap[0]],
                'kinds': [0]
            }]

            profile_relays = list(query_relays)
            relay_hint = str(each_zap[1] or "").strip()
            if relay_hint:
                normalized_hint = relay_hint if relay_hint.startswith("wss://") else f"wss://{relay_hint}"
                if normalized_hint not in profile_relays:
                    profile_relays = [normalized_hint] + profile_relays

            async with ClientPool(profile_relays) as c:
                events_profile = await c.query(profile_filter)
            lnaddress = None
            try:
                self.logger.debug("getting profile")
                event_profile = events_profile[0]  
                profile_str =   event_profile.content
                profile_obj = json.loads(profile_str)
                lnaddress = profile_obj.get("lud16")
                if not lnaddress:
                    raise ValueError("profile missing lud16")
                self.logger.debug("op=zap status=profile_payment_address_found")

                
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                skipped_profiles += 1
                self.logger.error("op=zap status=skip_profile author=%s error=%s", each_zap[0], exc)
                continue
            
            # Now we can create zap request
            self.logger.debug("create zap request")
            zap_request_relays = self._build_zap_request_relays()
            if not zap_request_relays:
                raise RuntimeError("No relays configured for zap request publish")
            tags = [
                ["lnurl", lnaddress_to_lnurl(lnaddress)],
                ["relays"] + zap_request_relays,
                ["amount", str(zap_amount * 1000)],
                ["p", each_zap[0]],
            ]
            event_ids = filter[0].get("ids") if filter and isinstance(filter[0], dict) else None
            if event_ids:
                tags.append(["e", event_ids[0]])
            zap_request = Zevent(
                                kind=9734,
                                content=comment,
                                tags = tags,
                                pub_key=self.pubkey_hex                            
                                )
            zap_request.sign(self.privkey_hex)
            zap_dict= zap_request.to_dict()
            self.logger.debug(
                "op=zap status=request_ready event_id=%s valid=%s tags=%s amount=%s",
                zap_request.id,
                zap_request.is_valid(),
                len(zap_request.tags),
                zap_amount,
            )
            
            zap_test = Event().load(zap_dict)
            self.logger.debug(f"zap_test.id: {zap_test.id}")
            self.logger.debug("op=zap status=request_roundtrip valid=%s", zap_test.is_valid())
            try:
                pr, _, _ = await asyncio.to_thread(zap_address_pay, zap_amount, lnaddress, zap_dict)
            except Exception as exc:
                skipped_invoice_requests += 1
                last_invoice_error = str(exc)
                self.logger.error(
                    "op=zap status=skip_invoice_request amount=%s error=%s",
                    zap_amount,
                    exc,
                )
                continue
            if not isinstance(pr, str) or not pr:
                skipped_invoice_requests += 1
                last_invoice_error = "zap callback returned invalid invoice"
                self.logger.error(
                    "op=zap status=skip_invoice_request amount=%s error=%s",
                    zap_amount,
                    last_invoice_error,
                )
                continue
            self.logger.debug("op=zap status=invoice_received amount=%s", zap_amount)
            prs.append(pr)

        if not prs:
            if skipped_invoice_requests > 0:
                raise RuntimeError(
                    f"No payable zap invoices generated (invoice request failures: {skipped_invoice_requests}; last_error={last_invoice_error})"
                )
            if skipped_profiles > 0:
                raise RuntimeError(
                    "No payable zap invoices generated (target profile missing lud16 or not found on relays)"
                )
            raise RuntimeError("No payable zap invoices generated")
        return prs
    async def _async_query_npub(self, amount:int, comment:str, filter: List[dict]):
        prs = []
        skipped_invoice_requests = 0
        last_invoice_error: str | None = None
        query_relays = self._build_discovery_relays()
        async with ClientPool(query_relays) as c:        
            events_profile = await c.query(filter)
            lnaddress = None
            try:
                self.logger.debug("getting profile")
                event_profile = events_profile[0]  
                profile_str =   event_profile.content
                profile_obj = json.loads(profile_str)
                lnaddress = profile_obj.get("lud16")
                if not lnaddress:
                    raise ValueError("profile missing lud16")
                self.logger.debug("op=zap status=profile_payment_address_found")

                # Now we can create zap request
                self.logger.debug("create zap request for profile")
                zap_request_relays = self._build_zap_request_relays()
                if not zap_request_relays:
                    raise RuntimeError("No relays configured for zap request publish")
                tags =  [   ["lnurl",lnaddress_to_lnurl(lnaddress)],
                            ["relays"] + zap_request_relays,
                            ["amount",str(amount*1000)],
                            ["p",event_profile.pub_key]
                            
                        ]
                zap_request = Zevent(
                                    kind=9734,
                                    content=comment,
                                    tags = tags,
                                    pub_key=self.pubkey_hex                            
                                    )
                zap_request.sign(self.privkey_hex)
                zap_dict= zap_request.to_dict()
                self.logger.debug(
                    "op=zap status=request_ready event_id=%s valid=%s tags=%s amount=%s",
                    zap_request.id,
                    zap_request.is_valid(),
                    len(zap_request.tags),
                    amount,
                )
                
                zap_test = Event().load(zap_dict)
                self.logger.debug(f"zap_test.id: {zap_test.id}")
                self.logger.debug("op=zap status=request_roundtrip valid=%s", zap_test.is_valid())

                #### End of Zap stuff

                # ln_return = lightning_address_pay(amount=amount,lnaddress=lnaddress,comment=comment)
                # pr = ln_return['pr']

                pr = None
                invoice_request_failed = False
                try:
                    pr, _, _ = await asyncio.to_thread(zap_address_pay, amount, lnaddress, zap_dict)
                except Exception as exc:
                    invoice_request_failed = True
                    skipped_invoice_requests += 1
                    last_invoice_error = str(exc)
                    self.logger.error(
                        "op=zap status=skip_profile_invoice_request amount=%s error=%s",
                        amount,
                        exc,
                    )
                if (not invoice_request_failed) and (not isinstance(pr, str) or not pr):
                    skipped_invoice_requests += 1
                    last_invoice_error = "zap callback returned invalid invoice"
                    self.logger.error(
                        "op=zap status=skip_profile_invoice_request amount=%s error=%s",
                        amount,
                        last_invoice_error,
                    )
                    raise RuntimeError(last_invoice_error)

                self.logger.debug("op=zap status=invoice_received amount=%s", amount)
                prs.append(pr)
               
                
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                self.logger.error("op=zap status=profile_error error=%s", exc)
                pass
        if not prs:
            if skipped_invoice_requests > 0:
                raise RuntimeError(
                    f"No payable zap invoices generated (invoice request failures: {skipped_invoice_requests}; last_error={last_invoice_error})"
                )
            raise RuntimeError("No payable zap invoices generated")
       
        return prs
    
    def monitor(self, nrecipient: str, relays: List[str]=None):
        self.logger.debug("op=monitor status=start recipient=%s", nrecipient)
        try:
            if '@' in nrecipient:
                npub_hex, relays = nip05_to_npub(nrecipient)
                npub = hex_to_bech32(npub_hex)
                self.logger.debug("op=monitor status=resolved_npub npub=%s", npub)
                
            else:
                npub = nrecipient
                npub_hex = bech32_to_hex(nrecipient)
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            return "error"
        
        self.logger.debug("op=monitor status=resolved recipient=%s", npub)
        # url = ['wss://relay.damus.io']
        url = relays
        asyncio.run(self.listen_notes(url, npub))
        while True:
            
            pass
        return 
    



    async def listen_notes(self, url, npub):


        AS_K = self.privkey_bech32
        # print("privkey", self.privkey_bech32)
        TO_K = npub
        tail = util_funcs.str_tails
        since = datetime.now().timestamp()
        # nip59 gift wrapper
        my_k = Keys(AS_K)
        my_gift = KindOtherGiftWrap(BasicKeySigner(my_k), kind_gift_wrap=1059)
        send_k = Keys(pub_k=TO_K)

        self.logger.info("op=listen_notes status=running")

        # q before printing events
        print_q = asyncio.Queue()

        # as we're using a pool we'll see the same events multiple times
        # DeduplicateAcceptor is used to ignore them
        # my_dd = DeduplicateAcceptor()


        # used for both eose and adhoc
        def my_handler(the_client: Client, sub_id: str, evt: Event):
            print_q.put_nowait(evt)

        def on_connect(the_client: Client):
            # oxchat seems to use a large date jitter... think 8 days is enough
            since = util_funcs.date_as_ticks(datetime.now() - timedelta(hours=24*8))

            the_client.subscribe(handlers=my_handler,
                                filters=[
                                    # can only get events for us from relays, we need to store are own posts
                                    {
                                        'kinds': [Event.KIND_GIFT_WRAP],
                                        '#p': [my_k.public_key_hex()]
                                    }
                                ]
                                )


        def on_auth(the_client: Client, challenge):
            self.logger.debug("op=listen_notes status=auth_requested")


        # create the client and start it running
        c = ClientPool(url,
                    on_connect=on_connect,
                    on_auth=on_auth,
                    on_eose=my_handler)
        asyncio.create_task(c.run())

        def sigint_handler(signal, frame):
            self.logger.debug("op=listen_notes status=stopping_listener")
            c.end()
            sys.exit(0)

        signal.signal(signal.SIGINT, sigint_handler)

        async def output(since):
            while True:
                events: List[Event] = await print_q.get()
                # because we use from both eose and adhoc, when adhoc it'll just be single event
                # make [] to simplify code
                if isinstance(events, Event):
                    events = [events]

                events = [await my_gift.unwrap(evt) for evt in events]
                # can't be sorted till unwrapped
                events.sort(reverse=True)

                for c_event in events:
                    if c_event.created_at.timestamp() > since:
                        self.logger.debug("op=listen_notes status=event event_id=%s", c_event.id)
                        content = c_event.content
                        array_token = content.splitlines()
                    
                        
                        for each in array_token:
                            if self._is_cashu_token(each):
                                
                                
                                # print(f"found token! {each}")
                                msg_out = await self._async_token_accept(each)
                                self.logger.info("op=listen_notes status=token_processed")
                                    
                                
                            elif each.startswith("creqA"):
                                self.logger.debug(
                                    "op=listen_notes status=request_found token_bytes=%s",
                                    len(each),
                                )
                    


        asyncio.create_task(output(since))

        msg_n = ''
        while msg_n != 'exit':
            msg_n = await aioconsole.ainput('')
            # msg_n = msg.lower().replace(' ', '')


            send_evt = Event(content=msg_n,
                            tags=[
                                ['p', send_k.public_key_hex()]
                            ])

            wrapped_evt, trans_k = await my_gift.wrap(send_evt,
                                                    to_pub_k=send_k.public_key_hex())
            c.publish(wrapped_evt)
            # print("published")
            self.logger.debug(f"send dm to {send_k.public_key_hex()}")

            # this version is for us.. this seems to be the way oxchat does it I think but you could
            # just store locally though it'd be a pain getting your events on different instance
            await asyncio.sleep(0.2)
            # wrapped_evt, trans_k = await my_gift.wrap(send_evt,
            #                                       to_pub_k=my_k.public_key_hex())
            # c.publish(wrapped_evt)


            # if msg_n != '' and msg_n != 'exit':
            #     tags = []
            #     if to_user:
            #         tags = [['p', to_user.public_key_hex()]]
            #
            #     n_event = Event(kind=Event.KIND_TEXT_NOTE,
            #                     content=msg,
            #                     pub_key=as_user.public_key_hex(),
            #                     tags=tags)
            #     n_event.sign(as_user.private_key_hex())
            #     client.publish(n_event)

        self.logger.debug("op=listen_notes status=stopped")
        c.end()

    async def listen_nip17(self, url):


        AS_K = self.privkey_bech32

        tail = util_funcs.str_tails
        since = datetime.now().timestamp()
        since_ticks = util_funcs.date_as_ticks(datetime.now() - timedelta(minutes=1))
        # since_ticks = util_funcs.date_as_ticks(datetime.now())

        # nip59 gift wrapper
        my_k = Keys(AS_K)
        my_gift = KindOtherGiftWrap(BasicKeySigner(my_k), kind_gift_wrap=1059)


  

        # print(f'running as npub{tail(my_k.public_key_bech32()[4:])}, messaging npub{tail(send_k.public_key_bech32()[4:])}')
        self.logger.info("op=listen_nip17 status=running")

        # q before printing events
        print_q = asyncio.Queue()

        # as we're using a pool we'll see the same events multiple times
        # DeduplicateAcceptor is used to ignore them
        # my_dd = DeduplicateAcceptor()


        # used for both eose and adhoc
        def my_handler(the_client: Client, sub_id: str, evt: Event):
            print_q.put_nowait(evt)

        def on_connect(the_client: Client):
            # oxchat seems to use a large date jitter... think 8 days is enough
            since = util_funcs.date_as_ticks(datetime.now() - timedelta(hours=24*8))

            the_client.subscribe(handlers=my_handler,
                                filters=[
                                    # can only get events for us from relays, we need to store are own posts
                                    {
                                        'kinds': [Event.KIND_GIFT_WRAP],
                                        '#p': [my_k.public_key_hex()]
                                    }
                                ]
                                )


        def on_auth(the_client: Client, challenge):
            self.logger.debug("op=listen_nip17 status=auth_requested")


        # create the client and start it running
        c = ClientPool(url,
                    on_connect=on_connect,
                    on_auth=on_auth,
                    on_eose=my_handler)
        asyncio.create_task(c.run())

        def sigint_handler(signal, frame):
            self.logger.debug("op=listen_nip17 status=stopping_listener")
            c.end()
            sys.exit(0)

        signal.signal(signal.SIGINT, sigint_handler)

        async def output(since):
            # print("output")
            home_directory = os.path.expanduser('~')
            log_directory = '.safebox'
            log_file = 'log.txt'
            log_directory = os.path.join(home_directory, log_directory)
            file_path = os.path.join(home_directory, log_directory, log_file)

            while True:
                events: List[Event] = await print_q.get()
                # because we use from both eose and adhoc, when adhoc it'll just be single event
                # make [] to simplify code
                if isinstance(events, Event):
                    events = [events]

                events = [await my_gift.unwrap(evt) for evt in events]
                # can't be sorted till unwrapped
                events.sort(reverse=True)

                for c_event in events:
                    if c_event.created_at.timestamp() > since:
                        msg_out =''
                        self.logger.debug("op=listen_nip17 status=event event_id=%s", c_event.id)
                        content = c_event.content                           

                        array_token = content.splitlines()                        
                            
                        for each in array_token:
                            if self._is_cashu_token(each):                                   
                                    
                                # print(f"found token! {each}")
                                msg_out = await self.nip17_accept(each)
                                # print(self.trusted_mints)
                                # await self._async_set_wallet_info(label="trusted_mints", label_info=json.dumps(self.trusted_mints))
                                # print(msg_out)
                                        
                                    
                            elif each.startswith("creqA"):
                                msg_out = "creqA"
                            
                        TO_K = c_event.pub_key
                        send_k = Keys(pub_k=TO_K)
                        # print(send_k, c_event.content)
                        msg_n = c_event.content
                        send_evt = Event(content=msg_n,
                            tags=[
                                ['p', send_k.public_key_hex()]
                            ])

                        wrapped_evt, trans_k = await my_gift.wrap(send_evt,
                                                    to_pub_k=send_k.public_key_hex())
                        c.publish(wrapped_evt)

                        with open(file_path, "a+") as f:   
                            pass    
                            f.write(f"{c_event.created_at} {c_event.pub_key} {content} {msg_out}\n")
                            f.flush()  # Ensure the log is written to disk


        asyncio.create_task(output(since_ticks))
        msg_n = ''
        while msg_n != 'exit':
            msg_n = await aioconsole.ainput('')
                  
            
            await asyncio.sleep(0.2)
            

           

        self.logger.debug("op=listen_nip17 status=stopped")
        c.end()

       

    def run(self, listen_relay: List[str]= None):
        # print(f"\n listening for ecash for: {self.pubkey_bech32}")
        
        # asyncio.run(self._async_run())
        # npub = 'npub19xlhmu806lf7yh62kmr6gg4qus9uyss4sr9jeylqqvtud36cuxls2h9s37'
        
        if listen_relay:
            url = listen_relay
        else:
            url = [self.home_relay]
        
        asyncio.run(self.listen_nip17(url))
      
        

    async def _async_run(self):
       
        task1 = asyncio.create_task(self._async_task())
       
        await asyncio.sleep(10)
        self.logger.debug("op=async_run status=start")
        await task1

    async def _async_task(self):
       
     
        await asyncio.sleep(1)
        self.logger.debug("op=async_task status=start")

    def create_payment_request( self, 
                                amount:int, 
                                unit:str='sat', 
                                single_use: bool=True,
                                description: str = "Payment"):
        payment_request_dict = {}
        random_id = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))

        payment_request_dict['i'] = random_id
        payment_request_dict['a'] = amount
        payment_request_dict['u'] = unit
        payment_request_dict['s'] = single_use
        payment_request_dict['d'] = description
        payment_request_dict['m'] = self.mints
        payment_request_dict['t'] = {
                                    "t":"nostr",
                                    "a": "nprofile",
                                    "g": [["n","17"]]

                                    }

        self.logger.debug("op=get_payment_request status=payload_ready")
        cbor_data = cbor2.dumps(payment_request_dict)
        base64_encoded_data = base64.b64encode(cbor_data)
        base64_string = base64_encoded_data.decode('utf-8')

        payment_request = "creqA" + base64_string
        return payment_request

    async def _async_token_accept(self, token:str):
        return

    async def issue_private_record(self, content:str, holder:str=None, kind:int =34002, origsha256:str = None)->Event:
        """Issue private record"""
        holder_pubhex = ""
        if holder:
            try:
                holder_key = Keys(pub_k=holder)
                holder_pubhex = holder_key.public_key_hex()
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                self.logger.warning("Invalid holder key supplied for private record: %s", exc)
            
        
        tags = [["safebox", self.pubkey_hex], ["safebox_owner", npub_to_hex(self.owner)],["safebox_holder", holder_pubhex]]
        if origsha256:
            tags.append(["origsha25",origsha256])

        issued_record = Event(  pub_key=self.pubkey_hex,
                                kind=kind,
                                tags = tags,
                                content=content)
        issued_record.sign(self.privkey_hex)

        return issued_record
    
    async def create_grant_from_offer(self, offer_kind:int, offer_name:str, holder: str, grant_kind:int=None,shared_secret_hex: str=None, relays: List[str]=None, blossom_xfer_server:str=None):
        """This function creates a corresponding grant for an offer and if an orginal record (blob) exists for the record, it will create the transfer blob"""
        blob_data: bytes = None
        blob_type: str = None
        original_record: OriginalRecordTransfer = None
        h_pubhex = Keys(pub_k=holder).public_key_hex()

        blossom_server = self._default_blossom_home_server()
        default_xfer_server = self._default_blossom_xfer_server()
        if not blossom_xfer_server:
            blossom_xfer_server = default_xfer_server
        
        mime_type_guess = None
        origsha256 = None
        encrypt_parms = None

        if not (30000 <= offer_kind < 40000 and offer_kind % 2 == 1):
            """Create a grant from an offer"""
            raise ValueError("offer_kind must be an odd integer in the range 30000–39999")
        
        # If grant kind is not supplied, the convention is that the grant kind is an increment of 1
        if not grant_kind:
            grant_kind = offer_kind +1
        
        # Get the offer

        
        safebox_record: SafeboxRecord = await self.get_record_safebox(record_name=offer_name,record_kind=offer_kind)
        
        self.logger.debug("op=create_grant_from_offer status=payload_loaded")
        blob_type,blob_data = await self.get_record_blobdata(record_name=offer_name,record_kind=offer_kind)
        
        issued_private_record: Event = await self.issue_private_record(content=safebox_record.payload,holder=h_pubhex,kind=grant_kind)
        # Need to create original_transfer to tell where to pick up

        if blob_data:
            
            self.logger.debug("op=create_grant_from_offer status=blob_found type=%s size=%s", blob_type, len(blob_data))


            self.logger.debug("op=create_grant_from_offer status=encrypt_blob")
            origsha256 = hashlib.sha256(blob_data).hexdigest()
            self.logger.debug("op=create_grant_from_offer status=origsha256")
            origmime_type_guess = filetype.guess(blob_data).mime
            self.logger.debug("op=create_grant_from_offer status=mime mime=%s", origmime_type_guess)
            if shared_secret_hex:
                blob_key = bytes.fromhex(shared_secret_hex)
                self.logger.debug("op=create_grant_from_offer status=shared_secret_from_kem")
            else:
                blob_key = os.urandom(32)  # 256-bit key
            try:    
                self.logger.debug("op=create_grant_from_offer status=encrypting")
                encrypt_result:EncryptionResult = encrypt_bytes(blob_data, blob_key)
                encrypt_parms = EncryptionParms(alg=encrypt_result.alg,key=blob_key.hex(),iv=encrypt_result.iv.hex())
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as e:
                self.logger.exception("Encryption error while creating grant from offer")
                raise RuntimeError(f"encryption error while creating grant: {e}") from e

            # final_blob_data = blob_data
            final_blob_data = encrypt_result.cipherbytes
            self.logger.debug("op=create_grant_from_offer status=upload_blob")
            blob_nsec = Keys().private_key_bech32()
            client_xfer = BlossomClient(nsec=blob_nsec, default_servers=[blossom_xfer_server])
            upload_result = client_xfer.upload_blob(blossom_xfer_server, data=final_blob_data,
                            description='Blob to server')
            sha256 = upload_result['sha256']
            blob_ref = upload_result.get('url', f"{blossom_xfer_server}/{sha256}")
            # blob_ref = upload_result['sha256']
            blob_type = upload_result['type']
            self.logger.debug("op=create_grant_from_offer status=blob_uploaded")
            # await asyncio.sleep(5)

            # Create what is necessary for original record trasfer
            original_record = OriginalRecordTransfer(   origsha256=origsha256,
                                                        origmimetype=origmime_type_guess,
                                                        encryptparms=encrypt_parms,
                                                        blobserver= blossom_xfer_server,
                                                        blobsha256=sha256,
                                                        blobmimetype=blob_type,
                                                        blobref=blob_ref,
                                                        blobnsec=blob_nsec
                                                    )


            #TODO Eliminate the delete function once the receiving party can clean it up
            # delete_result = client_xfer.delete_blob(server=blossom_xfer_server,sha256=sha256)
            # print(f"Delete result: {delete_result}")
        else:
            self.logger.debug("op=create_grant_from_offer status=no_blob kind=%s", offer_kind)


        issued_private_record: Event = await self.issue_private_record(content=safebox_record.payload,holder=h_pubhex,kind=grant_kind, origsha256=origsha256)
        self.logger.debug("op=create_grant_from_offer status=issued")
        return issued_private_record, original_record
    
    async def create_request_from_grant(self, grant_name:str, grant_kind:int=34102, shared_secret_hex: str=None, relays: List[str]=None, blossom_xfer_server:str=None):
        """This function creates a request that can be sent for verififcation and if an orginal record (blob) exists for the record, it will create the transfer blob"""
        blob_data: bytes = None
        blob_type: str = None
        original_record: OriginalRecordTransfer = None
        

        blossom_server = self._default_blossom_home_server()
        default_xfer_server = self._default_blossom_xfer_server()
        if not blossom_xfer_server:
            blossom_xfer_server = default_xfer_server
        
        mime_type_guess = None
        origsha256 = None
        encrypt_parms = None

        self.logger.debug("op=create_request_from_grant status=grant_kind kind=%s", grant_kind)

        if not (30000 <= grant_kind < 40000 and grant_kind % 2 == 0):
            """Create a grant from an offer"""
            raise ValueError("offer_kind must be an odd integer in the range 30000–39999")
        

        
        # Get the grant record to send

        self.logger.debug("op=create_request_from_grant status=load_record kind=%s", grant_kind)
        safebox_record: SafeboxRecord = await self.get_record_safebox(record_name=grant_name,record_kind=grant_kind)
        
        self.logger.debug("op=create_request_from_grant status=payload_loaded")
        blob_type,blob_data = await self.get_record_blobdata(record_name=grant_name,record_kind=grant_kind)
        
        # issued_private_record: Event = await self.issue_private_record(content=safebox_record.payload,# holder=h_pubhex,kind=grant_kind)
        # The grant record is a signed event that stored as a serialized payload in the safebox record
        try:
            payload_json = json.loads(safebox_record.payload)
            self.logger.debug("op=create_request_from_grant status=payload_json_loaded")
            payload_json['pub_key'] = payload_json['pubkey'] 
            del payload_json['pubkey']
            issued_grant_record = Event(**payload_json)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            self.logger.exception("Error retrieving grant record")
            raise ValueError(f"error retrieving grant record {e}") from e
        # Need to create original_transfer to tell where to pick up

        if blob_data:
            
            self.logger.debug("op=create_request_from_grant status=blob_found type=%s size=%s", blob_type, len(blob_data))


            self.logger.debug("op=create_request_from_grant status=encrypt_blob")
            origsha256 = hashlib.sha256(blob_data).hexdigest()
            self.logger.debug("op=create_request_from_grant status=origsha256")
            origmime_type_guess = filetype.guess(blob_data).mime
            self.logger.debug("op=create_request_from_grant status=mime mime=%s", origmime_type_guess)
            if shared_secret_hex:
                blob_key = bytes.fromhex(shared_secret_hex)
                self.logger.debug("op=create_request_from_grant status=shared_secret_from_kem")
            else:
                blob_key = os.urandom(32)  # 256-bit key
            try:    
                self.logger.debug("op=create_request_from_grant status=encrypting")
                encrypt_result:EncryptionResult = encrypt_bytes(blob_data, blob_key)
                encrypt_parms = EncryptionParms(alg=encrypt_result.alg,key=blob_key.hex(),iv=encrypt_result.iv.hex())
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as e:
                self.logger.exception("Encryption error while creating request from grant")
                raise RuntimeError(f"encryption error while creating request: {e}") from e

            # final_blob_data = blob_data
            final_blob_data = encrypt_result.cipherbytes
            self.logger.debug("op=create_request_from_grant status=upload_blob")
            blob_nsec = Keys().private_key_bech32()
            client_xfer = BlossomClient(nsec=blob_nsec, default_servers=[blossom_xfer_server])
            upload_result = client_xfer.upload_blob(blossom_xfer_server, data=final_blob_data,
                            description='Blob to server')
            sha256 = upload_result['sha256']
            blob_ref = upload_result.get('url', f"{blossom_xfer_server}/{sha256}")
            # blob_ref = upload_result['sha256']
            blob_type = upload_result['type']
            self.logger.debug("op=create_request_from_grant status=blob_uploaded")
            # await asyncio.sleep(5)

            # Create what is necessary for original record trasfer
            original_record = OriginalRecordTransfer(   origsha256=origsha256,
                                                        origmimetype=origmime_type_guess,
                                                        encryptparms=encrypt_parms,
                                                        blobserver= blossom_xfer_server,
                                                        blobsha256=sha256,
                                                        blobmimetype=blob_type,
                                                        blobref=blob_ref,
                                                        blobnsec=blob_nsec
                                                    )


            #TODO Eliminate the delete function once the receiving party can clean it up
            # delete_result = client_xfer.delete_blob(server=blossom_xfer_server,sha256=sha256)
            # print(f"Delete result: {delete_result}")
        else:
            self.logger.debug("op=create_request_from_grant status=no_blob kind=%s", grant_kind)


        # print(f"issued grant: {issued_grant_record.data()}")
        return issued_grant_record, original_record
    
    async def get_trusted_entities(self,kind:int=37376, relays: List[str]=None):

        pubhex_list_out = []
        try:
            record_out = await self.get_wallet_info(label="trusted entities", record_kind=kind)
            if record_out is None:
                return []
            record_out_json = json.loads(record_out)
            pubs_to_process = [
                each.strip()
                for each in str(record_out_json.get("payload", "")).split()
                if each.strip()
            ]
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            self.logger.debug("No trusted entities configured: %s", exc)
            return []
       
        for each in pubs_to_process:
            try:
                k_to_add = Keys(pub_k=each)
                # Now we are going to get the followers
                
                pubhex_list_out.append(k_to_add.public_key_hex())
            except Exception as exc:
                self.logger.debug("Skipping invalid root entity=%s error=%s", each, exc)

        if not pubhex_list_out:
            return []
        
        self.logger.debug("op=get_trusted_entities status=expanded_roots count=%s relays=%s", len(pubhex_list_out), self.relays)
        FILTER = [{
            'limit': RECORD_LIMIT,
            'authors': pubhex_list_out,
            'kinds': [3]
        }]
        async with ClientPool(relays) as c:  
            events = await c.query(FILTER)
            if events:
                for each in events:
                    self.logger.debug("op=get_trusted_entities status=follow_tags event=%s count=%s", each.id, len(each.tags))
                    for each_tag in each.tags:
                        if each_tag[0] == "p":
                            pubhex_list_out.append(each_tag[1])
        pubhex_list_out = list(set(pubhex_list_out))
        return pubhex_list_out

    async def get_trusted_entity_sources(self, kind: int = 37376, relays: List[str] = None):
        root_to_trusted: dict[str, set[str]] = {}
        relays = relays or self.relays

        try:
            record_out = await self.get_wallet_info(label="trusted entities", record_kind=kind)
            if record_out is None:
                return {}
            record_out_json = json.loads(record_out)
            pubs_to_process = [
                each.strip()
                for each in str(record_out_json.get("payload", "")).split()
                if each.strip()
            ]
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            self.logger.debug("No trusted entity sources configured: %s", exc)
            return {}

        root_hexes: list[str] = []
        for each in pubs_to_process:
            try:
                root_hex = Keys(pub_k=each).public_key_hex()
                root_hexes.append(root_hex)
                root_to_trusted[root_hex] = {root_hex}
            except Exception as exc:
                self.logger.debug("Skipping invalid root entity=%s error=%s", each, exc)

        if not root_hexes:
            return {}

        filter_obj = [{
            'limit': RECORD_LIMIT,
            'authors': root_hexes,
            'kinds': [3]
        }]
        async with ClientPool(relays) as c:
            events = await c.query(filter_obj)
            if events:
                for each in events:
                    root_hex = each.pub_key
                    root_to_trusted.setdefault(root_hex, {root_hex})
                    for each_tag in each.tags:
                        if each_tag[0] == "p" and len(each_tag) > 1:
                            root_to_trusted[root_hex].add(each_tag[1])

        return {root_hex: sorted(list(trusted_hexes)) for root_hex, trusted_hexes in root_to_trusted.items()}

    async def get_root_entities(self,kind:int=37376, relays: List[str]=None):

        try:
            record_out = await self.get_wallet_info(label="trusted entities",record_kind=kind)
            if record_out is None:
                return ""
            record_out_json = json.loads(record_out)
            final_out = record_out_json.get('payload', "")
            if not isinstance(final_out, str):
                final_out = str(final_out)
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            self.logger.debug("No root entities payload found: %s", exc)
            final_out = ""
        return final_out

    async def set_trusted_entities(self,kind:int=37376, pub_list_str: str=None):

        pubs_to_validate = pub_list_str.split()
        pubs_to_store = ''
        for each in pubs_to_validate:
            try:
                k_to_validate = Keys(pub_k=each)
                pubs_to_store += k_to_validate.public_key_bech32() + ' '
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                self.logger.debug("Skipping invalid trusted entity npub=%s error=%s", each, exc)

        
        
        await self.put_record(record_name="trusted entities", record_value=pubs_to_store, record_kind=kind, record_type="internal")
        
        
        return True
        
    async def set_wot_entities(self,kind:int=37376, pub_list_str: str=None):

        pubs_to_validate = pub_list_str.split()
        self.logger.debug("op=set_wot_entities status=validate_input count=%s", len(pubs_to_validate))
        pubs_to_store = ''
        for each in pubs_to_validate:
            each_component = each.split(":")
            self.logger.debug("op=set_wot_entities status=parse_component component=%s", each_component)
            each_npub = each_component[0]
            part_2 = ':'+ each_component[1] if len(each_component)>=2 else ''
            part_3 = ':'+ each_component[2] if len(each_component)>=3 else ''
           

            try:
                k_to_validate = Keys(pub_k=each_npub)
                pubs_to_store += f"{k_to_validate.public_key_bech32()}{part_2}{part_3}" + ' '
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                self.logger.debug("Skipping invalid wot entity npub=%s error=%s", each_npub, exc)

        
        
        await self.put_record(record_name="wot entities", record_value=pubs_to_store, record_kind=kind, record_type="internal")
        
        
        return True
    
    async def get_wot_entities(self,kind:int=37376, relays: List[str]=None):

        pubhex_list_out = []    
        try:
            record_out = await self.get_wallet_info(label="wot entities",record_kind=kind)
            if not record_out:
                return []
            record_out_json = json.loads(record_out)
            pubs_to_process = [
                each.strip()
                for each in str(record_out_json.get('payload', '')).split()
                if each.strip()
            ]
            self.logger.debug("op=get_wot_entities status=processing count=%s", len(pubs_to_process))
        
            for each in pubs_to_process:
                each_component = each.split(":")   
                self.logger.debug("op=get_wot_entities status=parse_component component=%s", each_component)
                each_npub = each_component[0]
                if len(each_component)>=2:
                    part_2 = ':'+each_component[1] 
                else: 
                    part_2 = ''
                if len(each_component)>=3:
                    part_3 = ':'+each_component[2] 
                else: 
                    part_3 = ''


                    
                
                try:
                    k_to_add = Keys(pub_k=each_npub)
                    final_entry = f"{k_to_add.public_key_bech32()}{part_2}{part_3}"
                    self.logger.debug("op=get_wot_entities status=valid_entry entry=%s", final_entry)
                    
                    pubhex_list_out.append(final_entry)
                   
                except Exception as exc:
                    self.logger.debug("Skipping malformed wot score entity=%s error=%s", each, exc)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.logger.debug("Could not load wot entities: %s", exc)
            return []
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            self.logger.warning("Could not load wot entities: %s", exc)
            return []
        
       

        return pubhex_list_out
    
    async def get_wot_scores(self, pub_key_to_score: str, relays: List[str]=None):
        scores_out = []
        try:
            k_to_use = Keys(pub_k=pub_key_to_score)
            pubhex = k_to_use.public_key_hex()
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            return "invalid npub"
        

        
        wot_entities = await self.get_wot_entities()
        for each_wot in wot_entities:
            each_wot_npub, each_wot_tag, each_wot_relay = (each_wot.split(':') + [None, None, None])[:3]
            each_wot_relay = each_wot_relay if not each_wot_relay or each_wot_relay.startswith("wss://") else f"wss://{each_wot_relay}"
            found_score = False
            self.logger.debug("op=get_wot_scores status=processing_entity npub=%s", each_wot_npub)
            FILTER = [{
            'limit': RECORD_LIMIT,
             '#d': [pubhex],                       
            'authors': [Keys(pub_k=each_wot_npub).public_key_hex()],
            'kinds': [30382]
            }]
            self.logger.debug("op=get_wot_scores status=query_filter")
            each_event: Event
            try:
                async with ClientPool(clients=[each_wot_relay],timeout=3) as c:  
                    events = await c.query(FILTER)
                    if events:
                        self.logger.debug("op=get_wot_scores status=events count=%s", len(events))
                        for each_event  in events:
                            self.logger.debug("op=get_wot_scores status=event_tags pubkey=%s", each_event.pub_key)
                            for each_tag in each_event.tags:
                                if each_tag[0] == each_wot_tag:
                                    score = each_tag[1]
                                    scores_out.append([each_wot_tag, score])
                                    found_score = True
                                    break
                            if found_score:
                                break
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                self.logger.warning("Failed querying wot score relay=%s error=%s", each_wot_relay, exc)
            if each_wot_tag and not found_score:
                scores_out.append([each_wot_tag, "na"])
        

        return scores_out

        try:
            k_to_use = Keys(pub_k=pub_key_to_score)
            pubhex = k_to_use.public_key_hex()
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            pubhex = None

        FILTER = [{
            'limit': RECORD_LIMIT,
             '#d': [pubhex],                       
            'authors': wot_entities,
            'kinds': [30382]
        }]

        # print(f"FILTER {FILTER} with relays: {relays}")
        each: Event
        async with ClientPool(relays) as c:  
            events = await c.query(FILTER)
            if events:
                # print(f"total events: {len(events)}")
                for each  in events:
                    # print(f"tags from {each.pub_key} {each.tags}")
                    for each_tag in each.tags:
                        if each_tag[0] == 'rank':
                            rank = each_tag[1]

                        
        


        return rank
       
    async def get_social_profile(self,npub: str, relays: List[str]=None):
        try:
            pubhex = Keys(pub_k=npub).public_key_hex()
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
            raise ValueError("Invalid public key")
        social_profile: Dict[str, Any] = {}
        
        FILTER = [{
                'limit': 1,                                
                'authors': [pubhex],
                'kinds': [0]
                }]
        
        async with ClientPool(relays) as c:  
                    event: Event
                    events = await c.query(FILTER)
                    if events:
                        event = events[0]
                        try:
                            social_profile = json.loads(event.content)
                        except (json.JSONDecodeError, TypeError) as exc:
                            social_profile = {}

        return social_profile       

    def _resolve_pubkey_identifier(self, identifier: str) -> str:
        pubhex, _ = self._resolve_pubkey_and_relays(identifier)
        return pubhex

    def _resolve_pubkey_and_relays(self, identifier: str) -> tuple[str, List[str]]:
        value = (identifier or "").strip()
        if not value:
            raise ValueError("Missing identifier")
        if "@" in value:
            pubhex, relays = nip05_to_npub(value)
            if not pubhex:
                raise ValueError(f"Unable to resolve NIP-05 identifier: {value}")
            return str(pubhex).lower(), self._normalize_relays(relays)
        if value.startswith("npub"):
            return bech32_to_hex(value).lower(), []
        if len(value) == 64 and all(ch in string.hexdigits for ch in value):
            return value.lower(), []
        raise ValueError("Identifier must be nip05, npub, or 64-char pubhex")

    async def _get_latest_contacts_event(self, relays: List[str] | None = None) -> Event | None:
        relay_pool = relays if relays else self._build_discovery_relays()
        if not relay_pool:
            return None
        query_filter = [{
            "limit": 1,
            "authors": [self.pubkey_hex],
            "kinds": [3],
        }]
        async with ClientPool(relay_pool) as c:
            events: List[Event] = await c.query(query_filter)
        if not events:
            return None
        events_sorted = sorted(
            events,
            key=lambda each_event: int(each_event.created_at.timestamp()),
            reverse=True,
        )
        return events_sorted[0]

    async def _publish_contact_list(self, tags: List[List[str]], relays: List[str] | None = None) -> Dict[str, Any]:
        publish_relays = self._build_kind1_publish_relays(relays=relays)
        if not publish_relays:
            raise RuntimeError("No relays configured for contact list publish")

        async with ClientPool(publish_relays) as c:
            n_msg = Event(
                kind=3,
                content="",
                tags=tags,
                pub_key=self.pubkey_hex,
            )
            n_msg.sign(self.privkey_hex)
            c.publish(n_msg)
            self.logger.debug("op=contact_list status=published event_id=%s relays=%s", n_msg.id, publish_relays)

        return {
            "status": "OK",
            "event_id": str(n_msg.id),
            "count": len([t for t in tags if t and t[0] == "p"]),
            "tags": tags,
            "relays": publish_relays,
        }

    async def add_follower(
        self,
        identifier: str,
        relay_hint: str | None = None,
        relays: List[str] | None = None,
    ) -> Dict[str, Any]:
        pubhex = self._resolve_pubkey_identifier(identifier)
        latest_event = await self._get_latest_contacts_event(relays=relays)
        tags: List[List[str]] = list(latest_event.tags) if latest_event else []

        found = False
        for each_tag in tags:
            if each_tag and each_tag[0] == "p" and len(each_tag) > 1 and each_tag[1].lower() == pubhex:
                found = True
                if relay_hint:
                    if len(each_tag) > 2:
                        each_tag[2] = relay_hint
                    else:
                        each_tag.append(relay_hint)
                break

        if not found:
            new_tag = ["p", pubhex]
            if relay_hint:
                new_tag.append(relay_hint)
            tags.append(new_tag)

        result = await self._publish_contact_list(tags=tags, relays=relays)
        result["action"] = "add"
        result["pubkey"] = pubhex
        return result

    async def follow(
        self,
        identifier: str,
        relay_hint: str | None = None,
        relays: List[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Follow a user by nip05, npub, or pubhex by updating kind-3 contact list.
        """
        return await self.add_follower(
            identifier=identifier,
            relay_hint=relay_hint,
            relays=relays,
        )

    async def delete_follower(
        self,
        identifier: str,
        relays: List[str] | None = None,
    ) -> Dict[str, Any]:
        pubhex = self._resolve_pubkey_identifier(identifier)
        latest_event = await self._get_latest_contacts_event(relays=relays)
        tags: List[List[str]] = list(latest_event.tags) if latest_event else []
        filtered_tags: List[List[str]] = []
        removed = 0
        for each_tag in tags:
            if each_tag and each_tag[0] == "p" and len(each_tag) > 1 and each_tag[1].lower() == pubhex:
                removed += 1
                continue
            filtered_tags.append(each_tag)

        result = await self._publish_contact_list(tags=filtered_tags, relays=relays)
        result["action"] = "delete"
        result["pubkey"] = pubhex
        result["removed"] = removed
        return result

    async def unfollow(
        self,
        identifier: str,
        relays: List[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Unfollow a user by nip05, npub, or pubhex by updating kind-3 contact list.
        """
        return await self.delete_follower(
            identifier=identifier,
            relays=relays,
        )

    async def get_followers_for_identifier(
        self,
        identifier: str | None = None,
        limit: int = 100,
        relays: List[str] | None = None,
        strict: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Return followers for a target identifier by inspecting kind-3 contact lists.

        - If identifier is None/blank, target defaults to this wallet pubkey.
        - In strict mode, each candidate author is validated against their latest
          known kind-3 event to reduce stale follower false positives.
        """

        target_identifier = (identifier or "").strip()
        target_pubhex = (
            self._resolve_pubkey_identifier(target_identifier)
            if target_identifier
            else str(self.pubkey_hex).lower()
        )
        safe_limit = max(1, min(int(limit), 500))
        relay_pool = relays if relays else self._build_discovery_relays()
        if not relay_pool:
            raise ValueError("No relays available for query")

        # First pass: candidate contacts events that mention target in `p` tags.
        candidate_fetch_limit = max(safe_limit * 5, 200)
        candidate_filter = [{
            "limit": candidate_fetch_limit,
            "kinds": [3],
            "#p": [target_pubhex],
        }]
        async with ClientPool(relay_pool) as c:
            candidate_events: List[Event] = await c.query(candidate_filter)

        if not candidate_events:
            return []

        candidates_by_author: Dict[str, Event] = {}
        for each_event in sorted(
            candidate_events,
            key=lambda each: int(each.created_at.timestamp()),
            reverse=True,
        ):
            author = str(each_event.pub_key or "").lower()
            if len(author) != 64 or not all(ch in string.hexdigits for ch in author):
                continue
            if author not in candidates_by_author:
                candidates_by_author[author] = each_event
            if len(candidates_by_author) >= candidate_fetch_limit:
                break

        if not strict:
            out: List[Dict[str, Any]] = []
            for author, event in list(candidates_by_author.items())[:safe_limit]:
                relay_hint = None
                for each_tag in list(event.tags or []):
                    if each_tag and each_tag[0] == "p" and len(each_tag) >= 2 and str(each_tag[1]).lower() == target_pubhex:
                        relay_hint = each_tag[2] if len(each_tag) >= 3 else None
                        break
                out.append({
                    "follower_pubkey": author,
                    "follower_npub": hex_to_bech32(author),
                    "event_id": str(event.id),
                    "created_at": int(event.created_at.timestamp()),
                    "relay_hint": relay_hint,
                    "verified_latest_contacts": False,
                })
            return out

        # Second pass: fetch latest kind-3 events for candidate authors and verify
        # that target still exists in each author's current contact list.
        candidate_authors = list(candidates_by_author.keys())
        latest_filter = [{
            "limit": max(len(candidate_authors) * 3, 200),
            "kinds": [3],
            "authors": candidate_authors,
        }]
        async with ClientPool(relay_pool) as c:
            latest_events: List[Event] = await c.query(latest_filter)

        latest_by_author: Dict[str, Event] = {}
        for each_event in sorted(
            latest_events,
            key=lambda each: int(each.created_at.timestamp()),
            reverse=True,
        ):
            author = str(each_event.pub_key or "").lower()
            if not author or author in latest_by_author:
                continue
            latest_by_author[author] = each_event

        out: List[Dict[str, Any]] = []
        for author in candidate_authors:
            latest_event = latest_by_author.get(author)
            if not latest_event:
                continue
            relay_hint = None
            still_follows = False
            for each_tag in list(latest_event.tags or []):
                if not each_tag or each_tag[0] != "p" or len(each_tag) < 2:
                    continue
                if str(each_tag[1]).lower() == target_pubhex:
                    still_follows = True
                    relay_hint = each_tag[2] if len(each_tag) >= 3 else None
                    break
            if not still_follows:
                continue
            out.append({
                "follower_pubkey": author,
                "follower_npub": hex_to_bech32(author),
                "event_id": str(latest_event.id),
                "created_at": int(latest_event.created_at.timestamp()),
                "relay_hint": relay_hint,
                "verified_latest_contacts": True,
            })
            if len(out) >= safe_limit:
                break

        return out

    async def get_latest_kind1_posts_from_follow_list(
        self,
        limit: int = 20,
        relays: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        latest_contacts = await self._get_latest_contacts_event(relays=relays)
        if not latest_contacts:
            return []

        follow_pubkeys: List[str] = []
        for each_tag in list(latest_contacts.tags):
            if not each_tag or each_tag[0] != "p" or len(each_tag) < 2:
                continue
            each_pub = str(each_tag[1]).lower()
            if len(each_pub) == 64 and all(ch in string.hexdigits for ch in each_pub):
                if each_pub not in follow_pubkeys:
                    follow_pubkeys.append(each_pub)

        if not follow_pubkeys:
            return []

        limit_value = max(1, min(int(limit), 200))
        relay_pool = relays if relays else self._build_discovery_relays()
        if not relay_pool:
            raise ValueError("No relays available for query")

        query_filter = [{
            "limit": limit_value,
            "authors": follow_pubkeys,
            "kinds": [1],
        }]

        async with ClientPool(relay_pool) as c:
            events: List[Event] = await c.query(query_filter)

        if not events:
            return []

        events_sorted = sorted(
            events,
            key=lambda each_event: int(each_event.created_at.timestamp()),
            reverse=True,
        )[:limit_value]

        def _kind1_event_to_dict(each_event: Event) -> Dict[str, Any]:
            event_tags = list(each_event.tags or [])
            reply_event_ids: List[str] = []
            for each_tag in event_tags:
                if each_tag and each_tag[0] == "e" and len(each_tag) > 1:
                    reply_event_ids.append(str(each_tag[1]))
            return {
                "id": str(each_event.id),
                "event_id": str(each_event.id),
                "event_id_hex": str(each_event.id),
                "pubkey": str(each_event.pub_key),
                "created_at": int(each_event.created_at.timestamp()),
                "content": str(each_event.content),
                "is_reply": bool(reply_event_ids),
                "reply_to_event_ids": reply_event_ids,
                "reply_to_primary_event_id": reply_event_ids[0] if reply_event_ids else None,
                "tags": event_tags,
            }

        return [
            _kind1_event_to_dict(each_event)
            for each_event in events_sorted
        ]


    @staticmethod


    async def get_event_by_id(
        self,
        event_id: str,
        relays: List[str] | None = None,
    ) -> Dict[str, Any] | None:
        target_event_id = str(event_id or "").strip()
        if not target_event_id:
            raise ValueError("event_id is required")
        if target_event_id.startswith("note"):
            target_event_id = bech32_to_hex(target_event_id)
        target_event_id = target_event_id.lower()
        if len(target_event_id) != 64 or not all(ch in string.hexdigits for ch in target_event_id):
            raise ValueError("Invalid event_id")

        relay_pool = relays if relays else self._build_discovery_relays()
        if not relay_pool:
            raise ValueError("No relays available for query")

        async with ClientPool(relay_pool) as c:
            events: List[Event] = await c.query([{"limit": 1, "ids": [target_event_id]}])

        if not events:
            return None

        event = events[0]
        return {
            "id": str(event.id),
            "event_id": str(event.id),
            "pubkey": str(event.pub_key),
            "created_at": int(event.created_at.timestamp()),
            "kind": int(event.kind),
            "content": str(event.content),
            "tags": list(event.tags or []),
        }


    
    async def get_kind0_profile_by_identifier(
        self,
        identifier: str,
        relays: List[str] | None = None,
    ) -> Dict[str, Any]:
        value = (identifier or "").strip()
        if not value:
            raise ValueError("Identifier is required")

        pubhex: str | None = None
        try:
            if "@" in value:
                pubhex, _ = nip05_to_npub(value)
            elif value.startswith("npub"):
                pubhex = Keys(pub_k=value).public_key_hex()
            elif len(value) == 64 and all(ch in string.hexdigits for ch in value):
                pubhex = value.lower()
            else:
                raise ValueError("Identifier must be nip05, npub, or pubhex")
        except Exception as exc:
            raise ValueError(f"Could not resolve identifier: {value}") from exc

        relay_pool = relays if relays else self._build_discovery_relays()
        if not relay_pool:
            raise ValueError("No relays available for query")

        query_filter = [{
            "limit": 1,
            "authors": [pubhex],
            "kinds": [0],
        }]

        async with ClientPool(relay_pool) as c:
            events: List[Event] = await c.query(query_filter)

        if not events:
            raise RuntimeError("No kind 0 profile found")

        event = sorted(
            events,
            key=lambda each_event: int(each_event.created_at.timestamp()),
            reverse=True,
        )[0]

        try:
            content_json = json.loads(event.content)
        except Exception as exc:
            raise RuntimeError("Kind 0 profile content is not valid JSON") from exc

        return {
            "id": str(event.id),
            "pubkey": str(event.pub_key),
            "created_at": int(event.created_at.timestamp()),
            "content": content_json,
        }

    def format_mention(self, identifier: str, style: str = "nostr_uri") -> Dict[str, Any]:
        pubhex = self._resolve_pubkey_identifier(identifier)
        npub = hex_to_bech32(pubhex)
        normalized_style = (style or "nostr_uri").strip().lower()
        if normalized_style in ["nostr_uri", "nostr", "uri", "default"]:
            mention = f"nostr:{npub}"
            normalized_style = "nostr_uri"
        elif normalized_style in ["at", "@", "at_npub"]:
            mention = f"@{npub}"
            normalized_style = "at_npub"
        elif normalized_style in ["both", "dual", "test"]:
            mention = f"nostr:{npub} @{npub}"
            normalized_style = "both"
        else:
            raise ValueError("style must be one of: nostr_uri, at_npub, both")

        return {
            "identifier": identifier,
            "pubkey": pubhex,
            "npub": npub,
            "style": normalized_style,
            "mention": mention,
        }

    def compose_post_with_mentions(
        self,
        base_text: str | None,
        identifiers: List[str],
        style: str = "nostr_uri",
    ) -> Dict[str, Any]:
        if not identifiers:
            raise ValueError("identifiers must include at least one value")
        mention_items: List[Dict[str, Any]] = []
        mention_texts: List[str] = []
        for each in identifiers:
            item = self.format_mention(each, style=style)
            mention_items.append(item)
            mention_texts.append(item["mention"])

        text_prefix = (base_text or "").strip()
        mentions_joined = " ".join(mention_texts)
        if text_prefix:
            final_text = f"{text_prefix} {mentions_joined}"
        else:
            final_text = mentions_joined

        return {
            "style": mention_items[0]["style"],
            "mentions": mention_items,
            "content": final_text,
        }
    
    async def get_latest_kind1_posts_by_nip05(
        self,
        nip05: str,
        limit: int = 10,
        relays: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        if not nip05 or "@" not in nip05:
            raise ValueError("Invalid nip05 address")

        try:
            pubhex, nip05_relays = nip05_to_npub(nip05)
        except Exception as exc:
            raise ValueError(f"Could not resolve nip05: {nip05}") from exc

        limit_value = max(1, min(int(limit), 100))
        relay_pool: List[str] = []
        relay_candidates = relays if relays else (nip05_relays or [])
        if not relay_candidates:
            relay_candidates = self._build_discovery_relays()

        for each in relay_candidates:
            if each and each not in relay_pool:
                relay_pool.append(each)

        if not relay_pool:
            raise ValueError("No relays available for query")

        query_filter = [{
            "limit": limit_value,
            "authors": [pubhex],
            "kinds": [1],
        }]
        async with ClientPool(relay_pool) as c:
            events: List[Event] = await c.query(query_filter)

        if not events:
            return []

        events_sorted = sorted(
            events,
            key=lambda each_event: int(each_event.created_at.timestamp()),
            reverse=True,
        )[:limit_value]

        def _kind1_event_to_dict(each_event: Event) -> Dict[str, Any]:
            event_tags = list(each_event.tags or [])
            reply_event_ids: List[str] = []
            for each_tag in event_tags:
                if each_tag and each_tag[0] == "e" and len(each_tag) > 1:
                    reply_event_ids.append(str(each_tag[1]))
            return {
                "id": str(each_event.id),
                "event_id": str(each_event.id),
                "event_id_hex": str(each_event.id),
                "pubkey": str(each_event.pub_key),
                "created_at": int(each_event.created_at.timestamp()),
                "content": str(each_event.content),
                "is_reply": bool(reply_event_ids),
                "reply_to_event_ids": reply_event_ids,
                "reply_to_primary_event_id": reply_event_ids[0] if reply_event_ids else None,
                "tags": event_tags,
            }
        return [
            _kind1_event_to_dict(each_event)
            for each_event in events_sorted
        ]

    async def get_latest_kind1_posts_by_author(
        self,
        pubhex: str | None = None,
        limit: int = 10,
        relays: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        author_pubhex = (pubhex or self.pubkey_hex or "").strip().lower()
        if not author_pubhex or len(author_pubhex) != 64 or not all(ch in string.hexdigits for ch in author_pubhex):
            raise ValueError("Invalid author pubhex")

        limit_value = max(1, min(int(limit), 100))
        relay_pool = relays if relays else self._build_discovery_relays()
        if not relay_pool:
            raise ValueError("No relays available for query")

        query_filter = [{
            "limit": limit_value,
            "authors": [author_pubhex],
            "kinds": [1],
        }]

        async with ClientPool(relay_pool) as c:
            events: List[Event] = await c.query(query_filter)

        if not events:
            return []

        events_sorted = sorted(
            events,
            key=lambda each_event: int(each_event.created_at.timestamp()),
            reverse=True,
        )[:limit_value]

        def _kind1_event_to_dict(each_event: Event) -> Dict[str, Any]:
            event_tags = list(each_event.tags or [])
            reply_event_ids: List[str] = []
            for each_tag in event_tags:
                if each_tag and each_tag[0] == "e" and len(each_tag) > 1:
                    reply_event_ids.append(str(each_tag[1]))
            return {
                "id": str(each_event.id),
                "event_id": str(each_event.id),
                "event_id_hex": str(each_event.id),
                "pubkey": str(each_event.pub_key),
                "created_at": int(each_event.created_at.timestamp()),
                "content": str(each_event.content),
                "is_reply": bool(reply_event_ids),
                "reply_to_event_ids": reply_event_ids,
                "reply_to_primary_event_id": reply_event_ids[0] if reply_event_ids else None,
                "tags": event_tags,
            }

        return [
            _kind1_event_to_dict(each_event)
            for each_event in events_sorted
        ]

    async def get_zap_receipts_for_event(
        self,
        event_id: str,
        limit: int = 100,
        relays: List[str] | None = None,
        strict: bool = False,
    ) -> List[Dict[str, Any]]:
        target_event_id = (event_id or "").strip()
        if not target_event_id:
            raise ValueError("event_id is required")

        if target_event_id.startswith("note"):
            target_event_id = bech32_to_hex(target_event_id)
        target_event_id = target_event_id.lower()
        if len(target_event_id) != 64 or not all(ch in string.hexdigits for ch in target_event_id):
            raise ValueError("Invalid event_id")

        limit_value = max(1, min(int(limit), 200))
        relay_pool = relays if relays else self._build_discovery_relays()
        if not relay_pool:
            raise ValueError("No relays available for query")

        query_filter = [{
            "limit": limit_value,
            "kinds": [9735],
            "#e": [target_event_id],
        }]

        async with ClientPool(relay_pool) as c:
            events: List[Event] = await c.query(query_filter)

        if not events:
            return []

        def _tag_values(tags: List[List[str]], key: str) -> List[str]:
            values: List[str] = []
            for each in tags:
                if each and each[0] == key and len(each) > 1:
                    values.append(str(each[1]))
            return values

        def _first_tag(tags: List[List[str]], key: str) -> str | None:
            vals = _tag_values(tags, key)
            return vals[0] if vals else None

        receipts_sorted = sorted(
            events,
            key=lambda each_event: int(each_event.created_at.timestamp()),
            reverse=True,
        )[:limit_value]

        results: List[Dict[str, Any]] = []
        for receipt in receipts_sorted:
            tags = list(receipt.tags or [])
            description_raw = _first_tag(tags, "description")
            bolt11_invoice = _first_tag(tags, "bolt11")
            lnurl_provider_pubkey = str(receipt.pub_key)
            lnurl_provider_npub: str | None = None
            recipient_pubkey = _first_tag(tags, "p")
            p_sender_tag = _first_tag(tags, "P")
            receipt_event_refs = _tag_values(tags, "e")
            zap_request: Dict[str, Any] | None = None
            zapper_pubkey: str | None = None
            zapper_npub: str | None = None
            zapper_identity_source = "none"
            zap_amount_msat: int | None = None
            zap_comment: str | None = None
            matches_target_event = target_event_id in [each.lower() for each in receipt_event_refs]
            description_hash_matches = None
            amount_from_invoice_msat: int | None = None

            if description_raw:
                try:
                    parsed_description = json.loads(description_raw)
                    if isinstance(parsed_description, dict):
                        zap_request = parsed_description
                        zapper_pubkey = str(zap_request.get("pubkey") or "").lower() or None
                        if zapper_pubkey:
                            zapper_identity_source = "description_pubkey"
                        zap_comment = str(zap_request.get("content") or "")
                        req_tags = list(zap_request.get("tags") or [])
                        for each_tag in req_tags:
                            if each_tag and each_tag[0] == "amount" and len(each_tag) > 1:
                                try:
                                    zap_amount_msat = int(str(each_tag[1]))
                                except Exception:
                                    zap_amount_msat = None
                                break
                except Exception:
                    zap_request = None

            if not zapper_pubkey and p_sender_tag:
                zapper_pubkey = p_sender_tag.lower()
                zapper_identity_source = "P_tag"

            if len(lnurl_provider_pubkey) == 64 and all(ch in string.hexdigits for ch in lnurl_provider_pubkey):
                try:
                    lnurl_provider_npub = hex_to_bech32(lnurl_provider_pubkey)
                except Exception:
                    lnurl_provider_npub = None

            if zapper_pubkey and len(zapper_pubkey) == 64 and all(ch in string.hexdigits for ch in zapper_pubkey):
                try:
                    zapper_npub = hex_to_bech32(zapper_pubkey)
                except Exception:
                    zapper_npub = None

            if bolt11_invoice:
                try:
                    decoded_invoice = bolt11.decode(bolt11_invoice)
                    if getattr(decoded_invoice, "amount_msat", None) is not None:
                        amount_from_invoice_msat = int(decoded_invoice.amount_msat)
                    if description_raw and getattr(decoded_invoice, "description_hash", None):
                        description_hash = hashlib.sha256(description_raw.encode("utf-8")).hexdigest()
                        description_hash_matches = (description_hash == str(decoded_invoice.description_hash))
                except Exception:
                    amount_from_invoice_msat = None

            amount_matches = None
            if zap_amount_msat is not None and amount_from_invoice_msat is not None:
                amount_matches = (zap_amount_msat == amount_from_invoice_msat)

            verified = bool(matches_target_event)
            if description_hash_matches is not None:
                verified = verified and bool(description_hash_matches)
            if amount_matches is not None:
                verified = verified and bool(amount_matches)

            if strict and not verified:
                continue

            results.append({
                "receipt_id": str(receipt.id),
                "created_at": int(receipt.created_at.timestamp()),
                "lnurl_provider_pubkey": lnurl_provider_pubkey,
                "lnurl_provider_npub": lnurl_provider_npub,
                "recipient_pubkey": recipient_pubkey,
                "zapper_pubkey": zapper_pubkey,
                "zapper_npub": zapper_npub,
                "zapper_identity_source": zapper_identity_source,
                "zap_request_raw": description_raw,
                "zap_request": zap_request,
                "zap_comment": zap_comment,
                "zap_amount_msat": zap_amount_msat,
                "invoice_amount_msat": amount_from_invoice_msat,
                "amount_matches": amount_matches,
                "matches_target_event": matches_target_event,
                "description_hash_matches": description_hash_matches,
                "verified": verified,
                "bolt11": bolt11_invoice,
                "raw_tags": tags,
            })

        return results

    async def get_replies_for_event(
        self,
        event_id: str,
        limit: int = 100,
        relays: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        target_event_id = (event_id or "").strip()
        if not target_event_id:
            raise ValueError("event_id is required")

        if target_event_id.startswith("note"):
            target_event_id = bech32_to_hex(target_event_id)
        target_event_id = target_event_id.lower()
        if len(target_event_id) != 64 or not all(ch in string.hexdigits for ch in target_event_id):
            raise ValueError("Invalid event_id")

        limit_value = max(1, min(int(limit), 200))
        relay_pool = relays if relays else self._build_discovery_relays()
        if not relay_pool:
            raise ValueError("No relays available for query")

        query_filter = [{
            "limit": limit_value,
            "kinds": [1],
            "#e": [target_event_id],
        }]

        async with ClientPool(relay_pool) as c:
            events: List[Event] = await c.query(query_filter)

        if not events:
            return []

        def _tag_values(tags: List[List[str]], key: str) -> List[str]:
            values: List[str] = []
            for each in tags:
                if each and each[0] == key and len(each) > 1:
                    values.append(str(each[1]))
            return values

        events_sorted = sorted(
            events,
            key=lambda each_event: int(each_event.created_at.timestamp()),
            reverse=True,
        )[:limit_value]

        results: List[Dict[str, Any]] = []
        for each_event in events_sorted:
            tags = list(each_event.tags or [])
            reply_refs = [value.lower() for value in _tag_values(tags, "e")]
            is_direct_reply = bool(reply_refs) and reply_refs[0] == target_event_id

            results.append(
                {
                    "id": str(each_event.id),
                    "event_id": str(each_event.id),
                    "event_id_hex": str(each_event.id),
                    "pubkey": str(each_event.pub_key),
                    "created_at": int(each_event.created_at.timestamp()),
                    "content": str(each_event.content),
                    "reply_to_event_ids": reply_refs,
                    "is_direct_reply": is_direct_reply,
                    "tags": tags,
                }
            )

        return results
        
if __name__ == "__main__":
    
    # url = ['wss://relay.0xchat.com','wss://relay.damus.io']
    # this relay seems to work the best with these kind of anon published events, atleast for now
    # others it seems to be a bit of hit and miss...
    url = ['wss://relay.getsafebox.app']
    # asyncio.run(listen_notes(url))  
