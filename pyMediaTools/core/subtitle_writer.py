"""
SubtitleWriter：统一的字幕文件写入与多格式导出工具

职责：
- 提供标准的 SRT / VTT / ASS / FCPXML 文件写入与预览文本转换接口
- 统一时间格式化逻辑
- 消除多模块中的重复导出逻辑
"""

from pathlib import Path
from ..logging_config import get_logger

logger = get_logger(__name__)


class SubtitleWriter:
    """SRT 字幕文件写入工具"""

    @staticmethod
    def write_srt(filename, segments):
        """
        将分段列表写入 SRT 文件

        Args:
            filename (str): 输出文件路径
            segments (list): 分段列表，每个元素为 dict
                            {
                                "text": "字幕文本",
                                "start": 1.5,    # 开始时间（秒）
                                "end": 3.2       # 结束时间（秒）
                            }

        Returns:
            None

        Raises:
            IOError: 文件写入失败
            ValueError: 分段格式不符合要求
        """
        if not segments:
            # 空分段列表，创建空的 SRT 文件
            with open(filename, "w", encoding="utf-8") as f:
                pass
            return

        try:
            with open(filename, "w", encoding="utf-8") as f:
                for idx, segment in enumerate(segments):
                    # 获取分段信息
                    text = segment.get("text", "").strip()
                    start = segment.get("start")
                    end = segment.get("end")

                    # 验证必要字段
                    if start is None or end is None:
                        raise ValueError(
                            f"分段 {idx} 缺少 'start' 或 'end' 字段"
                        )

                    # 跳过空文本
                    if not text:
                        continue

                    # 写入 SRT 条目
                    f.write(f"{idx + 1}\n")
                    f.write(
                        f"{SubtitleWriter._format_time(start)} --> {SubtitleWriter._format_time(end)}\n"
                    )
                    f.write(f"{text}\n\n")
        except IOError as e:
            raise IOError(f"无法写入 SRT 文件 {filename}: {str(e)}")
        except Exception as e:
            raise ValueError(f"处理分段时出错: {str(e)}")

    @staticmethod
    def _format_time(seconds):
        """
        将秒数转换为 SRT 时间格式 HH:MM:SS,mmm

        Args:
            seconds (float): 时间（秒）

        Returns:
            str: 格式化后的时间字符串，如 "00:01:30,500"

        Examples:
            >>> SubtitleWriter._format_time(1.5)
            '00:00:01,500'
            >>> SubtitleWriter._format_time(90.123)
            '00:01:30,123'
        """
        mils = int((seconds % 1) * 1000)
        secs = int(seconds % 60)
        mins = int((seconds / 60) % 60)
        hours = int(seconds / 3600)
        return f"{hours:02d}:{mins:02d}:{secs:02d},{mils:03d}"


def format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间格式 HH:MM:SS,mmm"""
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis -= 1000
        secs += 1
        if secs >= 60:
            secs -= 60
            minutes += 1
            if minutes >= 60:
                minutes -= 60
                hours += 1
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_vtt_time(seconds: float) -> str:
    """将秒数转换为 WebVTT 时间格式 HH:MM:SS.mmm"""
    return format_srt_time(seconds).replace(",", ".")


def segments_to_srt_text(segments: list) -> str:
    """将 segments 转换为 SRT 格式字符串（用于 UI 预览或写文件）。"""
    lines = []
    for idx, seg in enumerate(segments, 1):
        start = format_srt_time(seg["start"])
        end = format_srt_time(seg["end"])
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def export_srt(segments: list, output_path: str) -> str:
    """导出 SRT 字幕文件。"""
    content = segments_to_srt_text(segments)
    Path(output_path).write_text(content, encoding="utf-8")
    logger.info(f"SRT 导出完成: {output_path} ({len(segments)} 条)")
    return output_path


def export_vtt(segments: list, output_path: str) -> str:
    """导出 WebVTT 字幕文件。"""
    lines = ["WEBVTT", ""]
    for idx, seg in enumerate(segments, 1):
        start = format_vtt_time(seg["start"])
        end = format_vtt_time(seg["end"])
        lines.append(f"{idx}")
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"])
        lines.append("")

    content = "\n".join(lines)
    Path(output_path).write_text(content, encoding="utf-8")
    logger.info(f"VTT 导出完成: {output_path}")
    return output_path


def export_ass(segments: list, output_path: str) -> str:
    """导出 ASS 字幕文件（基础格式）。"""
    def sec_to_ass(s: float) -> str:
        s = max(0.0, s)
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = s % 60
        return f"{h}:{m:02d}:{sec:05.2f}"

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,70,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,1,2,10,10,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for seg in segments:
        start = sec_to_ass(seg["start"])
        end = sec_to_ass(seg["end"])
        text = seg["text"].replace("\n", "\\N")
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    content = header + "\n".join(events) + "\n"
    Path(output_path).write_text(content, encoding="utf-8")
    logger.info(f"ASS 导出完成: {output_path}")
    return output_path


def export_fcpxml(segments: list, output_path: str, fps: float = 25.0) -> str:
    """导出 Final Cut Pro XML (FCPXML v1.11) 字幕文件。"""
    def to_fcp(secs: float) -> str:
        frames = round(secs * fps)
        return f"{frames}/{int(fps)}s"

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE fcpxml>',
        '<fcpxml version="1.11">',
        '    <resources>',
        f'        <format id="r1" name="FFVideoFormat1080p{int(fps)}" frameDuration="1/{int(fps)}s" width="1920" height="1080" colorSpace="1-1-1 (Rec. 709)"/>',
        '    </resources>',
        '    <library>',
        '        <event name="Gladia Subtitles">',
        '            <project name="Gladia Subtitles">',
        '                <sequence format="r1" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48000">',
        '                    <spine>',
        '                        <gap name="Gap" offset="0s" duration="' + to_fcp(segments[-1]["end"] if segments else 10) + '" start="0s">',
    ]

    for idx, seg in enumerate(segments):
        start = to_fcp(seg["start"])
        dur = to_fcp(max(0.05, seg["end"] - seg["start"]))
        text = seg["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        xml_lines += [
            f'                            <title name="Subtitle {idx+1}" lane="1" offset="{start}" ref="r1" duration="{dur}" role="titles">',
            f'                                <text>',
            f'                                    <text-style ref="ts{idx+1}">{text}</text-style>',
            f'                                </text>',
            f'                                <text-style-def id="ts{idx+1}">',
            f'                                    <text-style font="Helvetica Neue" fontSize="80" fontFace="Bold" fontColor="1 1 1 1" alignment="center"/>',
            f'                                </text-style-def>',
            f'                            </title>',
        ]

    xml_lines += [
        '                        </gap>',
        '                    </spine>',
        '                </sequence>',
        '            </project>',
        '        </event>',
        '    </library>',
        '</fcpxml>',
    ]

    content = "\n".join(xml_lines)
    Path(output_path).write_text(content, encoding="utf-8")
    logger.info(f"FCPXML 导出完成: {output_path}")
    return output_path
