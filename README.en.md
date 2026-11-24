# Antigravity Chinese Localization for macOS (`antigravity-zh-macos`)

> **Open-source, non-destructive Chinese localization launcher for Google Antigravity on macOS**  
> Supports **Traditional Chinese (`zh-TW`, default)** & **Simplified Chinese (`zh-CN`)** · Apple Silicon & Intel Mac · **Zero external dependencies**

[繁體中文](README.md) · [English](README.en.md) · [Contributing](CONTRIBUTING.md)

---

## Why Non-Destructive for macOS?

Patching `/Applications/Antigravity.app/Contents/Resources/app.asar` directly breaks Apple code signing (triggering Gatekeeper warnings) and gets wiped out on every auto-update.

`antigravity-zh-macos` leaves `/Applications/Antigravity.app` **100% untouched**:
- Launches Antigravity with a localhost-only Electron remote debugging port (`127.0.0.1`).
- Injects a lightweight, code-block-safe DOM localization engine (`src/overlay.js`) via a zero-dependency Python 3 stdlib CDP WebSocket client (`src/cdp_injector.py`).
- Creates a native `~/Applications/Antigravity 中文版.app` launcher bundle with the official icon so both English and Chinese icons coexist cleanly in Spotlight and Dock.

## Quick Install (macOS)

```bash
# Traditional Chinese (zh-TW, default)
curl -fsSL https://raw.githubusercontent.com/gj8329-bot/antigravity-zh-macos/main/install.sh | bash

# Simplified Chinese (zh-CN)
curl -fsSL https://raw.githubusercontent.com/gj8329-bot/antigravity-zh-macos/main/install.sh | bash -s -- --lang zh-CN
```

## CLI Usage

```bash
antigravity-zh-macos start                 # Launch localized Antigravity
antigravity-zh-macos doctor                # Verify macOS environment, signature & locale files
antigravity-zh-macos config --lang zh-TW   # Change default locale (zh-TW or zh-CN)
```

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/gj8329-bot/antigravity-zh-macos/main/uninstall.sh | bash -s -- --purge
```

## License

[MIT License](LICENSE). Community-maintained open-source project; not affiliated with Google.
