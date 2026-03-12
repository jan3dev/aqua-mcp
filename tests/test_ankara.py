"""Tests for Ankara Lightning receive integration (Layers 1-7)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, UTC

import pytest

from aqua_mcp.ankara import (
    AnkaraClient,
    AnkaraSwapInfo,
    MIN_SWAP_AMOUNT_SATS,
    MAX_SWAP_AMOUNT_SATS,
)
from aqua_mcp.storage import Storage
from aqua_mcp.tools import (
    ankara_ln_receive,
    ankara_ln_claim,
    ankara_ln_verify,
)
from aqua_mcp.wallet import WalletManager
import urllib.error


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon about"
)

VALID_INVOICE = "lnbc500u1ptest_valid_bolt11_invoice_data"

MOCK_ANKARA_CREATE_RESPONSE = {
    "swap_id": "ankara_test_123",
    "boltz_swap_id": "boltz_abc_456",
    "invoice": VALID_INVOICE,
}

MOCK_ANKARA_VERIFY_RESPONSE_PENDING = {
    "settled": False,
}

MOCK_ANKARA_VERIFY_RESPONSE_SETTLED = {
    "settled": True,
    "preimage": "aa" * 32,
}


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_response(data, status=200):
    """Create a mock urllib response (context manager)."""
    resp = MagicMock()
    if isinstance(data, dict):
        resp.read.return_value = json.dumps(data).encode()
    else:
        resp.read.return_value = data
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_manager():
    """Replace the global manager with one using a temp directory."""
    import aqua_mcp.tools as tools_module

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = Storage(Path(tmpdir))
        manager = WalletManager(storage=storage)
        tools_module._manager = manager
        tools_module._btc_manager = None
        yield manager
        tools_module._manager = None
        tools_module._btc_manager = None


@pytest.fixture
def test_wallet(isolated_manager):
    """Create a test wallet with balance."""
    isolated_manager.import_mnemonic(TEST_MNEMONIC, "default", "testnet")
    return isolated_manager.load_wallet("default")


# ===========================================================================
# Layer 1: AnkaraSwapInfo dataclass
# ===========================================================================


class TestAnkaraSwapInfo:
    """Tests for AnkaraSwapInfo dataclass."""

    def test_to_dict(self):
        """Convert AnkaraSwapInfo to dict."""
        swap = AnkaraSwapInfo(
            swap_id="test_swap",
            boltz_swap_id="boltz_123",
            invoice="lnbc...",
            address="lq1test",
            amount=100000,
            wallet_name="default",
            status="pending",
            created_at="2026-03-01T00:00:00+00:00",
        )
        result = swap.to_dict()
        assert result["swap_id"] == "test_swap"
        assert result["status"] == "pending"

    def test_from_dict(self):
        """Create AnkaraSwapInfo from dict."""
        data = {
            "swap_id": "test_swap",
            "boltz_swap_id": "boltz_123",
            "invoice": "lnbc...",
            "address": "lq1test",
            "amount": 100000,
            "wallet_name": "default",
            "status": "pending",
            "created_at": "2026-03-01T00:00:00+00:00",
            "preimage": None,
        }
        swap = AnkaraSwapInfo.from_dict(data)
        assert swap.swap_id == "test_swap"
        assert swap.wallet_name == "default"

    def test_with_preimage(self):
        """AnkaraSwapInfo with preimage."""
        swap = AnkaraSwapInfo(
            swap_id="test",
            boltz_swap_id="bolt",
            invoice="lnbc",
            address="lq1",
            amount=1000,
            wallet_name="w",
            status="settled",
            created_at="2026-01-01T00:00:00+00:00",
            preimage="aa" * 32,
        )
        assert swap.preimage == "aa" * 32
        assert swap.to_dict()["preimage"] == "aa" * 32


# ===========================================================================
# Layer 2: AnkaraClient HTTP
# ===========================================================================


class TestAnkaraClientHTTP:
    """Tests for AnkaraClient HTTP communication."""

    def test_create_swap_success(self):
        """POST /api/v1/lightning/swaps/create/ succeeds."""
        client = AnkaraClient()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_response(MOCK_ANKARA_CREATE_RESPONSE)
            result = client.create_swap(100000, "lq1test")
            assert result["swap_id"] == "ankara_test_123"
            assert result["invoice"] == VALID_INVOICE

    def test_create_swap_http_error(self):
        """POST /api/v1/lightning/swaps/create/ handles HTTP error."""
        client = AnkaraClient()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_error = urllib.error.HTTPError(
                "url", 400, "Bad Request", {}, MagicMock()
            )
            mock_error.read = MagicMock(
                return_value=json.dumps({"error": "Invalid amount"}).encode()
            )
            mock_urlopen.side_effect = mock_error
            with pytest.raises(RuntimeError) as exc:
                client.create_swap(0, "lq1test")
            assert "Invalid amount" in str(exc.value)

    def test_claim_swap_success(self):
        """POST /api/v1/lightning/swaps/{swap_id}/claim/ succeeds."""
        client = AnkaraClient()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_response({"status": "claimed"})
            result = client.claim_swap("test_swap_123")
            assert result["status"] == "claimed"

    def test_verify_swap_success(self):
        """GET /api/v1/lightning/lnurlp/verify/{swap_id} succeeds."""
        client = AnkaraClient()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_response(
                MOCK_ANKARA_VERIFY_RESPONSE_SETTLED
            )
            result = client.verify_swap("test_swap_123")
            assert result["settled"] is True
            assert result["preimage"] == "aa" * 32

    def test_api_request_url_error(self):
        """_api_request handles URLError."""
        client = AnkaraClient()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
            with pytest.raises(RuntimeError) as exc:
                client.create_swap(100000, "lq1test")
            assert "unreachable" in str(exc.value)


# ===========================================================================
# Layer 3: Storage persistence
# ===========================================================================


class TestAnkaraStoragePersistence:
    """Tests for Ankara swap storage operations."""

    @pytest.fixture
    def storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Storage(Path(tmpdir))

    def test_save_ankara_swap(self, storage):
        """save_ankara_swap writes to disk."""
        swap = AnkaraSwapInfo(
            swap_id="test_123",
            boltz_swap_id="boltz_456",
            invoice="lnbc...",
            address="lq1test",
            amount=100000,
            wallet_name="default",
            status="pending",
            created_at="2026-03-01T00:00:00+00:00",
        )
        storage.save_ankara_swap(swap)
        assert (storage.ankara_swaps_dir / "test_123.json").exists()

    def test_load_ankara_swap(self, storage):
        """load_ankara_swap reads from disk."""
        swap = AnkaraSwapInfo(
            swap_id="test_123",
            boltz_swap_id="boltz_456",
            invoice="lnbc...",
            address="lq1test",
            amount=100000,
            wallet_name="default",
            status="pending",
            created_at="2026-03-01T00:00:00+00:00",
        )
        storage.save_ankara_swap(swap)
        loaded = storage.load_ankara_swap("test_123")
        assert loaded is not None
        assert loaded.swap_id == "test_123"
        assert loaded.wallet_name == "default"

    def test_load_ankara_swap_not_found(self, storage):
        """load_ankara_swap returns None for missing swap."""
        result = storage.load_ankara_swap("nonexistent")
        assert result is None

    def test_list_ankara_swaps(self, storage):
        """list_ankara_swaps returns all swap IDs."""
        swap1 = AnkaraSwapInfo(
            swap_id="swap_1",
            boltz_swap_id="bolt_1",
            invoice="lnbc1",
            address="lq1a",
            amount=1000,
            wallet_name="w1",
            status="pending",
            created_at="2026-03-01T00:00:00+00:00",
        )
        swap2 = AnkaraSwapInfo(
            swap_id="swap_2",
            boltz_swap_id="bolt_2",
            invoice="lnbc2",
            address="lq1b",
            amount=2000,
            wallet_name="w2",
            status="settled",
            created_at="2026-03-02T00:00:00+00:00",
        )
        storage.save_ankara_swap(swap1)
        storage.save_ankara_swap(swap2)
        swaps = storage.list_ankara_swaps()
        assert len(swaps) == 2
        assert "swap_1" in swaps
        assert "swap_2" in swaps

    def test_swap_file_permissions(self, storage):
        """Ankara swap files have restricted permissions (0o600)."""
        swap = AnkaraSwapInfo(
            swap_id="test_123",
            boltz_swap_id="boltz_456",
            invoice="lnbc...",
            address="lq1test",
            amount=100000,
            wallet_name="default",
            status="pending",
            created_at="2026-03-01T00:00:00+00:00",
        )
        storage.save_ankara_swap(swap)
        path = storage.ankara_swaps_dir / "test_123.json"
        assert path.exists()
        import os
        stat_info = os.stat(path)
        mode = stat_info.st_mode & 0o777
        assert mode == 0o600


# ===========================================================================
# Layer 5: ankara_ln_receive tool
# ===========================================================================


class TestAnkaraLnReceive:
    """Tests for ankara_ln_receive tool."""

    def test_ankara_ln_receive_success(self, test_wallet, isolated_manager):
        """ankara_ln_receive creates swap and returns invoice."""
        with patch.object(AnkaraClient, "create_swap") as mock_create:
            mock_create.return_value = MOCK_ANKARA_CREATE_RESPONSE
            result = ankara_ln_receive(100000, "default")
            assert result["swap_id"] == "ankara_test_123"
            assert result["invoice"] == VALID_INVOICE
            assert result["amount"] == 100000
            assert result["wallet_name"] == "default"

    def test_ankara_ln_receive_amount_too_low(self, test_wallet):
        """ankara_ln_receive rejects amount below minimum."""
        with pytest.raises(ValueError) as exc:
            ankara_ln_receive(50, "default")
        assert "minimum" in str(exc.value)

    def test_ankara_ln_receive_amount_too_high(self, test_wallet):
        """ankara_ln_receive rejects amount above maximum."""
        with pytest.raises(ValueError) as exc:
            ankara_ln_receive(30_000_000, "default")
        assert "exceeds" in str(exc.value)

    def test_ankara_ln_receive_wallet_not_found(self):
        """ankara_ln_receive rejects nonexistent wallet."""
        with pytest.raises(ValueError) as exc:
            ankara_ln_receive(100000, "nonexistent")
        assert "not found" in str(exc.value)

    def test_ankara_ln_receive_requires_passphrase(self, isolated_manager):
        """ankara_ln_receive requires passphrase for encrypted wallet."""
        isolated_manager.import_mnemonic(
            TEST_MNEMONIC, "encrypted", "testnet", passphrase="secret"
        )
        with pytest.raises(ValueError) as exc:
            ankara_ln_receive(100000, "encrypted")
        assert "Passphrase required" in str(exc.value)

    def test_ankara_ln_receive_persists_swap(self, test_wallet, isolated_manager):
        """ankara_ln_receive saves swap to storage."""
        with patch.object(AnkaraClient, "create_swap") as mock_create:
            mock_create.return_value = MOCK_ANKARA_CREATE_RESPONSE
            ankara_ln_receive(100000, "default")
            swap = isolated_manager.storage.load_ankara_swap("ankara_test_123")
            assert swap is not None
            assert swap.swap_id == "ankara_test_123"
            assert swap.wallet_name == "default"

    def test_ankara_ln_receive_includes_wallet_note_multiple(
        self, test_wallet, isolated_manager
    ):
        """ankara_ln_receive includes wallet name when multiple wallets exist."""
        isolated_manager.import_mnemonic(TEST_MNEMONIC, "second", "testnet")
        with patch.object(AnkaraClient, "create_swap") as mock_create:
            mock_create.return_value = MOCK_ANKARA_CREATE_RESPONSE
            result = ankara_ln_receive(100000, "default")
            assert "in wallet 'default'" in result["message"]

    def test_ankara_ln_receive_api_error(self, test_wallet):
        """ankara_ln_receive handles API errors."""
        with patch.object(AnkaraClient, "create_swap") as mock_create:
            mock_create.side_effect = RuntimeError("API unreachable")
            with pytest.raises(RuntimeError) as exc:
                ankara_ln_receive(100000, "default")
            assert "Failed to create Ankara swap" in str(exc.value)


# ===========================================================================
# Layer 6: ankara_ln_claim tool
# ===========================================================================


class TestAnkaraLnClaim:
    """Tests for ankara_ln_claim tool."""

    def test_ankara_ln_claim_success(self, isolated_manager):
        """ankara_ln_claim claims swap and updates status."""
        # Save a swap first
        swap = AnkaraSwapInfo(
            swap_id="test_swap",
            boltz_swap_id="boltz_123",
            invoice="lnbc...",
            address="lq1test",
            amount=100000,
            wallet_name="default",
            status="pending",
            created_at="2026-03-01T00:00:00+00:00",
        )
        isolated_manager.storage.save_ankara_swap(swap)

        # Claim it
        with patch.object(AnkaraClient, "claim_swap") as mock_claim:
            mock_claim.return_value = {"status": "claimed"}
            result = ankara_ln_claim("test_swap")
            assert result["swap_id"] == "test_swap"
            assert result["status"] == "claimed"

    def test_ankara_ln_claim_swap_not_found(self, isolated_manager):
        """ankara_ln_claim rejects nonexistent swap."""
        with pytest.raises(ValueError) as exc:
            ankara_ln_claim("nonexistent")
        assert "not found" in str(exc.value)

    def test_ankara_ln_claim_persists_status(self, isolated_manager):
        """ankara_ln_claim updates and saves status."""
        swap = AnkaraSwapInfo(
            swap_id="test_swap",
            boltz_swap_id="boltz_123",
            invoice="lnbc...",
            address="lq1test",
            amount=100000,
            wallet_name="default",
            status="pending",
            created_at="2026-03-01T00:00:00+00:00",
        )
        isolated_manager.storage.save_ankara_swap(swap)

        with patch.object(AnkaraClient, "claim_swap") as mock_claim:
            mock_claim.return_value = {"status": "claimed"}
            ankara_ln_claim("test_swap")
            reloaded = isolated_manager.storage.load_ankara_swap("test_swap")
            assert reloaded.status == "claimed"

    def test_ankara_ln_claim_api_error(self, isolated_manager):
        """ankara_ln_claim handles API errors."""
        swap = AnkaraSwapInfo(
            swap_id="test_swap",
            boltz_swap_id="boltz_123",
            invoice="lnbc...",
            address="lq1test",
            amount=100000,
            wallet_name="default",
            status="pending",
            created_at="2026-03-01T00:00:00+00:00",
        )
        isolated_manager.storage.save_ankara_swap(swap)

        with patch.object(AnkaraClient, "claim_swap") as mock_claim:
            mock_claim.side_effect = RuntimeError("API unreachable")
            with pytest.raises(RuntimeError) as exc:
                ankara_ln_claim("test_swap")
            assert "Failed to claim Ankara swap" in str(exc.value)


# ===========================================================================
# Layer 7: ankara_ln_verify tool
# ===========================================================================


class TestAnkaraLnVerify:
    """Tests for ankara_ln_verify tool."""

    def test_ankara_ln_verify_pending(self, isolated_manager):
        """ankara_ln_verify reports pending status."""
        swap = AnkaraSwapInfo(
            swap_id="test_swap",
            boltz_swap_id="boltz_123",
            invoice="lnbc...",
            address="lq1test",
            amount=100000,
            wallet_name="default",
            status="pending",
            created_at="2026-03-01T00:00:00+00:00",
        )
        isolated_manager.storage.save_ankara_swap(swap)

        with patch.object(AnkaraClient, "verify_swap") as mock_verify:
            mock_verify.return_value = MOCK_ANKARA_VERIFY_RESPONSE_PENDING
            result = ankara_ln_verify("test_swap")
            assert result["swap_id"] == "test_swap"
            assert result["settled"] is False
            assert "preimage" not in result

    def test_ankara_ln_verify_settled(self, isolated_manager):
        """ankara_ln_verify reports settled status with preimage."""
        swap = AnkaraSwapInfo(
            swap_id="test_swap",
            boltz_swap_id="boltz_123",
            invoice="lnbc...",
            address="lq1test",
            amount=100000,
            wallet_name="default",
            status="pending",
            created_at="2026-03-01T00:00:00+00:00",
        )
        isolated_manager.storage.save_ankara_swap(swap)

        with patch.object(AnkaraClient, "verify_swap") as mock_verify:
            mock_verify.return_value = MOCK_ANKARA_VERIFY_RESPONSE_SETTLED
            result = ankara_ln_verify("test_swap")
            assert result["settled"] is True
            assert result["preimage"] == "aa" * 32
            assert result["wallet_name"] == "default"

    def test_ankara_ln_verify_updates_status(self, isolated_manager):
        """ankara_ln_verify updates swap status when settled."""
        swap = AnkaraSwapInfo(
            swap_id="test_swap",
            boltz_swap_id="boltz_123",
            invoice="lnbc...",
            address="lq1test",
            amount=100000,
            wallet_name="default",
            status="pending",
            created_at="2026-03-01T00:00:00+00:00",
        )
        isolated_manager.storage.save_ankara_swap(swap)

        with patch.object(AnkaraClient, "verify_swap") as mock_verify:
            mock_verify.return_value = MOCK_ANKARA_VERIFY_RESPONSE_SETTLED
            ankara_ln_verify("test_swap")
            reloaded = isolated_manager.storage.load_ankara_swap("test_swap")
            assert reloaded.status == "settled"
            assert reloaded.preimage == "aa" * 32

    def test_ankara_ln_verify_swap_not_found_locally(self, isolated_manager):
        """ankara_ln_verify works even if swap not found locally."""
        with patch.object(AnkaraClient, "verify_swap") as mock_verify:
            mock_verify.return_value = MOCK_ANKARA_VERIFY_RESPONSE_SETTLED
            result = ankara_ln_verify("unknown_swap")
            assert result["settled"] is True
            assert "wallet_name" not in result  # Not found locally

    def test_ankara_ln_verify_api_error(self, isolated_manager):
        """ankara_ln_verify handles API errors."""
        with patch.object(AnkaraClient, "verify_swap") as mock_verify:
            mock_verify.side_effect = RuntimeError("API unreachable")
            with pytest.raises(RuntimeError) as exc:
                ankara_ln_verify("test_swap")
            assert "Failed to verify Ankara swap" in str(exc.value)
