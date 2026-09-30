"""stablematch: 稳定婚姻配对库。"""

from stablematch.core import (
    Erro,
    InvalidInput,
    UnstableMatching,
    all_stable,
    enumerate_pairings,
    first_unstable,
    instabilities,
    normalise,
    stable_pairing,
)

__all__ = [
    "Erro",
    "InvalidInput",
    "UnstableMatching",
    "all_stable",
    "enumerate_pairings",
    "first_unstable",
    "instabilities",
    "normalise",
    "stable_pairing",
]
