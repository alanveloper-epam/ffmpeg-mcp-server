"""Offline unit test suite for ffmpeg-mcp-server."""

from __future__ import annotations

import json
import pytest

from ffmpeg_mcp_server.core import (
    SubtitleCue,
    WorkspaceSecurityError,
    build_aspect_ratio_command,
    build_burn_subtitles_command,
    build_extract_audio_command,
    build_probe_command,
    build_trim_command,
    format_srt,
    parse_timestamp,
    resolve_workspace_path,
)
from ffmpeg_mcp_server.server import FFmpegMCPServer


def test_resolve_workspace_path_blocks_traversal_and_flags(tmp_path):
    valid = resolve_workspace_path("clips/intro.mp4", tmp_path)
    assert valid == (tmp_path / "clips" / "intro.mp4").resolve()

    with pytest.raises(WorkspaceSecurityError, match="outside the allowed workspace"):
        resolve_workspace_path("../../etc/passwd", tmp_path)

    with pytest.raises(WorkspaceSecurityError, match="flag injection"):
        resolve_workspace_path("-f", tmp_path)

    with pytest.raises(WorkspaceSecurityError, match="protocols are not allowed"):
        resolve_workspace_path("https://example.com/video.mp4", tmp_path)


def test_parse_timestamp_supports_numeric_and_hhmmss():
    assert parse_timestamp(12.3456) == 12.346
    assert parse_timestamp("00:01:30.500") == 90.5
    assert parse_timestamp("02:15") == 135.0

    with pytest.raises(ValueError):
        parse_timestamp(-1)
    with pytest.raises(ValueError):
        parse_timestamp("invalid")


def test_format_srt_renders_valid_cues_and_rejects_bad_ranges():
    cues = [
        SubtitleCue(start=0.0, end=2.5, text="Hello MCP world!"),
        SubtitleCue(start=2.5, end=5.125, text="Second line\nwith wrap"),
    ]
    srt = format_srt(cues)
    assert "1\n00:00:00,000 --> 00:00:02,500\nHello MCP world!" in srt
    assert "2\n00:00:02,500 --> 00:00:05,125\nSecond line\nwith wrap" in srt

    with pytest.raises(ValueError, match="must be greater than start time"):
        format_srt([SubtitleCue(start=5.0, end=3.0, text="Invalid")])


def test_build_trim_and_aspect_ratio_commands(tmp_path):
    in_file = tmp_path / "in.mp4"
    out_file = tmp_path / "out.mp4"

    trim_cmd = build_trim_command(in_file, out_file, start_time="00:00:10", end_time="00:00:25.5")
    assert trim_cmd[:7] == ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "10.000"]
    assert "-t" in trim_cmd and "15.500" in trim_cmd

    aspect_cmd = build_aspect_ratio_command(in_file, out_file, aspect_ratio="9:16", mode="crop")
    assert "crop=1080:1920" in " ".join(aspect_cmd)


def test_build_extract_audio_and_burn_subtitles(tmp_path):
    in_file = tmp_path / "in.mp4"
    sub_file = tmp_path / "subs.srt"
    out_audio = tmp_path / "out.mp3"
    out_video = tmp_path / "subtitled.mp4"

    audio_cmd = build_extract_audio_command(in_file, out_audio, audio_format="mp3", normalize=True)
    assert "loudnorm=I=-16:TP=-1.5:LRA=11" in audio_cmd
    assert "libmp3lame" in audio_cmd

    burn_cmd = build_burn_subtitles_command(in_file, sub_file, out_video, font_size=28, margin_v=50)
    assert "FontSize=28" in " ".join(burn_cmd)

    probe_cmd = build_probe_command(in_file)
    assert probe_cmd[0] == "ffprobe"


def test_mcp_server_jsonrpc_and_dry_run_tools(tmp_path):
    server = FFmpegMCPServer(workdir=tmp_path)

    init_resp = server.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_resp["result"]["serverInfo"]["name"] == "ffmpeg-mcp-server"

    list_resp = server.handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tool_names = {t["name"] for t in list_resp["result"]["tools"]}
    assert {
        "probe_media",
        "trim_clip",
        "convert_aspect_ratio",
        "extract_audio",
        "generate_srt",
        "burn_subtitles",
    } <= tool_names

    # Generate an SRT file inside the sandbox
    srt_resp = server.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "generate_srt",
                "arguments": {
                    "output_path": "captions.srt",
                    "cues": [{"start": 0, "end": 1.5, "text": "Fast cut intro"}],
                },
            },
        }
    )
    assert not srt_resp["result"]["isError"]
    assert (tmp_path / "captions.srt").exists()

    # Dry-run trim_clip
    trim_resp = server.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "trim_clip",
                "arguments": {
                    "input_path": "raw.mp4",
                    "output_path": "short.mp4",
                    "start_time": 2.0,
                    "duration": 10.0,
                    "dry_run": True,
                },
            },
        }
    )
    payload = json.loads(trim_resp["result"]["content"][0]["text"])
    assert payload["status"] == "dry_run"
    assert payload["command"][0] == "ffmpeg"
