import json
from types import SimpleNamespace

import pytest

from pyMediaTools.core import elevenlabs as backend_mod
from pyMediaTools.core.elevenlabs import SFXWorker as LegacySFXWorker


class DummyResp:
    def __init__(self, status_code=404, text="Not Found", json_obj=None):
        self.status_code = status_code
        self._text = text
        self._json = json_obj

    def iter_content(self, chunk_size=1024):
        return []

    @property
    def text(self):
        return self._text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def test_sfx_404_backend(monkeypatch):
    called = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        return DummyResp(404, text='{"detail":"Not Found"}')

    monkeypatch.setattr(backend_mod.requests, "post", fake_post)

    worker = backend_mod.SFXWorker(api_key="key", prompt="p", duration=2, save_path="/tmp/out.wav")

    def on_error(msg):
        called['msg'] = msg

    worker.error.connect(on_error)

    worker.run()

    assert '404' in called['msg'] and '权限' in called['msg'] or 'Not Found' in called['msg']


def test_sfx_404_legacy(monkeypatch):
    called = {}

    def fake_post(url, json=None, headers=None):
        return DummyResp(404, text='{"detail":"Not Found"}')

    monkeypatch.setattr(__import__("requests"), "post", fake_post)

    worker = LegacySFXWorker(api_key="key", prompt="p", duration=2, save_path="/tmp/out.wav")

    def on_error(msg):
        called['msg'] = msg

    worker.error.connect(on_error)

    worker.run()

    assert '404' in called['msg'] and '权限' in called['msg'] or 'Not Found' in called['msg']


def test_sfx_422_backend(monkeypatch):
    called = {}

    def fake_post(url, json=None, headers=None, timeout=None, params=None):
        called['json'] = json
        return DummyResp(422, json_obj=[{"type": "missing", "loc": ["body", "text"], "msg": "Field required", "input": None}])

    monkeypatch.setattr(backend_mod.requests, "post", fake_post)

    worker = backend_mod.SFXWorker(api_key="key", prompt="p", duration=2, save_path="/tmp/out.wav")

    def on_error(msg):
        called['msg'] = msg

    worker.error.connect(on_error)

    worker.run()

    assert '422' in called['msg'] and ('text' in str(called.get('json', '')) or 'Field required' in called['msg'])


def test_sfx_422_legacy(monkeypatch):
    called = {}

    def fake_post(url, json=None, headers=None, params=None):
        called['json'] = json
        return DummyResp(422, json_obj=[{"type": "missing", "loc": ["body", "text"], "msg": "Field required", "input": None}])

    monkeypatch.setattr(__import__("requests"), "post", fake_post)

    worker = LegacySFXWorker(api_key="key", prompt="p", duration=2, save_path="/tmp/out.wav")

    def on_error(msg):
        called['msg'] = msg

    worker.error.connect(on_error)

    worker.run()

    assert '422' in called['msg'] and ('text' in str(called.get('json', '')) or 'Field required' in called['msg'])
