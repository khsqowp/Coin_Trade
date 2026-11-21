import assert from 'node:assert/strict';
import { createLayout } from '../dist/force3d.js';
import { nodeRadius } from '../dist/size.js';
import { readFile } from 'node:fs/promises';

const nodes = [
  { id: 'a', family: 'trend', verification_depth: 1 },
  { id: 'b', family: 'trend', verification_depth: 4 },
  { id: 'c', family: 'mean_reversion', verification_depth: 0 },
];
const edges = [
  { source: 'a', target: 'b', edge_kind: 'return_correlation', weight: 0.9 },
  { source: 'a', target: 'c', edge_kind: 'return_correlation', weight: 0.2 },
];
const first = createLayout(nodes, edges, { seed: 'fixture', iterations: 180 });
const second = createLayout(nodes, edges, { seed: 'fixture', iterations: 180 });
assert.deepEqual(first, second, '같은 시드는 같은 배치를 만들어야 합니다');
for (const point of Object.values(first)) for (const value of Object.values(point)) assert.ok(Number.isFinite(value));
const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
assert.ok(distance(first.a, first.b) < distance(first.a, first.c), '강한 연결은 약한 연결보다 가까워야 합니다');
const sizeSource = await readFile(new URL('../dist/size.js', import.meta.url), 'utf8');
assert.ok(!sizeSource.includes('return'));
const original = { verification_depth: 2, train_return: 50, test_return: -10 };
const originalSize = nodeRadius(original);
assert.equal(nodeRadius({ ...original, train_return: -1e10, test_return: 1e10 }), originalSize);
assert.ok(nodeRadius({ verification_depth: 3 }) > originalSize);
console.log('프런트 단위 확인: 6개 통과');
