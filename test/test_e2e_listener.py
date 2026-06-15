"""End-to-end listener tests for ovos-vad-plugin-webrtcvad.

Tests the real WebRTCVAD engine both directly (silence/speech classification on
raw PCM frames) and wired through MiniVoiceLoop (full record-begin → utterance
bus sequence driven from the command.wav fixture).

Fixture: test/fixtures/command.wav — 16 kHz, 16-bit, mono, ~2.4 s of speech
("what time is it in london").  Committed once; never synthesised in CI.
"""
import os
import struct
import wave

import pytest

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "command.wav")

# webrtcvad requires 10/20/30 ms frames at 8/16/32 kHz, 16-bit signed PCM.
# At 16 kHz with 16-bit samples: 30 ms = 16000 * 0.03 * 2 bytes = 960 bytes.
SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_BYTES = int(SAMPLE_RATE * (FRAME_MS / 1000.0) * 2)  # 960


def _read_pcm(path: str) -> bytes:
    """Return the raw PCM payload from a WAV file."""
    with wave.open(path) as wf:
        return wf.readframes(wf.getnframes())


def _silent_frame() -> bytes:
    """Return one 30 ms frame of pure silence (all-zero 16-bit samples)."""
    return b"\x00" * FRAME_BYTES


def _speech_frame(pcm: bytes, offset_frames: int = 20) -> bytes:
    """Return one 30 ms frame taken from the middle of the speech fixture.

    Uses frame at *offset_frames* (default 20 → 600 ms in), well within the
    "what time is it in london" utterance.
    """
    start = offset_frames * FRAME_BYTES
    return pcm[start:start + FRAME_BYTES]


# ---------------------------------------------------------------------------
# Part 1 — direct VAD behaviour on raw audio
# ---------------------------------------------------------------------------

class TestWebRTCVADDirect:
    """Exercise WebRTCVAD.is_silence() directly without any listener plumbing."""

    def setup_method(self):
        from ovos_vad_plugin_webrtcvad import WebRTCVAD

        # vad_mode=3 is the default (most aggressive); use mode=1 so the mid-
        # utterance frame is reliably classified as speech without needing many
        # ring-buffer frames to accumulate.
        self.vad = WebRTCVAD(config={"vad_mode": 1}, sample_rate=SAMPLE_RATE)
        self.pcm = _read_pcm(FIXTURE)

    def test_silent_frame_is_silence(self):
        """A 30 ms all-zero frame must be classified as silence."""
        chunk = _silent_frame()
        assert self.vad.is_silence(chunk) is True

    def test_speech_frame_not_silence(self):
        """A 30 ms frame from the centre of the speech fixture must NOT be silence.

        The plugin's is_silence() returns not self.triggered.  After feeding
        several voiced frames the ring buffer crosses the 80 % voiced threshold
        and triggered flips True, so is_silence() returns False.  We prime the
        VAD with enough consecutive speech frames to guarantee detection.
        """
        # Prime with 15 consecutive speech frames so the ring buffer fills and
        # triggers (num_padding_frames = 300 ms / 30 ms = 10 by default).
        for i in range(15):
            frame = _speech_frame(self.pcm, offset_frames=10 + i)
            self.vad.is_silence(frame)

        # Now the VAD should be in triggered state (speech detected).
        result = self.vad.is_silence(_speech_frame(self.pcm, offset_frames=25))
        assert result is False, (
            "Expected speech frame to cause is_silence()=False after priming "
            "the ring buffer with voiced frames."
        )

    def test_silence_after_reset(self):
        """After reset(), a fresh silent frame is classified as silence again."""
        # Prime as speech first.
        for i in range(15):
            self.vad.is_silence(_speech_frame(self.pcm, offset_frames=10 + i))

        self.vad.reset()
        assert self.vad.is_silence(_silent_frame()) is True


# ---------------------------------------------------------------------------
# Part 2 — MiniListener VAD wiring
# ---------------------------------------------------------------------------

class TestMiniListenerVAD:
    """WebRTCVAD wired through get_mini_listener() for VAD delegation tests."""

    def setup_method(self):
        from ovos_vad_plugin_webrtcvad import WebRTCVAD
        from ovoscope.listener import get_mini_listener

        self.vad = WebRTCVAD(config={"vad_mode": 1}, sample_rate=SAMPLE_RATE)
        self.listener = get_mini_listener(vad_instance=self.vad)
        self.pcm = _read_pcm(FIXTURE)

    def teardown_method(self):
        self.listener.shutdown()

    def test_listener_is_silence_on_zeros(self):
        """MiniListener.is_silence() delegates correctly for a silent chunk."""
        assert self.listener.is_silence(_silent_frame()) is True

    def test_listener_is_speech_after_priming(self):
        """MiniListener.is_silence() returns False after priming with speech."""
        for i in range(15):
            frame = _speech_frame(self.pcm, offset_frames=10 + i)
            self.listener.is_silence(frame)

        result = self.listener.is_silence(_speech_frame(self.pcm, offset_frames=25))
        assert result is False


# ---------------------------------------------------------------------------
# Part 3 — MiniVoiceLoop end-to-end (real VAD drives speech segmentation)
# ---------------------------------------------------------------------------

class TestMiniVoiceLoopE2E:
    """Full voice loop driven from the fixture WAV with the real WebRTCVAD.

    A MockHotWordEngine fires immediately (trigger_after=1) so the loop enters
    RECORDING state.  MockStreamingSTT returns the expected transcript.  The real
    WebRTCVAD detects end-of-speech in the silence tail and the loop emits
    recognizer_loop:utterance.
    """

    def test_real_vad_drives_utterance_from_fixture(self):
        from ovos_vad_plugin_webrtcvad import WebRTCVAD
        from ovoscope.voice_loop import (
            MiniVoiceLoop,
            MockHotWordEngine,
            MockStreamingSTT,
        )

        vad = WebRTCVAD(config={"vad_mode": 1}, sample_rate=SAMPLE_RATE)
        ww = MockHotWordEngine(key_phrase="hey_mycroft", trigger_after=1)
        stt = MockStreamingSTT(transcript="what time is it in london")

        with MiniVoiceLoop(
            ww_instances={"hey_mycroft": ww},
            vad_instance=vad,
            stt_instance=stt,
        ) as vl:
            msgs = vl.feed_file(FIXTURE, silence_tail_chunks=40, chunk_size=960)

        msg_types = [m.msg_type for m in msgs]
        assert "recognizer_loop:record_begin" in msg_types, (
            f"Expected record_begin; got: {msg_types}"
        )
        assert "recognizer_loop:utterance" in msg_types, (
            f"Expected utterance; got: {msg_types}"
        )
        utts = [
            u
            for m in msgs
            if m.msg_type == "recognizer_loop:utterance"
            for u in m.data.get("utterances", [])
        ]
        assert "what time is it in london" in utts, (
            f"Expected transcript in utterances; got: {utts}"
        )
