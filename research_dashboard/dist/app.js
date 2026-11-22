import * as THREE from 'three';
import { OrbitControls } from './vendor/three-r160/examples/jsm/controls/OrbitControls.js';
import { createLayout } from './force3d.js';
import { nodeRadius } from './size.js';
import { TEXT as T, familyName } from './i18n.js';
import { nodeGlowFragmentShader, nodeGlowVertexShader, starFragmentShader, starVertexShader } from './shaders.js';

const $ = selector => document.querySelector(selector);
const colors = { not_tested: '#89939c', failed: '#ef5350', downgraded: '#ff9800', adjusted_pass: '#fdd835', forward_running: '#43a047', forward_confirmed: '#00e676' };
const verdicts = Object.keys(colors);
const clusterPalette = ['#3fe0d0','#9b7bff','#ffd24a','#ff6fb5','#4aa3ff','#ff9a52','#8ee06b','#8f9bd6'];
const lightClusterPalette = ['#007c72','#6543b5','#9b6900','#b82f71','#1766ad','#b94f00','#3e7d27','#5b638a'];
let clusterByFamily = new Map(), activeCluster = null, hiddenClusters = new Set(), colorMode = 'cluster', stars;
const baseStarBrightness = [];
const settings = { glow: 1.4, nodeScale: 1, edgeWidth: 1, edgeOpacity: .5, showEdges: true, showLabels: true, labelDistance: 420, repulsion: 1, attraction: 1 };
let data, scene, camera, renderer, controls, sphereMesh, nodePointGeometry, positions = {}, visibleNodes = [], visibleEdges = [], nodeIndex = new Map();
let selectedId = null, hoveredId = null, target = new THREE.Vector3(), flatMode = false, layoutSignature = '', layoutRunning = false, cameraFitted = false;
const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2(), dummy = new THREE.Object3D(), materials = [];
const labels = $('#labels');

function initializeText() {
  $('#settings-title').textContent = T.settings; $('#display-title').textContent = T.display; $('#labels-title').textContent = T.labels; $('#links-title').textContent = T.links; $('#clusters-title').textContent = T.clusters; $('#reset-filters').textContent = T.resetFilters; $('#search').placeholder = T.search; $('#family-label').textContent = T.family; $('#timeframe-label').textContent = T.timeframe; $('#verdict-label').textContent = T.verdict; $('#symbol-label').textContent = T.symbol;
  $('#reset').textContent = T.reset; $('#flat').textContent = T.flat; $('#theme').textContent = T.theme;
  $('#strength-label').textContent = T.filterStrength; $('#controls-note').textContent = T.controls;
  $('#edge-note').textContent = T.correlationNote; $('#edge-threshold').textContent = T.thresholds;
  $('#layout-status').textContent = T.loading; $('#empty').textContent = T.empty; $('#webgl-error').textContent = T.webglError;
  $('#detail-close').textContent = T.close; $('#list-title').textContent = T.list;
}
function timeframe(v) { if (T.timeframeNames[v]) return T.timeframeNames[v]; const match = /^(\d+)([mhdw])$/.exec(v); return match ? `${match[1]}${({ m: '분봉', h: '시간봉', d: '일봉', w: '주봉' })[match[2]]}` : T.unknown; }
function family(v) { return familyName(v); }
function side(v) { return T.sideNames[v] || T.sideNames.unknown; }
function symbolClass(v) { return T.symbolNames[v] || T.symbolNames.unknown; }
function strategyDisplay(node) { return `${family(node.family)} · ${timeframe(node.timeframe)} · ${side(node.side)}`; }
function verdict(v) { return T[v] || T.not_tested; }
function status(v) { return T[`status_${v}`] || T.status_not_run; }
function escaped(value) { return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char])); }
function number(value) { return value == null ? '기록 없음' : Number(value).toFixed(2); }
function safeId(value) { return `n-${Array.from(value).map(ch => ch.codePointAt(0).toString(16)).join('-')}`; }

function setupScene() {
  try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); }
  catch { $('#webgl-error').hidden = false; $('.list-panel').classList.add('open'); $('#list-toggle').querySelector('b').textContent='−'; return false; }
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2)); renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.debug.checkShaderErrors = true;
  $('#graph').append(renderer.domElement);
  scene = new THREE.Scene(); scene.background = null; addStars();
  camera = new THREE.PerspectiveCamera(50, 1, 0.1, 2500); camera.position.set(0, 0, 400);
  controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true; controls.dampingFactor = 0.075;
  controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
  controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };
  controls.target.copy(target); controls.addEventListener('change', draw);
  scene.add(new THREE.AmbientLight(0xffffff, 2.1));
  const key = new THREE.DirectionalLight(0xffffff, 2.4); key.position.set(140, 210, 350); scene.add(key);
  renderer.domElement.addEventListener('pointermove', onPointerMove);
  renderer.domElement.addEventListener('pointerleave', () => { hoveredId = null; renderLabels(); applyEmphasis(); });
  renderer.domElement.addEventListener('dblclick', onDoubleClick);
  renderer.domElement.addEventListener('click', onGraphClick);
  renderer.domElement.addEventListener('contextmenu', event => event.preventDefault());
  window.addEventListener('resize', resize); resize(); animate(); return true;
}
function resize() {
  if (!renderer) return;
  const rect = $('#graph').getBoundingClientRect(); renderer.setSize(rect.width, rect.height, false);
  updatePointScale(rect.height);
  camera.aspect = rect.width / Math.max(rect.height, 1); camera.updateProjectionMatrix(); draw();
}
function updatePointScale(height = $('#graph').getBoundingClientRect().height) {
  if (!renderer || !camera) return;
  const pxScale = height * renderer.getPixelRatio() / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
  scene.traverse(object => { if (object.material?.uniforms?.pxScale) object.material.uniforms.pxScale.value = pxScale; });
}
function animate() { requestAnimationFrame(animate); if (controls?.update()) draw(); }
function draw() { if (renderer && scene && camera) renderer.render(scene, camera); }
function clearGraph() {
  for (const object of [...scene.children]) if (object.userData.graphObject) { scene.remove(object); object.geometry?.dispose(); if (object.material) { if (Array.isArray(object.material)) object.material.forEach(m => m.dispose()); else object.material.dispose(); } }
  materials.length = 0; sphereMesh = null; nodePointGeometry = null;
}
function signature(nodes, edges) { return nodes.map(n => n.id).join('\n') + '|' + edges.map(e => `${e.source}:${e.target}:${e.edge_kind}`).join('\n'); }
function updateDataOnly() {
  if (!sphereMesh) return;
  visibleNodes.forEach((node, index) => { sphereMesh.setColorAt(index, new THREE.Color(colors[node.verdict] || colors.not_tested)); });
  if (sphereMesh.instanceColor) sphereMesh.instanceColor.needsUpdate = true;
  render();
}
function displayPoint(point) { return new THREE.Vector3(point.x, point.y, point.z * (flatMode ? 0.035 : 1)); }
function makeLayout() {
  if (!scene) { renderList(visibleNodes); return; }
  if (!visibleNodes.length) { clearGraph(); $('#empty').hidden = false; return; }
  $('#empty').hidden = true; const next = signature(visibleNodes, visibleEdges);
  if (next === layoutSignature && sphereMesh) { buildObjects(); renderLabels(); draw(); return; }
  layoutSignature = next; layoutRunning = true; $('#layout-status').hidden = false; $('#layout-status').textContent = T.loadingLayout;
  const snapshotNodes = visibleNodes, snapshotEdges = visibleEdges;
  const runChunk = (iterationCount) => {
    if (snapshotNodes !== visibleNodes) return;
    const result = createLayout(snapshotNodes, snapshotEdges, { seed: snapshotNodes.map(n => n.id).join('|'), iterations: iterationCount, repulsion: settings.repulsion, attraction: settings.attraction, groupOf: node => node.family, groupPull: 0.16, clusterOf: node => (clusterByFamily.get(node.family) ?? 7) < 7 ? clusterByFamily.get(node.family) : null, clusterPull: 0.00035, gravity: 0.025 });
    positions = result; buildObjects(); fitCamera(); layoutRunning = false; $('#layout-status').textContent = ''; $('#layout-status').hidden = true; renderLabels(); draw();
  };
  requestAnimationFrame(() => runChunk(150));
}
function buildObjects() {
  clearGraph(); nodeIndex = new Map(visibleNodes.map((node, index) => [node.id, index]));
  const geometry = new THREE.SphereGeometry(1, 10, 8);
  const material = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, colorWrite: false, depthWrite: false });
  sphereMesh = new THREE.InstancedMesh(geometry, material, visibleNodes.length); sphereMesh.userData.graphObject = true;
  visibleNodes.forEach((node, index) => {
    const point = displayPoint(positions[node.id]); dummy.position.copy(point); const radius = nodeRadius(node) * 0.7; dummy.scale.setScalar(radius * settings.nodeScale); dummy.updateMatrix();
    sphereMesh.setMatrixAt(index, dummy.matrix); sphereMesh.setColorAt(index, new THREE.Color(colors[node.verdict] || colors.not_tested));
  });
  sphereMesh.instanceMatrix.needsUpdate = true; if (sphereMesh.instanceColor) sphereMesh.instanceColor.needsUpdate = true; scene.add(sphereMesh);
  addEdges(); addNodeGlow(); applyEmphasis();
}
function addStars() {
  const geo = new THREE.BufferGeometry(), points = [];
  let state = 99173; const rand = () => ((state = (Math.imul(state,1664525)+1013904223)>>>0) / 4294967296);
  const sizes=[], brightness=[];
  for (let i=0;i<1800;i++) { points.push((rand()-.5)*2200,(rand()-.5)*1600,-200-rand()*900); sizes.push(.7+rand()*1.7); const value=.12+rand()*.38; brightness.push(value); baseStarBrightness.push(value); }
  geo.setAttribute('position', new THREE.Float32BufferAttribute(points,3));
  geo.setAttribute('size',new THREE.Float32BufferAttribute(sizes,1)); geo.setAttribute('brightness',new THREE.Float32BufferAttribute(brightness,1));
  const material=new THREE.ShaderMaterial({transparent:true,depthWrite:false,uniforms:{pxScale:{value:0}},vertexShader:starVertexShader,fragmentShader:starFragmentShader});
  stars = new THREE.Points(geo,material); stars.userData.graphObject=false; scene.add(stars); updateStarBrightness();
}
function activePalette() { return document.body.classList.contains('light') ? lightClusterPalette : clusterPalette; }
function clusterColor(node) { return activePalette()[clusterByFamily.get(node.family) ?? 7]; }
function updateStarBrightness() {
  const attribute = stars?.geometry.getAttribute('brightness');
  if (!attribute) return;
  const factor = document.body.classList.contains('light') ? .12 : 1;
  baseStarBrightness.forEach((value, index) => attribute.setX(index, value * factor));
  attribute.needsUpdate = true;
}
function addNodeGlow() {
  const geo = new THREE.BufferGeometry(), pts=[], cols=[], sizes=[];
  const halo=[], core=[]; visibleNodes.forEach(node=>{const p=displayPoint(positions[node.id]),c=new THREE.Color(clusterColor(node));pts.push(p.x,p.y,p.z);cols.push(c.r,c.g,c.b);halo.push(c.r,c.g,c.b);core.push(nodeRadius(node)*10*settings.nodeScale);sizes.push(nodeRadius(node)*50*settings.nodeScale*settings.glow);});
  geo.setAttribute('position',new THREE.Float32BufferAttribute(pts,3)); geo.setAttribute('nodeColor',new THREE.Float32BufferAttribute(cols,3)); geo.setAttribute('coreColor',new THREE.Float32BufferAttribute(halo,3)); geo.setAttribute('size',new THREE.Float32BufferAttribute(sizes,1)); geo.setAttribute('coreSize',new THREE.Float32BufferAttribute(core,1));
  nodePointGeometry=geo;
  const mat=new THREE.ShaderMaterial({transparent:true,depthTest:false,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{glowStrength:{value:settings.glow},pxScale:{value:0}},vertexShader:nodeGlowVertexShader,fragmentShader:nodeGlowFragmentShader}); const glow=new THREE.Points(geo,mat); glow.userData.graphObject=true; glow.frustumCulled=false; glow.renderOrder=10; scene.add(glow); updatePointScale();
}
function fitCamera(){ if(cameraFitted||!visibleNodes.length)return; const center=new THREE.Vector3(); visibleNodes.forEach(n=>center.add(displayPoint(positions[n.id])));center.multiplyScalar(1/visibleNodes.length);let radius=1;visibleNodes.forEach(n=>radius=Math.max(radius,center.distanceTo(displayPoint(positions[n.id]))));const distance=radius*1.33/Math.sin(THREE.MathUtils.degToRad(camera.fov/2));target.copy(center);controls.target.copy(center);camera.position.set(center.x,center.y,center.z+distance);camera.updateProjectionMatrix();controls.update();cameraFitted=true; }
function addEdges() {
  const groups = new Map();
  if (!settings.showEdges) return;
  for (const edge of visibleEdges) {
    const a = positions[edge.source], b = positions[edge.target]; if (!a || !b) continue;
    const weight = Math.max(0, Math.min(1, Number(edge.weight) || 0));
    const isApprox = edge.edge_kind === 'metadata_similarity';
    const kind = isApprox ? 'approx' : (weight >= .7 ? 'strong' : weight >= .5 ? 'medium' : 'weak');
    const key = `${kind}:${isApprox ? 'meta' : 'corr'}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ a, b, weight, isApprox });
  }
  for (const [key, rows] of groups) {
    const [kind, type] = key.split(':'); const radius = (kind === 'strong' ? 0.72 : kind === 'medium' ? 0.36 : kind === 'weak' ? 0.16 : 0.2) * settings.edgeWidth;
    const color = type === 'meta' ? '#82919d' : kind === 'strong' ? '#f4d35e' : kind === 'medium' ? '#61c8be' : '#778491';
    const material = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: (kind === 'strong' ? .55 : kind === 'medium' ? .2 : .07) * settings.edgeOpacity, depthWrite: false });
    const geometry = new THREE.CylinderGeometry(radius, radius, 1, 5, 1, true); const mesh = new THREE.InstancedMesh(geometry, material, rows.length); mesh.userData.graphObject = true;
    rows.forEach((edge, i) => {
      const start = displayPoint(edge.a), end = displayPoint(edge.b);
      dummy.position.copy(start).add(end).multiplyScalar(.5); dummy.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), end.clone().sub(start).normalize());
      dummy.scale.set(1, start.distanceTo(end), 1); dummy.updateMatrix(); mesh.setMatrixAt(i, dummy.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true; mesh.renderOrder = 1; scene.add(mesh);
  }
}
function applyEmphasis() {
  if(!sphereMesh)return; const focus=hoveredId||selectedId, node=visibleNodes.find(n=>n.id===focus); const neighbors=new Set(); if(node) visibleEdges.forEach(e=>{if(e.source===focus)neighbors.add(e.target);if(e.target===focus)neighbors.add(e.source)});
  const halo=nodePointGeometry?.getAttribute('nodeColor'), core=nodePointGeometry?.getAttribute('coreColor');
  visibleNodes.forEach((n,i)=>{const cluster=clusterByFamily.get(n.family)??7; const hidden=hiddenClusters.has(cluster);const dim=(node&&n.id!==focus&&!neighbors.has(n.id))||(activeCluster!=null&&cluster!==activeCluster)||hidden; const amount=dim?.18:focus&&n.id===focus?1.8:1;const c=colorMode==='cluster'?new THREE.Color(clusterColor(n)):new THREE.Color(colors[n.verdict]||colors.not_tested); sphereMesh.setColorAt(i,c.clone().multiplyScalar(amount)); if(halo){const h=new THREE.Color(clusterColor(n)).multiplyScalar(amount);halo.setXYZ(i,h.r,h.g,h.b);} if(core){const v=new THREE.Color(clusterColor(n)).multiplyScalar(amount);core.setXYZ(i,v.r,v.g,v.b);}}); if(sphereMesh.instanceColor)sphereMesh.instanceColor.needsUpdate=true; if(halo)halo.needsUpdate=true;if(core)core.needsUpdate=true; draw();
}
function recolor(){ if(sphereMesh){sphereMesh.material.color.set(0xffffff);buildObjects();} }
function setPanel(button,panel,open){panel.classList.toggle('open',open);button.querySelector('b').textContent=open?'−':'＋';}
function render() {
  if (!data) return;
  const query = $('#search').value.trim().toLocaleLowerCase(); const threshold = Number($('#strength').value);
  const matching = data.nodes.filter(node => (!$('#family').value || node.family === $('#family').value) && (!$('#timeframe').value || node.timeframe === $('#timeframe').value) && (!$('#verdict').value || node.verdict === $('#verdict').value) && (!$('#symbol').value || node.symbol_class === $('#symbol').value) && (!query || `${node.name} ${node.strategy_id} ${node.id}`.toLocaleLowerCase().includes(query)));
  const allowed = new Set(matching.map(node => node.id));
  visibleNodes = matching.sort((a, b) => b.verification_depth - a.verification_depth || forwardRank(a) - forwardRank(b) || a.id.localeCompare(b.id));
  visibleEdges = data.edges.filter(edge => allowed.has(edge.source) && allowed.has(edge.target) && (edge.edge_kind === 'metadata_similarity' || edge.weight >= threshold));
  visibleNodes=visibleNodes.filter(n=>!hiddenClusters.has(clusterByFamily.get(n.family)??7)); makeLayout(); renderList(visibleNodes);
}
function forwardRank(node) { const value = node.forward?.verdict; return value === 'ON TRACK' ? 0 : value === 'UNDERPERFORMING' ? 1 : value === 'NEGATIVE' ? 2 : 3; }
function fillSelect(id, values, label) {
  const element = $(id), old = element.value;
  element.innerHTML = `<option value="">${T.all}</option>` + [...new Set(values)].sort().map(value => `<option value="${escaped(value)}">${escaped(label(value))}</option>`).join('');
  element.value = old;
}
function renderHeader() {
  const counts = data.counts;
  $('#headline').textContent = `${counts.adjusted_tested}개 중 ${counts.adjusted_passed}개가 다중검정 보정 후 통과`; $('#confirmed').textContent = `${T.confirmed} ${counts.confirmed_real_winners}`;
  $('#stats').innerHTML = [[T.countArchived, counts.total_archived], [T.countComplete, counts.spec_complete], [T.countImplemented, counts.implemented_tested], [T.countTrials, counts.trials_counted]].map(([label, value]) => `<span class="stat"><b>${escaped(value)}</b>${escaped(label)}</span>`).join('');
  $('#forward').innerHTML = data.forward.map(forwardCard).join('');
  fillSelect('#family', data.nodes.map(n => n.family), family); fillSelect('#timeframe', data.nodes.map(n => n.timeframe), timeframe); fillSelect('#verdict', data.nodes.map(n => n.verdict), verdict); fillSelect('#symbol', data.nodes.map(n => n.symbol_class), symbolClass);
  const families=[...new Set(data.nodes.map(n=>n.family))].sort((a,b)=>data.nodes.filter(n=>n.family===b).length-data.nodes.filter(n=>n.family===a).length); clusterByFamily=new Map(families.map((f,i)=>[f,i<7?i:7]));
  const palette = activePalette();
  const groups=new Map(); families.forEach(f=>groups.set(clusterByFamily.get(f),[...(groups.get(clusterByFamily.get(f))||[]),f])); $('#cluster-legend').innerHTML=[...groups].map(([id,fs])=>`<div class="cluster-row"><button class="cluster-chip" data-cluster="${id}" style="--cluster-color:${palette[id]}"><i></i><span>${id===7?T.clusterOther:escaped(family(fs[0]))}</span><small>${data.nodes.filter(n=>(clusterByFamily.get(n.family)??7)===id).length}</small></button><button class="cluster-hide" data-hide="${id}">${hiddenClusters.has(id)?'표시':'숨김'}</button></div>`).join('');
}
function forwardText(value) { return ({ 'not loaded': T.forwardNotLoaded, 'INSUFFICIENT DATA': T.forwardInsufficient, NEGATIVE: T.forwardNegative, UNDERPERFORMING: T.forwardUnder, 'ON TRACK': T.forwardTrack })[value] || T.forwardNotLoaded; }
function sparkline(values) {
  if (!values?.length) return '';
  const numbers = values.map(point => Number(point.return_pct));
  const low = Math.min(...numbers), high = Math.max(...numbers), range = high - low || 1;
  const coords = numbers.map((value, index) => {
    const x = numbers.length < 2 ? 50 : index * 100 / (numbers.length - 1);
    const y = 28 - (value - low) / range * 24;
    return x.toFixed(1) + ',' + y.toFixed(1);
  }).join(' ');
  return '<svg class="equity-curve" viewBox="0 0 100 32" role="img" aria-label="' + T.forwardCurve + '"><polyline points="' + coords + '"></polyline></svg>';
}
function forwardCard(row) {
  const name = T.profileNames[row.profile] || T.noForward;
  if (!row.loaded) return '<article class="forward-card"><h3>' + escaped(name) + '</h3><div class="big">' + T.forwardNotLoaded + '</div></article>';
  const age = row.copied_at ? Math.max(0, Math.floor((Date.now() - Date.parse(row.copied_at)) / 60000)) : null;
  const copied = age == null ? T.noCopyTime : T.copiedMinutes + ' ' + age + T.copiedSuffix;
  const decision = row.no_signals ? T.forwardNoSignals : row.data_sufficient ? T.forwardPossible : T.forwardInsufficient;
  const confirmation = row.confirmed ? T.forwardConfirmed : T.forwardNotConfirmed;
  const remaining = row.trades_left + '건 · ' + row.days_left + '일';
  const expected = row.backtest_expectation_return_pct == null
    ? T.noBacktestPeriod
    : T.expectedReturn + ' ' + row.backtest_expectation_return_pct.toFixed(2) + '% · 기대 거래 ' + row.backtest_expectation_trades.toFixed(1) + '건';
  const update = row.last_update_time ? new Date(row.last_update_time).toLocaleString('ko-KR') : T.unknown;
  const candle = row.last_candle_time ? new Date(row.last_candle_time).toLocaleString('ko-KR') : T.unknown;
  const health = row.stale
    ? '<p class="forward-warning">' + T.forwardStale + ': ' + update + '</p>'
    : '<p>' + T.forwardFresh + ': ' + update + '</p>';
  return '<article class="forward-card' + (row.confirmed ? ' confirmed' : '') + '">' +
    '<h3>' + escaped(name) + '</h3><div class="big">' + decision + ' · ' + confirmation + '</div>' +
    '<p>' + T.trades + ' ' + row.trades + '건 / ' + row.required_trades + '건 · ' + row.days_running.toFixed(1) + '일 진행</p>' +
    '<p>' + T.forwardRemaining + ': ' + remaining + '</p>' +
    '<p>' + T.forwardPnl + ': ' + row.realized_pnl_pct.toFixed(2) + '% 실현</p>' + sparkline(row.equity_curve) +
    '<p>' + T.forwardExpected + ': 실현 ' + row.realized_pnl_pct.toFixed(2) + '% · ' + expected + '</p>' +
    '<p>' + T.forwardLastCandle + ': ' + candle + ' · ' + T.forwardOpen + ' ' + row.open_positions + '건</p>' +
    health + '<p class="copy-age">' + copied + '</p></article>';
}
function renderList(nodes) { const max=Math.max(1,...nodes.map(n=>n.verification_depth)); $('#results').innerHTML=`<div class="list-count">${T.totalCount} ${nodes.length}</div>`+(nodes.slice(0,100).map(node=>`<button class="result" data-id="${escaped(node.id)}"><span class="result-name" title="${escaped(strategyDisplay(node))}">${escaped(strategyDisplay(node))}</span><span class="strategy-id" title="${escaped(node.strategy_id)}">${escaped(node.strategy_id)}</span><span class="depth-line"><span class="depth-track"><i style="width:${Math.max(0,node.verification_depth/max*100)}%"></i></span>${node.verification_depth}</span></button>`).join('') || `<p>${T.searchEmpty}</p>`); }
function renderLabels() {
  labels.replaceChildren(); if (!camera || !positions || !settings.showLabels) return;
  const ids = new Set([selectedId, hoveredId]); const closeEnough = camera.position.distanceTo(target) < settings.labelDistance;
  if (closeEnough) for (const node of visibleNodes) if (ids.has(node.id)) {
    const p = displayPoint(positions[node.id]).project(camera); const tag = document.createElement('span');
    tag.className = 'node-label'; tag.textContent = strategyDisplay(node); tag.style.left = `${(p.x * .5 + .5) * labels.clientWidth}px`; tag.style.top = `${(-p.y * .5 + .5) * labels.clientHeight}px`; labels.append(tag);
  }
  const node = visibleNodes.find(item => item.id === (hoveredId || selectedId)); if (node) labels.title = `${strategyDisplay(node)} · ${node.strategy_id}`; else labels.removeAttribute('title');
}
function onPointerMove(event) {
  if (!sphereMesh || !renderer) return;
  const rect = renderer.domElement.getBoundingClientRect(); pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera); const hit = raycaster.intersectObject(sphereMesh, false)[0]; const nextId = hit ? visibleNodes[hit.instanceId]?.id : null;
  if (nextId !== hoveredId) { hoveredId = nextId; renderer.domElement.style.cursor = hoveredId ? 'pointer' : 'grab'; renderLabels(); applyEmphasis(); }
}
function onGraphClick(event) { if (!sphereMesh || event.detail > 1) return; const rect = renderer.domElement.getBoundingClientRect(); pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1); raycaster.setFromCamera(pointer, camera); const hit = raycaster.intersectObject(sphereMesh, false)[0]; if (hit) { const node = visibleNodes[hit.instanceId]; if (node) focusNode(node); } }
function onDoubleClick() { if (!hoveredId) return; const point = displayPoint(positions[hoveredId]); smoothCamera(new THREE.Vector3(point.x, point.y, point.z + 95), point); }
function focusNode(node) {
  selectedId = node.id; const p = positions[node.id]; if (p) { const shown = displayPoint(p); target.copy(shown); const destination = new THREE.Vector3(shown.x, shown.y, shown.z + 90); smoothCamera(destination, shown); }
  showDetail(node); renderLabels(); applyEmphasis();
}
function smoothCamera(destination, lookAt) {
  const from = camera.position.clone(), fromTarget = controls.target.clone(), started = performance.now(), duration = 700;
  const move = now => { const k = Math.min(1, (now - started) / duration), eased = 1 - (1 - k) ** 3; camera.position.lerpVectors(from, destination, eased); controls.target.lerpVectors(fromTarget, lookAt, eased); controls.update(); if (k < 1) requestAnimationFrame(move); };
  requestAnimationFrame(move);
}
function showDetail(node) {
  const tests = node.tests.map(test => `<li class="${test.status}"><b>${escaped(T[test.name] || T.tests)}: ${escaped(status(test.status))}</b><span>${escaped(reason(test.name, test.status))}</span></li>`).join('');
  const years = node.per_year.length ? `<h3>${T.years}</h3><div class="years">${node.per_year.map(row => `<div><i class="${row.value < 0 ? 'negative' : ''}" style="height:${Math.max(5, Math.min(100, Math.abs(row.value) * 1.4))}px"></i><small>${row.year}</small></div>`).join('')}</div>` : '';
  const symbols = node.symbols.length ? ` · ${node.symbols.map(escaped).join(', ')}` : '';
  const summary = `${escaped(family(node.family))} · ${escaped(timeframe(node.timeframe))} · ${escaped(side(node.side))}${symbols}`;
  const english = [node.name, node.description].filter(Boolean).map(value => `<p>${escaped(value)}</p>`).join('');
  $('#detail-body').innerHTML = `<h2>${T.detail}</h2><p class="strategy-id">${escaped(node.strategy_id)}</p><p><b>${escaped(summary)}</b></p><p>${T.strategyWhat} ${escaped(family(node.family))}, ${escaped(timeframe(node.timeframe))}, ${escaped(side(node.side))} 조건을 살펴보는 방식입니다.</p><p>${escaped(verdict(node.verdict))} · ${T.passed} ${node.verification_depth} · ${T.failedCount} ${node.tests.filter(t => t.status === 'failed').length} · ${T.unknownCount} ${node.tests.filter(t => t.status === 'not_run').length}</p><h3>${T.tests}</h3><ul class="tests">${tests}</ul>${years}<h3>${T.forwardStatus}</h3><p>${escaped(forwardText(node.forward?.verdict || 'not loaded'))}</p><h3>${T.secondary}</h3><p>${T.train}: ${number(node.train_return)}% · ${T.test}: ${number(node.test_return)}% · ${T.null}: ${number(node.null_percentile)}</p><p>${T.params}: <code>${escaped(node.params || T.unknown)}</code></p><details><summary>${T.english}</summary>${english || `<p>${T.noReason}</p>`}</details>`;
  $('#detail').hidden = false;
}
function reason(name, state) {
  const table = {
    null: { passed: '우연한 결과보다 높은 기준을 넘었습니다.', failed: '우연과 비교한 기준을 넘지 못했습니다.', not_run: '비교 결과가 기록되지 않았습니다.' },
    plateau: { passed: '주변 설정에서도 결과가 유지됐습니다.', failed: '주변 설정에서 결과가 유지되지 않았습니다.', not_run: '주변 설정 검사가 기록되지 않았습니다.' },
    adjusted: { passed: '많은 시도를 감안한 재판정을 통과했습니다.', failed: '많은 시도를 감안한 재판정을 통과하지 못했습니다.', not_run: '재판정 결과가 기록되지 않았습니다.' },
    A1: { passed: '계열 전체 통계 확인을 통과했습니다.', failed: '계열 전체 통계 확인을 통과하지 못했습니다.', not_run: '계열 전체 통계 결과가 없습니다.' },
    B1: { passed: '연도별 확인 기준을 통과했습니다.', failed: '연도별 확인 기준을 통과하지 못했습니다.', not_run: '연도별 확인 결과가 없습니다.' },
    B2: { passed: '다른 종목 확인 기준을 통과했습니다.', failed: '다른 종목 확인 기준을 통과하지 못했습니다.', not_run: '다른 종목 확인 결과가 없습니다.' },
    B3: { passed: '넓힌 설정 확인 기준을 통과했습니다.', failed: '넓힌 설정 확인 기준을 통과하지 못했습니다.', not_run: '넓힌 설정 확인 결과가 없습니다.' },
    B4: { passed: '구간을 옮겨가며 확인한 결과가 양수였습니다.', failed: '구간을 옮겨가며 확인한 결과가 기준을 못 넘었습니다.', not_run: '구간별 확인 결과가 없습니다.' },
    B5: { passed: '그냥 보유하는 방법과의 비교 기준을 통과했습니다.', failed: '그냥 보유하는 방법과의 비교 기준을 통과하지 못했습니다.', not_run: '그냥 보유와 비교한 결과가 없습니다.' },
    B6: { passed: '신호 방식 확인 기준을 통과했습니다.', failed: '신호 방식 확인 기준을 통과하지 못했습니다.', not_run: '신호 방식 확인 결과가 없습니다.' },
    execution_stress: { passed: '비용을 두 배로 잡아도 결과가 양수였습니다.', failed: '비용을 두 배로 잡으면 결과가 양수가 아닙니다.', not_run: '비용 두 배 확인 결과가 없습니다.' },
    regime: { passed: '장세별 확인 중 하나 이상을 통과했습니다.', failed: '장세별 확인 기준을 통과하지 못했습니다.', not_run: '장세별 확인 결과가 없습니다.' },
  };
  return table[name]?.[state] || T.unknown;
}
async function load() {
  try {
    const response = await fetch(`data.json?시각=${Date.now()}`, { cache: 'no-store' }); if (!response.ok) throw new Error('데이터 응답 오류');
    const next = await response.json(); const previousSignature = data ? signature(data.nodes, data.edges) : '';
    data = next; renderHeader();
    if (previousSignature && previousSignature === signature(data.nodes, data.edges) && sphereMesh) { render(); updateDataOnly(); }
    else render();
  } catch { $('#headline').textContent = T.loadError; $('#layout-status').textContent = T.loadError; }
}
function toggleTheme() { document.body.classList.toggle('light'); updateStarBrightness(); renderHeader(); recolor(); }
function resetView() { const wasFlat = flatMode; flatMode = false; camera.position.set(0, 0, 400); target.set(0, 0, 0); controls.target.copy(target); controls.update(); $('#flat').textContent = T.flat; if (wasFlat && sphereMesh) buildObjects(); renderLabels(); }

initializeText();
if (new URLSearchParams(location.search).get('theme') === 'light') document.body.classList.add('light');
setupScene(); load();
['#family', '#timeframe', '#verdict', '#symbol', '#strength'].forEach(selector => $(selector).addEventListener('change', render));
$('#search').addEventListener('input', render);
$('#theme').onclick = toggleTheme; $('#reset').onclick = resetView;
$('#settings-toggle').onclick=()=>setPanel($('.settings'),$('.settings'),!$('.settings').classList.contains('open')); $('#list-toggle').onclick=()=>setPanel($('#list-toggle'),$('.list-panel'),!$('.list-panel').classList.contains('open'));
$('#filter-toggle').onclick=()=>{const open=$('.filters').classList.toggle('filters-open');$('#filter-toggle').setAttribute('aria-expanded',String(open));$('#filter-toggle').querySelector('b').textContent=open?'−':'＋'};
$('#cluster-legend').addEventListener('click',e=>{const hide=e.target.closest('[data-hide]');if(hide){const id=Number(hide.dataset.hide);hiddenClusters.has(id)?hiddenClusters.delete(id):hiddenClusters.add(id);renderHeader();render();return;}const chip=e.target.closest('[data-cluster]');if(!chip)return;const id=Number(chip.dataset.cluster);activeCluster=activeCluster===id?null:id;document.querySelectorAll('.cluster-chip').forEach(c=>c.classList.toggle('active',Number(c.dataset.cluster)===activeCluster));applyEmphasis();});
$('#color-mode').onchange=e=>{colorMode=e.target.value;recolor()};
[['glow','glow'],['node-scale','nodeScale'],['edge-width','edgeWidth'],['edge-opacity','edgeOpacity'],['label-distance','labelDistance']].forEach(([id,key])=>$('#'+id).oninput=e=>{settings[key]=Number(e.target.value);if(id==='label-distance')renderLabels();else recolor()});
document.querySelectorAll('.settings input[type="range"]').forEach(input=>{const output=document.createElement('output');const format=()=>Number(input.value).toFixed(input.id==='strength'?2:['glow','node-scale','edge-width'].includes(input.id)?1:0);output.value=format();input.after(output);input.addEventListener('input',()=>{output.value=format();});});
$('#links-on').onchange=e=>{settings.showEdges=e.target.checked;recolor()};$('#labels-on').onchange=e=>{settings.showLabels=e.target.checked;renderLabels()};
['repulsion','attraction'].forEach(id=>$('#'+id).onchange=e=>{settings[id]=Number(e.target.value);layoutSignature='';render()});
$('#reset-filters').onclick=()=>{['family','timeframe','verdict','symbol'].forEach(id=>$('#'+id).value='');$('#search').value='';render()};
if(innerWidth<=700){setPanel($('#settings-toggle'),$('.settings'),false);setPanel($('#list-toggle'),$('.list-panel'),false)}else{setPanel($('#settings-toggle'),$('.settings'),true);setPanel($('#list-toggle'),$('.list-panel'),true)}
$('#flat').onclick = () => { flatMode = !flatMode; if (flatMode) { camera.position.set(target.x, target.y, target.z + 520); camera.up.set(0, 1, 0); } else camera.position.set(target.x + 90, target.y + 45, target.z + 480); camera.lookAt(target); $('#flat').textContent = flatMode ? T.solid : T.flat; if (sphereMesh) buildObjects(); renderLabels(); draw(); };
$('#results').addEventListener('click', event => { const button = event.target.closest('[data-id]'); if (!button) return; const node = data.nodes.find(item => item.id === button.dataset.id); if (node) focusNode(node); });
$('#detail-close').onclick = () => { $('#detail').hidden = true; selectedId = null; renderLabels(); applyEmphasis(); };
setInterval(load, 60000);
