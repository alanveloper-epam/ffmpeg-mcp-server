# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-25

### Added
- Initial release of `ffmpeg-mcp-server`.
- Workspace path sandboxing (`resolve_workspace_path`) preventing path traversal and option-flag injection.
- Deterministic FFmpeg command builders for `probe_media`, `trim_clip`, `convert_aspect_ratio` (`9:16`, `1:1`, `16:9`, `4:5`), `extract_audio` (with optional EBU R128 `loudnorm`), `generate_srt`, and `burn_subtitles`.
- Built-in JSON-RPC 2.0 stdio MCP server (`ffmpeg-mcp-server`) with full `tools/list` and `tools/call` support.
- Comprehensive offline unit test suite (`tests/test_ffmpeg_mcp.py`).
