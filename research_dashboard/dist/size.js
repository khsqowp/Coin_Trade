export const nodeRadius = node => 1.15 + Math.min(2.8, Math.sqrt(Math.max(0, Number(node.verification_depth) || 0)) * 0.5);
