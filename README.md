# ovos-vad-plugin-webrtcvad

A voice activity detection (VAD) plugin for [OpenVoiceOS](https://openvoiceos.org).

The plugin uses [webrtcvad](https://pypi.org/project/webrtcvad/) to detect speech in an audio stream. [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener) uses a VAD plugin like this one. It decides when a user has stopped speaking.

## Install

```bash
pip install ovos-vad-plugin-webrtcvad
```

## Configuration

Set the plugin as the VAD engine in the OpenVoiceOS configuration:

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

## Related projects

- [ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager): loads VAD plugins for OpenVoiceOS
- [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener): the listener service that consumes this plugin

## License

Apache-2.0
