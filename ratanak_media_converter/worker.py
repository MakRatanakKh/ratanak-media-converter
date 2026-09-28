from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .ffmpeg import (
    MediaProbeError,
    build_ffmpeg_command,
    original_audio_extension,
    probe_audio,
    unique_output_path,
)


class ConversionWorker(QThread):
    file_started = Signal(int, str)
    file_info = Signal(int, str)
    file_progress = Signal(int, int)
    file_finished = Signal(int, bool, str, str)
    batch_finished = Signal(int, int, bool)

    def __init__(
        self,
        files: list[Path],
        mode: str,
        output_directory: Path | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.files = files
        self.mode = mode
        self.output_directory = output_directory
        self._cancel_requested = threading.Event()
        self._process: subprocess.Popen[str] | None = None
        self._process_lock = threading.Lock()

    def cancel(self) -> None:
        self._cancel_requested.set()
        with self._process_lock:
            process = self._process
        if process and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def _output_path(self, source: Path, codec: str) -> Path:
        output_dir = self.output_directory or source.parent
        suffix = ".mp3" if self.mode.startswith("mp3_") else original_audio_extension(codec)
        return unique_output_path(output_dir, source.stem, suffix)

    def run(self) -> None:
        completed = 0
        failed = 0

        for index, source in enumerate(self.files):
            if self._cancel_requested.is_set():
                break

            self.file_started.emit(index, source.name)

            try:
                info = probe_audio(source)
                self.file_info.emit(index, info.summary)
                output = self._output_path(source, info.codec)
                command = build_ffmpeg_command(
                    source,
                    output,
                    self.mode,
                    source_channels=info.channels,
                )
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=flags,
                )
                with self._process_lock:
                    self._process = process

                last_percent = -1
                assert process.stdout is not None
                for raw_line in process.stdout:
                    if self._cancel_requested.is_set():
                        try:
                            process.terminate()
                        except OSError:
                            pass
                        break

                    key, _, value = raw_line.strip().partition("=")
                    if key in {"out_time_ms", "out_time_us"} and info.duration:
                        try:
                            elapsed_seconds = int(value) / 1_000_000
                            percent = max(0, min(99, int(elapsed_seconds / info.duration * 100)))
                            if percent != last_percent:
                                last_percent = percent
                                self.file_progress.emit(index, percent)
                        except ValueError:
                            pass

                return_code = process.wait()
                stderr = process.stderr.read().strip() if process.stderr else ""
                with self._process_lock:
                    self._process = None

                if self._cancel_requested.is_set():
                    if output.exists():
                        try:
                            output.unlink()
                        except OSError:
                            pass
                    break

                if return_code == 0 and output.exists():
                    self.file_progress.emit(index, 100)
                    self.file_finished.emit(index, True, str(output), "")
                    completed += 1
                else:
                    if output.exists():
                        try:
                            output.unlink()
                        except OSError:
                            pass
                    error = stderr or f"FFmpeg exited with code {return_code}."
                    self.file_finished.emit(index, False, "", error)
                    failed += 1

            except (MediaProbeError, OSError, RuntimeError, ValueError) as exc:
                self.file_finished.emit(index, False, "", str(exc))
                failed += 1

        cancelled = self._cancel_requested.is_set()
        self.batch_finished.emit(completed, failed, cancelled)
