import collections

import webrtcvad
from ovos_plugin_manager.templates.vad import VADEngine


class Frame:
    """Represents a "frame" of audio data."""

    def __init__(self, bytes, timestamp, duration):
        self.bytes = bytes
        self.timestamp = timestamp
        self.duration = duration


def frame_generator(frame_duration_ms, audio, sample_rate):
    """Generates audio frames from PCM audio data.
    Takes the desired frame duration in milliseconds, the PCM data, and
    the sample rate.
    Yields Frames of the requested duration.
    """
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    offset = 0
    timestamp = 0.0
    duration = (float(n) / sample_rate) / 2.0

    while offset + n <= len(audio):
        yield Frame(audio[offset:offset + n], timestamp, duration)
        timestamp += duration
        offset += n


class WebRTCVAD(VADEngine):
    def __init__(self, config=None, sample_rate=None):
        super().__init__(config, sample_rate)
        self.vad_mode = self.config.get("vad_mode", 3)
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(self.vad_mode)

        self.padding_duration_ms = self.config.get("padding_duration_ms", 300)
        self.frame_duration_ms = self.config.get("frame_duration_ms", 30)
        self.thresh = self.config.get("thresh", 0.8)

        self.num_padding_frames = int(self.padding_duration_ms / self.frame_duration_ms)
        # We use a deque for our sliding window/ring buffer.
        self.ring_buffer = collections.deque(maxlen=self.num_padding_frames)
        self.triggered = False
        self.is_speech = False
        self.voiced_frames = []

    def reset(self):
        self.is_speech = False
        self.ring_buffer.clear()
        self.triggered = False
        self.voiced_frames = []

    def is_silence(self, chunk):
        for frame in frame_generator(self.frame_duration_ms, chunk, self.sample_rate):

            self.is_speech = self.vad.is_speech(frame.bytes, self.sample_rate)

            if not self.triggered:
                self.ring_buffer.append((frame, self.is_speech))
                num_voiced = len([f for f, speech in self.ring_buffer if speech])
                # If we're NOTTRIGGERED and more than 90% of the frames in
                # the ring buffer are voiced frames, then enter the
                # TRIGGERED state.
                if num_voiced > self.thresh * self.ring_buffer.maxlen:
                    self.triggered = True
                    # We want to yield all the audio we see from now until
                    # we are NOTTRIGGERED, but we have to start with the
                    # audio that's already in the ring buffer.
                    for f, s in self.ring_buffer:
                        self.voiced_frames.append(f)
                    self.ring_buffer.clear()
            else:
                # We're in the TRIGGERED state, so collect the audio data
                # and add it to the ring buffer.
                self.voiced_frames.append(frame)
                self.ring_buffer.append((frame, self.is_speech))
                num_unvoiced = len([f for f, speech in self.ring_buffer if not speech])

                # If more than 90% of the frames in the ring buffer are
                # unvoiced, then enter NOTTRIGGERED and yield whatever
                # audio we've collected.
                if num_unvoiced > self.thresh * self.ring_buffer.maxlen:
                    self.triggered = False
                    # full_speech = b''.join([f.bytes for f in self.voiced_frames])
                    self.ring_buffer.clear()
                    self.voiced_frames = []

        # return True or False
        return not self.triggered
