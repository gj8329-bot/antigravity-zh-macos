import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const require = createRequire(import.meta.url);

const overlay = require(path.join(projectRoot, "src", "overlay.js"));
const zhTW = JSON.parse(
  fs.readFileSync(path.join(projectRoot, "locales", "zh-TW.json"), "utf-8")
);

function createMockElement(tagName, { classes = [], attrs = {}, children = [] } = {}) {
  const attrMap = new Map(Object.entries(attrs));
  const el = {
    nodeType: 1,
    tagName: tagName.toUpperCase(),
    classList: new Set(classes),
    parentElement: null,
    childNodes: [],
    hasAttribute(name) {
      return attrMap.has(name);
    },
    getAttribute(name) {
      return attrMap.get(name);
    },
    setAttribute(name, val) {
      attrMap.set(name, val);
    },
    closest(selector) {
      const parts = selector.split(",").map((s) => s.trim());
      let cur = this;
      while (cur) {
        for (const p of parts) {
          if (p.startsWith(".") && cur.classList.has(p.slice(1))) return cur;
          if (p === cur.tagName.toLowerCase()) return cur;
          if (p === "[data-antigravity-no-translate]" && cur.hasAttribute("data-antigravity-no-translate")) return cur;
          if (p === "[data-message-content]" && cur.hasAttribute("data-message-content")) return cur;
        }
        cur = cur.parentElement;
      }
      return null;
    },
  };

  for (const child of children) {
    child.parentElement = el;
    el.childNodes.push(child);
  }
  return el;
}

function createTextNode(value) {
  return {
    nodeType: 3,
    nodeValue: value,
    parentElement: null,
  };
}

test("translateText handles exact matches with surrounding whitespace", () => {
  const compiled = overlay.compileBundle(zhTW);
  assert.equal(overlay.translateText("  Agent Manager  ", compiled), "  代理管理員  ");
  assert.equal(overlay.translateText("Planning Mode", compiled), "規劃模式");
});

test("translateText handles dynamic regex patterns", () => {
  const compiled = overlay.compileBundle(zhTW);
  assert.equal(overlay.translateText("3 files changed", compiled), "已變更 3 個檔案");
  assert.equal(overlay.translateText("Step 2 of 5", compiled), "步驟 2 / 5");
  assert.equal(overlay.translateText("5 minutes ago", compiled), "5 分鐘前");
});

test("controller translates UI nodes & attributes while protecting code/chat content", () => {
  const uiButtonText = createTextNode("Accept All");
  const uiButton = createMockElement("button", {
    attrs: { title: "Apply Changes", "aria-label": "Confirm" },
    children: [uiButtonText],
  });

  const searchInput = createMockElement("input", {
    attrs: { placeholder: "Search files..." },
  });

  const codeText = createTextNode("Accept All");
  const codeBlock = createMockElement("code", { children: [codeText] });

  const chatText = createTextNode("Settings");
  const chatBubble = createMockElement("div", {
    attrs: { "data-message-content": "true" },
    children: [chatText],
  });

  const body = createMockElement("body", {
    children: [uiButton, searchInput, codeBlock, chatBubble],
  });
  const doc = { documentElement: body, body };

  const controller = overlay.createLocalizationController(doc, zhTW);
  controller.start();

  // UI elements & attributes are localized
  assert.equal(uiButtonText.nodeValue, "全部接受");
  assert.equal(uiButton.getAttribute("title"), "套用變更");
  assert.equal(uiButton.getAttribute("aria-label"), "確認");
  assert.equal(searchInput.getAttribute("placeholder"), "搜尋檔案⋯");

  // Code blocks and user/AI message content remain strictly untouched
  assert.equal(codeText.nodeValue, "Accept All");
  assert.equal(chatText.nodeValue, "Settings");

  // Restore cleanly reverts everything back to English
  controller.restore();
  assert.equal(uiButtonText.nodeValue, "Accept All");
  assert.equal(uiButton.getAttribute("title"), "Apply Changes");
  assert.equal(searchInput.getAttribute("placeholder"), "Search files...");
});
