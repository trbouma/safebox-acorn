"""Wallet token wrappers: parse both versions; serialize without mint calls."""
from acorn.models import TokenV3, TokenV4


def normalize_cashu_token(token: str) -> str:
    value = str(token or "").strip()
    if value.startswith("cashu:"):
        value = value[6:]
    if not value.startswith(("cashuA", "cashuB")) or len(value) > 128 * 1024:
        raise ValueError("Enter a valid cashuA or cashuB token")
    return value


def decode_cashu_token(token: str) -> TokenV3:
    value = normalize_cashu_token(token)
    try:
        if value.startswith("cashuB"):
            return TokenV4.deserialize(value).to_tokenv3()
        return TokenV3.deserialize(value)
    except Exception as exc:
        # Decoder errors can contain proof secrets; keep the public error generic.
        raise ValueError("Invalid Cashu token encoding") from exc


def encode_cashu_token(token: TokenV3, token_format: str = "auto") -> str:
    if token_format not in {"auto", "cashuA", "cashuB"}:
        raise ValueError("Token format must be auto, cashuA, or cashuB")
    if token_format != "cashuA" and len(token.get_mints()) == 1:
        try:
            return TokenV4.from_tokenv3(token).serialize(include_dleq=True)
        except (ValueError, TypeError):
            if token_format == "cashuB":
                raise ValueError("These proofs cannot be represented as cashuB") from None
    elif token_format == "cashuB":
        raise ValueError("cashuB requires exactly one mint")
    return token.serialize(include_dleq=True)
