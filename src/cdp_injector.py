#!/usr/bin/env python3
"""
Google Antigravity macOS Non-Destructive Localization Launcher & CDP Injector.

Zero external dependencies (pure Python 3 standard library).
Launches /Applications/Antigravity.app with a localhost-only Electron remote
debugging port, attaches to renderer targets over RFC 6455 WebSocket, and
injects the DOM localization overlay without modifying app.asar or breaking
macOS code signing.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import plistlib
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
DEFAULT_LOCALE = "zh-TW"


def find_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def discover_antigravity_app(custom_path: str | None = None) -> Path | None:
    candidates: list[Path] = []
    if custom_path:
        candidates.append(Path(custom_path).expanduser())
    env_path = os.environ.get("ANTIGRAVITY_APP_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.extend(
        [
            Path("/Applications/Antigravity.app"),
            Path.home() / "Applications" / "Antigravity.app",
        ]
    )

    for candidate in candidates:
        if candidate.is_dir() and (candidate / "Contents" / "Info.plist").is_file():
            return candidate
    return None


def read_app_metadata(app_path: Path) -> dict[str, Any]:
    plist_path = app_path / "Contents" / "Info.plist"
    with plist_path.open("rb") as fh:
        data = plistlib.load(fh)
    executable_name = data.get("CFBundleExecutable", "Antigravity")
    executable_path = app_path / "Contents" / "MacOS" / executable_name
    return {
        "app_path": str(app_path),
        "bundle_id": data.get("CFBundleIdentifier", ""),
        "version": data.get("CFBundleShortVersionString", "unknown"),
        "build": data.get("CFBundleVersion", ""),
        "executable": str(executable_path),
        "executable_exists": executable_path.is_file(),
        "icon_file": data.get("CFBundleIconFile", ""),
    }


def load_locale_bundle(project_root: Path, locale: str) -> dict[str, Any]:
    locale_file = project_root / "locales" / f"{locale}.json"
    if not locale_file.is_file():
        available = sorted(p.stem for p in (project_root / "locales").glob("*.json"))
        raise FileNotFoundError(
            f"Locale '{locale}' not found at {locale_file}. Available: {', '.join(available)}"
        )
    with locale_file.open("r", encoding="utf-8") as fh:
        bundle = json.load(fh)
    if "exact" not in bundle or not isinstance(bundle["exact"], dict):
        raise ValueError(f"Invalid locale bundle format in {locale_file}")
    return bundle


def build_injection_script(project_root: Path, locale: str) -> str:
    bundle = load_locale_bundle(project_root, locale)
    overlay_path = project_root / "src" / "overlay.js"
    overlay_js = overlay_path.read_text(encoding="utf-8")
    bundle_json = json.dumps(bundle, ensure_ascii=False)
    return f"window.__ANTIGRAVITY_ZH_BUNDLE__ = {bundle_json};\n{overlay_js}\n"


def encode_ws_frame(payload: bytes, opcode: int = 0x1, mask_key: bytes | None = None) -> bytes:
    """Encode a masked RFC 6455 client-to-server WebSocket frame."""
    fin_opcode = 0x80 | (opcode & 0x0F)
    mask_bit = 0x80
    length = len(payload)
    if mask_key is None:
        mask_key = os.urandom(4)
    if len(mask_key) != 4:
        raise ValueError("WebSocket mask_key must be exactly 4 bytes")

    header = bytearray([fin_opcode])
    if length < 126:
        header.append(mask_bit | length)
    elif length < 65536:
        header.append(mask_bit | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(mask_bit | 127)
        header.extend(struct.pack("!Q", length))

    masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    return bytes(header) + mask_key + masked


def decode_ws_frame(data: bytes) -> tuple[int, bytes, int]:
    """Decode a single WebSocket frame. Returns (opcode, payload, bytes_consumed)."""
    if len(data) < 2:
        raise ValueError("Incomplete WebSocket frame header")

    first_byte, second_byte = data[0], data[1]
    opcode = first_byte & 0x0F
    is_masked = bool(second_byte & 0x80)
    length = second_byte & 0x7F
    offset = 2

    if length == 126:
        if len(data) < offset + 2:
            raise ValueError("Incomplete 16-bit WebSocket length")
        length = struct.unpack("!H", data[offset : offset + 2])[0]
        offset += 2
    elif length == 127:
        if len(data) < offset + 8:
            raise ValueError("Incomplete 64-bit WebSocket length")
        length = struct.unpack("!Q", data[offset : offset + 8])[0]
        offset += 8

    mask_key = b""
    if is_masked:
        if len(data) < offset + 4:
            raise ValueError("Incomplete WebSocket mask key")
        mask_key = data[offset : offset + 4]
        offset += 4

    if len(data) < offset + length:
        raise ValueError("Incomplete WebSocket payload")

    payload = data[offset : offset + length]
    if is_masked:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    return opcode, payload, offset + length


class MinimalCDPClient:
    """Zero-dependency RFC 6455 WebSocket client for Chrome DevTools Protocol."""

    def __init__(self, ws_url: str, timeout: float = 5.0) -> None:
        self.ws_url = ws_url
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self._msg_id = 0
        self._recv_buf = bytearray()

    def connect(self) -> None:
        parsed = urllib.parse.urlparse(self.ws_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 80
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"

        sock = socket.create_connection((host, port), timeout=self.timeout)
        sock.settimeout(self.timeout)

        ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
        expected_accept = base64.b64encode(
            hashlib.sha1((ws_key + WS_GUID).encode("ascii")).digest()
        ).decode("ascii")

        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(request.encode("ascii"))

        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                raise ConnectionError("CDP WebSocket handshake closed unexpectedly")
            response += chunk

        header_bytes, leftover = response.split(b"\r\n\r\n", 1)
        header_text = header_bytes.decode("latin1")
        if "101" not in header_text.splitlines()[0]:
            sock.close()
            raise ConnectionError(f"CDP WebSocket upgrade failed: {header_text.splitlines()[0]}")
        if expected_accept not in header_text:
            sock.close()
            raise ConnectionError("CDP WebSocket Sec-WebSocket-Accept mismatch")

        self.sock = sock
        if leftover:
            self._recv_buf.extend(leftover)

    def send_command(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.sock:
            raise RuntimeError("CDP client is not connected")
        self._msg_id += 1
        cmd_id = self._msg_id
        payload = json.dumps(
            {"id": cmd_id, "method": method, "params": params or {}},
            ensure_ascii=False,
        ).encode("utf-8")
        self.sock.sendall(encode_ws_frame(payload, opcode=0x1))

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            opcode, data = self._read_frame()
            if opcode == 0x9:  # Ping -> Pong
                self.sock.sendall(encode_ws_frame(data, opcode=0xA))
                continue
            if opcode == 0x8:  # Close
                raise ConnectionError("CDP WebSocket closed by target")
            if opcode == 0x1:
                msg = json.loads(data.decode("utf-8"))
                if msg.get("id") == cmd_id:
                    return msg
        raise TimeoutError(f"Timed out waiting for CDP response to {method}")

    def _read_frame(self) -> tuple[int, bytes]:
        assert self.sock is not None
        while True:
            try:
                opcode, payload, consumed = decode_ws_frame(bytes(self._recv_buf))
                del self._recv_buf[:consumed]
                return opcode, payload
            except ValueError:
                chunk = self.sock.recv(65536)
                if not chunk:
                    raise ConnectionError("CDP WebSocket EOF")
                self._recv_buf.extend(chunk)

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.sendall(encode_ws_frame(b"", opcode=0x8))
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None


def fetch_cdp_targets(port: int, timeout: float = 2.0) -> list[dict[str, Any]]:
    url = f"http://127.0.0.1:{port}/json/list"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def inject_into_target(ws_url: str, script: str) -> bool:
    client = MinimalCDPClient(ws_url, timeout=5.0)
    try:
        client.connect()
        client.send_command("Page.enable")
        client.send_command("Page.addScriptToEvaluateOnNewDocument", {"source": script})
        client.send_command("Runtime.evaluate", {"expression": script, "awaitPromise": False})
        return True
    except Exception:
        return False
    finally:
        client.close()


def run_doctor(project_root: Path, app_path_arg: str | None, locale: str) -> int:
    print("=== Antigravity macOS 中文化環境診斷 (Doctor) ===")
    print(f"作業系統: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python 版本: {platform.python_version()} ({sys.executable})")

    if platform.system() != "Darwin":
        print("[警告] 目前環境非 macOS（Darwin），實際啟動僅支援 macOS 桌面環境。")

    app_path = discover_antigravity_app(app_path_arg)
    if app_path:
        meta = read_app_metadata(app_path)
        print(f"Antigravity.app: 找到於 {meta['app_path']}")
        print(f"  版本: {meta['version']} (Build {meta['build']})")
        print(f"  執行檔: {meta['executable']} (存在: {meta['executable_exists']})")
        if platform.system() == "Darwin" and shutil.which("codesign"):
            res = subprocess.run(
                ["codesign", "--verify", "--deep", "--strict", str(app_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            status = "完好（官方簽章未受破壞）" if res.returncode == 0 else f"異常 ({res.stderr.strip()})"
            print(f"  程式碼簽章: {status}")
    else:
        print("Antigravity.app: 未找到（請先從 https://antigravity.google 安裝至 /Applications/）")

    try:
        bundle = load_locale_bundle(project_root, locale)
        print(
            f"詞庫 ({locale}): 正常 — "
            f"{len(bundle.get('exact', {}))} 筆精確詞條, "
            f"{len(bundle.get('patterns', []))} 筆正規規則"
        )
    except Exception as exc:
        print(f"詞庫 ({locale}): 錯誤 — {exc}")
        return 1

    launcher_app = Path.home() / "Applications" / "Antigravity 中文版.app"
    print(f"macOS 啟動器 App: {'已安裝' if launcher_app.exists() else '尚未安裝'} ({launcher_app})")
    return 0


def run_launcher(args: argparse.Namespace) -> int:
    project_root = find_project_root()
    app_path = discover_antigravity_app(args.app_path)
    if not app_path:
        print(
            "[錯誤] 找不到 Google Antigravity.app。請確認已安裝於 /Applications/Antigravity.app，"
            "或使用 --app-path 指定路徑。",
            file=sys.stderr,
        )
        return 1

    meta = read_app_metadata(app_path)
    executable = meta["executable"]
    if not meta["executable_exists"]:
        print(f"[錯誤] 找不到執行檔: {executable}", file=sys.stderr)
        return 1

    injection_script = build_injection_script(project_root, args.lang)
    port = args.port or find_free_port()

    cmd = [
        executable,
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        *args.extra_args,
    ]

    print(f"[antigravity-zh-macos] 啟動 Google Antigravity ({args.lang})，CDP 連接埠: 127.0.0.1:{port}")
    proc = subprocess.Popen(cmd)

    stop_requested = False

    def handle_signal(_signum: int, _frame: Any) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    injected_targets: set[str] = set()
    poll_interval = 0.8

    try:
        while proc.poll() is None and not stop_requested:
            try:
                targets = fetch_cdp_targets(port, timeout=1.5)
                for target in targets:
                    target_id = target.get("id")
                    target_type = target.get("type", "")
                    ws_url = target.get("webSocketDebuggerUrl")
                    if (
                        target_id
                        and ws_url
                        and target_id not in injected_targets
                        and target_type in ("page", "webview", "iframe")
                    ):
                        if inject_into_target(ws_url, injection_script):
                            injected_targets.add(target_id)
                            if args.verbose:
                                title = target.get("title", target_id)
                                print(f"[antigravity-zh-macos] 已注入中文化引擎: {title}")
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
                pass
            time.sleep(poll_interval)
    finally:
        if stop_requested and proc.poll() is None:
            proc.terminate()

    return proc.returncode or 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="antigravity-zh-macos",
        description="Google Antigravity macOS 無損中文化啟動器與 CDP 注入守護程式",
    )
    parser.add_argument(
        "--lang",
        default=DEFAULT_LOCALE,
        choices=["zh-TW", "zh-CN"],
        help="目標中文語系（預設: zh-TW 繁體中文）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="本機 CDP 除錯連接埠（預設: 自動選擇空閒連接埠）",
    )
    parser.add_argument(
        "--app-path",
        default=None,
        help="自訂 Antigravity.app 路徑（預設偵測 /Applications/Antigravity.app）",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="執行 macOS 環境與詞庫健康檢查",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="輸出詳細注入日誌",
    )
    parser.add_argument(
        "extra_args",
        nargs=argparse.REMAINDER,
        help="額外傳遞給 Antigravity 的啟動參數",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.doctor:
        return run_doctor(find_project_root(), args.app_path, args.lang)
    return run_launcher(args)


if __name__ == "__main__":
    raise SystemExit(main())
