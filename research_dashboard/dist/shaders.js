export const starVertexShader = `
attribute float size;
attribute float brightness;
varying float vBrightness;
uniform float pxScale;
void main() {
  vBrightness = brightness;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = min(size * pxScale / max(-mv.z, 0.001), 64.0);
  gl_Position = projectionMatrix * mv;
}`;

export const starFragmentShader = `
varying float vBrightness;
void main() {
  float d = length(gl_PointCoord - 0.5);
  float a = 1.0 - smoothstep(0.15, 0.5, d);
  gl_FragColor = vec4(vec3(0.62, 0.72, 1.0), a * vBrightness);
}`;

export const nodeGlowVertexShader = `
attribute vec3 nodeColor;
attribute vec3 coreColor;
attribute float size;
attribute float coreSize;
varying vec3 vColor;
varying vec3 vCore;
varying float vCoreRatio;
uniform float pxScale;
void main() {
  vColor = nodeColor;
  vCore = coreColor;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float corePixels = min(max(coreSize * pxScale / max(-mv.z, 0.001), 4.0), 5.0);
  float haloPixels = min(max(size * pxScale / max(-mv.z, 0.001), corePixels * 5.0), 64.0);
  vCoreRatio = corePixels / haloPixels;
  gl_PointSize = haloPixels;
  gl_Position = projectionMatrix * mv;
}`;

export const nodeGlowFragmentShader = `
uniform float glowStrength;
varying vec3 vColor;
varying vec3 vCore;
varying float vCoreRatio;
void main() {
  float d = length(gl_PointCoord - 0.5);
  float halo = pow(max(1.0 - d * 2.0, 0.0), 2.0) * glowStrength * 0.55;
  float ratio = min(vCoreRatio, 1.0 / 4.0);
  float core = 1.0 - smoothstep(ratio * 0.42, ratio * 0.5, d);
  gl_FragColor = vec4(vColor * halo + vCore * core, halo + core);
}`;
