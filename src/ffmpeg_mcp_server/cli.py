"""Command-line entrypoint for ffmpeg-mcp-server."""

from __future__ import annotations

import argparse
from typing import Optional, Sequence

from . import __version__
from .server import FFmpegMCPServer


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ffmpeg-mcp-server",
        description="Deterministic Model Context Protocol (MCP) server for FFmpeg workflows.",
    )
    parser.add_argument(
        "--workdir",
        default=None,
        help="Root directory confining all input and output media operations.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ffmpeg-mcp-server {__version__}",
    )
    args = parser.parse_args(argv)
    server = FFmpegMCPServer(workdir=args.workdir)
    server.serve_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
