"""Core deterministic FFmpeg command builders, timestamp parsers, and workspace sandbox."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

_TIMESTAMP_RE = re.compile(
    r"^(?:(?P<hours>\d{1,3}):(?P<minutes>[0-5]?\d):)?(?P<seconds>\d+(?:\.\d{1,6})?)$"
)
_DISALLOWED_PROTOCOLS = ("http://", "https://", "ftp://", "sftp://", "concat:", "subfile:", "file:")

ASPECT_PRESETS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
    "4:5": (1080, 1350),
}

SUPPORTED_AUDIO_FORMATS = {
    "mp3": ("libmp3lame", ["-q:a", "2"]),
    "wav": ("pcm_s16le", []),
    "flac": ("flac", []),
    "m4a": ("aac", ["-b:a", "192k"]),
}


class WorkspaceSecurityError(ValueError):
    """Raised when a path escapes the allowed workspace or uses a forbidden syntax."""


@dataclass(frozen=True)
class SubtitleCue:
    """A single subtitle cue with start/end times in seconds and display text."""

    start: float
    end: float
    text: str


def resolve_workspace_path(
    user_path: Union[str, Path],
    workdir: Union[str, Path],
    *,
    must_exist: bool = False,
) -> Path:
    """Resolve ``user_path`` inside ``workdir`` and block path traversal or flag injection."""
    raw = str(user_path or "").strip()
    if not raw:
        raise WorkspaceSecurityError("Path must not be empty.")
    if raw.startswith("-"):
        raise WorkspaceSecurityError(f"Path '{raw}' must not start with '-' (flag injection blocked).")
    lower_raw = raw.lower()
    if any(lower_raw.startswith(proto) for proto in _DISALLOWED_PROTOCOLS):
        raise WorkspaceSecurityError(f"Remote or virtual FFmpeg protocols are not allowed: '{raw}'.")

    root = Path(workdir).expanduser().resolve()
    candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorkspaceSecurityError(
            f"Path '{raw}' resolves outside the allowed workspace '{root}'."
        ) from exc

    if must_exist and not candidate.exists():
        raise FileNotFoundError(f"Media file not found inside workspace: {candidate}")

    return candidate


def parse_timestamp(value: Union[str, int, float]) -> float:
    """Parse a non-negative timestamp in seconds or ``HH:MM:SS.mmm`` format into float seconds."""
    if isinstance(value, bool):
        raise ValueError("Timestamp cannot be a boolean.")
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds < 0:
            raise ValueError("Timestamp must be non-negative.")
        return round(seconds, 3)

    raw = str(value or "").strip()
    match = _TIMESTAMP_RE.match(raw)
    if not match:
        raise ValueError(
            f"Invalid timestamp '{value}'. Expected non-negative seconds or HH:MM:SS[.mmm]."
        )
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    secs = float(match.group("seconds"))
    if hours > 0 and secs >= 60.0:
        raise ValueError(f"Invalid seconds component in timestamp '{value}'.")
    total = hours * 3600.0 + minutes * 60.0 + secs
    return round(total, 3)


def format_srt_timestamp(seconds: Union[int, float]) -> str:
    """Format seconds as an SRT timestamp ``HH:MM:SS,mmm``."""
    total_ms = int(round(parse_timestamp(seconds) * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_srt(cues: Iterable[SubtitleCue]) -> str:
    """Render an iterable of ``SubtitleCue`` objects into a valid SRT document."""
    blocks: List[str] = []
    for idx, cue in enumerate(cues, start=1):
        start_s = parse_timestamp(cue.start)
        end_s = parse_timestamp(cue.end)
        if end_s <= start_s:
            raise ValueError(f"Cue {idx}: end time ({end_s}) must be greater than start time ({start_s}).")
        cleaned_text = "\n".join(
            line.strip() for line in (cue.text or "").splitlines() if line.strip()
        )
        if not cleaned_text:
            raise ValueError(f"Cue {idx}: subtitle text must not be empty.")
        blocks.append(
            f"{idx}\n{format_srt_timestamp(start_s)} --> {format_srt_timestamp(end_s)}\n{cleaned_text}"
        )
    if not blocks:
        raise ValueError("At least one subtitle cue is required to generate an SRT file.")
    return "\n\n".join(blocks) + "\n"


def build_probe_command(input_path: Path) -> List[str]:
    """Build a deterministic ``ffprobe`` command returning container and stream JSON."""
    return [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        "--",
        str(input_path),
    ]


def build_trim_command(
    input_path: Path,
    output_path: Path,
    *,
    start_time: Union[str, int, float] = 0.0,
    end_time: Optional[Union[str, int, float]] = None,
    duration: Optional[Union[str, int, float]] = None,
    reencode: bool = True,
) -> List[str]:
    """Build a deterministic ``ffmpeg`` command to trim a media clip."""
    start_s = parse_timestamp(start_time)
    if end_time is not None and duration is not None:
        raise ValueError("Specify either 'end_time' or 'duration', not both.")
    if end_time is not None:
        end_s = parse_timestamp(end_time)
        if end_s <= start_s:
            raise ValueError(f"end_time ({end_s}) must be greater than start_time ({start_s}).")
        clip_duration = round(end_s - start_s, 3)
    elif duration is not None:
        clip_duration = parse_timestamp(duration)
        if clip_duration <= 0:
            raise ValueError("duration must be greater than 0.")
    else:
        raise ValueError("Either 'end_time' or 'duration' must be provided.")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start_s:.3f}",
        "-i",
        str(input_path),
        "-t",
        f"{clip_duration:.3f}",
    ]
    if reencode:
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac"])
    else:
        cmd.extend(["-c", "copy"])
    cmd.append(str(output_path))
    return cmd


def build_aspect_ratio_command(
    input_path: Path,
    output_path: Path,
    *,
    aspect_ratio: str = "9:16",
    mode: str = "crop",
) -> List[str]:
    """Build an ``ffmpeg`` command to reframe video to a target aspect ratio."""
    if aspect_ratio not in ASPECT_PRESETS:
        supported = ", ".join(sorted(ASPECT_PRESETS))
        raise ValueError(f"Unsupported aspect_ratio '{aspect_ratio}'. Supported: {supported}.")
    if mode not in ("crop", "pad"):
        raise ValueError("mode must be either 'crop' or 'pad'.")

    target_w, target_h = ASPECT_PRESETS[aspect_ratio]
    if mode == "crop":
        vf = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h},setsar=1"
        )
    else:
        vf = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
        )

    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-c:a",
        "copy",
        str(output_path),
    ]


def build_extract_audio_command(
    input_path: Path,
    output_path: Path,
    *,
    audio_format: str = "mp3",
    normalize: bool = False,
) -> List[str]:
    """Build an ``ffmpeg`` command to extract and optionally normalize audio."""
    fmt = (audio_format or "").strip().lower().lstrip(".")
    if fmt not in SUPPORTED_AUDIO_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_AUDIO_FORMATS))
        raise ValueError(f"Unsupported audio_format '{audio_format}'. Supported: {supported}.")

    codec, extra_args = SUPPORTED_AUDIO_FORMATS[fmt]
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-vn",
    ]
    if normalize:
        cmd.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])
    cmd.extend(["-c:a", codec, *extra_args, str(output_path)])
    return cmd


def _escape_ffmpeg_filter_path(path: Path) -> str:
    """Escape special characters in a file path for FFmpeg's ``subtitles=`` filter."""
    raw = str(path)
    raw = raw.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return raw


def build_burn_subtitles_command(
    input_path: Path,
    subtitle_path: Path,
    output_path: Path,
    *,
    font_size: int = 22,
    margin_v: int = 40,
) -> List[str]:
    """Build an ``ffmpeg`` command to burn an SRT subtitle file into a video."""
    if font_size < 8 or font_size > 120:
        raise ValueError("font_size must be between 8 and 120.")
    if margin_v < 0 or margin_v > 500:
        raise ValueError("margin_v must be between 0 and 500.")

    escaped_sub = _escape_ffmpeg_filter_path(subtitle_path)
    style = f"FontSize={font_size},Alignment=2,MarginV={margin_v},Outline=2"
    vf = f"subtitles='{escaped_sub}':force_style='{style}'"

    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-c:a",
        "copy",
        str(output_path),
    ]
