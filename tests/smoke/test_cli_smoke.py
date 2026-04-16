"""CLI smoke tests mirroring prompt_test_read_only.md.

These tests hit MAINNET via real Electrum/Esplora servers.
They are SKIPPED unless SIGNER_MNEMONIC is set in the environment.

Usage:
    SIGNER_MNEMONIC="word1 word2 ..." uv run python -m pytest tests/smoke/ -v
"""

import json
import os
import time

import pytest

SIGNER_MNEMONIC = os.getenv("SIGNER_MNEMONIC")

pytestmark = pytest.mark.skipif(
    not SIGNER_MNEMONIC,
    reason="SIGNER_MNEMONIC not set — skipping mainnet smoke tests",
)


@pytest.fixture(scope="module")
def wallet_name():
    """Unique wallet name for this smoke run."""
    return f"smoke_cli_{int(time.time())}"


@pytest.fixture(scope="module")
def cli_runner():
    """Return a function that invokes aqua-cli and returns parsed JSON."""
    from click.testing import CliRunner
    from aqua_mcp.cli.main import cli

    runner = CliRunner()

    def run(*args):
        result = runner.invoke(cli, ["--format", "json", *args])
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        return json.loads(result.output)

    return run


# ---------------------------------------------------------------------------
# 1. Import Wallet (prompt_test_read_only.md #1)
# ---------------------------------------------------------------------------


class TestSmokeImportWallet:
    def test_import_wallet(self, cli_runner, wallet_name):
        """Import the test wallet from SIGNER_MNEMONIC."""
        result = cli_runner(
            "wallet", "import-mnemonic",
            "--mnemonic", SIGNER_MNEMONIC,
            "--wallet-name", wallet_name,
        )
        assert result["wallet_name"] == wallet_name
        assert result["watch_only"] is False


# ---------------------------------------------------------------------------
# 2-3. Generate Receive Addresses (prompt_test_read_only.md #2)
# ---------------------------------------------------------------------------


class TestSmokeAddresses:
    def test_liquid_address(self, cli_runner, wallet_name):
        """Liquid address starts with lq1 (mainnet)."""
        result = cli_runner("liquid", "address", "--wallet-name", wallet_name)
        assert result["address"].startswith("lq1") or result["address"].startswith("ex1")

    def test_btc_address(self, cli_runner, wallet_name):
        """Bitcoin address starts with bc1 (mainnet)."""
        result = cli_runner("btc", "address", "--wallet-name", wallet_name)
        assert result["address"].startswith("bc1")


# ---------------------------------------------------------------------------
# 4. Unified Balance (prompt_test_read_only.md #3)
# ---------------------------------------------------------------------------


class TestSmokeBalance:
    def test_unified_balance(self, cli_runner, wallet_name):
        """Unified balance returns both networks."""
        result = cli_runner("balance", "--wallet-name", wallet_name)
        assert "liquid" in result
        # Bitcoin may be None if no BTC descriptors, but key should exist
        assert "bitcoin" in result or "bitcoin_error" in result


# ---------------------------------------------------------------------------
# 5. BTC Transaction History (prompt_test_read_only.md #4)
# ---------------------------------------------------------------------------


class TestSmokeBtcTransactions:
    def test_btc_transactions(self, cli_runner, wallet_name):
        """BTC transactions returns a list."""
        result = cli_runner("btc", "transactions", "--wallet-name", wallet_name)
        assert "transactions" in result
        assert isinstance(result["transactions"], list)


# ---------------------------------------------------------------------------
# 6. Liquid Transaction History (prompt_test_read_only.md #5)
# ---------------------------------------------------------------------------


class TestSmokeLiquidTransactions:
    def test_liquid_transactions(self, cli_runner, wallet_name):
        """Liquid transactions returns a list."""
        result = cli_runner("liquid", "transactions", "--wallet-name", wallet_name)
        assert "transactions" in result
        assert isinstance(result["transactions"], list)


# ---------------------------------------------------------------------------
# 7. List All Wallets (prompt_test_read_only.md #6)
# ---------------------------------------------------------------------------


class TestSmokeListWallets:
    def test_list_wallets(self, cli_runner, wallet_name):
        """Wallet list includes the smoke wallet."""
        result = cli_runner("wallet", "list")
        assert result["count"] >= 1
        wallet_names = [w["name"] if isinstance(w, dict) else w for w in result["wallets"]]
        assert wallet_name in wallet_names


# ---------------------------------------------------------------------------
# 8. Export Descriptor (prompt_test_read_only.md #7)
# ---------------------------------------------------------------------------


class TestSmokeExportDescriptor:
    def test_export_descriptor(self, cli_runner, wallet_name):
        """Export descriptor returns a CT descriptor string."""
        result = cli_runner("wallet", "export-descriptor", "--wallet-name", wallet_name)
        assert "descriptor" in result
        assert result["descriptor"].startswith("ct(")


# ---------------------------------------------------------------------------
# 9. Lightning Receive (prompt_test_read_only.md #9)
# ---------------------------------------------------------------------------


class TestSmokeLightningReceive:
    def test_lightning_receive(self, cli_runner, wallet_name):
        """Generate a Lightning invoice for 500 sats."""
        result = cli_runner(
            "lightning", "receive",
            "--amount", "500",
            "--wallet-name", wallet_name,
        )
        assert "swap_id" in result
        assert "invoice" in result
        assert result["amount"] == 500
        # Store swap_id for status check
        TestSmokeLightningReceive._swap_id = result["swap_id"]


# ---------------------------------------------------------------------------
# 10. Lightning Swap Status (prompt_test_read_only.md #10)
# ---------------------------------------------------------------------------


class TestSmokeLightningStatus:
    def test_lightning_status(self, cli_runner):
        """Check status of the receive swap created above."""
        swap_id = getattr(TestSmokeLightningReceive, "_swap_id", None)
        if swap_id is None:
            pytest.skip("No swap_id from lightning receive test")
        result = cli_runner("lightning", "status", "--swap-id", swap_id)
        assert "swap_id" in result
        assert "status" in result


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


class TestSmokeCleanup:
    def test_delete_smoke_wallet(self, wallet_name):
        """Delete the smoke wallet after all tests."""
        from click.testing import CliRunner
        from aqua_mcp.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--format", "json", "wallet", "delete", "--wallet-name", wallet_name, "--yes"],
        )
        assert result.exit_code == 0
