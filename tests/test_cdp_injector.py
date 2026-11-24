import json
import plistlib
import tempfile
import unittest
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import cdp_injector  # noqa: E402


class TestWebSocketCodec(unittest.TestCase):
    def test_encode_decode_short_payload(self) -> None:
        payload = "你好 Antigravity".encode("utf-8")
        frame = cdp_injector.encode_ws_frame(payload, opcode=0x1, mask_key=b"\x12\x34\x56\x78")
        opcode, decoded, consumed = cdp_injector.decode_ws_frame(frame)
        self.assertEqual(opcode, 0x1)
        self.assertEqual(decoded, payload)
        self.assertEqual(consumed, len(frame))

    def test_encode_decode_medium_payload_16bit(self) -> None:
        payload = b"A" * 512
        frame = cdp_injector.encode_ws_frame(payload, opcode=0x1, mask_key=b"\x01\x02\x03\x04")
        opcode, decoded, consumed = cdp_injector.decode_ws_frame(frame)
        self.assertEqual(opcode, 0x1)
        self.assertEqual(decoded, payload)
        self.assertEqual(consumed, len(frame))

    def test_encode_decode_large_payload_64bit(self) -> None:
        payload = b"B" * 70000
        frame = cdp_injector.encode_ws_frame(payload, opcode=0x1, mask_key=b"\xaa\xbb\xcc\xdd")
        opcode, decoded, consumed = cdp_injector.decode_ws_frame(frame)
        self.assertEqual(opcode, 0x1)
        self.assertEqual(decoded, payload)
        self.assertEqual(consumed, len(frame))


class TestLocalesAndInjection(unittest.TestCase):
    def test_locale_bundles_exist_and_align(self) -> None:
        tw = cdp_injector.load_locale_bundle(PROJECT_ROOT, "zh-TW")
        cn = cdp_injector.load_locale_bundle(PROJECT_ROOT, "zh-CN")
        self.assertEqual(tw["meta"]["locale"], "zh-TW")
        self.assertEqual(cn["meta"]["locale"], "zh-CN")
        self.assertEqual(set(tw["exact"].keys()), set(cn["exact"].keys()))
        self.assertGreater(len(tw["exact"]), 100)
        self.assertEqual(len(tw["patterns"]), len(cn["patterns"]))

    def test_build_injection_script_embeds_bundle_and_engine(self) -> None:
        script = cdp_injector.build_injection_script(PROJECT_ROOT, "zh-TW")
        self.assertIn("window.__ANTIGRAVITY_ZH_BUNDLE__", script)
        self.assertIn("Agent Manager", script)
        self.assertIn("代理管理員", script)
        self.assertIn("createLocalizationController", script)

    def test_discover_and_read_mock_macos_app_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            app_dir = Path(tmpdir) / "Antigravity.app"
            contents = app_dir / "Contents"
            macos_dir = contents / "MacOS"
            macos_dir.mkdir(parents=True)

            exec_file = macos_dir / "Antigravity"
            exec_file.write_text("#!/bin/sh\n", encoding="utf-8")

            plist_data = {
                "CFBundleExecutable": "Antigravity",
                "CFBundleIdentifier": "com.google.antigravity",
                "CFBundleShortVersionString": "2.34.0",
                "CFBundleVersion": "2340",
            }
            with (contents / "Info.plist").open("wb") as fh:
                plistlib.dump(plist_data, fh)

            found = cdp_injector.discover_antigravity_app(str(app_dir))
            self.assertEqual(found, app_dir)

            meta = cdp_injector.read_app_metadata(app_dir)
            self.assertEqual(meta["version"], "2.34.0")
            self.assertTrue(meta["executable_exists"])
            self.assertTrue(meta["executable"].endswith("Contents/MacOS/Antigravity"))


if __name__ == "__main__":
    unittest.main()
