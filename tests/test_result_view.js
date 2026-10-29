const assert = require('node:assert/strict');
const view = require('../static/result_view.js');

const sample = {
  index: '<span>First Round Path: [D1, D1, D1, D1, D3]</span> + <span>Revisit [1]</span> + <span>Bonus Path: D1, D3</span>',
  chains: ['<span>First Round Path: D1, D1, D1, D1, D3</span>'],
  dupes: [],
  nature: 'Relaxed',
  gender: 'male',
  rolls: 17,
  ivs: [10, 31, 31, 31, 31, 29]
};
const summary = view.buildRouteSummary(sample);
assert.deepEqual(summary.path.firstRound, [1, 1, 1, 1, 3]);
assert.deepEqual(summary.path.revisit, [1]);
assert.deepEqual(summary.path.bonus, [1, 3]);
assert.equal(summary.lines[0].label, '第一轮路径');
assert.equal(summary.lines[0].value, '[D1, D1, D1, D1, D3]');
assert.equal(summary.lines[1].label, '重新访问');
assert.equal(summary.lines[2].label, '第二轮路径');
assert.equal(summary.chains[0], '第一轮路径：D1, D1, D1, D1, D3');
assert.equal(summary.multiShinyCount, 2);
assert.equal(view.localizeNature('Relaxed'), '悠闲');
assert.equal(view.localizeNature('Careful'), '谨慎');
assert.equal(view.localizeGender('male'), '公 ♂');
assert.equal(view.localizeGender('female'), '母 ♀');
const ops = view.buildOperationSections(sample);
assert.deepEqual(ops.sections[0].steps.map(step => step.count), [1, 1, 1, 1, 3]);
assert.deepEqual(ops.sections[0].steps.map(step => step.cumulative), [1, 2, 3, 4, 7]);
assert.deepEqual(ops.sections[1].steps, []);
assert.deepEqual(ops.sections[1].revisitMarkers, [{ number: 1, marker: 1, title: '群聚剩余 1 只时', description: '离开群聚点至少 120 米（建议按地图标记留到约 150 米），再返回群聚点。' }]);
assert.match(ops.sections[1].note, /剩余的宝可梦数量/);
assert.match(ops.sections[1].note, /120 米/);
assert.match(ops.sections[1].methodNote, /捕捉、击败或吓跑/);
assert.equal(ops.sections[2].title, '进入大规模发生（第二次）');
assert.deepEqual(ops.sections[3].steps.map(step => step.count), [1, 3]);
assert.equal(ops.sections[0].steps.at(-1).checkTargetAfter, undefined);
assert.equal(ops.sections[3].steps.at(-1).checkTargetAfter, undefined);
assert.equal(ops.sections.at(-1).title, '目标出现');
assert.equal(ops.sections.at(-1).targetEvent, true);
assert.deepEqual(ops.chainOperations[0].steps.map(step => step.count), [1, 1, 1, 1, 3]);
const ordinary = view.buildOperationSections({ path: 'Path: D1, D3' });
assert.deepEqual(ordinary.sections[0].steps.map(step => step.count), [1, 3]);
assert.equal(ordinary.sections.at(-1).targetEvent, true);
assert.equal(ordinary.sections.at(-1).title, '目标出现');
const initial = view.buildOperationSections({ path: 'Initial Spawn 4' });
assert.equal(initial.sections[0].note, '目标位于初始生成的第 4 只宝可梦；这是生成位置，不是需要清除的宝可梦数量。');
assert.equal(initial.sections[0].targetEvent, true);
assert.equal(view.buildRouteSummary({ path: 'Path: D1', multi: 'false' }).hasMultiple, false);
assert.equal(view.buildRouteSummary({ path: 'Path: D1', multi: 'true' }).hasMultiple, true);
assert.equal(view.buildRouteSummary({ path: 'Path: D1', multi: 'true' }).multiShinyCount, null);

// Alternative routes to one shiny target must not be classified as simultaneous shines.
const oneShinyWithAlternative = view.buildRouteSummary({
  path: 'Path: D1, D1, D1, D1, D3',
  chains: [],
  dupes: ['First Round Path: D1, D1, D1, D1, D4']
});
assert.equal(oneShinyWithAlternative.hasMultiple, false);
assert.equal(oneShinyWithAlternative.dupes.length, 1);

// A bonus round that starts from an initial spawn is not a missing/empty second wave.
const bonusInitial = view.buildRouteSummary({
  path: 'First Round Path: [D1, D1, D1, D2] + Revisit [3, 1] + Bonus Initial Spawn 4'
});
assert.equal(bonusInitial.path.hasBonus, true);
assert.equal(bonusInitial.path.initialSpawn, null);
assert.equal(bonusInitial.path.bonusInitialSpawn, 4);
assert.equal(bonusInitial.lines.at(-1).label, '第二轮初始生成');
assert.equal(bonusInitial.lines.at(-1).value, '第 4 只');
const bonusInitialOps = view.buildOperationSections({
  path: 'First Round Path: [D1, D1, D1, D2] + Revisit [3, 1] + Bonus Initial Spawn 4'
});
assert.equal(bonusInitialOps.sections[2].title, '进入大规模发生（第二次）');
assert.equal(bonusInitialOps.sections.at(-1).title, '目标出现');
assert.equal(bonusInitialOps.sections.at(-1).targetEvent, true);
assert.equal(bonusInitialOps.sections.at(-1).steps.length, 0);
assert.equal(bonusInitialOps.sections.at(-1).note.includes('第 4 只'), true);
assert.equal(bonusInitialOps.sections[0].targetEvent, undefined);
assert.equal(bonusInitialOps.sections[1].targetEvent, undefined);
assert.deepEqual(bonusInitialOps.sections[1].revisitMarkers.map(item => item.marker), [3, 1]);
assert.equal(bonusInitialOps.sections[1].revisitMarkers[0].title, '群聚剩余 3 只时');

// Simultaneous-shiny chain summary must retain first-round/revisit/bonus details.
assert.equal(
  view.formatChainPath('First Round Path: D2, D1, D2 + Revisit [1] + Bonus Initial Spawn 3'),
  '第一轮路径：D2, D1, D2 + 重新访问 [1] + 第二轮初始生成：第 3 只'
);
console.log('result_view tests passed');
