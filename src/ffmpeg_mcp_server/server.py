"""JSON-RPC 2.0 stdio MCP server and tool dispatcher for ffmpeg-mcp-server."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .core import (
    SubtitleCue,
    build_aspect_ratio_command,
    build_burn_subtitles_command,
    build_extract_audio_command,
    build_probe_command,
    build_trim_command,
    format_srt,
    resolve_workspace_path,
)

TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "probe_media",
        "description": "Inspect media container duration, resolution, codecs, and streams via ffprobe.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "Path to media file inside workspace."},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["input_path"],
        },
    },
    {
        "name": "trim_clip",
        "description": "Trim a video or audio clip between start_time and end_time/duration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "output_path": {"type": "string"},
                "start_time": {"type": ["string", "number"], "default": 0},
                "end_time": {"type": ["string", "number"]},
                "duration": {"type": ["string", "number"]},
                "reencode": {"type": "boolean", "default": True},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["input_path", "output_path"],
        },
    },
    {
        "name": "convert_aspect_ratio",
        "description": "Reframe a video to 9:16, 1:1, 16:9, or 4:5 using crop or pad mode.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "output_path": {"type": "string"},
                "aspect_ratio": {"type": "string", "enum": ["9:16", "1:1", "16:9", "4:5"], "default": "9:16"},
                "mode": {"type": "string", "enum": ["crop", "pad"], "default": "crop"},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["input_path", "output_path"],
        },
    },
    {
        "name": "extract_audio",
        "description": "Extract audio track from media file into mp3, wav, flac, or m4a.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "output_path": {"type": "string"},
                "audio_format": {"type": "string", "enum": ["mp3", "wav", "flac", "m4a"], "default": "mp3"},
                "normalize": {"type": "boolean", "default": False},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["input_path", "output_path"],
        },
    },
    {
        "name": "generate_srt",
        "description": "Generate a validated .srt subtitle file inside the workspace from structured cues.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_path": {"type": "string"},
                "cues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "number"},
                            "end": {"type": "number"},
                            "text": {"type": "string"},
                        },
                        "required": ["start", "end", "text"],
                    },
                },
            },
            "required": ["output_path", "cues"],
        },
    },
    {
        "name": "burn_subtitles",
        "description": "Burn an .srt subtitle file into a video with customizable font size and vertical margin.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "subtitle_path": {"type": "string"},
                "output_path": {"type": "string"},
                "font_size": {"type": "integer", "default": 22},
                "margin_v": {"type": "integer", "default": 40},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["input_path", "subtitle_path", "output_path"],
        },
    },
]


class FFmpegMCPServer:
    """Sandboxed MCP tool dispatcher and JSON-RPC 2.0 stdio handler."""

    def __init__(self, workdir: Optional[str | Path] = None) -> None:
        env_dir = os.environ.get("FFMPEG_MCP_WORKDIR")
        self.workdir = Path(workdir or env_dir or os.getcwd()).expanduser().resolve()

    def _run_command(self, argv: List[str], *, dry_run: bool = False) -> Dict[str, Any]:
        if dry_run:
            return {"status": "dry_run", "command": argv}
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"Command failed (exit {proc.returncode}): {proc.stderr.strip()}")
        return {
            "status": "ok",
            "command": argv,
            "stdout": proc.stdout.strip(),
        }

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch an MCP tool call inside the configured workspace."""
        dry_run = bool(arguments.get("dry_run", False))
        must_exist = not dry_run

        if name == "probe_media":
            in_path = resolve_workspace_path(arguments["input_path"], self.workdir, must_exist=must_exist)
            cmd = build_probe_command(in_path)
            res = self._run_command(cmd, dry_run=dry_run)
            if not dry_run and res.get("stdout"):
                res["probe"] = json.loads(res.pop("stdout"))
            return res

        if name == "trim_clip":
            in_path = resolve_workspace_path(arguments["input_path"], self.workdir, must_exist=must_exist)
            out_path = resolve_workspace_path(arguments["output_path"], self.workdir, must_exist=False)
            cmd = build_trim_command(
                in_path,
                out_path,
                start_time=arguments.get("start_time", 0.0),
                end_time=arguments.get("end_time"),
                duration=arguments.get("duration"),
                reencode=bool(arguments.get("reencode", True)),
            )
            return self._run_command(cmd, dry_run=dry_run)

        if name == "convert_aspect_ratio":
            in_path = resolve_workspace_path(arguments["input_path"], self.workdir, must_exist=must_exist)
            out_path = resolve_workspace_path(arguments["output_path"], self.workdir, must_exist=False)
            cmd = build_aspect_ratio_command(
                in_path,
                out_path,
                aspect_ratio=arguments.get("aspect_ratio", "9:16"),
                mode=arguments.get("mode", "crop"),
            )
            return self._run_command(cmd, dry_run=dry_run)

        if name == "extract_audio":
            in_path = resolve_workspace_path(arguments["input_path"], self.workdir, must_exist=must_exist)
            out_path = resolve_workspace_path(arguments["output_path"], self.workdir, must_exist=False)
            cmd = build_extract_audio_command(
                in_path,
                out_path,
                audio_format=arguments.get("audio_format", "mp3"),
                normalize=bool(arguments.get("normalize", False)),
            )
            return self._run_command(cmd, dry_run=dry_run)

        if name == "generate_srt":
            out_path = resolve_workspace_path(arguments["output_path"], self.workdir, must_exist=False)
            raw_cues = arguments.get("cues") or []
            cues = [
                SubtitleCue(start=c["start"], end=c["end"], text=c["text"])
                for c in raw_cues
            ]
            srt_content = format_srt(cues)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(srt_content, encoding="utf-8")
            return {
                "status": "ok",
                "output_path": str(out_path),
                "cues_written": len(cues),
                "srt_preview": srt_content,
            }

        if name == "burn_subtitles":
            in_path = resolve_workspace_path(arguments["input_path"], self.workdir, must_exist=must_exist)
            sub_path = resolve_workspace_path(arguments["subtitle_path"], self.workdir, must_exist=must_exist)
            out_path = resolve_workspace_path(arguments["output_path"], self.workdir, must_exist=False)
            cmd = build_burn_subtitles_command(
                in_path,
                sub_path,
                out_path,
                font_size=int(arguments.get("font_size", 22)),
                margin_v=int(arguments.get("margin_v", 40)),
            )
            return self._run_command(cmd, dry_run=dry_run)

        raise ValueError(f"Unknown tool: {name}")

    def handle_jsonrpc(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single JSON-RPC 2.0 request and return a response dict (or None for notifications)."""
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params") or {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "ffmpeg-mcp-server", "version": __version__},
                },
            }

        if method.startswith("notifications/"):
            return None

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS_SCHEMA},
            }

        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments") or {}
            try:
                result = self.call_tool(tool_name, tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                        "isError": False,
                    },
                }
            except Exception as exc:  # noqa: BLE001
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {exc}"}],
                        "isError": True,
                    },
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    def serve_stdio(self) -> None:
        """Run the JSON-RPC 2.0 stdio loop."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue
            resp = self.handle_jsonrpc(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
