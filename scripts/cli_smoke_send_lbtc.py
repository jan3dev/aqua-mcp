#!/usr/bin/env python3
"""CLI smoke test: Send real L-BTC on Liquid mainnet.

Mirrors prompt_test_send_real_lbtc.md using the aqua-cli CLI.

Requirements:
    SIGNER_MNEMONIC     - BIP39 mnemonic for the test wallet
    LIQUID_DEST_ADDRESS  - Liquid address to send to

Usage:
    uv run python scripts/cli_smoke_send_lbtc.py
"""

import json
import os
import sys
import time

from click.testing import CliRunner
from aqua_mcp.cli.main import cli

MNEMONIC = os.getenv("SIGNER_MNEMONIC")
DEST_ADDRESS = os.getenv("LIQUID_DEST_ADDRESS")
SEND_AMOUNT = 500  # sats

if not MNEMONIC or not DEST_ADDRESS:
    print("ERROR: Set SIGNER_MNEMONIC and LIQUID_DEST_ADDRESS in .env")
    sys.exit(1)

runner = CliRunner()
WALLET = f"lbtc_smoke_{int(time.time())}"
passed = 0
failed = 0


def run_cli(*args):
    """Invoke CLI and return parsed JSON, or exit on failure."""
    result = runner.invoke(cli, ["--format", "json", *args])
    if result.exit_code != 0:
        print(f"  FAIL (exit {result.exit_code}): {result.output}")
        return None
    return json.loads(result.output)


def test(name, fn):
    global passed, failed
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    try:
        fn()
        passed += 1
        print(f"  PASS")
    except Exception as e:
        failed += 1
        print(f"  FAIL: {e}")


# ---------------------------------------------------------------------------
# 1. Import Wallet and Check Balance
# ---------------------------------------------------------------------------

def test_import_and_balance():
    result = run_cli(
        "wallet", "import-mnemonic",
        "--mnemonic", MNEMONIC,
        "--wallet-name", WALLET,
    )
    assert result is not None, "Import failed"
    assert result["wallet_name"] == WALLET
    print(f"  Wallet '{WALLET}' imported")

    balance = run_cli("liquid", "balance", "--wallet-name", WALLET)
    assert balance is not None, "Balance check failed"
    print(f"  Liquid balances: {json.dumps(balance['balances'], indent=2)}")

    # Check L-BTC balance is sufficient
    lbtc_sats = 0
    for b in balance["balances"]:
        if b.get("ticker") == "L-BTC":
            lbtc_sats = b.get("amount_sats", b.get("value", 0))
    print(f"  L-BTC balance: {lbtc_sats} sats")
    assert lbtc_sats > SEND_AMOUNT, f"Insufficient L-BTC: {lbtc_sats} < {SEND_AMOUNT}"

test("1. Import Wallet and Check L-BTC Balance", test_import_and_balance)

# ---------------------------------------------------------------------------
# 2. Send L-BTC
# ---------------------------------------------------------------------------

txid = None

def test_send_lbtc():
    global txid
    result = run_cli(
        "liquid", "send",
        "--wallet-name", WALLET,
        "--address", DEST_ADDRESS,
        "--amount", str(SEND_AMOUNT),
    )
    assert result is not None, "Send failed"
    txid = result["txid"]
    print(f"  Sent {SEND_AMOUNT} sats to {DEST_ADDRESS}")
    print(f"  TXID: {txid}")
    assert len(txid) == 64, f"Invalid txid length: {len(txid)}"

test("2. Send L-BTC", test_send_lbtc)

# ---------------------------------------------------------------------------
# 3. Check Transaction Status
# ---------------------------------------------------------------------------

def test_tx_status():
    assert txid is not None, "No txid from send test"
    result = run_cli("liquid", "tx-status", "--tx", txid)
    assert result is not None, "Status check failed"
    print(f"  Status: {result.get('status')}")
    print(f"  Explorer: {result.get('explorer_url')}")
    assert result["txid"] == txid

test("3. Check Transaction Status", test_tx_status)

# ---------------------------------------------------------------------------
# 4. Verify Updated Balance
# ---------------------------------------------------------------------------

def test_updated_balance():
    balance = run_cli("liquid", "balance", "--wallet-name", WALLET)
    assert balance is not None, "Balance check failed"
    for b in balance["balances"]:
        if b.get("ticker") == "L-BTC":
            print(f"  Updated L-BTC balance: {b.get('amount_sats', b.get('value', 0))} sats")

test("4. Verify Updated Balance", test_updated_balance)

# ---------------------------------------------------------------------------
# 5. View Transaction History
# ---------------------------------------------------------------------------

def test_tx_history():
    result = run_cli("liquid", "transactions", "--wallet-name", WALLET)
    assert result is not None, "Transactions failed"
    print(f"  Transaction count: {result['count']}")
    if result["transactions"]:
        latest = result["transactions"][0]
        print(f"  Latest txid: {latest.get('txid', 'N/A')}")

test("5. View Transaction History", test_tx_history)

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

print(f"\n{'='*60}")
print("CLEANUP: Deleting smoke wallet")
run_cli("wallet", "delete", "--wallet-name", WALLET, "--yes")
print(f"  Wallet '{WALLET}' deleted")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
print(f"{'='*60}")
sys.exit(1 if failed > 0 else 0)
