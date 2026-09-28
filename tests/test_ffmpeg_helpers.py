import tempfile
import unittest
from pathlib import Path

from ratanak_media_converter.ffmpeg import original_audio_extension, unique_output_path


class FFmpegHelperTests(unittest.TestCase):
    def test_original_audio_extension(self):
        self.assertEqual(original_audio_extension("aac"), ".m4a")
        self.assertEqual(original_audio_extension("opus"), ".opus")
        self.assertEqual(original_audio_extension("flac"), ".flac")
        self.assertEqual(original_audio_extension("pcm_s16le"), ".wav")
        self.assertEqual(original_audio_extension("something_new"), ".mka")

    def test_unique_output_path_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "clip.mp3").write_bytes(b"existing")
            result = unique_output_path(folder, "clip", ".mp3")
            self.assertEqual(result.name, "clip (1).mp3")


if __name__ == "__main__":
    unittest.main()
