/**
 * 多选框「无」冲突校验
 * 目标字段：画内人声 / 唇动方式 / 非语言人声 / 画外声
 * 规则：当这些字段的多选框里同时选中了「无」和其它任意选项时，视为冲突 —— 标红并报错。
 */

const STORAGE_KEY = "ocv-settings";

const DEFAULT_SETTINGS = {
  enabled: true,
  // 需要校验的字段名（与页面 .rubric-select-label 文本一致，已去掉前导 * 和空白）
  fields: ["画内人声", "唇动方式", "非语言人声", "画外声"],
  // 被视为“无”的选项文案（命中其中之一即算“无”）
  noneValues: ["无", "无人声", "无声", "None", "none"]
};

let currentSettings = { ...DEFAULT_SETTINGS };
let observer = null;
let scanTimer = null;

const ERROR_CLASS = "ocv-error";
const MSG_CLASS = "ocv-error-msg";

function isPluginNode(node) {
  const el = node instanceof Element ? node : node?.parentElement;
  return el instanceof HTMLElement && !!el.closest(`.${MSG_CLASS}`);
}

/** 读取某个 rubric-select-item 的标签文字（去掉前导 * 与空白） */
function getItemLabel(item) {
  const labelEl = item.querySelector(".rubric-select-label");
  if (!labelEl) {
    return "";
  }
  // required-mark 是单独的 span，innerText 会带上 “*”，统一清掉
  return (labelEl.innerText || labelEl.textContent || "")
    .replace(/\*/g, "")
    .trim();
}

/** 收集某个 select-item 内当前已选中的 chip 文本 */
function getSelectedTags(item) {
  return Array.from(item.querySelectorAll(".t-tag span"))
    .map((span) => (span.innerText || span.textContent || "").trim())
    .filter(Boolean);
}

function isNoneValue(value) {
  return currentSettings.noneValues.some(
    (none) => none && value === none.trim()
  );
}

/** 判断一组已选标签是否构成冲突：包含“无” 且 同时包含非“无”的其它选项 */
function hasConflict(tags) {
  if (tags.length < 2) {
    return false;
  }
  const hasNone = tags.some((t) => isNoneValue(t));
  const hasOther = tags.some((t) => !isNoneValue(t));
  return hasNone && hasOther;
}

/** 找到 select-item 中用于标红的控件容器 */
function getControlEl(item) {
  return (
    item.querySelector(".t-select-input, .t-cascader, .t-select__wrap") || item
  );
}

function clearError(item) {
  item.classList.remove(ERROR_CLASS);
  const msg = item.querySelector(`:scope > .${MSG_CLASS}`);
  if (msg) {
    msg.remove();
  }
}

function applyError(item, label, conflictTags) {
  item.classList.add(ERROR_CLASS);

  let msg = item.querySelector(`:scope > .${MSG_CLASS}`);
  if (!msg) {
    msg = document.createElement("div");
    msg.className = MSG_CLASS;
    item.appendChild(msg);
  }

  const noneText = conflictTags.filter((t) => isNoneValue(t)).join("、");
  const otherText = conflictTags.filter((t) => !isNoneValue(t)).join("、");
  msg.textContent = `「${label}」选项冲突：「${noneText}」不能与「${otherText}」同时选择`;
}

function validate() {
  if (!currentSettings.enabled) {
    document
      .querySelectorAll(`.${ERROR_CLASS}`)
      .forEach((item) => clearError(item));
    return;
  }

  const fields = currentSettings.fields;
  let conflictCount = 0;

  document.querySelectorAll(".rubric-select-item").forEach((item) => {
    const label = getItemLabel(item);

    if (!fields.includes(label)) {
      // 非目标字段，确保没有残留错误标记
      if (item.classList.contains(ERROR_CLASS)) {
        clearError(item);
      }
      return;
    }

    const tags = getSelectedTags(item);

    if (hasConflict(tags)) {
      applyError(item, label, tags);
      conflictCount += 1;
    } else {
      clearError(item);
    }
  });

  return conflictCount;
}

function scheduleValidate() {
  window.clearTimeout(scanTimer);
  scanTimer = window.setTimeout(validate, 80);
}

async function loadSettings() {
  try {
    const stored = await chrome.storage.sync.get(STORAGE_KEY);
    currentSettings = { ...DEFAULT_SETTINGS, ...(stored[STORAGE_KEY] || {}) };
  } catch (error) {
    currentSettings = { ...DEFAULT_SETTINGS };
  }
  validate();
}

if (chrome?.storage?.onChanged) {
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "sync" || !changes[STORAGE_KEY]) {
      return;
    }
    currentSettings = {
      ...DEFAULT_SETTINGS,
      ...(changes[STORAGE_KEY].newValue || {})
    };
    validate();
  });
}

function boot() {
  loadSettings().catch(() => {
    currentSettings = { ...DEFAULT_SETTINGS };
    validate();
  });

  observer = new MutationObserver((mutations) => {
    const relevant = mutations.some((mutation) => {
      if (isPluginNode(mutation.target)) {
        return false;
      }
      const touchedNodes = [...mutation.addedNodes, ...mutation.removedNodes];
      if (touchedNodes.some((node) => isPluginNode(node))) {
        return touchedNodes.some((node) => !isPluginNode(node));
      }
      return true;
    });

    if (relevant) {
      scheduleValidate();
    }
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["class", "title", "style"]
  });
}

boot();
