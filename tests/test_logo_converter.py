import pytest
from pathlib import Path

from pyMediaTools.core.mediaconvert import LogoConverter
from pyMediaTools.core.factory import _build_modes


def test_logoconverter_single_legacy(tmp_path):
    # legacy parameters should still work
    params = {
        'x': 10,
        'y': 20,
        'logo_w': 50,
        'logo_h': 60,
        'target_w': 200,
        'target_h': 100,
        'logo_path': 'assets/hailuoDream.png',
    }
    conv = LogoConverter(params)
    assert len(conv.logos) == 1
    entry = conv.logos[0]
    assert entry['x'] == 10 and entry['y'] == 20
    assert entry['w'] == 50 and entry['h'] == 60
    assert entry['path'].name == 'hailuoDream.png'
    assert conv.target_w == 200 and conv.target_h == 100


def test_logoconverter_multiple(tmp_path, monkeypatch):
    # create fake logo files so existence check passes
    f1 = tmp_path / "l1.png"
    f2 = tmp_path / "l2.png"
    f1.write_text('')
    f2.write_text('')
    monkeypatch.setattr('pyMediaTools.core.mediaconvert.get_resource_path',
                        lambda p: Path(p) if Path(p).exists() else Path(p))
    params = {
        'target_w': 100,
        'target_h': 100,
        'logos': [
            {'x': 1, 'y': 2, 'logo_w': 10, 'logo_h': 20, 'logo_path': str(f1)},
            {'x': 3, 'y': 4, 'logo_w': 5, 'logo_h': 6, 'logo_path': str(f2)},
        ]
    }
    # mark second logo as no-blur so filter_complex should ignore it
    params['logos'][1]['blur'] = False
    conv = LogoConverter(params)
    assert len(conv.logos) == 2

    # intercept ffmpeg command built by process_file
    recorded = {}
    def fake_proc(cmd, duration, monitor, name):
        recorded['cmd'] = cmd
    conv.process_ffmpeg = fake_proc

    conv.process_file(Path('in.mp4'), Path('out'), duration=1.0)
    # each logo adds an input, plus the main input
    assert recorded['cmd'].count('-i') == 3
    assert str(f1) in recorded['cmd']
    assert str(f2) in recorded['cmd']
    # ensure blur only applied once: there should be exactly one "boxblur" in filter
    cmdstr = ' '.join(recorded['cmd'])
    assert cmdstr.count('boxblur') == 1
    # verify scaling expression uses gt(iw/ih) so scaling always happens
    assert 'gt(iw/ih' in cmdstr
    # final crop to target should be present
    assert 'crop=100:100' in cmdstr


def test_factory_loads_dream_mode(tmp_path, monkeypatch):
    # supply a minimal toml structure to _build_modes
    toml_data = {
        'modes': {
            'dream': {
                'class': 'LogoConverter',
                'params': {
                    'logos': [
                        {'x':0,'y':0,'logo_path':'a.png','logo_w':10,'logo_h':10},
                        {'x':5,'y':5,'logo_path':'b.png','logo_w':20,'logo_h':20, 'blur': False},
                    ]
                }
            }
        }
    }
    modes = _build_modes(toml_data)
    assert 'dream' in modes
    assert isinstance(modes['dream']['params']['logos'], list)
    assert len(modes['dream']['params']['logos']) == 2
    # second logo should carry blur flag False
    assert modes['dream']['params']['logos'][1].get('blur') is False
