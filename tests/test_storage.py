"""Tests for storage module."""

import tempfile
from pathlib import Path

import pytest

from liquid_wallet.storage import Storage, WalletData, Config


@pytest.fixture
def temp_storage():
    """Create a temporary storage instance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Storage(Path(tmpdir))


class TestStorage:
    """Tests for Storage class."""

    def test_init_creates_directories(self, temp_storage):
        """Test that initialization creates required directories."""
        assert temp_storage.base_dir.exists()
        assert temp_storage.wallets_dir.exists()
        assert temp_storage.cache_dir.exists()

    def test_config_save_load(self, temp_storage):
        """Test saving and loading config."""
        config = Config(network="testnet", default_wallet="test")
        temp_storage.save_config(config)
        
        loaded = temp_storage.load_config()
        assert loaded.network == "testnet"
        assert loaded.default_wallet == "test"

    def test_wallet_save_load(self, temp_storage):
        """Test saving and loading wallet."""
        wallet = WalletData(
            name="test",
            network="mainnet",
            descriptor="ct(...)",
        )
        temp_storage.save_wallet(wallet)
        
        assert temp_storage.wallet_exists("test")
        
        loaded = temp_storage.load_wallet("test")
        assert loaded.name == "test"
        assert loaded.network == "mainnet"
        assert loaded.descriptor == "ct(...)"

    def test_list_wallets(self, temp_storage):
        """Test listing wallets."""
        assert temp_storage.list_wallets() == []
        
        wallet1 = WalletData(name="w1", network="mainnet", descriptor="ct1")
        wallet2 = WalletData(name="w2", network="testnet", descriptor="ct2")
        temp_storage.save_wallet(wallet1)
        temp_storage.save_wallet(wallet2)
        
        wallets = temp_storage.list_wallets()
        assert set(wallets) == {"w1", "w2"}

    def test_delete_wallet(self, temp_storage):
        """Test deleting wallet."""
        wallet = WalletData(name="todelete", network="mainnet", descriptor="ct")
        temp_storage.save_wallet(wallet)
        
        assert temp_storage.wallet_exists("todelete")
        assert temp_storage.delete_wallet("todelete")
        assert not temp_storage.wallet_exists("todelete")

    def test_mnemonic_encryption(self, temp_storage):
        """Test mnemonic encryption/decryption."""
        mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        passphrase = "test123"
        
        encrypted = temp_storage.encrypt_mnemonic(mnemonic, passphrase)
        assert encrypted != mnemonic
        
        decrypted = temp_storage.decrypt_mnemonic(encrypted, passphrase)
        assert decrypted == mnemonic

    def test_mnemonic_wrong_passphrase(self, temp_storage):
        """Test that wrong passphrase fails."""
        mnemonic = "test mnemonic"
        encrypted = temp_storage.encrypt_mnemonic(mnemonic, "correct")
        
        with pytest.raises(Exception):
            temp_storage.decrypt_mnemonic(encrypted, "wrong")
