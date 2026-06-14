# ovos-vad-plugin-webrtcvad

WebRTC VAD plugin for [OpenVoiceOS](https://openvoiceos.org).

Uses [webrtcvad](https://pypi.org/project/webrtcvad/) to detect voice activity in audio streams.

## Install

```bash
pip install ovos-vad-plugin-webrtcvad
```

## Configuration

```json
{
  "listener": {
    "VAD": {
      "module": "ovos-vad-plugin-webrtcvad",
      "ovos-vad-plugin-webrtcvad": {
        "vad_mode": 3
      }
    }
  }
}
```

`vad_mode` ranges from 0 (least aggressive) to 3 (most aggressive, default).

## License

Apache-2.0
