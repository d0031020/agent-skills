"""Keep pytest scratch data and bytecode within the package boundary."""

import sys
from pathlib import Path


sys.dont_write_bytecode = True


def pytest_configure(config):
    if config.option.basetemp is None:
        config.option.basetemp = str(Path(__file__).resolve().parent / ".tmp")
