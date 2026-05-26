# cli_app.py
import typer

cli = typer.Typer()

def register_cli(config):
    func = config["func"]
    cli.command()(func)