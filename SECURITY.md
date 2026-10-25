# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Invariants

`ffmpeg-mcp-server` is designed to be invoked by autonomous AI coding and media agents. To prevent command injection and arbitrary file access:

1. **No Shell Execution:** Every `ffmpeg` and `ffprobe` invocation uses `subprocess.run(argv, shell=False)`. User and agent inputs are never interpolated into a shell command string.
2. **Workspace Sandboxing:** All file paths are resolved with `Path.resolve()` and verified to reside inside the configured `workdir` (`FFMPEG_MCP_WORKDIR`). Any path traversal (`../`) or symlink pointing outside the workspace raises a `WorkspaceSecurityError`.
3. **Protocol Whitelisting:** Input filenames starting with `-` (option injection) or remote protocols (`http://`, `https://`, `concat:`, `subfile:`) are rejected before command construction.

## Reporting a Vulnerability

Please report suspected security vulnerabilities privately by emailing **guillermolopezveliz24@gmail.com** with `[SECURITY] ffmpeg-mcp-server` in the subject line. Do not open a public issue for exploitable vulnerabilities.
