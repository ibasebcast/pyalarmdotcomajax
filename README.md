# pyalarmdotcomajax

Async Python interface for Alarm.com, maintained for use with the `ha-alarmdotcom` Home Assistant integration.

This fork is based on the `0.6.0-beta.9` code line and is packaged for direct use by the ibasebcast integration.

## Purpose

This repository is the backend client library used by the Home Assistant integration at:

- `https://github.com/ibasebcast/ha-alarmdotcom`

It handles Alarm.com authentication, API access, websocket messaging, and device model parsing.

## Install

```bash
pip install git+https://github.com/ibasebcast/pyalarmdotcomajax.git@2026.3.14
```

## Home Assistant integration requirement

```json
"requirements": [
  "beautifulsoup4>=4.10.0",
  "pyalarmdotcomajax @ git+https://github.com/ibasebcast/pyalarmdotcomajax.git@2026.3.14"
]
```

## Included

- Alarm.com async client library
- websocket client
- device controllers and models
- `adc` CLI entry point

## Removed from this fork package

- VS Code settings
- dev container files
- GitHub workflow files
- tests
- docs and extra development assets

## Version

This fork release: `2026.3.14`
Base code line: `0.6.0-beta.9`
