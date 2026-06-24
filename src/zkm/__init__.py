"""zkm — ze knowledge manager."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("zkm")
except PackageNotFoundError:  # running from a source tree with no install
    __version__ = "0.0.0+dev"
