/* Pure helpers for localizing and explaining upstream PLA MMO result paths.
 * The RNG engine and its original result payload are deliberately untouched.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.PLAResultView = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const NATURES_ZH = {
    Hardy: "勤奋", Lonely: "怕寂寞", Brave: "勇敢", Adamant: "固执", Naughty: "顽皮",
    Bold: "大胆", Docile: "坦率", Relaxed: "悠闲", Impish: "淘气", Lax: "乐天",
    Timid: "胆小", Hasty: "急躁", Serious: "认真", Jolly: "爽朗", Naive: "天真",
    Modest: "内敛", Mild: "慢吞吞", Quiet: "冷静", Bashful: "害羞", Rash: "马虎",
    Calm: "温和", Gentle: "温顺", Sassy: "自大", Careful: "谨慎", Quirky: "浮躁"
  };

  function stripHtml(value) {
    return String(value == null ? "" : value)
      .replace(/<[^>]*>/g, "")
      .replace(/&nbsp;/gi, " ")
      .replace(/&amp;/gi, "&")
      .replace(/&lt;/gi, "<")
      .replace(/&gt;/gi, ">")
      .replace(/&quot;/gi, '"')
      .replace(/&#39;/gi, "'")
      .replace(/\s+/g, " ")
      .trim();
  }

  function extractDSteps(value) {
    const text = stripHtml(value);
    const matches = text.match(/D\s*(\d+)/gi) || [];
    return matches.map(part => Number(part.replace(/[^0-9]/g, ""))).filter(n => Number.isFinite(n) && n > 0);
  }

  function extractBracketNumbers(value) {
    const text = stripHtml(value);
    const match = text.match(/\[([^\]]*)\]/);
    if (!match) return [];
    return (match[1].match(/\d+/g) || []).map(Number).filter(n => Number.isFinite(n) && n > 0);
  }

  function listify(value) {
    if (Array.isArray(value)) return value.map(stripHtml).filter(Boolean);
    if (value == null || value === "") return [];
    return [stripHtml(value)];
  }

  function isTrueFlag(value) {
    if (value === true || value === 1) return true;
    if (typeof value === "string") return ["true", "yes", "1"].includes(value.trim().toLowerCase());
    return false;
  }

  function parsePathInfo(item) {
    const raw = stripHtml(item && (item.index || item.path || item.default_path || item.defaultpath));
    // Upstream chains sometimes omit square brackets around the first-round steps.
    // Stop the first-round capture before revisit/clear/bonus metadata.
    const firstMatch = raw.match(/First Round Path:\s*(\[[^\]]*\]|.*?)(?=\s*\+\s*(?:Revisit|Clear Round|Bonus Path|Bonus Initial Spawn)\b|$)/i);
    const firstRound = firstMatch ? extractDSteps(firstMatch[1]) : [];
    const revisitMatch = raw.match(/Revisit\s*\[([^\]]*)\]/i);
    const revisit = revisitMatch ? (revisitMatch[1].match(/\d+/g) || []).map(Number).filter(n => n > 0) : [];
    const bonusMatch = raw.match(/Bonus Path:\s*(.*?)(?=\s*\+\s*(?:Revisit|Clear Round|Bonus Initial Spawn)\b|$)/i);
    const bonus = bonusMatch ? extractDSteps(bonusMatch[1]) : [];
    const bonusInitialMatch = raw.match(/Bonus Initial Spawn\s*(\d+)/i);
    // Do not let "Bonus Initial Spawn 4" also be mistaken for a top-level Initial Spawn.
    const withoutBonusInitial = raw.replace(/Bonus Initial Spawn\s*\d+/ig, "");
    const initialMatch = withoutBonusInitial.match(/(?:^|\+\s*|^\s*)Initial Spawn\s*(\d+)/i);
    const clearRound = /\[\s*Clear Round\s*\]/i.test(raw) || /Clear Round/i.test(raw);
    let ordinary = [];
    if (!firstMatch && !initialMatch) {
      const ordinaryMatch = raw.match(/^Path:\s*(.*)$/i);
      if (ordinaryMatch) ordinary = extractDSteps(ordinaryMatch[1]);
    }
    const hasBonus = Boolean(firstMatch || bonusMatch || bonusInitialMatch);
    const bonusInitialSpawn = bonusInitialMatch ? Number(bonusInitialMatch[1]) : null;
    return {
      raw,
      firstRound,
      revisit,
      bonus,
      ordinary,
      initialSpawn: initialMatch ? Number(initialMatch[1]) : null,
      bonusInitialSpawn,
      clearRound,
      hasBonus,
      isInitialSpawn: Boolean(initialMatch),
      routeKey: hasBonus
        ? `first:${firstRound.join(",")}|revisit:${revisit.join(",")}|bonus:${bonus.join(",")}|bonusInitial:${bonusInitialSpawn || ""}|clear:${clearRound}`
        : initialMatch
          ? `initial:${initialMatch[1]}`
          : `first:${ordinary.join(",")}`
    };
  }

  function formatDSteps(steps, brackets) {
    if (!Array.isArray(steps) || !steps.length) return "—";
    const text = steps.map(n => `D${n}`).join(", ");
    return brackets ? `[${text}]` : text;
  }

  function formatRevisit(steps) {
    if (!Array.isArray(steps) || !steps.length) return "";
    return `重新访问 [${steps.join(", ")}]`;
  }

  function localizeNature(value) {
    const raw = stripHtml(value);
    if (!raw) return "—";
    return NATURES_ZH[raw] || NATURES_ZH[raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase()] || raw;
  }

  function localizeGender(value) {
    const raw = stripHtml(value).toLowerCase();
    if (["male", "m", "♂", "公", "男"].includes(raw)) return "公 ♂";
    if (["female", "f", "♀", "母", "女"].includes(raw)) return "母 ♀";
    if (["genderless", "none", "无性别", "—", "-"].includes(raw)) return "无性别";
    return stripHtml(value) || "—";
  }

  function formatChainPath(value) {
    const raw = stripHtml(value);
    const path = parsePathInfo({ path: raw });
    const parts = [];
    if (path.firstRound.length) parts.push(`第一轮路径：${formatDSteps(path.firstRound, false)}`);
    if (path.revisit.length) parts.push(formatRevisit(path.revisit));
    else if (path.clearRound) parts.push("第一轮清空后进入第二轮");
    if (path.bonus.length) parts.push(`第二轮路径：${formatDSteps(path.bonus, false)}`);
    else if (path.bonusInitialSpawn) parts.push(`第二轮初始生成：第 ${path.bonusInitialSpawn} 只`);
    if (parts.length) return parts.join(" + ");
    if (path.isInitialSpawn) return `初始生成位置：第 ${path.initialSpawn} 只`;
    const steps = extractDSteps(raw);
    if (steps.length) return `第一轮路径：${formatDSteps(steps, false)}`;
    return raw ? `第一轮路径：${raw}` : "";
  }

  function formatAlternatePath(value) {
    const raw = stripHtml(value);
    const steps = extractDSteps(raw);
    if (steps.length) {
      const label = /Bonus Path:/i.test(raw) ? "第二轮路径" : "第一轮路径";
      return `${label}：${formatDSteps(steps, false)}`;
    }
    return raw;
  }

  function buildRouteSummary(item) {
    const path = parsePathInfo(item);
    const chains = listify(item && item.chains).map(formatChainPath).filter(Boolean);
    const dupes = listify(item && item.dupes).map(formatAlternatePath).filter(Boolean);
    const lines = [];
    if (path.hasBonus) {
      lines.push({ label: "第一轮路径", value: formatDSteps(path.firstRound, true) });
      if (path.revisit.length) lines.push({ label: "重新访问", value: `[${path.revisit.join(", ")}]` });
      else if (path.clearRound) lines.push({ label: "第一轮清空", value: "清空后进入第二轮" });
      if (path.bonus.length) lines.push({ label: "第二轮路径", value: formatDSteps(path.bonus, false) });
      else if (path.bonusInitialSpawn) lines.push({ label: "第二轮初始生成", value: `第 ${path.bonusInitialSpawn} 只` });
    } else if (path.isInitialSpawn) {
      lines.push({ label: "初始生成位置", value: `第 ${path.initialSpawn} 只` });
    } else if (path.ordinary.length) {
      lines.push({ label: "第一轮路径", value: formatDSteps(path.ordinary, false) });
    } else if (path.raw) {
      lines.push({ label: "路径", value: path.raw });
    }
    // `dupes` describes alternative routes to this same result. Only `chains`
    // or explicit simultaneous-shiny flags indicate multiple shiny encounters.
    const explicitMulti = Boolean(item && (
      isTrueFlag(item.multi) || isTrueFlag(item.multi_shiny) || isTrueFlag(item.multi_shiny_path)
    ));
    const hasMultiple = chains.length > 0 || explicitMulti;
    // `chains` contains additional simultaneous targets/routes in the engine payload.
    // Count the primary target as well, but do not invent a count for boolean-only flags.
    const multiShinyCount = chains.length > 0 ? chains.length + 1 : null;
    return { path, lines, chains, dupes, hasMultiple, multiShinyCount };
  }

  function buildOperationSections(item) {
    const summary = buildRouteSummary(item);
    const path = summary.path;
    const sections = [];
    const operation = (steps) => {
      const values = Array.isArray(steps) ? steps : [];
      return values.map((count, index) => ({
        number: index + 1,
        count,
        pathStep: `D${count}`,
        title: count === 1 ? "清除 1 只" : `一次清除 ${count} 只`,
        description: "",
        cumulative: values.slice(0, index + 1).reduce((sum, n) => sum + n, 0)
      }));
    };
    const chainOperations = listify(item && item.chains).map(raw => {
      const parsed = parsePathInfo({ path: raw });
      const steps = parsed.firstRound.length ? parsed.firstRound : (parsed.ordinary.length ? parsed.ordinary : []);
      return {
        label: formatChainPath(raw),
        initialSpawn: parsed.initialSpawn,
        bonusInitialSpawn: parsed.bonusInitialSpawn,
        revisit: parsed.revisit,
        bonus: parsed.bonus,
        clearRound: parsed.clearRound,
        hasBonus: parsed.hasBonus,
        steps: operation(steps),
        targetTiming: parsed.isInitialSpawn
          ? `初始生成第 ${parsed.initialSpawn} 只`
          : parsed.bonusInitialSpawn
            ? `第二轮初始生成第 ${parsed.bonusInitialSpawn} 只`
            : parsed.bonus.length
              ? "第二轮最后一步后"
              : "第一轮最后一步后"
      };
    }).filter(entry => entry.label);

    if (path.isInitialSpawn) {
      sections.push({
        title: "目标出现",
        note: `目标位于初始生成的第 ${path.initialSpawn} 只宝可梦；这是生成位置，不是需要清除的宝可梦数量。`,
        steps: [],
        targetEvent: true
      });
    }

    if (path.hasBonus) {
      sections.push({
        title: "第一轮操作",
        note: "按顺序执行每个 D 步骤。D 数字同时表示本步需要清除的数量；击败、捕捉或吓跑均可。",
        steps: operation(path.firstRound)
      });
      if (path.revisit.length) {
        sections.push({
          title: "重新访问",
          note: `数字表示当前群聚中剩余的宝可梦数量，而不是需要清除的数量。达到对应数量后，离开群聚点至少 120 米（建议按地图标记留到约 150 米），再返回；可传送到较远营地完成离开。`,
          methodNote: "如果前面的路线没有指定 D 步骤，可通过捕捉、击败或吓跑来调整剩余数量；如果指定了 D 步骤，请按路线执行。",
          steps: [],
          revisitMarkers: path.revisit.map((marker, index) => ({
            number: index + 1,
            marker,
            title: `群聚剩余 ${marker} 只时`,
            description: "离开群聚点至少 120 米（建议按地图标记留到约 150 米），再返回群聚点。"
          }))
        });
      }
      if (path.clearRound) {
        sections.push({
          title: "清空第一轮",
          note: "清空第一轮剩余宝可梦后，再进入第二轮。此操作不计入 D 清除数量。",
          steps: []
        });
      }
      sections.push({
        title: "进入大规模发生（第二次）",
        note: path.revisit.length && path.clearRound
          ? "完成重新访问顺序并清空第一轮剩余宝可梦后，再次进入该大规模发生。"
          : path.revisit.length
            ? "完成重新访问顺序后，再次进入该大规模发生。"
            : path.clearRound
              ? "清空第一轮剩余宝可梦后，再次进入该大规模发生。"
              : "完成第一轮后，进入第二轮群体。",
        steps: []
      });
      if (path.bonusInitialSpawn) {
        sections.push({
          title: "目标出现",
          note: `目标位于第二轮初始生成的第 ${path.bonusInitialSpawn} 只宝可梦；这是生成位置，不是需要清除的宝可梦数量。到达该位置时检查闪光。`,
          steps: [],
          targetEvent: true
        });
      } else {
        sections.push({
          title: "第二轮操作",
          note: "按顺序执行第二轮的 D 步骤。完成最后一步后，才检查目标宝可梦。",
          steps: operation(path.bonus)
        });
        if (path.bonus.length) {
          sections.push({
            title: "目标出现",
            note: "第二轮最后一步已完成；现在检查目标宝可梦是否出现闪光。",
            steps: [],
            targetEvent: true
          });
        } else {
          sections.push({
            title: "核对目标位置",
            note: "原始路径未提供第二轮 D 步骤或初始生成编号。为避免误导，请展开原始路径数据核对该结果。",
            steps: [],
            targetWarning: true
          });
        }
      }
    } else if (!path.isInitialSpawn && path.ordinary.length) {
      sections.push({
        title: "第一轮操作",
        note: "按顺序执行每个 D 步骤。D 数字同时表示本步需要清除的数量；击败、捕捉或吓跑均可。",
        steps: operation(path.ordinary)
      });
      sections.push({
        title: "目标出现",
        note: "完成最后一步后，检查目标宝可梦是否出现闪光。",
        steps: [],
        targetEvent: true
      });
    }
    return { ...summary, sections, chainOperations };
  }

  return {
    NATURES_ZH,
    stripHtml,
    extractDSteps,
    extractBracketNumbers,
    listify,
    parsePathInfo,
    formatDSteps,
    formatRevisit,
    localizeNature,
    localizeGender,
    formatChainPath,
    formatAlternatePath,
    buildRouteSummary,
    buildOperationSections
  };
});
