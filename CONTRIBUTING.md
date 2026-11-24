# 貢獻指南 (Contributing)

感謝你願意協助改善 **Google Antigravity macOS 無損中文化專案**！

## 1. 新增或修正翻譯詞條

詞庫檔案位於：
- 台灣繁體中文：`locales/zh-TW.json`
- 簡體中文：`locales/zh-CN.json`

編輯原則：
1. 請保持 `locales/zh-TW.json` 與 `locales/zh-CN.json` 的 `exact` 鍵值與 `patterns` 數量同步（CI 會自動驗證）。
2. `zh-TW` 請遵循台灣軟體介面常用術語（例如：檔案、資料夾、設定、終端機、剪貼簿、預設值）。
3. 專有名詞（如 `MCP`、`SSH`、`Git`、`Skills`、`Rules`、`Hooks`）可保留英文或採「中文 (英文)」對照，避免造成開發者理解困擾。

## 2. 本機執行測試

在提交 Pull Request 前，請先執行所有自動化測試：

```bash
bash -n install.sh uninstall.sh bin/antigravity-zh-macos
python3 -m unittest discover -s tests -v
node --test tests/test_overlay.mjs
```

## 3. 提交 Pull Request

1. Fork 本專案並建立功能分支（例如 `feat/add-settings-translations`）。
2. 確認所有測試皆通過。
3. 發起 Pull Request 並簡述新增或修正的介面區塊。
