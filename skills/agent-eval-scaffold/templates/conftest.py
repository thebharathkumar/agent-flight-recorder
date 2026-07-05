"""Determinism pinning for the eval suite. Do not add test logic here."""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

# make the target repo importable from evals/ regardless of invocation dir
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("EVAL_SEED", "0")
random.seed(int(os.environ["EVAL_SEED"]))

try:
    import numpy

    numpy.random.seed(int(os.environ["EVAL_SEED"]))
except ImportError:
    pass


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        help="rewrite golden files from current agent output",
    )
