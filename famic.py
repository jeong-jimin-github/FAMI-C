#!/usr/bin/env python3
"""FAMI-C entry point.

The compiler itself lives in the `famic/` package, one module per concern, so
an agent can open only the part it needs to change.  This file just forwards.
"""

import sys

from famic.cli import main

if __name__ == "__main__":
    sys.exit(main())
