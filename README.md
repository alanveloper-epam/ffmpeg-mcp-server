# ffmpeg-mcp-server 🎬

[![CI](https://github.com/alanveloper-epam/ffmpeg-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/alanveloper-epam/ffmpeg-mcp-server/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Stdio%20%26%20JSON--RPC-green.svg)](https://modelcontextprotocol.io)

**`ffmpeg-mcp-server`** is a deterministic, security-hardened **Model Context Protocol (MCP)** server that gives AI coding agents (Claude Code, Cursor, Windsurf, Cline, Gemini) safe, structured tools for inspecting, trimming, reframing (9:16 vertical shorts), extracting audio, and burning dynamic subtitles into video and audio files via `ffmpeg` and `ffprobe`.

Unlike raw shell-execution wrappers that expose agents to command injection or destructive path traversal, `ffmpeg-mcp-server` enforces **workspace sandboxing**, **strict argument validation**, **argument-list subprocess execution (`shell=False`)**, and **dry-run command inspection**.

---

## ✨ Key Features

- **🔒 Sandboxed Workspace Security:** Confines all input/output media operations to an explicit allowed root directory (`FFMPEG_MCP_WORKDIR`), blocking path traversal (`..`) and symlink escapes.
- **📊 Structured Media Probing (`probe_media`):** Extracts duration, resolution, codec, FPS, bitrates, and audio stream metadata via `ffprobe` in clean JSON.
- **✂️ Frame-Accurate Clip Trimming (`trim_clip`):** Cuts segments with millisecond-accurate timestamps (`HH:MM:SS.mmm` or seconds) and configurable stream copy or H.264/AAC re-encoding.
- **📱 Vertical 9:16 Reframing (`convert_aspect_ratio`):** Automatically computes center-crop or blurred-pad filtergraphs for TikTok, Reels, and YouTube Shorts (`9:16`, `1:1`, `16:9`, `4:5`).
- **💬 Deterministic SRT Generator & Subtitle Burn-In (`generate_srt`, `burn_subtitles`):** Creates valid `.srt` subtitle files from structured cue arrays and burns them into video with customizable font size and margin styling.
- **🎵 Audio Extraction & Normalization (`extract_audio`):** Extracts clean `mp3`, `wav`, `flac`, or `m4a` tracks with optional EBU R128 loudness normalization (`loudnorm`).
- **🧪 Zero-Dependency Core & Dry-Run Mode:** Built on the Python standard library with a compliant JSON-RPC 2.0 stdio MCP transport, plus `dry_run=True` support on every mutative tool so agents can preview exact `ffmpeg` argv arrays before execution.

---

## 🚀 Quick Start

### Prerequisites
- Python **3.10+**
- `ffmpeg` and `ffprobe` installed on your system `PATH` (`sudo apt install ffmpeg` or `brew install ffmpeg`).

### Installation

```bash
pip install -e ".[dev]"
```

### Claude Code / Claude Desktop Configuration

Add `ffmpeg-mcp-server` to your `claude_desktop_config.json` or `.mcp.json`:

```json
{
  "mcpServers": {
    "ffmpeg": {
      "command": "ffmpeg-mcp-server",
      "env": {
        "FFMPEG_MCP_WORKDIR": "/path/to/your/media/workspace"
      }
    }
  }
}
```

Or add it directly in Claude Code CLI:

```bash
claude mcp add ffmpeg -- ffmpeg-mcp-server --workdir /path/to/your/media/workspace
```

---

## 🛠️ Available MCP Tools

| Tool Name | Description | Supports `dry_run` |
|---|---|---|
| `probe_media` | Inspect container duration, streams, resolution, FPS, and codecs via `ffprobe`. | Yes |
| `trim_clip` | Cut a media segment between `start_time` and `end_time` or `duration`. | Yes |
| `convert_aspect_ratio` | Reframe video to `9:16`, `1:1`, `16:9`, or `4:5` using `crop` or `pad` mode. | Yes |
| `extract_audio` | Extract audio stream to `mp3`, `wav`, `flac`, or `m4a` with optional `loudnorm`. | Yes |
| `generate_srt` | Build a validated `.srt` subtitle file from a list of `{start, end, text}` cues. | No (Pure file/string) |
| `burn_subtitles` | Burn an `.srt` file into a video with custom font size and alignment. | Yes |

---

## 🧪 Running Tests

All unit tests run offline without requiring media fixtures or external network calls:

```bash
pytest -q
ruff check .
```

---

## 🤝 Contributing & Security

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and pull request guidelines, and [SECURITY.md](SECURITY.md) for our security policy and sandboxing invariants.

## 📄 License

Licensed under the [MIT License](LICENSE).
