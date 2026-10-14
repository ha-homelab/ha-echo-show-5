"""Replay only synthetic corpus bytes through the real bounded oracle."""

import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
oracle = importlib.import_module("fuzz.oracles").intercom_boundaries
decode_pcm = importlib.import_module("lease").decode_pcm


class FuzzOracleTest(unittest.TestCase):
    def test_positive_pcm_seed_reaches_valid_decode(self):
        seed = (ROOT / "fuzz/corpus/intercom-boundaries/pcm.txt").read_bytes()
        self.assertEqual(decode_pcm(seed.decode("ascii")), b"\0" * 1764)

    def test_synthetic_corpus(self):
        for seed in sorted((ROOT / "fuzz/corpus/intercom-boundaries").iterdir()):
            with self.subTest(seed=seed.name):
                oracle(seed.read_bytes())

    def test_empty_malformed_and_bounded_noise(self):
        for data in (b"", b"{", b"null", b"[]", bytes(range(256)) * 16):
            oracle(data)
