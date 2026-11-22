const seedOf = value => {
  let seed = 2166136261;
  for (const char of String(value)) seed = Math.imul(seed ^ char.charCodeAt(0), 16777619);
  return seed >>> 0;
};

function randomFor(seed) {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

export function createLayout(nodes, edges, options = {}) {
  const count = nodes.length;
  const random = randomFor(seedOf(options.seed ?? nodes.map(node => node.id).join('|')));
  const points = nodes.map(() => ({
    x: (random() - 0.5) * 120,
    y: (random() - 0.5) * 120,
    z: (random() - 0.5) * 120,
  }));
  const indexes = new Map(nodes.map((node, index) => [node.id, index]));
  const links = edges.map(edge => ({
    a: indexes.get(edge.source), b: indexes.get(edge.target),
    weight: Math.max(0.05, Math.min(1, Number(edge.weight) || 0.05)),
    kind: edge.edge_kind,
  })).filter(edge => edge.a !== undefined && edge.b !== undefined);
  const groupOf = options.groupOf ?? (node => node.family);
  const groups = nodes.map(groupOf);
  const clusterOf = options.clusterOf ?? (() => null);
  const clusters = nodes.map(clusterOf);
  const iterations = options.iterations ?? 150;
  const velocity = points.map(() => ({ x: 0, y: 0, z: 0 }));

  for (let step = 0; step < iterations; step++) {
    const force = points.map(() => ({ x: 0, y: 0, z: 0 }));
    for (let a = 0; a < count; a++) {
      const left = points[a];
      for (let b = a + 1; b < count; b++) {
        const right = points[b];
        let dx = left.x - right.x, dy = left.y - right.y, dz = left.z - right.z;
        let distance2 = dx * dx + dy * dy + dz * dz + 0.01;
        const distance = Math.sqrt(distance2);
        const push = Math.min(5, 190 / distance2) * (options.repulsion ?? 1);
        dx /= distance; dy /= distance; dz /= distance;
        force[a].x += dx * push; force[a].y += dy * push; force[a].z += dz * push;
        force[b].x -= dx * push; force[b].y -= dy * push; force[b].z -= dz * push;
        if (groups[a] === groups[b]) {
          const pull = (options.groupPull ?? 0.0006) * (options.attraction ?? 1);
          force[a].x -= dx * pull; force[a].y -= dy * pull; force[a].z -= dz * pull;
          force[b].x += dx * pull; force[b].y += dy * pull; force[b].z += dz * pull;
        }
        if (clusters[a] != null && clusters[a] === clusters[b]) {
          const pull = (options.clusterPull ?? 0) * (options.attraction ?? 1);
          force[a].x -= dx * pull; force[a].y -= dy * pull; force[a].z -= dz * pull;
          force[b].x += dx * pull; force[b].y += dy * pull; force[b].z += dz * pull;
        }
      }
    }
    for (const edge of links) {
      const a = points[edge.a], b = points[edge.b];
      const dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z;
      const distance = Math.sqrt(dx * dx + dy * dy + dz * dz) || 0.01;
      const strength = (edge.kind === 'return_correlation' ? edge.weight : 0.28) * (options.attraction ?? 1);
      const rest = edge.kind === 'return_correlation' ? 88 - strength * 54 : 145;
      const spring = Math.max(-2, Math.min(2, (distance - rest) * strength * 0.012));
      const fx = dx / distance * spring, fy = dy / distance * spring, fz = dz / distance * spring;
      force[edge.a].x += fx; force[edge.a].y += fy; force[edge.a].z += fz;
      force[edge.b].x -= fx; force[edge.b].y -= fy; force[edge.b].z -= fz;
    }
    for (let i = 0; i < count; i++) {
      const p = points[i], f = force[i], v = velocity[i];
      const gravity = options.gravity ?? 0.006;
      f.x -= p.x * gravity; f.y -= p.y * gravity; f.z -= p.z * gravity;
      v.x = (v.x + f.x) * 0.78; v.y = (v.y + f.y) * 0.78; v.z = (v.z + f.z) * 0.78;
      p.x += v.x; p.y += v.y; p.z += v.z;
    }
  }
  return Object.fromEntries(nodes.map((node, index) => [node.id, points[index]]));
}
