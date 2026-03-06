"""Boltz Exchange integration for submarine swaps (L-BTC -> Lightning)."""

import urllib.request
import urllib.error
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


BOLTZ_API = {
    "mainnet": "https://api.boltz.exchange",
    "testnet": "https://api.testnet.boltz.exchange",
}


@dataclass
class SwapInfo:
    """Holds all data for an active/completed submarine swap."""

    swap_id: str
    address: str
    expected_amount: int
    claim_public_key: str
    swap_tree: dict
    timeout_block_height: int
    refund_private_key: str
    refund_public_key: str
    invoice: str
    status: str
    network: str
    created_at: str
    lockup_txid: Optional[str] = None
    preimage: Optional[str] = None
    claim_txid: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class BoltzClient:
    """HTTP client for Boltz API v2."""

    def __init__(self, network: str = "mainnet"):
        raise NotImplementedError

    def get_submarine_pairs(self) -> dict:
        """GET /v2/swap/submarine - fetch available pairs, fees, limits."""
        raise NotImplementedError

    def create_submarine_swap(self, invoice: str, refund_public_key: str) -> dict:
        """POST /v2/swap/submarine - create a new swap."""
        raise NotImplementedError

    def get_swap_status(self, swap_id: str) -> dict:
        """POST /v2/swap/{swap_id} - get current swap status."""
        raise NotImplementedError

    def get_claim_details(self, swap_id: str) -> dict:
        """GET /v2/swap/submarine/{swap_id}/claim - get preimage after invoice paid."""
        raise NotImplementedError


def generate_keypair() -> tuple[str, str]:
    """Generate ephemeral secp256k1 keypair for refund.

    Returns (private_key_hex, public_key_hex).
    Uses coincurve for key derivation.
    """
    raise NotImplementedError


def verify_preimage(preimage_hex: str, expected_hash_hex: str) -> bool:
    """Verify SHA256(preimage) == expected_hash. Pure stdlib."""
    raise NotImplementedError
