"""Keep pytest scratch files inside the package."""

from pathlib import Path


def pytest_configure(config):
    config.option.basetemp = str(Path(__file__).resolve().parent / ".tmp")
