const $ = (id) => document.getElementById(id);
let speciesData = [];
let speciesMappingComplete = true;
let speciesNameMap = {};
let researchCatalog = [];
let researchCatalogNameMap = {};
let pokemonResearchLevels = {};
let defaultResearchLevel = "level10";
let settingsLoaded = false;
let pokemonSettingsSaveQueue = Promise.resolve();
let lastCalculation = null;
let toastTimer = null;
let engineVerified = false;
let engineProblemMessage = "";
let lastCalculationFailed = false;
let lastCalculationErrorMessage = "";
let lastAssetAvailableCount = -1;
let appearanceSaveQueue = Promise.resolve();

const RESEARCH_LABELS = {
  base: "基础研究",
  level10: "研究等级 10",
  perfect: "完美研究"
};

async function api(url, options = {}) {
  const { timeoutMs = 45000, ...requestOptions } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...requestOptions,
      headers: { "Content-Type": "application/json", ...(requestOptions.headers || {}) },
      signal: controller.signal
    });
    let data;
    try { data = await response.json(); }
    catch { throw new Error(`服务器响应不是 JSON（HTTP ${response.status}）`); }
    if (!response.ok || data.ok === false) {
      throw new Error(data.error || `请求失败（HTTP ${response.status}）`);
    }
    return data;
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(`请求超时（${Math.ceil(timeoutMs / 1000)} 秒）：${url}`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

function replayUiEntrance(node, className = "ui-soft-enter") {
  if (!node) return;
  if (node._uiEntranceCleanup) {
    node.removeEventListener("animationend", node._uiEntranceCleanup);
    node._uiEntranceCleanup = null;
  }
  node.classList.remove(className);
  // Force a style flush so repeated updates can replay the same small entrance.
  void node.offsetWidth;
  node.classList.add(className);
  const cleanup = event => {
    if (event.target !== node || event.animationName !== "plaUiSoftEnter") return;
    node.classList.remove(className);
    node.removeEventListener("animationend", cleanup);
    node._uiEntranceCleanup = null;
  };
  node._uiEntranceCleanup = cleanup;
  node.addEventListener("animationend", cleanup);
}

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  replayUiEntrance(toast);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 3200);
}

function showMessage(message, kind = "success") {
  const node = $("calculation-message");
  node.textContent = message;
  node.className = `message ${kind}`;
  node.classList.remove("hidden");
  replayUiEntrance(node);
}

function hideMessage() {
  $("calculation-message").classList.add("hidden");
}

function formatTime(value) {
  if (!value) return "—";
  return String(value).replace("T", " ").replace(/\+.*$/, "");
}

function renderSeedState(data) {
  $("current-seed").textContent = data.current_seed || "尚未读取";
  const quickSeed = $("quick-seed");
  if (quickSeed && document.activeElement !== quickSeed) quickSeed.value = data.current_seed || "";
  const status = $("seed-status");
  status.textContent = data.status || "未知状态";
  status.className = "status-pill";
  if (data.error) status.classList.add("status-error");
  else if ((data.status || "").includes("等待确认")) status.classList.add("status-pending");
  else if (data.current_seed) status.classList.add("status-success");
  else status.classList.add("status-muted");

  $("seed-source").textContent = data.source_mode === "manual"
    ? "来源：手动输入"
    : `来源：${data.source_path || "未设置文件路径"}`;
  if (data.source_mode) {
    document.querySelectorAll('input[name="source-mode"]').forEach(input => {
      input.checked = input.value === data.source_mode;
    });
  }
  $("seed-mtime").textContent = data.file_mtime || "—";
  $("seed-read-time").textContent = formatTime(data.last_successful_read_at);
  const err = $("seed-error");
  if (data.error) {
    err.textContent = data.error;
    err.classList.remove("hidden");
  } else {
    err.classList.add("hidden");
    err.textContent = "";
  }
}

async function loadSeedState() {
  const data = await api("/api/seed", { timeoutMs: 12000 });
  renderSeedState(data);
  return data;
}

let seedConfirmResolver = null;
let seedConfirmPreviousFocus = null;

function closeSeedConfirmation(accepted = false) {
  const modal = $("seed-confirm-modal");
  if (!modal || modal.classList.contains("hidden")) return;
  modal.classList.add("hidden");
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("seed-confirm-open");
  const resolver = seedConfirmResolver;
  seedConfirmResolver = null;
  if (resolver) resolver(Boolean(accepted));
  if (seedConfirmPreviousFocus && typeof seedConfirmPreviousFocus.focus === "function") {
    seedConfirmPreviousFocus.focus();
  }
  seedConfirmPreviousFocus = null;
}

function showSeedConfirmation(result, title = "确认切换 Seed", description = "检测到新的 Seed，是否应用？") {
  const modal = $("seed-confirm-modal");
  if (!modal) return Promise.resolve(false);
  if (seedConfirmResolver) closeSeedConfirmation(false);

  $("seed-confirm-title").textContent = title;
  $("seed-confirm-description").textContent = description;
  $("seed-confirm-current").textContent = String(result.previous_seed ?? "尚未读取");
  $("seed-confirm-candidate").textContent = String(result.candidate_seed ?? "未知");
  seedConfirmPreviousFocus = document.activeElement;

  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("seed-confirm-open");

  return new Promise(resolve => {
    seedConfirmResolver = resolve;
    $("seed-confirm-cancel").focus();
  });
}

$("seed-confirm-cancel").addEventListener("click", () => closeSeedConfirmation(false));
$("seed-confirm-accept").addEventListener("click", () => closeSeedConfirmation(true));
$("seed-confirm-modal").addEventListener("click", event => {
  if (event.target === $("seed-confirm-modal")) closeSeedConfirmation(false);
});

async function confirmIfNeeded(result, confirmEndpoint) {
  if (!result.needs_confirmation) {
    renderSeedState(result);
    return result;
  }
  const yes = await showSeedConfirmation(
    result,
    "检测到 Seed 变化",
    "新 Seed 与当前 Seed 不同。请确认是否切换；取消后会保留当前 Seed。"
  );
  if (!yes) {
    const cancelled = await api("/api/seed/cancel-pending", {
      method: "POST",
      body: JSON.stringify({})
    }).catch(() => null);
    if (cancelled) renderSeedState(cancelled);
    else await loadSeedState();
    showToast("已保留当前 Seed；新 Seed 未应用。");
    return result;
  }
  const confirmed = await api(confirmEndpoint, {
    method: "POST",
    body: JSON.stringify({ confirm: true, expected_seed: result.candidate_seed })
  });
  if (confirmed.needs_confirmation) {
    return confirmIfNeeded(confirmed, confirmEndpoint);
  }
  renderSeedState(confirmed);
  showToast("Seed 已切换。当前结果会保留，直到下一次计算。");
  return confirmed;
}

async function refreshSeed() {
  try {
    // Refresh always means "read the configured TXT file", regardless of the
    // previously active source. Keep the source mode and settings UI in sync.
    const path = $("seed-file-path")?.value.trim();
    if (!path) {
      showToast("尚未设置 TXT 文件路径。请先打开设置 → Seed 来源，选择或填写 TXT 文件。");
      openSettingsModal($("open-settings"));
      activateSettingsTab("seed");
      return;
    }
    await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({ seed_source_mode: "file", seed_file_path: path })
    });
    const result = await api("/api/seed/reload", {
      method: "POST",
      body: JSON.stringify({})
    });
    if (result.needs_confirmation) {
      await confirmIfNeeded(result, "/api/seed/reload");
    } else {
      renderSeedState(result);
      showToast(result.current_seed ? "已从 TXT 文件重新读取 Seed，并切换为自动读取。" : "TXT Seed 读取完成。");
    }
  } catch (error) {
    await loadSeedState().catch(() => {});
    showToast(error.message);
  }
}

async function copyText(text) {
  if (!text) {
    showToast("没有可复制的内容。");
    return;
  }
  try {
    await navigator.clipboard.writeText(String(text));
  } catch {
    const area = document.createElement("textarea");
    area.value = String(text);
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  showToast("已复制。");
}

function updateDiagnosticsBanner() {
  const banner = $("diagnostics-banner");
  if (!banner) return;
  if (!engineVerified) {
    $("diagnostics-banner-title").textContent = "本地计算引擎尚未通过验证";
    $("diagnostics-banner-message").textContent =
      `${engineProblemMessage || "本地引擎未通过验证。"} 请点击「复制诊断报告」收集完整日志。`;
    banner.classList.remove("hidden");
  } else if (lastCalculationFailed) {
    $("diagnostics-banner-title").textContent = "最近一次计算失败";
    $("diagnostics-banner-message").textContent =
      `${lastCalculationErrorMessage || "错误详情已保存到本地日志。"} 请点击「复制诊断报告」后发给开发者。`;
    banner.classList.remove("hidden");
  } else {
    banner.classList.add("hidden");
  }
}

async function copyDiagnosticsReport() {
  try {
    const data = await api("/api/diagnostics");
    await copyText(data.report || "");
    showToast("诊断报告已复制。请直接粘贴到反馈消息中；报告包含最近错误和本地日志末尾。");
  } catch (error) {
    showToast(`读取诊断报告失败：${error.message}。请手动收集 runtime_errors.log 和 offline_engine_setup.log。`);
  }
}


let settingsModalTrigger = null;
let settingsModalCloseTimer = null;
let settingsModalOpenTimer = null;

function activateSettingsTab(tabName, focus = false) {
  const allowed = new Set(["appearance", "seed", "pokemon", "resources", "help"]);
  const target = allowed.has(tabName) ? tabName : "appearance";
  document.querySelectorAll("[data-settings-tab]").forEach(button => {
    const active = button.dataset.settingsTab === target;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
    if (active && focus) button.focus();
  });
  document.querySelectorAll("[data-settings-panel]").forEach(panel => {
    const active = panel.dataset.settingsPanel === target;
    panel.classList.toggle("active", active);
    panel.classList.remove("is-entering");
    panel.hidden = !active;
    if (active) {
      // Restart a short content transition without changing the fixed dialog geometry.
      void panel.offsetWidth;
      panel.classList.add("is-entering");
    }
  });
  const tabContent = document.querySelector(".settings-tab-content");
  if (tabContent) tabContent.scrollTop = 0;
}

document.querySelectorAll("[data-settings-tab]").forEach(button => {
  button.addEventListener("click", () => activateSettingsTab(button.dataset.settingsTab));
});

function finishSettingsModalClose(modal) {
  if (settingsModalCloseTimer !== null) {
    window.clearTimeout(settingsModalCloseTimer);
    settingsModalCloseTimer = null;
  }
  modal.classList.add("hidden");
  modal.classList.remove("is-opening", "is-closing");
  modal.style.removeProperty("display");
  modal.setAttribute("aria-hidden", "true");
  modal.inert = true;
  document.body.classList.remove("settings-modal-open");
  if (settingsModalTrigger && typeof settingsModalTrigger.focus === "function") {
    settingsModalTrigger.focus();
  }
  settingsModalTrigger = null;
}

function openSettingsModal(trigger = null) {
  const modal = $("settings-modal");
  if (!modal) return;
  if (settingsModalCloseTimer !== null) {
    window.clearTimeout(settingsModalCloseTimer);
    settingsModalCloseTimer = null;
  }
  if (settingsModalOpenTimer !== null) window.clearTimeout(settingsModalOpenTimer);
  settingsModalTrigger = trigger || document.activeElement;
  activateSettingsTab(trigger?.dataset?.settingsTarget || "appearance");
  modal.classList.remove("hidden", "is-closing", "is-opening");
  modal.style.display = "grid";
  modal.inert = false;
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("settings-modal-open");
  if (!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
    void modal.offsetWidth;
    modal.classList.add("is-opening");
    settingsModalOpenTimer = window.setTimeout(() => {
      modal.classList.remove("is-opening");
      settingsModalOpenTimer = null;
    }, 240);
  }
  $("close-settings")?.focus();
}

function closeSettingsModal() {
  const modal = $("settings-modal");
  if (!modal || modal.classList.contains("hidden") || modal.classList.contains("is-closing")) return;
  if (settingsModalOpenTimer !== null) {
    window.clearTimeout(settingsModalOpenTimer);
    settingsModalOpenTimer = null;
  }
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
    finishSettingsModalClose(modal);
    return;
  }
  modal.classList.remove("is-opening");
  modal.classList.add("is-closing");
  modal.setAttribute("aria-hidden", "true");
  modal.inert = true;
  // The same close animation runs for the X button, backdrop click, and Escape.
  settingsModalCloseTimer = window.setTimeout(() => finishSettingsModalClose(modal), 200);
}

function setResultDetailsOpen(panel, button, label, shouldOpen) {
  const arrow = button.querySelector(".route-detail-arrow");
  if (panel._detailAnimationTimer) window.clearTimeout(panel._detailAnimationTimer);
  panel._detailAnimationTimer = null;
  button.classList.toggle("is-open", shouldOpen);
  button.setAttribute("aria-expanded", String(shouldOpen));
  button.setAttribute("aria-label", shouldOpen ? "收起详细操作步骤" : "展开详细操作步骤");
  label.textContent = shouldOpen ? "收起详细" : "查看详细";
  if (arrow) arrow.textContent = "⌄";
  panel.setAttribute("aria-hidden", String(!shouldOpen));
  panel.inert = !shouldOpen;

  const clearMotionStyles = () => {
    panel.style.removeProperty("max-height");
    panel.style.removeProperty("overflow");
    panel.style.removeProperty("opacity");
    panel.style.removeProperty("transform");
    panel.style.removeProperty("transition");
    panel._detailAnimationTimer = null;
  };
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
    panel.classList.toggle("hidden", !shouldOpen);
    clearMotionStyles();
    return;
  }

  panel.style.transition = "none";
  if (shouldOpen) {
    panel.classList.remove("hidden");
    panel.style.overflow = "hidden";
    panel.style.maxHeight = "0px";
    panel.style.opacity = "0";
    panel.style.transform = "translateY(-4px)";
    void panel.offsetHeight;
    panel.style.transition = "max-height 220ms cubic-bezier(.2,.7,.2,1), opacity 180ms ease, transform 220ms cubic-bezier(.2,.7,.2,1)";
    panel.style.maxHeight = `${panel.scrollHeight}px`;
    panel.style.opacity = "1";
    panel.style.transform = "translateY(0)";
    panel._detailAnimationTimer = window.setTimeout(() => {
      if (button.getAttribute("aria-expanded") === "true") clearMotionStyles();
    }, 250);
  } else {
    if (panel.classList.contains("hidden")) {
      clearMotionStyles();
      return;
    }
    panel.style.overflow = "hidden";
    panel.style.maxHeight = `${panel.getBoundingClientRect().height}px`;
    panel.style.opacity = "1";
    panel.style.transform = "translateY(0)";
    void panel.offsetHeight;
    panel.style.transition = "max-height 220ms cubic-bezier(.2,.7,.2,1), opacity 180ms ease, transform 220ms cubic-bezier(.2,.7,.2,1)";
    panel.style.maxHeight = "0px";
    panel.style.opacity = "0";
    panel.style.transform = "translateY(-4px)";
    panel._detailAnimationTimer = window.setTimeout(() => {
      if (button.getAttribute("aria-expanded") === "false") {
        panel.classList.add("hidden");
        clearMotionStyles();
      }
    }, 250);
  }
}
$("settings-modal").addEventListener("click", event => {
  if (event.target === $("settings-modal")) closeSettingsModal();
});
$("close-settings").addEventListener("click", closeSettingsModal);
// Bind each settings entry directly. The script is loaded after the page markup,
// so the gear and all shortcuts are present at binding time.
document.querySelectorAll("[data-open-settings]").forEach(trigger => {
  trigger.addEventListener("click", event => {
    event.preventDefault();
    openSettingsModal(trigger);
  });
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && $("seed-confirm-modal") && !$("seed-confirm-modal").classList.contains("hidden")) {
    closeSeedConfirmation(false);
    event.stopPropagation();
    return;
  }
  if (event.key === "Escape" && !$("settings-modal").classList.contains("hidden")) {
    closeSettingsModal();
    return;
  }
  if (!$("settings-modal").classList.contains("hidden") &&
      ["ArrowLeft", "ArrowRight"].includes(event.key) &&
      event.target?.matches?.("[data-settings-tab]")) {
    const tabs = [...document.querySelectorAll("[data-settings-tab]")];
    const index = tabs.indexOf(event.target);
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const next = tabs[(index + delta + tabs.length) % tabs.length];
    activateSettingsTab(next.dataset.settingsTab, true);
    event.preventDefault();
  }
});

function getNormalSpecies() {
  const normal = $("isnormal").checked;
  const expectedParent = normal ? "-1" : "0";
  const filtered = speciesData.filter(item => String(item.parent_id) === expectedParent);
  return filtered.length ? filtered : (speciesMappingComplete ? [] : speciesData);
}

function fillSelect(select, options, placeholder, preserveValue = true) {
  const oldValue = preserveValue ? select.value : "";
  select.innerHTML = "";
  const first = document.createElement("option");
  first.value = "";
  first.textContent = placeholder;
  select.appendChild(first);
  options.forEach(item => {
    const option = document.createElement("option");
    option.value = item.hash;
    option.textContent = item.label || item.species_zh || item.species;
    option.dataset.species = item.species;
    option.dataset.speciesZh = item.species_zh || localizePokemonName(item.species);
    option.dataset.sprite = item.sprite || "";
    option.dataset.search = `${item.species || ""} ${item.label_en || ""} ${item.species_zh || ""} ${item.label || ""}`.toLocaleLowerCase();
    select.appendChild(option);
  });
  if (oldValue && [...select.options].some(option => option.value === oldValue)) select.value = oldValue;
  refreshSearchableSelect(select);
}

function setupSearchableSelect(select) {
  if (select.dataset.searchableReady === "true") return;
  select.dataset.searchableReady = "true";
  const wrapper = document.createElement("div");
  wrapper.className = "search-select";
  const control = document.createElement("div");
  control.className = "search-select-control";
  const selectedArtWrap = document.createElement("span");
  selectedArtWrap.className = "search-select-selected-art-wrap";
  const selectedArt = document.createElement("img");
  selectedArt.className = "search-select-selected-art hidden";
  selectedArt.alt = "";
  selectedArt.setAttribute("aria-hidden", "true");
  const selectedArtFallback = document.createElement("span");
  selectedArtFallback.className = "search-select-selected-art-fallback hidden";
  selectedArtFallback.textContent = "✦";
  selectedArtFallback.setAttribute("aria-hidden", "true");
  selectedArtWrap.append(selectedArt, selectedArtFallback);
  const input = document.createElement("input");
  input.type = "text";
  input.id = `${select.id}-search-input`;
  input.className = "search-select-input";
  input.placeholder = "输入中文或英文搜索宝可梦…";
  input.autocomplete = "off";
  input.spellcheck = false;
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-label", select.id === "frpokemon" ? "搜索并选择第一轮宝可梦" : "搜索并选择第二轮宝可梦");
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "search-select-toggle";
  toggle.textContent = "▾";
  toggle.setAttribute("aria-label", "显示宝可梦候选列表");
  const list = document.createElement("div");
  list.className = "search-select-list hidden";
  list.setAttribute("role", "listbox");
  list.id = `${select.id}-search-results`;
  input.setAttribute("aria-controls", list.id);
  control.append(selectedArtWrap, input, toggle);
  const parent = select.parentNode;
  parent.insertBefore(wrapper, select);
  wrapper.append(control, list, select);
  select.classList.add("search-select-native");
  select.tabIndex = -1;

  const close = () => closeSearchableList(input);
  const open = (query = "") => {
    if (list._closeTimer) window.clearTimeout(list._closeTimer);
    list._closeTimer = null;
    renderSearchableOptions(select, input, list, query);
    list.classList.remove("hidden", "is-closing", "is-opening");
    void list.offsetWidth;
    list.classList.add("is-opening");
    input.setAttribute("aria-expanded", "true");
  };
  list.addEventListener("animationend", event => {
    if (event.target !== list) return;
    if (list.classList.contains("is-opening")) list.classList.remove("is-opening");
    if (list.classList.contains("is-closing")) {
      list.classList.add("hidden");
      list.classList.remove("is-closing");
    }
  });
  input.addEventListener("focus", () => {
    const query = input.value === selectedLabel(select) ? "" : input.value;
    input.select();
    open(query);
  });
  input.addEventListener("click", () => {
    if (list.classList.contains("hidden")) open(input.value === selectedLabel(select) ? "" : input.value);
  });
  input.addEventListener("input", () => open(input.value));
  input.addEventListener("keydown", event => {
    if (event.key === "Escape") close();
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (list.classList.contains("hidden")) open(input.value === selectedLabel(select) ? "" : input.value);
      list.querySelector(".search-select-option")?.focus();
    }
    if (event.key === "Enter") {
      const first = list.querySelector(".search-select-option");
      if (first && !list.classList.contains("hidden")) {
        event.preventDefault();
        first.click();
      }
    }
  });
  toggle.addEventListener("click", () => {
    if (list.classList.contains("hidden")) {
      input.focus();
      open("");
    } else close();
  });
  select.addEventListener("change", () => {
    input.value = selectedLabel(select);
    input.title = input.value;
    input.disabled = select.disabled;
    toggle.disabled = select.disabled;
    updateSelectedSpeciesArt(select, selectedArt);
  });
  document.addEventListener("click", event => {
    if (!wrapper.contains(event.target)) close();
  });
  refreshSearchableSelect(select);
}

function selectedLabel(select) {
  return select.selectedOptions?.[0]?.value ? select.selectedOptions[0].textContent : "";
}

function setSpriteImage(img, filename, onMissing = null, onLoad = null) {
  const candidates = spriteCandidates(filename);
  if (!img || !candidates.length) {
    if (img) {
      img.classList.add("hidden");
      delete img.dataset.spriteFilename;
      delete img._retrySprite;
    }
    if (onMissing) onMissing();
    return;
  }
  let index = 0;
  img.dataset.spriteFilename = filename;
  img._retrySprite = () => {
    index = 0;
    img.classList.remove("hidden");
    img.src = candidates[0];
  };
  img.classList.remove("hidden");
  img.onerror = () => {
    index += 1;
    if (index < candidates.length) img.src = candidates[index];
    else {
      img.classList.add("hidden");
      if (onMissing) onMissing();
    }
  };
  img.onload = () => {
    img.classList.remove("hidden");
    if (onLoad) onLoad();
  };
  img.src = candidates[0];
}

function updateSelectedSpeciesArt(select, image) {
  const option = select?.selectedOptions?.[0];
  const fallback = image?.parentElement?.querySelector(".search-select-selected-art-fallback");
  if (!image || !option?.value) {
    image?.classList.add("hidden");
    if (image) {
      image.removeAttribute("src");
      delete image.dataset.spriteFilename;
      delete image._retrySprite;
    }
    fallback?.classList.add("hidden");
    return;
  }
  if (!option.dataset.sprite) {
    image.classList.add("hidden");
    image.removeAttribute("src");
    delete image.dataset.spriteFilename;
    delete image._retrySprite;
    fallback?.classList.remove("hidden");
    return;
  }
  setSpriteImage(
    image,
    option.dataset.sprite,
    () => fallback?.classList.remove("hidden"),
    () => fallback?.classList.add("hidden")
  );
}

function retryMissingSpriteImages() {
  document.querySelectorAll("img[data-sprite-filename]").forEach(image => {
    if (image.classList.contains("hidden") || image.naturalWidth === 0) {
      if (typeof image._retrySprite === "function") image._retrySprite();
    }
  });
}

function appendCatalogOnlyMatches(select, list, normalized) {
  const empty = document.createElement("div");
  empty.className = "search-select-empty";
  const allMatches = normalized ? speciesData.filter(item => {
    if (/^Alpha\s/i.test(String(item.species || ""))) return false;
    const search = `${item.species || ""} ${item.label_en || ""} ${item.species_zh || ""} ${item.label || ""}`.toLocaleLowerCase();
    return search.includes(normalized);
  }) : [];
  const eligibleHashes = new Set([...select.options].map(option => String(option.value)));
  const uniqueMatches = new Map();
  allMatches.forEach(item => {
    if (!eligibleHashes.has(String(item.hash)) && !uniqueMatches.has(String(item.species || item.hash))) {
      uniqueMatches.set(String(item.species || item.hash), item);
    }
  });
  const otherStageMatches = [...uniqueMatches.values()].slice(0, 6);
  if (!otherStageMatches.length) {
    empty.textContent = "没有匹配的宝可梦";
    list.appendChild(empty);
    return;
  }
  empty.textContent = select.id === "frpokemon"
    ? "在本地候选数据中找到了相关宝可梦，但它不属于当前模式的第一轮可选列表。它可能只出现在特定奖励轮或形态组合中。"
    : "找到了相关宝可梦，但它不属于当前第一轮对应的奖励轮候选。请确认第一轮宝可梦与遭遇类型。";
  list.appendChild(empty);
  otherStageMatches.forEach(item => {
    const row = document.createElement("div");
    row.className = "search-select-ineligible";
    row.setAttribute("aria-disabled", "true");
    const artWrap = document.createElement("span");
    artWrap.className = "search-select-option-art-wrap";
    const art = document.createElement("img");
    art.className = "search-select-option-art hidden";
    art.alt = "";
    art.setAttribute("aria-hidden", "true");
    const fallback = document.createElement("span");
    fallback.className = "search-select-option-art-fallback";
    fallback.textContent = "✦";
    fallback.setAttribute("aria-hidden", "true");
    artWrap.append(art, fallback);
    const copy = document.createElement("span");
    copy.className = "search-select-ineligible-copy";
    const title = document.createElement("strong");
    title.textContent = item.label || item.species_zh || item.species;
    const note = document.createElement("small");
    note.textContent = `${item.label_en || item.species} · 当前轮次不可选`;
    copy.append(title, note);
    row.append(artWrap, copy);
    if (item.sprite) setSpriteImage(art, item.sprite, () => fallback.classList.remove("hidden"), () => fallback.classList.add("hidden"));
    else fallback.classList.remove("hidden");
    list.appendChild(row);
  });
}

function renderSearchableOptions(select, input, list, query) {
  list.innerHTML = "";
  const normalized = String(query || "").trim().toLocaleLowerCase();
  const options = [...select.options].slice(1).filter(option => {
    if (!normalized) return true;
    const search = option.dataset.search || `${option.textContent} ${option.dataset.species || ""}`.toLocaleLowerCase();
    return search.includes(normalized);
  }).slice(0, 80);
  if (!options.length) {
    appendCatalogOnlyMatches(select, list, normalized);
    return;
  }
  options.forEach(option => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "search-select-option";
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", String(option.value === select.value));
    const artWrap = document.createElement("span");
    artWrap.className = "search-select-option-art-wrap";
    const image = document.createElement("img");
    image.className = "search-select-option-art hidden";
    image.alt = "";
    image.setAttribute("aria-hidden", "true");
    const artFallback = document.createElement("span");
    artFallback.className = "search-select-option-art-fallback";
    artFallback.textContent = "✦";
    artFallback.setAttribute("aria-hidden", "true");
    artWrap.append(image, artFallback);
    const copy = document.createElement("span");
    copy.className = "search-select-option-copy";
    const main = document.createElement("span");
    main.className = "search-select-option-name";
    main.textContent = option.textContent;
    const english = document.createElement("small");
    english.className = "search-select-option-en";
    english.textContent = option.dataset.species || "";
    copy.append(main, english);
    button.append(artWrap, copy);
    if (option.dataset.sprite) {
      setSpriteImage(image, option.dataset.sprite, () => artFallback.classList.remove("hidden"), () => artFallback.classList.add("hidden"));
    } else {
      artFallback.classList.remove("hidden");
    }
    button.addEventListener("mousedown", event => event.preventDefault());
    button.addEventListener("click", () => {
      select.value = option.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      input.value = option.textContent;
      input.title = option.textContent;
      closeSearchableList(input);
    });
    list.appendChild(button);
  });
}

function closeSearchableList(input) {
  const wrapper = input.closest(".search-select");
  const list = wrapper?.querySelector(".search-select-list");
  input.setAttribute("aria-expanded", "false");
  if (!list || list.classList.contains("hidden") || list.classList.contains("is-closing")) return;
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
    list.classList.add("hidden");
    list.classList.remove("is-opening", "is-closing");
    return;
  }
  list.classList.remove("is-opening");
  list.classList.add("is-closing");
  if (list._closeTimer) window.clearTimeout(list._closeTimer);
  list._closeTimer = window.setTimeout(() => {
    if (list.classList.contains("is-closing")) {
      list.classList.add("hidden");
      list.classList.remove("is-closing");
    }
    list._closeTimer = null;
  }, 150);
}

function refreshSearchableSelect(select) {
  if (!select || select.dataset.searchableReady !== "true") return;
  const wrapper = select.parentElement;
  const input = wrapper.querySelector(".search-select-input");
  const toggle = wrapper.querySelector(".search-select-toggle");
  input.value = selectedLabel(select);
  input.title = input.value;
  input.disabled = select.disabled;
  updateSelectedSpeciesArt(select, wrapper.querySelector(".search-select-selected-art"));
  toggle.disabled = select.disabled;
  const list = wrapper.querySelector(".search-select-list");
  if (!list.classList.contains("hidden")) {
    renderSearchableOptions(select, input, list, input.value === selectedLabel(select) ? "" : input.value);
  }
}

function updateFirstSpecies() {
  fillSelect($("frpokemon"), getNormalSpecies(), speciesData.length ? "选择第一轮宝可梦" : "候选数据未加载");
  updateBonusSpecies();
}

function updateBonusSpecies() {
  const firstHash = $("frpokemon").value;
  let candidates = speciesData.filter(item => String(item.parent_id) === String(firstHash));
  if (!candidates.length && !speciesMappingComplete && firstHash) {
    const seen = new Set();
    candidates = speciesData.filter(item => {
      if (seen.has(String(item.hash))) return false;
      seen.add(String(item.hash));
      return true;
    });
  }
  fillSelect($("brpokemon"), candidates, firstHash ? (candidates.length ? "选择奖励轮宝可梦" : "该群体没有奖励轮候选") : "请先选择第一轮宝可梦");
  if (!$("isbonus").checked) $("brpokemon").disabled = true;
  else $("brpokemon").disabled = false;
  refreshSearchableSelect($("brpokemon"));
}

function syncAppearanceMode(refreshOptions = true) {
  const mode = $("appearance").value || "mmo_bonus";
  $("isnormal").checked = mode === "normal";
  $("isbonus").checked = mode === "mmo_bonus";

  const hint = $("mode-hint");
  if (mode === "normal") {
    hint.textContent = "普通大量出现：仅使用第一轮参数，第一轮数量选项为 10–15 只。";
  } else if (mode === "mmo") {
    hint.textContent = "大大量出现：只计算第一轮；第一轮数量选项为 8–10 只。";
  } else {
    hint.textContent = "大大量出现两波：自动启用第二轮，并填写第二轮数量与宝可梦。";
  }
  $("bonus-fields").classList.toggle("hidden", !$("isbonus").checked);
  if ($("brpokemon")) $("brpokemon").disabled = !$("isbonus").checked;
  if (refreshOptions) updateSpawnOptions();
  else refreshSearchableSelect($("brpokemon"));
}

function updateSpawnOptions() {
  const select = $("frspawns");
  const previous = select.value;
  const values = $("isnormal").checked ? [10, 11, 12, 13, 14, 15] : [8, 9, 10];
  select.innerHTML = "";
  values.forEach(value => {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = `${value} 只`;
    select.appendChild(option);
  });
  if (values.map(String).includes(previous)) select.value = previous;
  else select.value = String(values[0]);
  updateFirstSpecies();
}

function showSpeciesLoadError(message) {
  const warning = $("species-warning");
  warning.replaceChildren();
  warning.appendChild(document.createTextNode(
    `本地宝可梦候选数据不可用：${message}。请确认本地引擎已安装；也可以直接重试。`
  ));
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "btn btn-secondary species-retry-button";
  retry.textContent = "重试加载候选列表";
  retry.addEventListener("click", () => { loadSpecies(); });
  warning.appendChild(document.createTextNode(" "));
  warning.appendChild(retry);
  warning.classList.remove("hidden");
}

async function loadSpecies() {
  const warning = $("species-warning");
  try {
    const data = await api("/api/species", { timeoutMs: 12000 });
    const loadedSpecies = Array.isArray(data.species) ? data.species : [];
    if (!loadedSpecies.length) throw new Error(data.error || "候选列表为空或接口未返回 species 数组。");
    speciesData = loadedSpecies;
    speciesNameMap = data.name_map || {};
    speciesMappingComplete = data.mapping_complete !== false;
    updateSpawnOptions();
    if (data.warning) {
      warning.textContent = data.warning;
      warning.classList.remove("hidden");
    } else {
      warning.classList.add("hidden");
      warning.textContent = "";
    }
  } catch (error) {
    speciesData = [];
    updateFirstSpecies();
    showSpeciesLoadError(error?.message || "未知错误");
  }
}

function pokemonLevelDisplayLabel(value) {
  const labels = {
    base: "基础等级",
    level10: "研究等级 10",
    perfect: "完美研究"
  };
  return labels[String(value || "").trim()] || "研究等级 10";
}

function effectiveResearchLevel(species) {
  const key = String(species || "").trim().replace(/^Alpha\s+/i, "");
  if (!key) return defaultResearchLevel;
  if (Object.prototype.hasOwnProperty.call(pokemonResearchLevels, key)) {
    return pokemonResearchLevels[key];
  }
  const lookupKeys = [key];
  const formMatch = key.match(/^(.+)-\d+$/);
  if (formMatch) lookupKeys.push(formMatch[1]);
  for (const lookupKey of lookupKeys) {
    const folded = lookupKey.toLocaleLowerCase();
    const matching = Object.entries(pokemonResearchLevels).find(([name]) => String(name).trim().toLocaleLowerCase() === folded);
    if (matching) return matching[1];
  }
  return defaultResearchLevel;
}

function researchOverrideCount() {
  return Object.keys(pokemonResearchLevels).length;
}

function updateResearchCount(visibleCount = null) {
  const count = $("pokemon-research-count");
  if (!count || !researchCatalog.length) return;
  const query = String($("pokemon-research-search")?.value || "").trim();
  const visible = visibleCount == null
    ? document.querySelectorAll(".pokemon-research-row").length
    : visibleCount;
  const scope = query ? `显示 ${visible} / ${researchCatalog.length} 只` : `共 ${researchCatalog.length} 只`;
  count.textContent = `${scope} · ${researchOverrideCount()} 个单独设置`;
}

function updatePokemonBulkSummary() {
  const label = $("pokemon-default-level-label");
  if (label) label.textContent = pokemonLevelDisplayLabel(defaultResearchLevel);
  const count = $("pokemon-override-count");
  const overrides = researchOverrideCount();
  if (count) count.textContent = overrides ? `${overrides} 只宝可梦有单独设置` : "尚无单独设置";
  document.querySelectorAll("[data-research-bulk]").forEach(button => {
    button.disabled = !settingsLoaded;
    button.setAttribute("aria-pressed", String(button.dataset.researchBulk === defaultResearchLevel && overrides === 0));
  });
}

function renderResearchCatalog() {
  const list = $("pokemon-research-list");
  if (!list) return;
  if (!researchCatalog.length) {
    list.replaceChildren();
    const empty = document.createElement("div");
    empty.className = "pokemon-research-empty";
    empty.textContent = "洗翠图鉴暂时不可用。请检查本地程序文件后重启。";
    list.appendChild(empty);
    $("pokemon-research-count").textContent = "图鉴加载失败";
    return;
  }

  const query = String($("pokemon-research-search")?.value || "").trim().toLocaleLowerCase();
  const filtered = researchCatalog.filter(entry => {
    if (!query) return true;
    const haystack = `${entry.label || ""} ${entry.label_en || ""} ${entry.species || ""} ${entry.dex_number || ""}`.toLocaleLowerCase();
    return haystack.includes(query);
  });
  list.replaceChildren();
  if (!filtered.length) {
    const empty = document.createElement("div");
    empty.className = "pokemon-research-empty";
    empty.textContent = "没有找到匹配的宝可梦。";
    list.appendChild(empty);
  }

  filtered.forEach(entry => {
    const row = document.createElement("div");
    row.className = "pokemon-research-row";
    row.dataset.speciesKey = entry.species;

    const identity = document.createElement("div");
    identity.className = "pokemon-research-identity";
    const art = document.createElement("span");
    art.className = "pokemon-research-art-wrap";
    const image = document.createElement("img");
    image.className = "pokemon-research-art hidden";
    image.alt = "";
    image.loading = "lazy";
    image.decoding = "async";
    image.setAttribute("aria-hidden", "true");
    const fallback = document.createElement("span");
    fallback.className = "pokemon-research-art-fallback";
    fallback.textContent = "✦";
    fallback.setAttribute("aria-hidden", "true");
    art.append(image, fallback);
    setSpriteImage(image, entry.sprite, () => fallback.classList.remove("hidden"), () => fallback.classList.add("hidden"));

    const copy = document.createElement("span");
    copy.className = "pokemon-research-copy";
    const name = document.createElement("strong");
    name.textContent = entry.label || localizePokemonName(entry.species);
    const english = document.createElement("small");
    english.textContent = `#${String(entry.dex_number).padStart(3, "0")} · ${entry.label_en || entry.species}`;
    copy.append(name, english);
    identity.append(art, copy);

    const levels = document.createElement("div");
    levels.className = "pokemon-research-options";
    const selectedLevel = effectiveResearchLevel(entry.species);
    const choices = [
      ["base", "基础"],
      ["level10", "等级 10"],
      ["perfect", "完美"]
    ];
    choices.forEach(([value, label]) => {
      const optionLabel = document.createElement("label");
      optionLabel.className = "pokemon-research-option";
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = `pokemon-research-${entry.dex_number}`;
      radio.value = value;
      radio.checked = selectedLevel === value;
      radio.disabled = !settingsLoaded;
      radio.dataset.speciesKey = entry.species;
      radio.dataset.researchLevel = value;
      radio.setAttribute("aria-label", `${entry.label}：${label}`);
      const text = document.createElement("span");
      text.textContent = label;
      optionLabel.append(radio, text);
      levels.appendChild(optionLabel);
    });

    const overrideBadge = document.createElement("span");
    overrideBadge.className = "pokemon-research-override-badge";
    overrideBadge.textContent = Object.prototype.hasOwnProperty.call(pokemonResearchLevels, entry.species) ? "单独设置" : "";
    overrideBadge.classList.toggle("hidden", !overrideBadge.textContent);
    row.append(identity, levels, overrideBadge);
    list.appendChild(row);
  });

  updateResearchCount(filtered.length);
  updatePokemonBulkSummary();
}

async function loadResearchCatalog() {
  try {
    const data = await api("/api/pokemon-catalog", { timeoutMs: 12000 });
    researchCatalog = Array.isArray(data.species) ? data.species : [];
    researchCatalogNameMap = Object.fromEntries(researchCatalog.map(entry => [entry.species, entry.label]));
    renderResearchCatalog();
  } catch (error) {
    researchCatalog = [];
    renderResearchCatalog();
    showToast(`宝可梦研究等级列表加载失败：${error.message}`);
  }
}

function localizePokemonName(value) {
  const raw = String(value ?? "").trim();
  if (speciesNameMap[raw]) return speciesNameMap[raw];
  if (researchCatalogNameMap[raw]) return researchCatalogNameMap[raw];
  if (raw.startsWith("Alpha ")) return `头目${localizePokemonName(raw.slice(6))}`;
  if (raw.startsWith("Hisuian ")) return `洗翠${localizePokemonName(raw.slice(8))}`;
  if (raw.endsWith(" (Hisuian)")) return speciesNameMap[raw] || `洗翠${localizePokemonName(raw.slice(0, -10))}`;
  // The local RNG engine uses internal form IDs such as Growlithe-1 and Basculin-2.
  // Convert known Hisui form IDs to the same localized keys used by the species table.
  const formMatch = raw.match(/^(.+)-(\d+)$/);
  if (formMatch) {
    const base = formMatch[1];
    const formId = formMatch[2];
    if (formId === "1") {
      const mapped = speciesNameMap[`${base} (Hisuian)`] || speciesNameMap[`Hisuian ${base}`];
      if (mapped) return mapped;
    }
    if (formId === "2") {
      const mapped = speciesNameMap[`${base} (White-Striped)`] || speciesNameMap[`White-Striped ${base}`];
      if (mapped) return mapped;
    }
    return `${localizePokemonName(base)}（特殊形态）`;
  }
  return raw;
}

function localizeAreaName(value) {
  const raw = String(value ?? "").trim();
  const known = {
    "Obsidian Fieldlands": "黑曜原野",
    "Crimson Mirelands": "红莲湿地",
    "Cobalt Coastlands": "群青海岸",
    "Coronet Highlands": "天冠山麓",
    "Alabaster Icelands": "纯白冻土",
    "Jubilife Village": "祝庆村",
    "From Seed": "根据 Seed 计算"
  };
  return known[raw] || raw;
}

function selectedSpeciesName(selectId) {
  const select = $(selectId);
  const option = select.options[select.selectedIndex];
  return option?.dataset?.species || option?.textContent || "";
}

function setBusy(busy) {
  $("calculate-button").disabled = busy;
  $("calculate-button").textContent = busy ? "正在计算…" : "计算路径";
}

function isTruthyField(value) {
  if (value === true || value === 1) return true;
  if (typeof value === "string") return ["true", "yes", "1", "shiny", "alpha", "square", "square shiny", "square_shiny", "方块闪", "头目"].includes(value.toLowerCase());
  return false;
}

function firstValue(item, aliases) {
  if (!item || typeof item !== "object" || Array.isArray(item)) return undefined;
  const keys = Object.keys(item);
  for (const alias of aliases) {
    const key = keys.find(k => k.toLowerCase() === alias.toLowerCase());
    if (key !== undefined) return item[key];
  }
  return undefined;
}

function stringifyValue(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value, null, 2);
}

function normalizeResults(results) {
  if (Array.isArray(results)) return results;
  if (results && typeof results === "object") {
    const nested = firstValue(results, ["results", "items", "encounters", "paths"]);
    if (Array.isArray(nested)) return nested;
    return Object.entries(results).map(([key, value]) => {
      if (value && typeof value === "object" && !Array.isArray(value)) return { key, ...value };
      return { key, value };
    });
  }
  return [];
}

function formatResultPath(value) {
  if (Array.isArray(value)) return value.map(part => typeof part === "string" ? part : stringifyValue(part)).join(" / ");
  return stringifyValue(value);
}

function appendTextElement(parent, tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  parent.appendChild(element);
  return element;
}

function resultList(value) {
  return PLAResultView.listify(value);
}

function displaySpeciesTitle(species, isAlpha) {
  const localized = localizePokemonName(stringifyValue(species));
  if (isAlpha && localized && !localized.startsWith("头目")) return `头目${localized}`;
  return localized;
}

function extractIVValues(value) {
  if (Array.isArray(value)) return value.slice(0, 6);
  if (value === null || value === undefined || value === "") return [];
  const trimmed = String(value).trim();
  if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) return parsed.slice(0, 6);
    } catch { /* fall through to delimiter parsing */ }
  }
  return trimmed.split(/[\s,/|]+/).filter(Boolean).map(part => part.replace(/^\[|\]$/g, "")).slice(0, 6);
}

function getIVTier(value) {
  const values = extractIVValues(value).map(Number).filter(Number.isFinite);
  if (values.length !== 6) return "";
  const perfectCount = values.filter(number => number === 31).length;
  if (perfectCount === 6) return "6V";
  if (perfectCount === 5) return "5V";
  if (perfectCount === 4) return "4V";
  return "";
}

function renderIVValues(parent, value) {
  const values = extractIVValues(value);
  if (!values.length) {
    appendTextElement(parent, "span", "result-extra-value", value == null ? "—" : stringifyValue(value));
    return;
  }
  const ivRow = appendTextElement(parent, "div", "result-iv-row");
  const statNames = ["HP", "攻击", "防御", "特攻", "特防", "速度"];
  values.forEach((raw, index) => {
    const number = Number(raw);
    const chip = appendTextElement(ivRow, "span", `iv-chip${number === 31 ? " iv-perfect" : ""}`, raw);
    chip.title = statNames[index] || `个体值 ${index + 1}`;
    chip.setAttribute("aria-label", `${chip.title}：${raw}`);
  });
}

function appendRouteStepChips(parent, steps) {
  if (Array.isArray(steps) && steps.length) {
    steps.forEach(step => appendTextElement(parent, "span", "result-route-chip", `D${step}`));
  } else {
    appendTextElement(parent, "span", "result-route-empty", "—");
  }
}

function appendMetric(parent, label, value, kind = "text") {
  const metric = appendTextElement(parent, "div", "summary-metric");
  appendTextElement(metric, "div", "summary-label", label);
  const valueNode = appendTextElement(metric, "div", `summary-value${kind === "chips" ? " summary-value-chips" : ""}`);
  if (kind === "chips" && Array.isArray(value) && value.length) {
    value.forEach(step => appendTextElement(valueNode, "span", "result-route-chip", `D${step}`));
  } else {
    appendTextElement(valueNode, "span", kind === "number" ? "summary-number" : "summary-text", String(value ?? "—"));
  }
  return metric;
}

function renderRouteSummary(parent, routeSummary) {
  const path = routeSummary.path;
  const grid = appendTextElement(parent, "div", "result-summary-grid");
  if (path.hasBonus) {
    appendMetric(grid, "第一轮路径", path.firstRound, "chips");
    appendMetric(
      grid,
      path.revisit.length ? "重新访问 · 剩余数量" : "轮次切换",
      path.revisit.length ? `[ ${path.revisit.join(", ")} ]` : (path.clearRound ? "清空后进入第二轮" : "进入第二轮"),
      "text"
    );
    if (path.bonusInitialSpawn) {
      appendMetric(grid, "第二轮目标位置", `第 ${path.bonusInitialSpawn} 只`, "number");
    } else {
      appendMetric(grid, "第二轮路径", path.bonus, "chips");
    }
  } else if (path.isInitialSpawn) {
    appendMetric(grid, "目标生成位置", `第 ${path.initialSpawn} 只`, "number");
    appendMetric(grid, "目标出现时机", "初始生成", "text");
    appendMetric(grid, "额外清除步骤", "无需执行", "text");
  } else {
    appendMetric(grid, "第一轮路径", path.ordinary, "chips");
    appendMetric(grid, "目标出现时机", "完成最后一步后", "text");
    appendMetric(grid, "路径操作数", `${path.ordinary.length} 步`, "text");
  }

  if (routeSummary.chains.length) {
    const simultaneous = appendTextElement(parent, "div", "result-simultaneous has-simultaneous");
    appendTextElement(simultaneous, "strong", "result-simultaneous-label", "同时闪光路线");
    const list = appendTextElement(simultaneous, "ul", "result-path-chip-list");
    [...new Set(routeSummary.chains)].forEach(pathText => appendTextElement(list, "li", "result-path-chip", pathText));
  }
  return grid;
}

function renderOperationStepList(parent, steps, options = {}) {
  if (!Array.isArray(steps) || !steps.length) return;
  const list = appendTextElement(parent, "ol", "operation-step-list");
  steps.forEach(step => {
    const li = appendTextElement(list, "li", "operation-step");
    appendTextElement(li, "span", "operation-step-number", String(step.number));
    const content = appendTextElement(li, "div", "operation-step-content");
    const mainLine = appendTextElement(content, "div", "operation-step-mainline");
    appendTextElement(mainLine, "span", "operation-count", step.pathStep || `D${step.count}`);
    appendTextElement(mainLine, "strong", "operation-step-title", step.title || (step.count === 1 ? "清除 1 只" : `一次清除 ${step.count} 只`));
    appendTextElement(content, "span", "operation-cumulative", `本段累计 ${step.cumulative} 只`);
  });
}

function renderOperationDetails(item, routeSummary) {
  const details = document.createElement("div");
  details.className = "result-details operation-details operation-details-content";
  const operations = PLAResultView.buildOperationSections(item);
  if (!operations.sections.length) {
    appendTextElement(details, "p", "operation-empty", "引擎没有返回可解析的路径步骤。可展开原始数据核对路径字段；不会用演示路线替代计算结果。");
  }

  const timeline = appendTextElement(details, "div", "operation-timeline");
  let phaseNumber = 0;
  operations.sections.forEach(section => {
    phaseNumber += 1;
    const sectionClass = section.targetEvent ? " operation-target-event" : (section.targetWarning ? " operation-target-warning" : "");
    const sectionEl = appendTextElement(timeline, "section", `operation-section${sectionClass}`);
    const sectionHead = appendTextElement(sectionEl, "div", "operation-section-head");
    const phaseMarker = section.targetEvent ? "✦" : (section.targetWarning ? "!" : String(phaseNumber));
    appendTextElement(sectionHead, "span", `operation-phase-number${section.targetEvent ? " is-target" : ""}`, phaseMarker);
    const titleWrap = appendTextElement(sectionHead, "div", "operation-section-title-wrap");
    appendTextElement(titleWrap, "h4", "operation-section-title", section.title);
    if (section.note) appendTextElement(titleWrap, "p", "operation-section-note", section.note);

    if (section.revisitMarkers?.length) {
      const revisitOrder = appendTextElement(sectionEl, "div", "revisit-instruction-list");
      section.revisitMarkers.forEach((marker, index) => {
        const item = appendTextElement(revisitOrder, "div", "revisit-instruction");
        appendTextElement(item, "span", "revisit-instruction-number", String(index + 1));
        const copy = appendTextElement(item, "div", "revisit-instruction-copy");
        appendTextElement(copy, "strong", "revisit-instruction-title", marker.title || `群聚剩余 ${marker.marker} 只时`);
        appendTextElement(copy, "span", "revisit-instruction-description", marker.description || "离开群聚点至少 120 米，再返回群聚点。");
        if (index < section.revisitMarkers.length - 1) {
          appendTextElement(revisitOrder, "div", "revisit-instruction-connector", "↓");
        }
      });
      if (section.methodNote) appendTextElement(sectionEl, "p", "operation-section-note revisit-method-note", section.methodNote);
    }
    renderOperationStepList(sectionEl, section.steps);
  });

  if (operations.chainOperations.length) {
    const simultaneousSection = appendTextElement(timeline, "section", "operation-section simultaneous-detail-section");
    const sectionHead = appendTextElement(simultaneousSection, "div", "operation-section-head");
    appendTextElement(sectionHead, "span", "operation-phase-number", "＋");
    const titleWrap = appendTextElement(sectionHead, "div", "operation-section-title-wrap");
    appendTextElement(titleWrap, "h4", "operation-section-title", "同时闪光路线");
    appendTextElement(titleWrap, "p", "operation-section-note", "这些是可能同时出现闪光的其他目标路线，不代表同一目标的替代路线。");
    operations.chainOperations.forEach(chain => {
      const chainBlock = appendTextElement(simultaneousSection, "div", "simultaneous-operation-block");
      appendTextElement(chainBlock, "h5", "simultaneous-operation-title", chain.label);
      renderOperationStepList(chainBlock, chain.steps);
      if (chain.revisit?.length) {
        appendTextElement(chainBlock, "p", "operation-section-note", `重访顺序 [${chain.revisit.join(", ")}] 表示群聚剩余数量阈值：依次等到剩余 ${chain.revisit.join("、")} 只时，离开群聚点至少 120 米再返回；数字不是要清除的数量。`);
      }
      if (chain.clearRound) {
        appendTextElement(chainBlock, "p", "operation-section-note", "完成第一轮后清空剩余宝可梦，再进入第二轮。");
      }
      if (chain.bonus.length) {
        appendTextElement(chainBlock, "h5", "simultaneous-operation-title", "第二轮操作");
        const bonusSteps = chain.bonus.map((count, index) => ({
          number: index + 1,
          count,
          pathStep: `D${count}`,
          title: count === 1 ? "清除 1 只" : `一次清除 ${count} 只`,
          cumulative: chain.bonus.slice(0, index + 1).reduce((sum, value) => sum + value, 0)
        }));
        renderOperationStepList(chainBlock, bonusSteps);
      }
      const targetNote = chain.initialSpawn
        ? `目标位于初始生成第 ${chain.initialSpawn} 只。`
        : chain.bonusInitialSpawn
          ? `目标位于第二轮初始生成第 ${chain.bonusInitialSpawn} 只。`
          : `目标时机：${chain.targetTiming}。`;
      appendTextElement(chainBlock, "p", "operation-target-note", targetNote);
    });
  }

  // Keep engine-provided `dupes` in the raw result data for diagnostics, but do not
  // show a non-standard "other reachable path" panel in the official-style UI.
  // Alternative path metadata is not an additional shiny target or a required step.

  const rawDetails = appendTextElement(details, "details", "result-raw-details");
  appendTextElement(rawDetails, "summary", "", "查看原始路径数据");
  appendTextElement(rawDetails, "pre", "result-raw-json", JSON.stringify(item, null, 2));
  return details;
}

function applyResultFilters() {
  const shinyOnly = $("show-only-shiny")?.checked || false;
  const alphaOnly = $("show-only-alpha")?.checked || false;
  const defaultOnly = $("show-default-path")?.checked || false;
  const multiOnly = $("show-multi-path")?.checked || false;
  const cards = [...document.querySelectorAll("#results-list .result-card")];
  cards.forEach(card => {
    let show = true;
    if (shinyOnly && card.dataset.shiny === "false") show = false;
    if (alphaOnly && card.dataset.alpha === "false") show = false;
    if (defaultOnly && card.dataset.defaultPath !== "true") show = false;
    if (multiOnly && card.dataset.multiPath !== "true") show = false;
    card.classList.toggle("filtered-out", !show);
  });
  const visibleCount = cards.filter(card => !card.classList.contains("filtered-out")).length;
  const count = $("result-count");
  if (count) {
    const nextText = (shinyOnly || alphaOnly || defaultOnly || multiOnly)
      ? `显示 ${visibleCount} / ${cards.length} 条`
      : `${cards.length} 条结果`;
    if (count.textContent !== nextText) {
      count.textContent = nextText;
      replayUiEntrance(count);
    }
  }
}

function spriteCandidates(rawSprite) {
  const filename = String(rawSprite || "").trim();
  // Form, sex and shiny suffixes are semantically meaningful. Never display a
  // different form or normal-color sprite as if it were the requested target.
  if (!/^(c_\d+(?:-\d+)?f?s?)\.png$/i.test(filename)) return [];
  return [`/user-assets/custom/${filename}`, `/user-assets/cache/${filename}`];
}

function researchLevelLabel(value) {
  const labels = {
    base: "基础研究",
    level10: "研究等级 10",
    perfect: "完美研究"
  };
  return labels[String(value || "").trim()] || "—";
}

function speciesIdentityValues(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return [];
  const withoutAlpha = raw.replace(/^Alpha\s+/i, "").trim();
  const localizedRaw = localizePokemonName(raw);
  const localizedBase = localizePokemonName(withoutAlpha);
  return [...new Set([raw, withoutAlpha, localizedRaw, localizedBase]
    .map(value => String(value || "").replace(/^头目\s*/, "").trim().toLocaleLowerCase())
    .filter(Boolean))];
}

function sameSpeciesIdentity(left, right) {
  const leftKeys = speciesIdentityValues(left);
  const rightKeys = new Set(speciesIdentityValues(right));
  return leftKeys.some(key => rightKeys.has(key));
}

function researchLevelForSpecies(params, species, round) {
  if (!species) return "";
  const explicit = params?.[`${round}_research_level`];
  if (explicit) return explicit;

  const levels = params?.research_levels;
  if (levels && typeof levels === "object") {
    if (levels[species]) return levels[species];
    const entry = Object.entries(levels).find(([key]) => sameSpeciesIdentity(key, species));
    if (entry) return entry[1];
  }

  // Older result payloads may omit the research-level map. Use the current form
  // only when the selected species is the same as the species being resolved.
  const speciesSelectId = round === "br" ? "brpokemon" : "frpokemon";
  const selectedSpecies = typeof selectedSpeciesName === "function"
    ? selectedSpeciesName(speciesSelectId)
    : "";
  if (selectedSpecies && sameSpeciesIdentity(selectedSpecies, species)) {
    return effectiveResearchLevel(selectedSpecies);
  }
  return "";
}

function resultResearchContext(item, params) {
  const resultSpecies = String(firstValue(item, ["species", "pokemon", "name", "encounter", "mon", "key"]) || "")
    .replace(/^Alpha\s+/i, "")
    .trim();
  const candidates = [
    {
      species: params.fr_species,
      level: researchLevelForSpecies(params, params.fr_species, "fr")
    },
    {
      species: params.br_species,
      level: researchLevelForSpecies(params, params.br_species, "br")
    }
  ].filter(entry => entry.species);

  const match = candidates.find(entry => sameSpeciesIdentity(entry.species, resultSpecies));
  if (match) {
    return {
      species: localizePokemonName(match.species),
      level: researchLevelLabel(match.level)
    };
  }

  // If the engine returns a variant/form label that does not exactly match its
  // encounter table key, a single-round result can still be unambiguously tied
  // to the only selected species. Never guess between two different rounds.
  if (candidates.length === 1) {
    return {
      species: localizePokemonName(candidates[0].species),
      level: researchLevelLabel(candidates[0].level)
    };
  }
  return null;
}

function renderCalculationSettingsSummary(params) {
  const node = $("result-settings-summary");
  if (!node) return;
  const candidates = [
    { species: params?.fr_species, level: researchLevelForSpecies(params, params?.fr_species, "fr") },
    { species: params?.br_species, level: researchLevelForSpecies(params, params?.br_species, "br") }
  ].filter(entry => String(entry.species || "").trim());
  const unique = [];
  candidates.forEach(entry => {
    if (unique.some(existing => sameSpeciesIdentity(existing.species, entry.species))) return;
    unique.push(entry);
  });
  const levelText = unique.map(entry => {
    const species = localizePokemonName(String(entry.species).replace(/^Alpha\s+/i, ""));
    return `${species} ${researchLevelLabel(entry.level)}`;
  });
  const charmText = params?.shiny_charm ? "有" : "无";
  // Keep the separators authored as plain text; no HTML is inserted from names.
  node.textContent = `本次计算参数：${levelText.join("，")}，闪耀护符：${charmText}`;
  node.classList.remove("hidden");
  replayUiEntrance(node);
}

function addPokemonArtwork(parent, item, title) {
  const frame = appendTextElement(parent, "div", "pokemon-art-frame");
  const fallback = appendTextElement(frame, "div", "pokemon-art-fallback", "✦");
  fallback.setAttribute("aria-hidden", "true");
  const rawSprite = firstValue(item, ["sprite", "sprite_file", "spritefile"]);
  const rawSpecies = String(firstValue(item, ["species", "pokemon", "name", "encounter", "mon", "key"]) || "")
    .replace(/^Alpha\s+/i, "").trim().toLocaleLowerCase();
  const candidate = speciesData.find(entry =>
    String(entry.species || "").trim().toLocaleLowerCase() === rawSpecies ||
    String(entry.label_en || "").replace(/^Alpha\s+/i, "").trim().toLocaleLowerCase() === rawSpecies
  );
  const sprite = rawSprite || candidate?.sprite || "";
  const candidates = spriteCandidates(sprite);
  if (!candidates.length) {
    appendTextElement(frame, "span", "pokemon-art-caption", "图片未安装");
    return frame;
  }
  const img = document.createElement("img");
  img.className = "pokemon-art-image";
  img.alt = `${title}宝可梦图片`;
  img.loading = "lazy";
  img.decoding = "async";
  let cursor = 0;
  img.addEventListener("load", () => {
    fallback.classList.add("hidden");
    frame.classList.add("has-image");
    frame.querySelectorAll(".pokemon-art-caption").forEach(node => node.remove());
  });
  img.addEventListener("error", () => {
    cursor += 1;
    if (cursor < candidates.length) img.src = candidates[cursor];
    else {
      img.classList.add("hidden");
      if (!frame.querySelector(".pokemon-art-caption")) {
        appendTextElement(frame, "span", "pokemon-art-caption", "图片未安装");
      }
    }
  });
  img.dataset.spriteFilename = sprite;
  img._retrySprite = () => { cursor = 0; img.classList.remove("hidden"); img.src = candidates[0]; };
  img.src = candidates[0];
  frame.appendChild(img);
  return frame;
}

function renderResults(data) {
  lastCalculation = data;
  const list = $("results-list");
  list.innerHTML = "";
  const items = normalizeResults(data.results);
  const params = data.params || {};
  const appearance = params.isnormal ? "普通大量出现" : (params.isbonus ? "大大量出现两波" : "大大量出现");
  $("result-count").textContent = `${items.length} 条结果`;
  $("results-caption").textContent = `Seed ${data.seed} · ${appearance}`;
  replayUiEntrance($("result-count"));
  replayUiEntrance($("results-caption"));
  renderCalculationSettingsSummary(params);

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state panel result-empty-entering";
    empty.innerHTML = "<div class='empty-icon'>✦</div><h3>本次没有符合条件的结果</h3><p>计算已正常完成。可以调整计算筛选条件或群体参数后重新计算；研究等级可在设置中心的「宝可梦设置」中修改。不会用演示数据替代真实结果。</p>";
    empty.addEventListener("animationend", event => {
      if (event.target === empty && event.animationName === "plaResultCardEnter") {
        empty.classList.remove("result-empty-entering");
      }
    });
    list.appendChild(empty);
    return;
  }

  items.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "result-card result-card-editorial result-card-entering";
    card.style.setProperty("--result-enter-delay", `${Math.min(index * 36, 180)}ms`);

    const species = firstValue(item, ["species", "pokemon", "name", "encounter", "mon", "key"]);
    const area = firstValue(item, ["mapname", "map_name", "location", "area", "map"]);
    const shiny = firstValue(item, ["shiny", "is_shiny", "isshiny", "shiny_status"]);
    const square = firstValue(item, ["square", "is_square", "square_shiny", "is_square_shiny", "squares shiny"]);
    const alpha = firstValue(item, ["alpha", "is_alpha", "isalpha", "isAlpha"]);
    const defaultPath = firstValue(item, ["default_path", "defaultpath", "default_route", "defaultroute"]);
    const routeSummary = PLAResultView.buildRouteSummary(item);
    const isSquare = isTruthyField(square);
    const isShiny = isTruthyField(shiny) || isSquare;
    const isAlpha = alpha === undefined ? /^Alpha\s/i.test(String(species ?? "")) : isTruthyField(alpha);
    const multiPath = routeSummary.hasMultiple;
    const hasDefaultPath = isTruthyField(defaultPath);
    const ivs = firstValue(item, ["ivs", "individual_values", "individualvalues", "iv"]);
    const ivTier = getIVTier(ivs);
    const displayName = species !== undefined ? displaySpeciesTitle(species, isAlpha) : `结果 ${index + 1}`;

    card.dataset.shiny = shiny === undefined && square === undefined ? "unknown" : (isShiny ? "true" : "false");
    card.dataset.alpha = alpha === undefined ? "unknown" : (isAlpha ? "true" : "false");
    card.dataset.defaultPath = hasDefaultPath ? "true" : "false";
    card.dataset.multiPath = multiPath ? "true" : "false";
    card.dataset.routeKey = routeSummary.path.routeKey;

    const hero = appendTextElement(card, "div", "result-hero");
    addPokemonArtwork(hero, item, displayName);
    const heroCopy = appendTextElement(hero, "div", "result-hero-copy");
    const titleRow = appendTextElement(heroCopy, "div", "result-title-row");
    appendTextElement(titleRow, "h3", "result-title", `${displayName} #${index + 1}`);

    const statusLine = appendTextElement(heroCopy, "div", "result-status-line");
    if (isSquare) {
      appendTextElement(statusLine, "span", "result-status-tag status-square", "✦ 方块闪");
    } else {
      appendTextElement(statusLine, "span", `result-status-tag ${isShiny ? "status-shiny" : "status-not-shiny"}`, isShiny ? "✦ 闪光" : "未闪光");
    }
    appendTextElement(statusLine, "span", `result-status-tag ${isAlpha ? "status-alpha" : "status-normal"}`, isAlpha ? "头目（Alpha）" : "普通个体");
    if (ivTier) appendTextElement(statusLine, "span", `result-status-tag status-iv ${ivTier === "6V" ? "status-6v" : ivTier === "5V" ? "status-5v" : "status-4v"}`, ivTier);
    if (multiPath) {
      const multiCount = routeSummary.multiShinyCount;
      appendTextElement(statusLine, "span", "result-status-tag status-multi",
        multiCount ? `同路径多闪 ×${multiCount}` : "同路径多闪");
    }
    if (hasDefaultPath) appendTextElement(statusLine, "span", "result-status-tag status-default", "默认路径");

    const localizedArea = area === undefined ? "" : localizeAreaName(stringifyValue(area));
    const subtitle = localizedArea && !["根据 Seed 计算", "from seed", ""].includes(localizedArea)
      ? `出现区域 · ${localizedArea}`
      : (isShiny ? "已计算出闪光目标路线" : "已计算出目标路线");
    appendTextElement(heroCopy, "p", "result-subtitle", subtitle);

    const infoHeading = appendTextElement(card, "div", "result-section-heading result-info-heading");
    appendTextElement(infoHeading, "h4", "result-section-title", "宝可梦信息");
    const extra = appendTextElement(card, "div", "result-meta-strip");
    const nature = firstValue(item, ["nature", "personality"]);
    const gender = firstValue(item, ["gender", "sex"]);
    const rolls = firstValue(item, ["rolls", "shiny_attempts", "shiny_attempt_count", "shinyrolls", "shiny_checks"]);
    const metaField = (label, value) => {
      const field = appendTextElement(extra, "div", "result-meta-field");
      appendTextElement(field, "span", "result-meta-label", label);
      appendTextElement(field, "strong", "result-meta-value", value == null ? "—" : String(value));
      return field;
    };
    metaField("性格", PLAResultView.localizeNature(nature));
    metaField("性别", PLAResultView.localizeGender(gender));
    metaField("闪光判定", rolls === undefined ? "—" : `${stringifyValue(rolls)} 次`);
    const ivField = appendTextElement(extra, "div", "result-meta-field result-iv-field");
    appendTextElement(ivField, "span", "result-meta-label", "个体值");
    renderIVValues(ivField, ivs);

    const pathHeading = appendTextElement(card, "div", "result-section-heading result-path-heading");
    appendTextElement(pathHeading, "h4", "result-section-title", "路径概要");
    const summaryWrap = appendTextElement(card, "div", "result-route-overview");
    renderRouteSummary(summaryWrap, routeSummary);

    const detailHeading = appendTextElement(card, "div", "result-detail-heading");
    const detailTitle = appendTextElement(detailHeading, "div", "result-detail-title-wrap");
    appendTextElement(detailTitle, "h4", "result-detail-title", "详细步骤");
    const detailActions = appendTextElement(detailHeading, "div", "result-detail-actions");
    const detailsButton = document.createElement("button");
    detailsButton.className = "route-detail-button";
    detailsButton.type = "button";
    detailsButton.setAttribute("aria-expanded", "false");
    detailsButton.setAttribute("aria-label", "展开详细操作步骤");
    appendTextElement(detailsButton, "span", "route-detail-arrow", "⌄");
    const detailButtonLabel = appendTextElement(detailsButton, "span", "route-detail-label", "查看详细");
    detailActions.appendChild(detailsButton);

    // Keep the existing copy-summary action, but move it into the compact action row.
    const copy = document.createElement("button");
    copy.className = "text-button copy-path";
    copy.type = "button";
    copy.textContent = "复制路径";
    copy.addEventListener("click", () => {
      const text = routeSummary.lines.map(line => `${line.label}：${line.value}`).join("\n")
        + (routeSummary.chains.length ? `\n同时闪光：\n${routeSummary.chains.join("\n")}` : "");
      copyText(text || routeSummary.path.raw || "");
    });
    detailActions.appendChild(copy);

    const detailsPanel = renderOperationDetails(item, routeSummary);
    const initiallyOpen = false;
    detailsPanel.classList.toggle("hidden", !initiallyOpen);
    detailsPanel.setAttribute("aria-hidden", String(!initiallyOpen));
    detailsPanel.inert = !initiallyOpen;
    detailsButton.classList.toggle("is-open", initiallyOpen);
    detailsButton.setAttribute("aria-expanded", String(initiallyOpen));
    detailsButton.setAttribute("aria-label", initiallyOpen ? "收起详细操作步骤" : "展开详细操作步骤");
    detailButtonLabel.textContent = initiallyOpen ? "收起详细" : "查看详细";
    detailsButton.addEventListener("click", () => {
      const shouldOpen = detailsButton.getAttribute("aria-expanded") !== "true";
      setResultDetailsOpen(detailsPanel, detailsButton, detailButtonLabel, shouldOpen);
    });
    card.appendChild(detailsPanel);
    card.addEventListener("animationend", event => {
      if (event.target.classList?.contains("result-detail-heading") && event.animationName === "plaResultSectionEnter") {
        card.classList.remove("result-card-entering");
      }
    });
    list.appendChild(card);
  });

  applyResultFilters();
}

async function submitCalculation(event) {
  event.preventDefault();
  hideMessage();
  const firstSpecies = selectedSpeciesName("frpokemon");
  const secondSpecies = selectedSpeciesName("brpokemon");
  const payload = {
    isnormal: $("isnormal").checked,
    frspawns: Number($("frspawns").value),
    frencounter: $("frpokemon").value,
    fr_species: firstSpecies,
    isbonus: $("isbonus").checked,
    brspawns: Number($("brspawns").value),
    brencounter: $("brpokemon").value,
    br_species: secondSpecies,
    filter: $("filter").value
  };
  if (!$("current-seed").textContent || $("current-seed").textContent === "尚未读取") {
    showMessage("当前没有可用 Seed。请先在 Seed 设置中选择 TXT 文件或手动输入 Seed。", "error");
    return;
  }
  setBusy(true);
  try {
    const data = await api("/api/calculate", { method: "POST", body: JSON.stringify(payload) });
    renderResults(data);
    lastCalculationFailed = false;
    lastCalculationErrorMessage = "";
    updateDiagnosticsBanner();
    showMessage(`本地计算完成。Seed ${data.seed} 的结果已显示；本次未请求远程计算 API。`, "success");
  } catch (error) {
    lastCalculationFailed = true;
    lastCalculationErrorMessage = error.message;
    updateDiagnosticsBanner();
    showMessage(`${error.message}。没有使用假结果。请点击页面顶部「复制诊断报告」收集日志。`, "error");
  } finally {
    setBusy(false);
  }
}

async function loadSettings() {
  const settings = await api("/api/settings", { timeoutMs: 12000 });
  document.querySelectorAll('input[name="source-mode"]').forEach(input => {
    input.checked = input.value === settings.seed_source_mode;
  });
  $("seed-file-path").value = settings.seed_file_path || "";
  $("manual-seed").value = settings.manual_seed || "";
  defaultResearchLevel = settings.default_research_level || "level10";
  pokemonResearchLevels = settings.pokemon_research_levels && typeof settings.pokemon_research_levels === "object"
    ? { ...settings.pokemon_research_levels }
    : {};
  const defaultCharm = settings.default_shiny_charm !== false;
  if ($("pokemon-shiny-charm")) {
    $("pokemon-shiny-charm").checked = defaultCharm;
    $("pokemon-shiny-charm").disabled = false;
  }
  if ($("pokemon-research-search")) $("pokemon-research-search").disabled = false;
  settingsLoaded = true;
  renderResearchCatalog();
}

function selectedSourceMode() {
  return document.querySelector('input[name="source-mode"]:checked')?.value || "file";
}

async function saveSettings(modeOverride = null) {
  const payload = {
    seed_source_mode: modeOverride || selectedSourceMode(),
    seed_file_path: $("seed-file-path").value.trim(),
    manual_seed: $("manual-seed").value.trim()
  };
  const data = await api("/api/settings", { method: "PUT", body: JSON.stringify(payload) });
  return data.settings;
}

function persistPokemonSettings() {
  const status = $("pokemon-settings-save-status");
  if (status) status.textContent = "保存中…";
  pokemonSettingsSaveQueue = pokemonSettingsSaveQueue.catch(() => {}).then(async () => {
    await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({
        default_research_level: defaultResearchLevel,
        default_shiny_charm: Boolean($("pokemon-shiny-charm")?.checked),
        pokemon_research_levels: { ...pokemonResearchLevels }
      })
    });
    if (status) status.textContent = "已自动保存";
    return true;
  }).catch(error => {
    if (status) status.textContent = "保存失败";
    showToast(`宝可梦设置保存失败：${error.message}`);
    return false;
  });
  return pokemonSettingsSaveQueue;
}

async function setAllResearchLevels(level) {
  if (!settingsLoaded || !["base", "level10", "perfect"].includes(level)) return;
  defaultResearchLevel = level;
  pokemonResearchLevels = {};
  updatePokemonBulkSummary();
  renderResearchCatalog();
  const saved = await persistPokemonSettings();
  if (saved) showToast(`已将全部宝可梦统一设为「${pokemonLevelDisplayLabel(level)}」，并保存设置。`);
}

async function changePokemonResearchLevel(species, level) {
  const key = String(species || "").trim();
  if (!settingsLoaded || !key || !["base", "level10", "perfect"].includes(level)) return;
  if (level === defaultResearchLevel) delete pokemonResearchLevels[key];
  else pokemonResearchLevels[key] = level;
  updatePokemonBulkSummary();
  const row = [...document.querySelectorAll(".pokemon-research-row")].find(node => node.dataset.speciesKey === key);
  const badge = row?.querySelector(".pokemon-research-override-badge");
  if (badge) {
    const hasOverride = Object.prototype.hasOwnProperty.call(pokemonResearchLevels, key);
    badge.textContent = hasOverride ? "单独设置" : "";
    badge.classList.toggle("hidden", !hasOverride);
  }
  updateResearchCount();
  await persistPokemonSettings();
}

async function saveFileSettingsAndRead() {
  try {
    await saveSettings("file");
    const result = await api("/api/seed/reload", { method: "POST", body: JSON.stringify({}) });
    if (result.needs_confirmation) await confirmIfNeeded(result, "/api/seed/reload");
    else renderSeedState(result);
    showToast("TXT 路径设置已保存。");
  } catch (error) {
    showToast(error.message);
    await loadSeedState().catch(() => {});
  }
}

async function chooseFile() {
  try {
    const result = await api("/api/seed/select", { method: "POST", body: JSON.stringify({}) });
    if (result.cancelled) {
      showToast("已取消选择文件。");
      return;
    }
    if (result.selected_path) $("seed-file-path").value = result.selected_path;
    document.querySelector('input[name="source-mode"][value="file"]').checked = true;
    if (result.needs_confirmation) await confirmIfNeeded(result, "/api/seed/reload");
    else renderSeedState(result);
    showToast("文件路径已选择并尝试读取。");
  } catch (error) {
    showToast(error.message);
  }
}

async function applyManualSeed() {
  const seed = $("manual-seed").value.trim();
  try {
    const result = await api("/api/seed/manual", {
      method: "POST",
      body: JSON.stringify({ seed })
    });
    if (result.needs_confirmation) {
      const yes = await showSeedConfirmation(
        result,
        "应用手动 Seed",
        "你输入的 Seed 与当前 Seed 不同。确认后会切换到手动输入模式并应用新值。"
      );
      if (!yes) {
        const cancelled = await api("/api/seed/cancel-pending", {
          method: "POST",
          body: JSON.stringify({})
        }).catch(() => null);
        if (cancelled) renderSeedState(cancelled);
        else await loadSeedState();
        showToast("已保留当前 Seed。");
        return;
      }
      const confirmed = await api("/api/seed/manual", {
        method: "POST",
        body: JSON.stringify({ seed, confirm: true })
      });
      renderSeedState(confirmed);
    } else {
      renderSeedState(result);
    }
    document.querySelector('input[name="source-mode"][value="manual"]').checked = true;
    showToast("手动 Seed 已校验并应用。");
  } catch (error) {
    showToast(error.message);
  }
}

async function loadEngineStatus() {
  const statusNode = $("local-engine-status");
  const detailNode = $("local-engine-details");
  try {
    const data = await api("/api/engine", { timeoutMs: 18000 });
    engineVerified = Boolean(data.verified);
    engineProblemMessage = data.verified ? "" : (data.message || (data.missing || []).join("、"));
    statusNode.textContent = data.verified ? "本地引擎已验证" : (data.installed ? "引擎尚未验证" : "尚未安装");
    statusNode.className = `status-pill ${data.verified ? "status-success" : "status-error"}`;
    const details = [
      data.message || "",
      data.version && data.version !== "未记录" ? `版本/安装时间：${data.version}` : "",
      `候选映射：${data.mapping_complete ? "完整" : "备用/未验证"}`,
      data.missing?.length ? `缺失：${data.missing.join("、")}` : ""
    ].filter(Boolean);
    detailNode.textContent = details.join(" ");
    updateDiagnosticsBanner();
  } catch (error) {
    engineVerified = false;
    engineProblemMessage = error.message;
    statusNode.textContent = "检查失败";
    statusNode.className = "status-pill status-error";
    detailNode.textContent = error.message;
    updateDiagnosticsBanner();
  }
}

function safeText(value) {
  return value === undefined || value === null ? "—" : String(value);
}


async function applyQuickSeed() {
  const value = $("quick-seed").value.trim();
  if (!value) {
    showToast("请输入 Seed。");
    return;
  }
  $("manual-seed").value = value;
  document.querySelector('input[name="source-mode"][value="manual"]').checked = true;
  await applyManualSeed();
}

let assetPollTimer = null;
let assetPromptShown = false;
let assetPromptContext = "startup";

function showPokemonAssetPrompt(context = "manual") {
  assetPromptContext = context;
  const modal = $("pokemon-assets-prompt");
  if (!modal) return;
  modal.classList.remove("hidden");
  assetPromptShown = true;
  const downloadButton = $("choose-download-pokemon-assets");
  if (downloadButton) downloadButton.focus();
}

function hidePokemonAssetPrompt() {
  $("pokemon-assets-prompt")?.classList.add("hidden");
  assetPromptShown = false;
}

function renderPokemonAssetStatus(data) {
  const statusNode = $("pokemon-assets-status");
  const summaryNode = $("pokemon-assets-summary");
  if (!data || !statusNode || !summaryNode) return;
  const progress = data.progress || {};
  statusNode.className = "status-pill";
  if (data.manifest_ready === false || Number(data.total || 0) === 0) {
    statusNode.classList.add("status-error");
    statusNode.textContent = "清单不可用";
    summaryNode.textContent = "图片资源清单未找到。请先运行 prepare_offline_engine.bat 准备本地引擎资源；这不会影响已有计算功能。";
  } else if (data.complete) {
    statusNode.classList.add("status-success");
    statusNode.textContent = "资源已就绪";
    summaryNode.textContent = `已检查 ${data.total} 个图片文件，全部可用（本地缓存 ${data.cached || 0}，自定义图片 ${data.custom || 0}）。图片资源可离线使用。`;
  } else if (progress.status === "downloading") {
    statusNode.classList.add("status-pending");
    statusNode.textContent = "正在下载";
    summaryNode.textContent = `已准备 ${data.available || 0} / ${data.total || 0} 个图片文件。下载期间不影响 Seed 读取或 RNG 计算。`;
  } else if (progress.status === "partial") {
    statusNode.classList.add("status-pending");
    statusNode.textContent = "部分缺失";
    summaryNode.textContent = `已准备 ${data.available || 0} / ${data.total || 0} 个图片文件，仍缺少 ${data.missing || 0} 个。可重试下载，或将对应图片放入 custom 文件夹。`;
  } else {
    statusNode.classList.add("status-muted");
    statusNode.textContent = "可选资源";
    summaryNode.textContent = `已准备 ${data.available || 0} / ${data.total || 0} 个图片文件，缺少 ${data.missing || 0} 个。图片不是计算依赖；可稍后下载，也可手动添加。`;
  }

  const globalProgress = $("pokemon-assets-global-progress");
  if (globalProgress) {
    const isDownloading = progress.status === "downloading";
    globalProgress.classList.toggle("hidden", !isDownloading);
    if (isDownloading) {
      const percent = Number(progress.percent || 0);
      $("pokemon-assets-global-percent").textContent = `${percent}%`;
      $("pokemon-assets-global-bar").style.width = `${Math.max(0, Math.min(100, percent))}%`;
      const completed = Number(progress.completed || 0);
      const total = Number(progress.total || 0);
      $("pokemon-assets-global-detail").textContent = `${completed} / ${total} 个文件已处理。可继续使用计算器。`;
    }
  }

  const progressWrap = $("pokemon-assets-progress-wrap");
  if (progress.status === "downloading" || progress.status === "partial" || progress.status === "complete") {
    progressWrap?.classList.remove("hidden");
    const percent = Number(progress.percent || 0);
    $("pokemon-assets-progress-label").textContent = progress.status === "downloading"
      ? `正在处理：${progress.current || "图片资源"}`
      : progress.status === "complete" ? "图片资源准备完成" : "下载未完全完成";
    $("pokemon-assets-progress-percent").textContent = `${percent}%`;
    $("pokemon-assets-progress-bar").style.width = `${Math.max(0, Math.min(100, percent))}%`;
    const total = Number(progress.total || 0);
    const completed = Number(progress.completed || 0);
    const downloaded = Number(progress.downloaded || 0);
    const failed = Number(progress.failed || 0);
    $("pokemon-assets-progress-detail").textContent = progress.status === "complete"
      ? `资源已就绪。此次新增 ${downloaded} 个文件。`
      : `${completed} / ${total} 个文件已处理 · 成功 ${downloaded} · 缺失／失败 ${failed}${progress.errors?.length ? ` · 最近错误：${progress.errors[0]}` : ""}`;
  } else {
    progressWrap?.classList.add("hidden");
  }
  const downloadButton = $("download-pokemon-assets");
  if (downloadButton) {
    downloadButton.disabled = data.manifest_ready === false || Number(data.total || 0) === 0 || progress.status === "downloading" || data.complete;
    downloadButton.textContent = data.complete ? "图片资源已完整" : (progress.status === "downloading" ? "正在下载…" : "下载／补全图片");
  }
}

async function refreshPokemonAssetStatus(manualCheck = false) {
  try {
    const data = manualCheck
      ? await api("/api/pokemon-assets/check", { method: "POST", body: JSON.stringify({}), timeoutMs: 15000 })
      : await api("/api/pokemon-assets/status", { timeoutMs: 15000 });
    renderPokemonAssetStatus(data);
    const availableCount = Number(data.available || 0);
    if (availableCount > lastAssetAvailableCount) retryMissingSpriteImages();
    lastAssetAvailableCount = availableCount;
    if (manualCheck && data.missing > 0 && data.progress?.status !== "downloading") {
      showPokemonAssetPrompt("manual");
    } else if (!manualCheck && data.prompt_required && !assetPromptShown) {
      showPokemonAssetPrompt("startup");
    }
    if (data.progress?.status === "downloading") {
      if (assetPollTimer) clearTimeout(assetPollTimer);
      assetPollTimer = setTimeout(() => refreshPokemonAssetStatus(false), 1100);
    } else if (assetPollTimer) {
      clearTimeout(assetPollTimer);
      assetPollTimer = null;
    }
    return data;
  } catch (error) {
    const statusNode = $("pokemon-assets-status");
    if (statusNode) {
      statusNode.className = "status-pill status-error";
      statusNode.textContent = "检查失败";
    }
    if ($("pokemon-assets-summary")) $("pokemon-assets-summary").textContent = `图片资源状态读取失败：${error.message}。这不会影响计算功能。`;
    if (manualCheck) showToast(`检查图片资源失败：${error.message}`);
    return null;
  }
}

async function choosePokemonAssetAction(choice) {
  hidePokemonAssetPrompt();
  try {
    const data = await api("/api/pokemon-assets/choice", {
      method: "POST",
      body: JSON.stringify({ choice })
    });
    renderPokemonAssetStatus(data);
    if (choice === "skip") {
      showToast("已跳过图片下载。之后不会自动提醒；可在设置中手动检查。计算功能不受影响。");
      return;
    }
    showToast("图片资源已在后台开始准备。你可以继续使用计算器。");
    if (assetPollTimer) clearTimeout(assetPollTimer);
    assetPollTimer = setTimeout(() => refreshPokemonAssetStatus(false), 800);
  } catch (error) {
    showToast(`图片资源操作失败：${error.message}`);
  }
}

async function openPokemonAssetFolder() {
  try {
    const data = await api("/api/pokemon-assets/open-folder", { method: "POST", body: JSON.stringify({}) });
    showToast(data.opened ? "已打开自定义图片文件夹。" : `图片文件夹路径：${data.path}`);
  } catch (error) {
    showToast(`无法打开图片文件夹：${error.message}`);
  }
}

const APP_THEME_NAMES = {
  forest: "森林绿",
  ocean: "海洋蓝",
  snow: "纯净白",
  lavender: "薰衣草紫",
  amber: "暖阳琥珀"
};

function persistAppearance(key, value) {
  try { localStorage.setItem(key, value); } catch (_) { /* Server settings are the durable source. */ }
  const snapshot = {
    appearance_theme: document.body.dataset.theme || "forest",
    appearance_mode: document.body.classList.contains("dark-mode") ? "dark" : "light"
  };
  // Serialize writes so rapid theme/mode clicks cannot leave an older preference last.
  appearanceSaveQueue = appearanceSaveQueue
    .catch(() => {})
    .then(() => api("/api/settings", {
      method: "PUT",
      body: JSON.stringify(snapshot),
      timeoutMs: 8000
    }))
    .catch(error => console.warn("外观偏好保存失败：", error));
}

function syncAppearanceControls() {
  const dark = document.body.classList.contains("dark-mode");
  const modeButton = $("theme-toggle");
  if (modeButton) {
    modeButton.textContent = dark ? "☀" : "☾";
    modeButton.title = dark ? "切换日间模式" : "切换夜间模式";
    modeButton.setAttribute("aria-label", dark ? "切换日间模式" : "切换夜间模式");
    modeButton.setAttribute("aria-pressed", String(dark));
  }
  const modeCheckbox = $("appearance-dark-mode");
  if (modeCheckbox) modeCheckbox.checked = dark;
  document.querySelectorAll("[data-theme-choice]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.themeChoice === document.body.dataset.theme));
  });
}

function setAppearanceTheme(theme, persist = true) {
  if (!Object.prototype.hasOwnProperty.call(APP_THEME_NAMES, theme)) return;
  document.body.dataset.theme = theme;
  if (persist) persistAppearance("pla-mmo-theme", theme);
  syncAppearanceControls();
}

function setDarkMode(enabled, persist = true) {
  document.body.classList.toggle("dark-mode", Boolean(enabled));
  if (persist) persistAppearance("pla-mmo-mode", enabled ? "dark" : "light");
  syncAppearanceControls();
}

function initializeAppearance() {
  let theme = document.body.dataset.theme || "forest";
  let mode = document.body.classList.contains("dark-mode") ? "dark" : "light";
  let migratedPreference = false;
  // New versions persist appearance in settings.json. If this is the first
  // launch after upgrading from a localStorage-only release, migrate that choice.
  if (document.body.dataset.appearanceSaved !== "1") {
    try {
      const savedTheme = localStorage.getItem("pla-mmo-theme");
      const savedMode = localStorage.getItem("pla-mmo-mode");
      if (Object.prototype.hasOwnProperty.call(APP_THEME_NAMES, savedTheme)) {
        theme = savedTheme;
        migratedPreference = true;
      }
      if (savedMode === "dark" || savedMode === "light") {
        mode = savedMode;
        migratedPreference = true;
      }
    } catch (_) { /* Server-rendered defaults remain available. */ }
  }
  setAppearanceTheme(theme, false);
  setDarkMode(mode === "dark", false);
  // Persist defaults too, marking appearance preferences as initialized; when
  // migrating, this also transfers the previous WebView localStorage values.
  if (document.body.dataset.appearanceSaved !== "1") {
    persistAppearance("pla-mmo-theme", theme);
    if (!migratedPreference) {
      try { localStorage.setItem("pla-mmo-mode", mode); } catch (_) {}
    }
  }
}

function toggleTheme() {
  setDarkMode(!document.body.classList.contains("dark-mode"));
}

initializeAppearance();
document.querySelectorAll("[data-theme-choice]").forEach(button => {
  button.addEventListener("click", () => setAppearanceTheme(button.dataset.themeChoice));
});
$("appearance-dark-mode").addEventListener("change", event => setDarkMode(event.target.checked));

$("refresh-seed").addEventListener("click", refreshSeed);
$("quick-seed").addEventListener("keydown", event => {
  if (event.key === "Enter") {
    event.preventDefault();
    $("quick-seed").blur();
  }
});
$("quick-seed").addEventListener("change", applyQuickSeed);
$("copy-seed").addEventListener("click", () => copyText($("current-seed").textContent === "尚未读取" ? "" : $("current-seed").textContent));
$("theme-toggle").addEventListener("click", toggleTheme);
["show-only-shiny", "show-only-alpha", "show-default-path", "show-multi-path"].forEach(id => {
  $(id).addEventListener("change", applyResultFilters);
});
$("calculate-form").addEventListener("submit", submitCalculation);
$("calculate-form").addEventListener("change", event => {
  const target = event.target;
  if (!(target instanceof HTMLSelectElement)) return;
  const field = target.closest(".field");
  if (!field) return;
  if (field._selectionPulseTimer) window.clearTimeout(field._selectionPulseTimer);
  field.classList.remove("selection-updated");
  void field.offsetWidth;
  field.classList.add("selection-updated");
  field._selectionPulseTimer = window.setTimeout(() => {
    field.classList.remove("selection-updated");
    field._selectionPulseTimer = null;
  }, 300);
});
$("appearance").addEventListener("change", () => syncAppearanceMode(true));
$("frpokemon").addEventListener("change", () => {
  updateBonusSpecies();
});
document.querySelectorAll("[data-research-bulk]").forEach(button => {
  button.addEventListener("click", () => { setAllResearchLevels(button.dataset.researchBulk); });
});
$("pokemon-research-search").addEventListener("input", renderResearchCatalog);
$("pokemon-research-list").addEventListener("change", event => {
  const target = event.target;
  if (target instanceof HTMLInputElement && target.matches("input[data-species-key][data-research-level]")) {
    changePokemonResearchLevel(target.dataset.speciesKey, target.dataset.researchLevel);
  }
});
$("pokemon-shiny-charm").addEventListener("change", () => { persistPokemonSettings(); });
$("choose-file").addEventListener("click", chooseFile);
$("save-file-settings").addEventListener("click", saveFileSettingsAndRead);
$("refresh-file").addEventListener("click", refreshSeed);
$("apply-manual-seed").addEventListener("click", applyManualSeed);
$("choose-download-pokemon-assets").addEventListener("click", () => choosePokemonAssetAction("download"));
$("choose-skip-pokemon-assets").addEventListener("click", () => choosePokemonAssetAction("skip"));
$("check-pokemon-assets").addEventListener("click", () => refreshPokemonAssetStatus(true));
$("download-pokemon-assets").addEventListener("click", () => {
  // Explicit consent is required even when retrying a partial or interrupted download.
  showPokemonAssetPrompt("manual");
});
$("open-pokemon-assets").addEventListener("click", openPokemonAssetFolder);

$("refresh-engine-status").addEventListener("click", loadEngineStatus);
$("copy-engine-log").addEventListener("click", copyDiagnosticsReport);
$("copy-diagnostics-banner").addEventListener("click", copyDiagnosticsReport);
$("copy-installer-log-path").addEventListener("click", () => copyText("offline_engine_setup.log"));

(async function init() {
  // A setup error must not prevent the independent data requests from running.
  try {
    setupSearchableSelect($("frpokemon"));
    setupSearchableSelect($("brpokemon"));
  } catch (error) {
    console.error("宝可梦搜索框初始化失败", error);
    showToast(`宝可梦搜索框初始化失败：${error.message}`);
  }
  try {
    syncAppearanceMode(false);
  } catch (error) {
    console.error("群体类型初始化失败", error);
    showToast(`群体类型初始化失败：${error.message}`);
  }

  // Run startup requests independently. A slow settings/engine endpoint must
  // not prevent candidates from loading or leave a permanent loading label.
  const startupTasks = [
    loadSettings().catch(error => showToast(`设置读取失败：${error.message}`)),
    loadSeedState().catch(error => {
      const status = $("seed-status");
      status.textContent = "读取失败";
      status.className = "status-pill status-error";
      $("seed-error").textContent = error.message;
      $("seed-error").classList.remove("hidden");
      showToast(`Seed 状态读取失败：${error.message}`);
    }),
    loadEngineStatus(),
    loadSpecies(),
    loadResearchCatalog(),
    refreshPokemonAssetStatus(false)
  ];
  await Promise.allSettled(startupTasks);
  try { syncAppearanceMode(false); } catch (error) { console.error("群体类型刷新失败", error); }
  refreshSearchableSelect($("frpokemon"));
  refreshSearchableSelect($("brpokemon"));
})();
