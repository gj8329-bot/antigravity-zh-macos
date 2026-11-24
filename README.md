# Antigravity 中文版 for macOS (`antigravity-zh-macos`)

> **Google Antigravity macOS 專用無損開源中文化啟動器與翻譯套件**  
> 支援 **繁體中文（`zh-TW`，預設）** 與 **簡體中文（`zh-CN`）** · 支援 Apple Silicon (M1–M4) & Intel Mac · **零依賴（無需安裝 Node.js 或 pip 套件）**

[繁體中文](README.md) · [English](README.en.md) · [貢獻詞庫](CONTRIBUTING.md)

---

## ✨ 為什麼專為 macOS 設計「無損啟動器」？

傳統透過解包、修改 `/Applications/Antigravity.app/Contents/Resources/app.asar` 的中文化方式，在 macOS 上會遇到三大痛點：

1. **破壞 Apple 程式碼簽章（Code Signing）**：修改 `.app` 內部檔案會導致 macOS Gatekeeper 跳出「應用程式已損毀」警告，且每次更新後都要重新 `codesign`。
2. **自動更新覆蓋失效**：Google Antigravity 自動更新後，修改過的 `app.asar` 會立刻被還原。
3. **誤譯程式碼與對話內容**：粗暴的全域字串替換容易把程式碼片段或聊天內容誤翻成中文。

**`antigravity-zh-macos` 採用 100% 非破壞性（Non-Destructive）架構：**

| 特色 | 說明 |
| :--- | :--- |
| 🔒 **零修改原版 App** | 完全不碰 `/Applications/Antigravity.app`，完整保留 Google 官方簽章與自動更新機制 |
| 🍎 **原生 macOS 體驗** | 自動建立獨立的 `~/Applications/Antigravity 中文版.app`（支援 Spotlight、Launchpad 與 Dock），與原版英文共存 |
| 🪶 **零外部依賴** | 僅使用 macOS 內建 `bash` 與 Python 3 標準函式庫實作本機 CDP WebSocket 注入，無需安裝 Node.js 或第三方套件 |
| 🛡️ **程式碼與輸入區絕對免疫** | DOM 引擎自動排除 `code`、`pre`、Monaco/CodeMirror 編輯器、終端機與對話內文區，絕不誤傷打字與程式碼 |
| ⚡ **高效能微任務排程** | 採用 `MutationObserver` + `queueMicrotask` 批次處理與 `WeakMap` 還原快取，支援隨時切換回英文原介面 |
| 🇹🇼 / 🇨🇳 **雙語系支援** | 內建台灣繁體中文 (`zh-TW`) 與簡體中文 (`zh-CN`) 詞庫，涵蓋代理管理員、規劃模式、安全沙盒、MCP、Remote SSH 與 macOS 權限引導 |

---

## 🚀 快速安裝（macOS）

請先確認已安裝官方 [Google Antigravity](https://antigravity.google)（預設位於 `/Applications/Antigravity.app`）。

### 一行指令安裝（繁體中文 `zh-TW`）

```bash
curl -fsSL https://raw.githubusercontent.com/gj8329-bot/antigravity-zh-macos/main/install.sh | bash
```

### 安裝並預設為簡體中文（`zh-CN`）

```bash
curl -fsSL https://raw.githubusercontent.com/gj8329-bot/antigravity-zh-macos/main/install.sh | bash -s -- --lang zh-CN
```

### 從原始碼本機安裝

```bash
git clone https://github.com/gj8329-bot/antigravity-zh-macos.git
cd antigravity-zh-macos
./install.sh --lang zh-TW
```

---

## 🛠️ 使用方式

### 1. 圖形介面啟動（推薦）
安裝完成後，開啟 **Spotlight (`⌘ + Space`)** 搜尋 **`Antigravity 中文版`**，或前往 `~/Applications/Antigravity 中文版.app` 點擊啟動，也可以直接拖曳到 Dock 固定使用。

> 若需要切換回原版英文介面，直接開啟原本的 `/Applications/Antigravity.app` 即可，兩者完全獨立、互不干擾。

### 2. 終端機 CLI 指令

```bash
# 以預設語系啟動
antigravity-zh-macos start

# 臨時指定簡體中文啟動
antigravity-zh-macos start --lang zh-CN

# 永久切換預設語系
antigravity-zh-macos config --lang zh-TW

# 檢查 macOS 環境、Antigravity 版本、官方簽章與詞庫完整性
antigravity-zh-macos doctor

# 顯示詳細注入日誌（除錯用）
antigravity-zh-macos start --verbose
```

> 若終端機提示找不到 `antigravity-zh-macos`，請將 `~/.local/bin` 加入 `~/.zshrc`：
> ```bash
> echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
> ```

---

## 🧩 技術原理

1. 啟動器透過 `plistlib` 讀取 `/Applications/Antigravity.app/Contents/Info.plist` 定位原生執行檔。
2. 以僅綁定本機回環介面（`--remote-debugging-address=127.0.0.1 --remote-debugging-port=<隨機空閒埠>`）啟動 Antigravity。
3. 輕量級純 Python 守護程式 (`src/cdp_injector.py`) 透過 RFC 6455 WebSocket 連線至本機 Electron 視窗目標，使用 `Page.addScriptToEvaluateOnNewDocument` 與 `Runtime.evaluate` 動態注入 `src/overlay.js` 與對應語系詞庫 (`locales/zh-TW.json` / `locales/zh-CN.json`)。
4. 當 Antigravity 關閉時，背景守護程式會自動結束，不殘留任何常駐背景程序。

---

## 🗑️ 無痕解除安裝

```bash
curl -fsSL https://raw.githubusercontent.com/gj8329-bot/antigravity-zh-macos/main/uninstall.sh | bash -s -- --purge
```

---

## 🤝 參與貢獻

歡迎提交 Pull Request 擴充繁體中文／簡體中文詞庫或改善 macOS 體驗！詳細方式請參閱 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 📄 授權條款

本專案採用 [MIT License](LICENSE) 開源授權。本專案為社群開源中文化工具，與 Google 官方無隸屬關係。
