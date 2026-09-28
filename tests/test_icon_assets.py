import tempfile
import unittest
from pathlib import Path

from ratanak_media_converter.icon_data import icon_png_bytes, write_icon_files


class IconAssetTests(unittest.TestCase):
    def test_embedded_png_and_generated_ico(self):
        png = icon_png_bytes()
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

        with tempfile.TemporaryDirectory() as temporary:
            png_path, ico_path = write_icon_files(Path(temporary))

            self.assertTrue(png_path.is_file())
            self.assertTrue(ico_path.is_file())
            self.assertEqual(png_path.read_bytes(), png)

            ico = ico_path.read_bytes()
            self.assertEqual(ico[:6], b"\x00\x00\x01\x00\x01\x00")
            self.assertIn(b"PNG", ico[:64])


if __name__ == "__main__":
    unittest.main()
