"""MCP tool definitions for Liquid Wallet."""

from typing import Any

from .assets import resolve_asset_name
from .wallet import WalletManager


# Global wallet manager instance
_manager: WalletManager | None = None


def get_manager() -> WalletManager:
    """Get or create wallet manager."""
    global _manager
    if _manager is None:
        _manager = WalletManager()
    return _manager


# Tool implementations

def lw_generate_mnemonic(words: int = 12) -> dict[str, Any]:
    """
    Generate a new BIP39 mnemonic phrase.
    
    Args:
        words: Number of words (12 or 24). Default: 12
        
    Returns:
        mnemonic: The generated mnemonic phrase
    """
    manager = get_manager()
    mnemonic = manager.generate_mnemonic(words)
    return {
        "mnemonic": mnemonic,
        "words": len(mnemonic.split()),
        "warning": "Store this mnemonic securely. Anyone with access can control your funds.",
    }


def lw_import_mnemonic(
    mnemonic: str,
    wallet_name: str = "default",
    network: str = "mainnet",
    passphrase: str | None = None,
) -> dict[str, Any]:
    """
    Import a wallet from a BIP39 mnemonic.
    
    Args:
        mnemonic: BIP39 mnemonic phrase
        wallet_name: Name for the wallet. Default: "default"
        network: "mainnet" or "testnet". Default: "mainnet"
        passphrase: Optional passphrase to encrypt the mnemonic at rest
        
    Returns:
        wallet_name: Name of the created wallet
        network: Network the wallet is on
        descriptor: CT descriptor (can be shared for watch-only)
        watch_only: False (this is a full wallet)
    """
    manager = get_manager()
    wallet = manager.import_mnemonic(mnemonic, wallet_name, network, passphrase)
    return {
        "wallet_name": wallet.name,
        "network": wallet.network,
        "descriptor": wallet.descriptor,
        "watch_only": wallet.watch_only,
    }


def lw_import_descriptor(
    descriptor: str,
    wallet_name: str,
    network: str = "mainnet",
) -> dict[str, Any]:
    """
    Import a watch-only wallet from a CT descriptor.
    
    Args:
        descriptor: CT descriptor string
        wallet_name: Name for the wallet
        network: "mainnet" or "testnet". Default: "mainnet"
        
    Returns:
        wallet_name: Name of the created wallet
        network: Network the wallet is on
        watch_only: True (cannot sign transactions)
    """
    manager = get_manager()
    wallet = manager.import_descriptor(descriptor, wallet_name, network)
    return {
        "wallet_name": wallet.name,
        "network": wallet.network,
        "watch_only": wallet.watch_only,
    }


def lw_export_descriptor(wallet_name: str = "default") -> dict[str, Any]:
    """
    Export the CT descriptor for a wallet.
    
    The descriptor can be used to create a watch-only wallet elsewhere.
    
    Args:
        wallet_name: Name of the wallet. Default: "default"
        
    Returns:
        descriptor: CT descriptor string
        wallet_name: Name of the wallet
    """
    manager = get_manager()
    descriptor = manager.export_descriptor(wallet_name)
    return {
        "wallet_name": wallet_name,
        "descriptor": descriptor,
    }


def lw_balance(wallet_name: str = "default") -> dict[str, Any]:
    """
    Get wallet balance for all assets.
    
    Args:
        wallet_name: Name of the wallet. Default: "default"
        
    Returns:
        balances: List of asset balances
        wallet_name: Name of the wallet
    """
    manager = get_manager()
    balances = manager.get_balance(wallet_name)
    return {
        "wallet_name": wallet_name,
        "balances": [b.to_dict() for b in balances],
    }


def lw_address(
    wallet_name: str = "default",
    index: int | None = None,
) -> dict[str, Any]:
    """
    Generate a receive address.
    
    Args:
        wallet_name: Name of the wallet. Default: "default"
        index: Specific address index. Default: next unused
        
    Returns:
        address: The Liquid address
        index: Address index
    """
    manager = get_manager()
    addr = manager.get_address(wallet_name, index)
    return addr.to_dict()


def lw_transactions(
    wallet_name: str = "default",
    limit: int | None = 10,
) -> dict[str, Any]:
    """
    Get transaction history.
    
    Args:
        wallet_name: Name of the wallet. Default: "default"
        limit: Maximum number of transactions. Default: 10
        
    Returns:
        transactions: List of transactions
        count: Number of transactions returned
    """
    manager = get_manager()
    txs = manager.get_transactions(wallet_name, limit)
    return {
        "wallet_name": wallet_name,
        "transactions": [tx.to_dict() for tx in txs],
        "count": len(txs),
    }


def lw_send(
    wallet_name: str,
    address: str,
    amount: int,
    passphrase: str | None = None,
) -> dict[str, Any]:
    """
    Send L-BTC to an address.
    
    Args:
        wallet_name: Name of the wallet
        address: Destination Liquid address
        amount: Amount in satoshis
        passphrase: Passphrase to decrypt mnemonic (if encrypted)
        
    Returns:
        txid: Transaction ID
        amount: Amount sent
        address: Destination address
    """
    manager = get_manager()
    txid = manager.send(wallet_name, address, amount, passphrase=passphrase)
    return {
        "txid": txid,
        "amount": amount,
        "address": address,
    }


def lw_send_asset(
    wallet_name: str,
    address: str,
    amount: int,
    asset_id: str,
    passphrase: str | None = None,
) -> dict[str, Any]:
    """
    Send a Liquid asset to an address.
    
    Args:
        wallet_name: Name of the wallet
        address: Destination Liquid address
        amount: Amount in satoshis
        asset_id: Asset ID (hex string)
        passphrase: Passphrase to decrypt mnemonic (if encrypted)
        
    Returns:
        txid: Transaction ID
        amount: Amount sent
        asset_id: Asset sent
        address: Destination address
    """
    manager = get_manager()
    txid = manager.send(wallet_name, address, amount, asset_id, passphrase)
    ticker = resolve_asset_name(asset_id)
    return {
        "txid": txid,
        "amount": amount,
        "asset_id": asset_id,
        "ticker": ticker,
        "address": address,
    }


def lw_list_wallets() -> dict[str, Any]:
    """
    List all wallets.
    
    Returns:
        wallets: List of wallet names
        count: Number of wallets
    """
    manager = get_manager()
    wallets = manager.storage.list_wallets()
    return {
        "wallets": wallets,
        "count": len(wallets),
    }


# Tool registry for MCP
TOOLS = {
    "lw_generate_mnemonic": lw_generate_mnemonic,
    "lw_import_mnemonic": lw_import_mnemonic,
    "lw_import_descriptor": lw_import_descriptor,
    "lw_export_descriptor": lw_export_descriptor,
    "lw_balance": lw_balance,
    "lw_address": lw_address,
    "lw_transactions": lw_transactions,
    "lw_send": lw_send,
    "lw_send_asset": lw_send_asset,
    "lw_list_wallets": lw_list_wallets,
}
