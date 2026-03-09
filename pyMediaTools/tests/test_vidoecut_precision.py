import pytest
from pathlib import Path
from pyMediaTools.core.vidoecut import SceneCutter


def test_align_to_frame():
    cutter = SceneCutter()
    # fps = 25
    times = [0.0, 0.04, 1.001, 1.039, 5.12345]
    # expected rounding: multiply by 25, round, divide back
    expected = [round(t * 25) / 25 for t in times]
    assert cutter._align_to_frame(times, 25) == expected


def test_process_video_command_order(monkeypatch, tmp_path):
    # ensure ffmpeg command uses -i before -ss for accurate seek
    calls = []

    def fake_execute(self, cmd, debug_log_file=None):
        calls.append(cmd.copy())
        # 模拟所有 FFmpeg 调用均成功，具体参数在断言中检查
        return True, ""

    monkeypatch.setattr(SceneCutter, '_execute_ffmpeg_command', fake_execute)
    
    cutter = SceneCutter(debug=True)
    # stub fps and duration to avoid calling ffmpeg/ffprobe
    monkeypatch.setattr('pyMediaTools.core.vidoecut.get_video_fps', lambda path, debug=False: 25.0)
    monkeypatch.setattr('pyMediaTools.core.vidoecut._get_video_duration', lambda path, debug=False: 10.0)
    video = tmp_path / "dummy.mp4"
    video.write_text('')
    out = tmp_path / "out"
    cutter.process_video(video, out, threshold=0.2, export_frame=False, frame_offset=10)

    # look for the split command
    split_cmds = [cmd for cmd in calls if '-ss' in cmd and any(video.name in part for part in cmd)]
    assert split_cmds, "No splitting command was executed"
    # the first occurrence should place '-i' before '-ss'
    first = split_cmds[-1]  # last command executed is the splitting
    i_index = first.index('-i')
    ss_index = first.index('-ss')
    assert i_index < ss_index, "-ss should appear after -i for accurate seeking"


def test_frame_offset_not_affect_video(monkeypatch, tmp_path):
    # verify frame_offset only influences frame capture command
    calls = []

    def fake_exec(self, cmd, debug_log_file=None):
        calls.append(cmd.copy())
        # 所有 FFmpeg 命令都视为成功，真正的检测逻辑在 OpenCV/FFmpeg 内部完成
        return True, ""

    monkeypatch.setattr(SceneCutter, '_execute_ffmpeg_command', fake_exec)
    cutter = SceneCutter()
    # stub helpers to avoid external ffmpeg calls
    monkeypatch.setattr('pyMediaTools.core.vidoecut.get_video_fps', lambda path, debug=False: 25.0)
    monkeypatch.setattr('pyMediaTools.core.vidoecut._get_video_duration', lambda path, debug=False: 10.0)
    video = tmp_path / "dummy.mp4"
    video.write_text('')
    out = tmp_path / "out"
    cutter.process_video(video, out, frame_offset=50, export_frame=True)

    # ensure the split command does not contain any '-ss' offset derived from frame_offset
    for cmd in calls:
        if '-ss' in cmd and any(video.name in part for part in cmd) and '-frames:v' not in cmd:
            # video-split command should have only a single '-ss' for start time
            # and not a value equal to "frame_offset/fps" which in this test will be 50/?
            # we just assert that the number of '-ss' occurrences is 1
            assert cmd.count('-ss') == 1
