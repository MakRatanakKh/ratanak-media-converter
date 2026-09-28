# Ratanak Media Converter

A Windows 11 batch media converter built with **Python + PySide6 + FFmpeg**.

Drag multiple videos into the app, choose an audio mode, and let the queue run one file at a time. When the batch finishes, the app sends a Windows notification.

## Current features

- Drag-and-drop multiple local media files
- Mixed input formats in one queue
- Sequential batch processing
- **High Quality MP3 · VBR V0** as the recommended default
- Optional **320 kbps MP3**
- **Original Audio** mode using stream copy with no re-encoding
- FFprobe source-audio inspection
- Per-file and overall progress
- Cancel an active batch
- Failed files do not stop the rest of the queue
- Same-folder or custom-folder output
- Existing files are never overwritten; a numbered filename is created instead
- Open-output-folder shortcut
- Windows completion notification
- Saved quality/output preferences between app launches
- Restored window size and position
- Clear-completed action for finished batches
- Vibrant pink branded icon in the app window, taskbar, and packaged Windows executable

## Audio quality

### High Quality MP3 · VBR V0

The recommended MP3 mode uses `libmp3lame -q:a 0`. The app does not force a sample rate or channel count, so FFmpeg keeps the source values whenever possible.

Converting AAC, Opus, AC3, or another lossy source to MP3 still requires a new lossy encode. A 320 kbps MP3 cannot restore detail that was not present in the source. Because MP3 supports at most two channels, 5.1/7.1 sources are automatically downmixed to stereo in MP3 modes; Original Audio mode preserves the source channel layout.

### Maximum Bitrate MP3 · 320 kbps

Uses `libmp3lame -b:a 320k` for users who specifically prefer 320 kbps MP3 output.

### Original Audio · no re-encoding

Uses `-c:a copy`. This is the true no-generational-loss option because the source audio packets are copied instead of encoded again.

Common mappings are MP3 → `.mp3`, AAC/ALAC → `.m4a`, Opus → `.opus`, Vorbis → `.ogg`, FLAC → `.flac`, PCM → `.wav`, with `.mka` as a safe fallback for uncommon codecs.

## Requirements

- Windows 11 recommended
- Python 3.11 or newer
- PySide6
- FFmpeg and FFprobe

## Run from Python

1. Clone the repository and enter the folder.
2. Create and activate a virtual environment.
3. Run `pip install -r requirements.txt`.
4. Make `ffmpeg` and `ffprobe` available either on PATH or under `vendor/ffmpeg/bin/`.
5. Run `python main.py`.

The optional `RMC_FFMPEG_DIR` environment variable can point directly to a folder containing both FFmpeg executables.

## Build a Windows EXE

Put `ffmpeg.exe` and `ffprobe.exe` under `vendor/ffmpeg/bin/`, install `requirements-build.txt`, then run `./build_windows.ps1` from PowerShell.

The PyInstaller build bundles Python, PySide6, FFmpeg, FFprobe, and the application icon so the resulting Windows application does not require a separate Python installation.

The repository also contains a **Windows Build** GitHub Actions workflow. Every push to `main` produces a downloadable `RatanakMediaConverter-Windows` workflow artifact for testing.

## Input formats

FFmpeg supports a very large range of media containers/codecs. The file picker highlights common formats including MP4, MKV, MOV, AVI, WEBM, M4V, MPEG, MPG, TS, MTS, M2TS, WMV, FLV, 3GP, OGV, and VOB.

The drag-and-drop area accepts any local file. FFprobe validates it when processing begins. Files without a readable audio stream are marked **Failed** and the queue continues.

## Testing

Run all tests with:

`python -m unittest discover -s tests -v`

The Windows CI workflow includes real FFmpeg integration coverage. It creates a short synthetic MP4 with AAC audio, converts it to VBR V0 MP3, verifies codec/sample-rate/channel behavior, and separately verifies the original-audio stream-copy path.

## Current scope

Version `0.2.1` converts/extracts the **first audio stream** from each input.

Likely next improvements include audio-track selection for files with multiple tracks, richer source metadata, installer packaging, Windows version metadata, and additional audio output formats.
