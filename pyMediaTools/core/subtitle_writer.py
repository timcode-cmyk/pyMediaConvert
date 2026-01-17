"""
SubtitleWriter：统一的 SRT 文件写入工具

职责：
- 提供标准的 SRT 文件写入接口
- 统一时间格式化逻辑
- 消除代码重复（原 create_srt 和 generate_translated_srt 中的写文件逻辑）
"""


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
