const STORAGE_KEY = "ocv-settings";

const DEFAULT_SETTINGS = {
  enabled: true,
  fields: ["画内人声", "唇动方式", "非语言人声", "画外声"],
  noneValues: ["无", "无人声", "无声", "None", "none"]
};

const enabledInput = document.getElementById("enabled");
const fieldsInput = document.getElementById("fields");
const noneValuesInput = document.getElementById("noneValues");
const saveButton = document.getElementById("save");
const resetButton = document.getElementById("reset");
const statusEl = document.getElementById("status");

function linesToList(text) {
  return String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

async function getSettings() {
  const stored = await chrome.storage.sync.get(STORAGE_KEY);
  return { ...DEFAULT_SETTINGS, ...(stored[STORAGE_KEY] || {}) };
}

async function setSettings(settings) {
  await chrome.storage.sync.set({ [STORAGE_KEY]: settings });
}

function showStatus(message, timeout = 1800) {
  statusEl.textContent = message;
  if (timeout > 0) {
    window.clearTimeout(showStatus.timer);
    showStatus.timer = window.setTimeout(() => {
      statusEl.textContent = "";
    }, timeout);
  }
}

async function render() {
  const settings = await getSettings();
  enabledInput.checked = settings.enabled;
  fieldsInput.value = (settings.fields || []).join("\n");
  noneValuesInput.value = (settings.noneValues || []).join("\n");
}

saveButton.addEventListener("click", async () => {
  const fields = linesToList(fieldsInput.value);
  const noneValues = linesToList(noneValuesInput.value);

  const settings = {
    enabled: enabledInput.checked,
    fields: fields.length ? fields : DEFAULT_SETTINGS.fields,
    noneValues: noneValues.length ? noneValues : DEFAULT_SETTINGS.noneValues
  };

  await setSettings(settings);
  showStatus("已保存，页面校验会自动刷新");
});

resetButton.addEventListener("click", async () => {
  enabledInput.checked = DEFAULT_SETTINGS.enabled;
  fieldsInput.value = DEFAULT_SETTINGS.fields.join("\n");
  noneValuesInput.value = DEFAULT_SETTINGS.noneValues.join("\n");
  await setSettings(DEFAULT_SETTINGS);
  showStatus("已恢复默认配置");
});

render().catch((error) => {
  console.error(error);
  showStatus("读取配置失败", 0);
});
