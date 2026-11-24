/**
 * Google Antigravity macOS Non-Destructive DOM Localization Engine
 *
 * Designed for runtime injection via Chrome DevTools Protocol (CDP) without
 * modifying /Applications/Antigravity.app or breaking macOS code signing.
 */
(function (root) {
  "use strict";

  const VERSION = "1.0.0";
  const TRANSLATABLE_ATTRS = ["placeholder", "title", "aria-label"];

  const IMMUNE_TAGS = new Set([
    "SCRIPT",
    "STYLE",
    "NOSCRIPT",
    "TEXTAREA",
    "INPUT",
    "CODE",
    "PRE",
    "KBD",
    "SAMP",
    "VAR",
    "SVG",
    "CANVAS",
    "IFRAME",
  ]);

  const IMMUNE_SELECTOR = [
    "[data-antigravity-no-translate]",
    "[contenteditable='true']",
    "[contenteditable='']",
    ".monaco-editor",
    ".cm-editor",
    ".xterm",
    ".terminal",
    "[data-message-content]",
    ".markdown-body",
    ".prose",
    "pre",
    "code",
  ].join(",");

  function compileBundle(bundle) {
    const exactMap = new Map();
    const rawExact = (bundle && bundle.exact) || {};
    for (const key of Object.keys(rawExact)) {
      const trimmed = key.trim();
      if (trimmed) {
        exactMap.set(trimmed, rawExact[key]);
      }
    }

    const patterns = [];
    const rawPatterns = (bundle && bundle.patterns) || [];
    for (const item of rawPatterns) {
      if (!item || typeof item.pattern !== "string" || typeof item.replace !== "string") {
        continue;
      }
      try {
        patterns.push({
          regex: new RegExp(item.pattern, item.flags || ""),
          replace: item.replace,
        });
      } catch (_err) {
        // Skip invalid regex rules gracefully
      }
    }

    return {
      meta: (bundle && bundle.meta) || { locale: "zh-TW" },
      exactMap,
      patterns,
    };
  }

  function translateText(text, compiled) {
    if (typeof text !== "string" || text.length === 0) {
      return null;
    }

    const leadingMatch = text.match(/^\s*/);
    const trailingMatch = text.match(/\s*$/);
    const leading = leadingMatch ? leadingMatch[0] : "";
    const trailing = trailingMatch ? trailingMatch[0] : "";
    const core = text.slice(leading.length, text.length - trailing.length);

    if (!core || core.length > 240) {
      return null;
    }

    if (compiled.exactMap.has(core)) {
      return leading + compiled.exactMap.get(core) + trailing;
    }

    for (let i = 0; i < compiled.patterns.length; i += 1) {
      const rule = compiled.patterns[i];
      if (rule.regex.test(core)) {
        const replaced = core.replace(rule.regex, rule.replace);
        if (replaced !== core) {
          return leading + replaced + trailing;
        }
      }
    }

    return null;
  }

  function isImmuneElement(el) {
    if (!el || el.nodeType !== 1) {
      return false;
    }
    if (IMMUNE_TAGS.has(el.tagName)) {
      return true;
    }
    if (typeof el.closest === "function" && el.closest(IMMUNE_SELECTOR)) {
      return true;
    }
    return false;
  }

  function createLocalizationController(doc, bundle) {
    const compiled = compileBundle(bundle);
    const originalTextMap = new WeakMap();
    const originalAttrMap = new WeakMap();
    const translatedNodes = new Set();
    const translatedElements = new Set();

    let enabled = true;
    let observer = null;
    let pendingRoots = new Set();
    let flushScheduled = false;
    let translatedCount = 0;

    function processTextNode(node) {
      if (!enabled || !node || node.nodeType !== 3) {
        return;
      }
      const parent = node.parentElement;
      if (!parent || isImmuneElement(parent)) {
        return;
      }

      const current = node.nodeValue;
      const translated = translateText(current, compiled);
      if (translated !== null && translated !== current) {
        if (!originalTextMap.has(node)) {
          originalTextMap.set(node, current);
        }
        node.nodeValue = translated;
        translatedNodes.add(node);
        translatedCount += 1;
      }
    }

    function processElementAttributes(el) {
      if (!enabled || !el || el.nodeType !== 1) {
        return;
      }
      if (IMMUNE_TAGS.has(el.tagName) && el.tagName !== "INPUT" && el.tagName !== "TEXTAREA") {
        return;
      }
      if (el.tagName !== "INPUT" && el.tagName !== "TEXTAREA" && isImmuneElement(el)) {
        return;
      }

      for (let i = 0; i < TRANSLATABLE_ATTRS.length; i += 1) {
        const attr = TRANSLATABLE_ATTRS[i];
        if (!el.hasAttribute(attr)) {
          continue;
        }
        const current = el.getAttribute(attr);
        const translated = translateText(current, compiled);
        if (translated !== null && translated !== current) {
          let attrStore = originalAttrMap.get(el);
          if (!attrStore) {
            attrStore = new Map();
            originalAttrMap.set(el, attrStore);
          }
          if (!attrStore.has(attr)) {
            attrStore.set(attr, current);
          }
          el.setAttribute(attr, translated);
          translatedElements.add(el);
          translatedCount += 1;
        }
      }
    }

    function walkSubtree(rootNode) {
      if (!enabled || !rootNode) {
        return;
      }
      if (rootNode.nodeType === 3) {
        processTextNode(rootNode);
        return;
      }
      if (rootNode.nodeType !== 1 && rootNode.nodeType !== 9 && rootNode.nodeType !== 11) {
        return;
      }
      if (rootNode.nodeType === 1) {
        processElementAttributes(rootNode);
        if (isImmuneElement(rootNode)) {
          return;
        }
      }

      const children = rootNode.childNodes || [];
      for (let i = 0; i < children.length; i += 1) {
        walkSubtree(children[i]);
      }

      if (rootNode.shadowRoot) {
        walkSubtree(rootNode.shadowRoot);
      }
    }

    function scheduleFlush() {
      if (flushScheduled) {
        return;
      }
      flushScheduled = true;
      const run = () => {
        flushScheduled = false;
        const roots = Array.from(pendingRoots);
        pendingRoots.clear();
        for (let i = 0; i < roots.length; i += 1) {
          walkSubtree(roots[i]);
        }
      };

      if (typeof queueMicrotask === "function") {
        queueMicrotask(run);
      } else {
        setTimeout(run, 0);
      }
    }

    function start() {
      if (!doc || !doc.documentElement) {
        return;
      }
      enabled = true;
      walkSubtree(doc.body || doc.documentElement);

      if (typeof MutationObserver !== "undefined" && !observer) {
        observer = new MutationObserver((mutations) => {
          if (!enabled) {
            return;
          }
          for (let i = 0; i < mutations.length; i += 1) {
            const m = mutations[i];
            if (m.type === "characterData" && m.target) {
              pendingRoots.add(m.target);
            } else if (m.type === "attributes" && m.target) {
              pendingRoots.add(m.target);
            } else if (m.type === "childList" && m.addedNodes) {
              for (let j = 0; j < m.addedNodes.length; j += 1) {
                pendingRoots.add(m.addedNodes[j]);
              }
            }
          }
          if (pendingRoots.size > 0) {
            scheduleFlush();
          }
        });

        observer.observe(doc.documentElement, {
          childList: true,
          subtree: true,
          characterData: true,
          attributes: true,
          attributeFilter: TRANSLATABLE_ATTRS,
        });
      }
    }

    function restore() {
      enabled = false;
      translatedNodes.forEach((node) => {
        if (originalTextMap.has(node)) {
          node.nodeValue = originalTextMap.get(node);
        }
      });
      translatedElements.forEach((el) => {
        const attrStore = originalAttrMap.get(el);
        if (attrStore) {
          attrStore.forEach((origVal, attr) => {
            el.setAttribute(attr, origVal);
          });
        }
      });
    }

    function setEnabled(nextState) {
      if (nextState) {
        start();
      } else {
        restore();
      }
    }

    function toggle() {
      setEnabled(!enabled);
      return enabled;
    }

    function stats() {
      return {
        version: VERSION,
        locale: compiled.meta.locale,
        enabled,
        exactEntries: compiled.exactMap.size,
        patternEntries: compiled.patterns.length,
        translatedCount,
      };
    }

    return {
      version: VERSION,
      start,
      restore,
      setEnabled,
      toggle,
      stats,
      walkSubtree,
    };
  }

  const api = {
    VERSION,
    compileBundle,
    translateText,
    createLocalizationController,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  if (typeof window !== "undefined" && typeof document !== "undefined") {
    if (window.__antigravityZh && typeof window.__antigravityZh.restore === "function") {
      window.__antigravityZh.restore();
    }
    const bundle = window.__ANTIGRAVITY_ZH_BUNDLE__;
    if (bundle) {
      const controller = createLocalizationController(document, bundle);
      window.__antigravityZh = controller;
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => controller.start(), { once: true });
      } else {
        controller.start();
      }
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
