const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(require("path").join(__dirname, "..", "static", "app.js"), "utf8");
const start = source.indexOf("function researchLevelLabel(value) {");
const end = source.indexOf("\nfunction addPokemonArtwork", start);
if (start < 0 || end < 0) throw new Error("Research-level helper block not found");
const helpers = source.slice(start, end);

function localizePokemonName(value) {
  const raw = String(value || "").trim();
  if (/^Alpha\s+/i.test(raw)) return "头目" + localizePokemonName(raw.replace(/^Alpha\s+/i, ""));
  const names = { Kadabra: "勇基拉", "勇基拉": "勇基拉", "Alpha Kadabra": "头目勇基拉" };
  return names[raw] || raw;
}
function selectedSpeciesName() { return "Alpha Kadabra"; }
function $(id) { return { value: id === "br-research" ? "perfect" : "level10" }; }
function firstValue(item, aliases) {
  for (const alias of aliases) {
    const key = Object.keys(item || {}).find(k => k.toLowerCase() === alias.toLowerCase());
    if (key !== undefined) return item[key];
  }
}
const sandbox = { localizePokemonName, selectedSpeciesName, $, firstValue, console };
vm.createContext(sandbox);
vm.runInContext(helpers, sandbox);

const params = {
  fr_species: "Alpha Kadabra",
  br_species: "Alpha Kadabra",
  research_levels: { "Alpha Kadabra": "level10" }
};
const context = sandbox.resultResearchContext({ species: "Kadabra" }, params);
if (context.species !== "头目勇基拉") throw new Error(`Wrong localized species: ${JSON.stringify(context)}`);
if (context.level !== "研究等级 10") throw new Error(`Research level not resolved from research_levels: ${JSON.stringify(context)}`);
if (sandbox.researchLevelForSpecies(params, params.fr_species, "fr") !== "level10") {
  throw new Error("Caption research-level mapping failed");
}
const perfect = { fr_species: "Kadabra", research_levels: { Kadabra: "perfect" } };
if (sandbox.researchLevelLabel(sandbox.researchLevelForSpecies(perfect, "Kadabra", "fr")) !== "完美研究") {
  throw new Error("Perfect research label failed");
}

// Regression: editing one Pokémon should not change the unfiltered list label
// to the misleading "显示 N / N" wording.
const countStart = source.indexOf("function updateResearchCount(visibleCount = null) {");
const countEnd = source.indexOf("\nfunction updatePokemonBulkSummary", countStart);
if (countStart < 0 || countEnd < 0) throw new Error("Research count helper not found");
const countHelper = source.slice(countStart, countEnd);
let searchQuery = "";
const countNode = { textContent: "" };
const countSandbox = {
  $: id => id === "pokemon-research-count" ? countNode : ({ value: searchQuery }),
  researchCatalog: Array.from({ length: 242 }, (_, index) => ({ dex_number: index + 1 })),
  pokemonResearchLevels: { Pikachu: "base" },
  researchOverrideCount: () => Object.keys(countSandbox.pokemonResearchLevels).length,
  document: { querySelectorAll: () => Array.from({ length: 242 }) }
};
vm.createContext(countSandbox);
vm.runInContext(countHelper, countSandbox);
countSandbox.updateResearchCount();
if (countNode.textContent !== "共 242 只 · 1 个单独设置") {
  throw new Error(`Unfiltered count is incorrect: ${countNode.textContent}`);
}
searchQuery = "pika";
countSandbox.$ = id => id === "pokemon-research-count" ? countNode : ({ value: searchQuery });
countSandbox.updateResearchCount(3);
if (countNode.textContent !== "显示 3 / 242 只 · 1 个单独设置") {
  throw new Error(`Filtered count is incorrect: ${countNode.textContent}`);
}
console.log("research-level UI tests passed");
