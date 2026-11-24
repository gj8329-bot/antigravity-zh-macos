#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${ANTIGRAVITY_ZH_REPO:-https://github.com/gj8329-bot/antigravity-zh-macos.git}"
INSTALL_DIR="${ANTIGRAVITY_ZH_HOME:-$HOME/.local/share/antigravity-zh-macos}"
BIN_DIR="${HOME}/.local/bin"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/antigravity-zh-macos"
LAUNCHER_APP_DIR="${HOME}/Applications/Antigravity 中文版.app"
LANG_CODE="zh-TW"

while [ $# -gt 0 ]; do
  case "$1" in
    --lang)
      LANG_CODE="${2:-zh-TW}"
      shift 2
      ;;
    -h|--help)
      echo "用法: ./install.sh [--lang zh-TW|zh-CN]"
      exit 0
      ;;
    *)
      echo "[錯誤] 未知參數: $1" >&2
      exit 1
      ;;
  esac
done

if [ "$LANG_CODE" != "zh-TW" ] && [ "$LANG_CODE" != "zh-CN" ]; then
  echo "[錯誤] 不支援的語系: $LANG_CODE（僅支援 zh-TW 或 zh-CN）" >&2
  exit 1
fi

echo "==> 安裝 Google Antigravity macOS 無損中文化啟動器 (${LANG_CODE})"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "[警告] 偵測到非 macOS 環境 ($(uname -s))，將僅安裝 CLI 與詞庫檔案。"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[錯誤] 需要 Python 3。請在 macOS 終端機執行: xcode-select --install" >&2
  exit 1
fi

# Determine whether running from a local git checkout or curl pipe
SCRIPT_PATH="${BASH_SOURCE[0]:-}"
if [ -n "$SCRIPT_PATH" ] && [ -f "$SCRIPT_PATH" ]; then
  LOCAL_ROOT="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
else
  LOCAL_ROOT=""
fi

if [ -n "$LOCAL_ROOT" ] && [ -f "$LOCAL_ROOT/src/cdp_injector.py" ] && [ "$LOCAL_ROOT" != "$INSTALL_DIR" ]; then
  echo "==> 從本機專案目錄同步至 ${INSTALL_DIR}"
  mkdir -p "$INSTALL_DIR"
  cp -R "$LOCAL_ROOT/bin" "$LOCAL_ROOT/src" "$LOCAL_ROOT/locales" "$LOCAL_ROOT/uninstall.sh" "$INSTALL_DIR/"
elif [ -d "$INSTALL_DIR/.git" ]; then
  echo "==> 更新既有安裝於 ${INSTALL_DIR}"
  git -C "$INSTALL_DIR" pull --ff-only
elif [ "$LOCAL_ROOT" != "$INSTALL_DIR" ]; then
  echo "==> 下載專案至 ${INSTALL_DIR}"
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

chmod +x "$INSTALL_DIR/bin/antigravity-zh-macos" "$INSTALL_DIR/src/cdp_injector.py" "$INSTALL_DIR/uninstall.sh"

# Save default locale config
mkdir -p "$CONFIG_DIR"
printf '{"lang": "%s"}\n' "$LANG_CODE" > "$CONFIG_DIR/config.json"

# Link CLI binary
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/bin/antigravity-zh-macos" "$BIN_DIR/antigravity-zh-macos"
echo "==> 已建立 CLI 指令: ${BIN_DIR}/antigravity-zh-macos"

# Create native macOS .app launcher bundle (non-destructive, separate icon)
if [ "$(uname -s)" = "Darwin" ]; then
  echo "==> 建立 macOS 原生啟動器: ${LAUNCHER_APP_DIR}"
  mkdir -p "$LAUNCHER_APP_DIR/Contents/MacOS" "$LAUNCHER_APP_DIR/Contents/Resources"

  # Copy official Antigravity icon if present
  ICON_NAME=""
  for APP_CANDIDATE in "/Applications/Antigravity.app" "$HOME/Applications/Antigravity.app"; do
    if [ -d "$APP_CANDIDATE/Contents/Resources" ]; then
      FOUND_ICNS="$(find "$APP_CANDIDATE/Contents/Resources" -maxdepth 1 -name '*.icns' | head -n 1 || true)"
      if [ -n "$FOUND_ICNS" ]; then
        cp "$FOUND_ICNS" "$LAUNCHER_APP_DIR/Contents/Resources/AppIcon.icns"
        ICON_NAME="AppIcon.icns"
        break
      fi
    fi
  done

  cat > "$LAUNCHER_APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>zh_TW</string>
  <key>CFBundleExecutable</key>
  <string>launcher</string>
  <key>CFBundleIdentifier</key>
  <string>com.gj8329bot.antigravity-zh-macos</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>Antigravity 中文版</string>
  <key>CFBundleDisplayName</key>
  <string>Antigravity 中文版</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  $( [ -n "$ICON_NAME" ] && printf '<key>CFBundleIconFile</key>\n  <string>%s</string>' "$ICON_NAME" )
</dict>
</plist>
PLIST

  cat > "$LAUNCHER_APP_DIR/Contents/MacOS/launcher" <<LAUNCHER
#!/usr/bin/env bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:\$PATH"
exec "${INSTALL_DIR}/bin/antigravity-zh-macos" start
LAUNCHER
  chmod +x "$LAUNCHER_APP_DIR/Contents/MacOS/launcher"
fi

echo ""
echo "✅ 安裝完成！"
echo "   • CLI 指令: antigravity-zh-macos start（如找不到指令，請將 ${BIN_DIR} 加入 PATH）"
echo "   • 環境診斷: antigravity-zh-macos doctor"
if [ "$(uname -s)" = "Darwin" ]; then
  echo "   • 桌面圖示: ~/Applications/Antigravity 中文版.app（可於 Spotlight 搜尋或拖至 Dock）"
fi
echo "   • 原版英文 /Applications/Antigravity.app 完全未被修改，官方簽章與自動更新皆不受影響。"
