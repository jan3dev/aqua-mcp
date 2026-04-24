"""Shared pytest configuration.

Loads `.env` at the project root so tests can pick up SIGNER_MNEMONIC and
other credentials without manual exporting.
"""

from dotenv import load_dotenv

load_dotenv()
