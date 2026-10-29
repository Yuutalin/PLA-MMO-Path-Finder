import tempfile
import unittest
from pathlib import Path

from pla_mmo.seed_reader import read_seed_file, validate_seed


class SeedReaderTests(unittest.TestCase):
    def test_accepts_decimal_seed_and_preserves_text(self):
        self.assertEqual(validate_seed(" 001234 \n"), "001234")

    def test_rejects_hex_and_mixed_text(self):
        for value in ("0x1234", "-1", "12abc", "", "123\n456"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_seed(value)

    def test_large_integer_text_is_not_converted_to_float(self):
        value = "9" * 100
        self.assertEqual(validate_seed(value), value)

    def test_reads_utf8_txt(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "seed.txt"
            path.write_text("987654321\n", encoding="utf-8")
            result = read_seed_file(str(path))
            self.assertEqual(result["seed"], "987654321")
            self.assertEqual(result["path"], str(path.resolve()))

    def test_empty_and_missing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "empty.txt"
            path.write_text("  \n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_seed_file(str(path))
            with self.assertRaises(ValueError):
                read_seed_file(str(Path(temp) / "missing.txt"))


if __name__ == "__main__":
    unittest.main()
