from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


class FFmpegNotFoundError(RuntimeError):
    pass


class MediaProbeError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioInfo:
    codec: str
    bitrate: int | None
    sample_rate: int | None
    channels: int | None
    duration: float | None

    @property
    def summary(self) -> str:
        parts = [self.codec.upper()]
        if self.bitrate:
            parts.append(f"{round(self.bitrate / 1000)} kbps")
        if self.sample_rate:
            parts.append(f"{self.sample_rate / 1000:g} kHz")
        if self.channels:
            parts.append(f"{self.channels} ch")
        return " · ".join(parts)


def _candidate_dirs() -> list[Path]:
    candidates: list[Path] = []

    configured = os.environ.get("RMC_FFMPEG_DIR")
    if configured:
        candidates.append(Path(configured))

    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parents[1]

    candidates.extend(
        [
            app_dir,
            app_dir / "ffmpeg",
            app_dir / "ffmpeg" / "bin",
            app_dir / "vendor" / "ffmpeg" / "bin",
        ]
    )

    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        bundle = Path(bundle_dir)
        candidates.extend([bundle, bundle / "ffmpeg", bundle / "ffmpeg" / "bin"])

    unique: list[Path] = []
    seen: set[str] = set()
    for item in candidates:
        key = str(item).lower()
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return unique


def find_binary(name: str) -> Path:
    executable = f"{name}.exe" if os.name == "nt" else name

    for directory in _candidate_dirs():
        path = directory / executable
        if path.is_file():
            return path

    from_path = shutil.which(name) or shutil.which(executable)
    if from_path:
        return Path(from_path)

    raise FFmpegNotFoundError(
        f"Could not find {executable}. Install FFmpeg and add its bin folder to PATH, "
        "or place ffmpeg/ffprobe in vendor/ffmpeg/bin."
    )


def probe_audio(path: Path) -> AudioInfo:
    import subprocess

    ffprobe = find_binary("ffprobe")
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_name,bit_rate,channels,sample_rate,duration:format=duration",
        "-of",
        "json",
        str(path),
    ]

    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or "FFprobe could not read this file."
        raise MediaProbeError(message)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError("FFprobe returned invalid metadata.") from exc

    streams = payload.get("streams") or []
    if not streams:
        raise MediaProbeError("No audio stream was found in this file.")

    stream = streams[0]
    codec = stream.get("codec_name") or "unknown"

    def to_int(value: object) -> int | None:
        try:
            return int(value) if value not in (None, "", "N/A") else None
        except (TypeError, ValueError):
            return None

    def to_float(value: object) -> float | None:
        try:
            return float(value) if value not in (None, "", "N/A") else None
        except (TypeError, ValueError):
            return None

    duration = to_float(stream.get("duration"))
    if duration is None:
        duration = to_float((payload.get("format") or {}).get("duration"))

    return AudioInfo(
        codec=codec,
        bitrate=to_int(stream.get("bit_rate")),
        sample_rate=to_int(stream.get("sample_rate")),
        channels=to_int(stream.get("channels")),
        duration=duration,
    )


def original_audio_extension(codec: str) -> str:
    codec = codec.lower()
    if codec == "mp3":
        return ".mp3"
    if codec in {"aac", "alac"}:
        return ".m4a"
    if codec == "opus":
        return ".opus"
    if codec == "vorbis":
        return ".ogg"
    if codec == "flac":
        return ".flac"
    if codec == "wavpack":
        return ".wv"
    if codec == "ac3":
        return ".ac3"
    if codec == "eac3":
        return ".eac3"
    if codec in {"dts", "dca"}:
        return ".dts"
    if codec.startswith("pcm_"):
        return ".wav"
    return ".mka"


def unique_output_path(directory: Path, stem: str, suffix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


def build_ffmpeg_command(
    input_path: Path,
    output_path: Path,
    mode: str,
    source_channels: int | None = None,
) -> list[str]:
    ffmpeg = find_binary("ffmpeg")
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-n",
        "-i",
        str(input_path),
        "-map",
        "0:a:0",
        "-vn",
    ]

    if mode == "original":
        command.extend(["-c:a", "copy"])
    elif mode == "mp3_v0":
        command.extend(["-c:a", "libmp3lame", "-q:a", "0"])
        if source_channels and source_channels > 2:
            command.extend(["-ac", "2"])
    elif mode == "mp3_320":
        command.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
        if source_channels and source_channels > 2:
            command.extend(["-ac", "2"])
    else:
        raise ValueError(f"Unknown conversion mode: {mode}")

    command.extend(["-progress", "pipe:1", "-nostats", str(output_path)])
    return command
