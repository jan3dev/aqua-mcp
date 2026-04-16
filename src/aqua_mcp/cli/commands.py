"""Register all CLI subcommand groups."""

import sys

import click

from ..tools import unified_balance
from .output import render, render_error


def register_commands(cli):
    """Register all subcommand groups and top-level commands on the root CLI group."""
    from .wallet import wallet
    from .liquid import liquid
    from .btc import btc
    from .lightning import lightning
    from .serve import serve

    cli.add_command(wallet)
    cli.add_command(liquid)
    cli.add_command(btc)
    cli.add_command(lightning)
    cli.add_command(serve)
    cli.add_command(balance)


@click.command("balance")
@click.option("--wallet-name", default="default", show_default=True, help="Name of the wallet.")
@click.pass_obj
def balance(ctx, wallet_name):
    """Get unified balance for both Bitcoin and Liquid networks."""
    try:
        result = unified_balance(wallet_name)
        click.echo(render(result, ctx.fmt))
    except Exception as e:
        click.echo(render_error(type(e).__name__, str(e), ctx.fmt), err=True)
        sys.exit(1)
