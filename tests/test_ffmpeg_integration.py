import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from ratanak_media_converter.ffmpeg import (
    build_ffmpeg_command,
    find_binary,
    probe_audio,
)


class FFmpegIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.ffmpeg = find_binary("ffmpeg")
            cls.ffprobe = find_binary("ffprobe")
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

    def run_command(self, command):
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [str(part) for part in command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout or f"Command failed: {command}")
        return result

    def create_source(self, folder: Path) -> Path:
        source = folder / "source.mp4"
        self.run_command(
            [
                self.ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=320x240:r=25:d=1.2",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=1000:sample_rate=44100:duration=1.2",
                "-shortest",
                "-c:v",
                "mpeg4",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ac",
                "2",
                str(source),
            ]
        )
        return source

    def create_multichannel_source(self, folder: Path) -> Path:
        source = folder / "source-5.1.mp4"
        self.run_command(
            [
                self.ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=320x240:r=25:d=1.2",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=5.1:sample_rate=48000",
                "-t",
                "1.2",
                "-c:v",
                "mpeg4",
                "-c:a",
                "aac",
                "-b:a",
                "384k",
                str(source),
            ]
        )
        return source

    def test_mp3_v0_preserves_sample_rate_and_channels(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = self.create_source(folder)
            source_info = probe_audio(source)

            self.assertEqual(source_info.codec, "aac")
            self.assertEqual(source_info.sample_rate, 44100)
            self.assertEqual(source_info.channels, 2)

            output = folder / "output.mp3"
            self.run_command(
                build_ffmpeg_command(
                    source,
                    output,
                    "mp3_v0",
                    source_channels=source_info.channels,
                )
            )

            output_info = probe_audio(output)
            self.assertEqual(output_info.codec, "mp3")
            self.assertEqual(output_info.sample_rate, source_info.sample_rate)
            self.assertEqual(output_info.channels, source_info.channels)

    def test_mp3_v0_downmixes_multichannel_audio_to_stereo(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = self.create_multichannel_source(folder)
            source_info = probe_audio(source)

            self.assertEqual(source_info.codec, "aac")
            self.assertEqual(source_info.sample_rate, 48000)
            self.assertEqual(source_info.channels, 6)

            output = folder / "output-stereo.mp3"
            self.run_command(
                build_ffmpeg_command(
                    source,
                    output,
                    "mp3_v0",
                    source_channels=source_info.channels,
                )
            )

            output_info = probe_audio(output)
            self.assertEqual(output_info.codec, "mp3")
            self.assertEqual(output_info.channels, 2)

    def test_original_mode_stream_copies_aac(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = self.create_source(folder)
            source_info = probe_audio(source)

            output = folder / "output.m4a"
            self.run_command(
                build_ffmpeg_command(
                    source,
                    output,
                    "original",
                    source_channels=source_info.channels,
                )
            )

            output_info = probe_audio(output)
            self.assertEqual(output_info.codec, source_info.codec)
            self.assertEqual(output_info.sample_rate, source_info.sample_rate)
            self.assertEqual(output_info.channels, source_info.channels)


if __name__ == "__main__":
    unittest.main()
