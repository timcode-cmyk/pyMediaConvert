import pytest

import pyMediaTools.core.elevenlabs as el


def test_ttsworker_uses_config_default(monkeypatch):
    # monkeypatch load_project_config used by elevenlabs module
    monkeypatch.setattr(el, 'load_project_config', lambda: {'elevenlabs': {'default_output_format': 'wav_48000_16'}})

    w = el.TTSWorker(api_key='k', voice_id='v', text='t', save_path='out')
    assert w.output_format == 'wav_48000_16'


def test_ttsworker_uses_explicit_output_format():
    w = el.TTSWorker(api_key='k', voice_id='v', text='t', save_path='out', output_format='mp3_44100_128')
    assert w.output_format == 'mp3_44100_128'
