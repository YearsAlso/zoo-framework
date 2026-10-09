"""The entry point of ``python -m zoo_framework``.

The CLI implementation lives in `zoo_framework.cli`. This forwards, keeping
the historical module-style entry working - its existence does not affect
`zoo_framework.cli` being the single implementation location.
"""

from zoo_framework.cli import zfc

if __name__ == "__main__":
    zfc()
