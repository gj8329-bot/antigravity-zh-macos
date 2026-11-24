#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${ANTIGRAVITY_ZH_HOME:-$HOME/.local/share/antigravity-zh-macos}"
BIN_LINK="${HOME}/.local/bin/antigravity-zh-macos"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/antigravity-zh-macos"
LAUNCHER_APP_DIR="${HOME}/Applications/Antigravity 中文版.app"
PURGE=0

for arg in "$@"; do
  case "$arg" in
    --purge)
      PURGE=1
      ;;
    -h|--help)
      echo "用法: ./uninstall.sh [--purge]"
      echo "  --purge  同時移除使用者設定檔 (${CONFIG_DIR})"
      exit 0
      ;;
    *)
      echo "[錯誤] 未知參數: $arg" >&2
      exit 1
      ;;
  esac
done

echo "==> 解除安裝 Google Antigravity macOS 無損中文化啟動器"

if [ -L "$BIN_LINK" ] || [ -f "$BIN_LINK" ]; then
  rm -f "$BIN_LINK"
  echo "  • 已移除 CLI 連結: ${BIN_LINK}"
fi

if [ -d "$LAUNCHER_APP_DIR" ]; then
  rm -rf "$LAUNCHER_APP_DIR"
  echo "  • 已移除啟動器 App: ${LAUNCHER_APP_DIR}"
fi

if [ -d "$INSTALL_DIR" ]; then
  rm -rf "$INSTALL_DIR"
  echo "  • 已移除安裝目錄: ${INSTALL_DIR}"
fi

if [ "$PURGE" -eq 1 ] && [ -d "$CONFIG_DIR" ]; then
  rm -rf "$CONFIG_DIR"
  echo "  • 已移除設定目錄: ${CONFIG_DIR}"
fi

echo "✅ 已無痕解除安裝完成。原版 /Applications/Antigravity.app 完全未受影響。"
