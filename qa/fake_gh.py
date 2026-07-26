#!/usr/bin/env python3
"""Network-disabled gh stand-in placed first on PATH during live evals."""

import sys

print("gh is disabled in the network-isolated live-eval sandbox", file=sys.stderr)
raise SystemExit(69)
