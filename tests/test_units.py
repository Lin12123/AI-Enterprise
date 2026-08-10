import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from solidworks_api.units import mm_to_m


class TestUnits(unittest.TestCase):
    def test_tc_p0_010_mm_to_m_conversion(self):
        self.assertEqual(mm_to_m(1), 0.001)
        self.assertEqual(mm_to_m(10), 0.01)
        self.assertEqual(mm_to_m(120), 0.12)


if __name__ == "__main__":
    unittest.main()
