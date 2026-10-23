"""/asr-diarize puts the transcript in `text` as speaker turns.

Audio decoding and the pipeline are faked, so no model is loaded.
"""

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient

from test_model_selection import MODEL_ENV, _drop_app_modules, fresh  # noqa: F401  (fixture)


SEGMENTS = [
    {"start": 0.5, "end": 2.0, "text": " Shall we start?", "speaker": "SPEAKER_00"},
    {"start": 2.1, "end": 3.0, "text": " The budget first.", "speaker": "SPEAKER_00"},
    {"start": 63.4, "end": 65.0, "text": " Fine by me.", "speaker": "SPEAKER_01"},
    {"start": 66.0, "end": 67.0, "text": " ", "speaker": "SPEAKER_00"},
    {"start": 4530.0, "end": 4532.0, "text": " Thanks, all.", "speaker": "SPEAKER_00"},
]


@pytest.fixture
def fmt(fresh):
    return fresh().format_speaker_transcript


def test_turns_merge_same_speaker_segments_and_show_start_times(fmt):
    assert fmt(SEGMENTS) == (
        "**SPEAKER_00** [00:00]: Shall we start? The budget first.\n\n"
        "**SPEAKER_01** [01:03]: Fine by me.\n\n"
        "**SPEAKER_00** [75:30]: Thanks, all."
    )


def test_a_segment_without_a_speaker_is_unknown(fmt):
    segments = [
        {"start": 0.0, "text": " Hello.", "speaker": "SPEAKER_00"},
        {"start": 5.0, "text": " Who is there?"},
    ]
    assert fmt(segments) == (
        "**SPEAKER_00** [00:00]: Hello.\n\n"
        "**UNKNOWN** [00:05]: Who is there?"
    )


def test_without_any_speaker_the_plain_transcript_is_returned(fmt):
    segments = [{"start": 0.0, "text": " Hello."}, {"start": 5.0, "text": " Bye."}]
    assert fmt(segments) == " Hello.  Bye."
    assert fmt([]) == ""


@pytest.fixture
def client(monkeypatch):
    for key in MODEL_ENV:
        monkeypatch.delenv(key, raising=False)
    _drop_app_modules()
    import whisperx
    monkeypatch.setattr(whisperx, "load_audio", lambda path: np.zeros(16000, dtype=np.float32))
    import app.main as main
    seen = {}

    def fake_pipeline(audio, **kwargs):
        seen.update(kwargs)
        return {"language": "en", "segments": [dict(s) for s in SEGMENTS], "word_segments": []}, None

    monkeypatch.setattr(main, "run_pipeline", fake_pipeline)
    yield TestClient(main.app), seen   # no `with`: the startup preload does not run
    _drop_app_modules()


def test_endpoint_returns_speaker_turns_and_the_segments(client):
    client, seen = client
    r = client.post(
        "/asr-diarize",
        files={"file": ("a.wav", io.BytesIO(b"RIFF0000WAVE"), "audio/wav")},
        data={"model": "whisper-1"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"].startswith("**SPEAKER_00** [00:00]: Shall we start?")
    assert "\n\n**SPEAKER_01** [01:03]: Fine by me." in body["text"]
    assert body["segments"] == SEGMENTS
    assert seen["should_diarize"] is True
