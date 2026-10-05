import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from analysis import kitagawa, two_prop_ztest  # noqa: E402
from generate_data import generate  # noqa: E402


class TestStats(unittest.TestCase):
    def test_ztest_matches_textbook(self):
        # 200/1000 vs 150/1000 -> pooled p=0.175, SE=0.01699 -> z=2.9424
        r = two_prop_ztest(200, 1000, 150, 1000)
        self.assertAlmostEqual(r["diff"], 0.05)
        self.assertAlmostEqual(r["z"], 2.9424, places=3)
        self.assertLess(r["p_value"], 0.01)
        self.assertTrue(r["ci"][0] < 0.05 < r["ci"][1])

    def test_kitagawa_sums_to_total(self):
        rng = np.random.default_rng(0)
        b = pd.DataFrame({"user_id": range(1000), "g": rng.choice(list("ab"), 1000, p=[.7, .3]),
                          "retained_d7": rng.random(1000) < .3})
        a = pd.DataFrame({"user_id": range(800), "g": rng.choice(list("ab"), 800, p=[.4, .6]),
                          "retained_d7": rng.random(800) < .25})
        k = kitagawa(b, a, a.retained_d7.astype(float).to_numpy(), by="g")
        total = a.retained_d7.mean() - b.retained_d7.mean()
        self.assertAlmostEqual(k["mix"] + k["rate"], total, places=10)


class TestGenerator(unittest.TestCase):
    def test_reproducible_and_consistent(self):
        u1, e1 = generate(2000, seed=7)
        u2, e2 = generate(2000, seed=7)
        pd.testing.assert_frame_equal(u1, u2)
        self.assertEqual(len(e1), len(e2))
        self.assertTrue(set(e1.user_id) <= set(u1.user_id))
        # funnel is monotone: nobody orders without confirming an address
        steps = e1[e1.event_name != "session"].groupby("event_name").user_id.nunique()
        self.assertGreaterEqual(steps["address_confirmed"], steps["payment_added"])
        self.assertGreaterEqual(steps["payment_added"], steps["first_order"])


if __name__ == "__main__":
    unittest.main()
