// motion.js: the shared page engine. Every function is a pure function of time (in beats), so any
// frame can be drawn on its own. A film page loads timeline.js (const TL = {...}) and then this file,
// defines draw(b), and calls studio(draw).

const TLB = TL.beat;
const cue = n => { if (!(n in TL.cues)) throw new Error('missing cue ' + n); return TL.cues[n]; };
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const easeIO = k => k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;

// ---------- springs: closed-form damped spring 0 -> 1, x in beats ----------
// Presets are defaults: tune by eye, keep the names.
const PRESET = {
  snappy:  [0.9, 0.8],     // buttons, toggles, leading edges
  normal:  [0.62, 0.74],   // cards, containers, camera
  heavy:   [0.45, 0.95],   // big type, logo lockups: no visible overshoot
  playful: [0.7, 0.5],     // stickers, mascots only
};
function spring(x, freq = 0.62, zeta = 0.74) {
  if (x <= 0) return 0;
  const w = 2 * Math.PI * freq;
  if (zeta >= 1) return 1 - Math.exp(-w * x) * (1 + w * x);
  const wd = w * Math.sqrt(1 - zeta * zeta);
  return 1 - Math.exp(-zeta * w * x) * (Math.cos(wd * x) + (zeta * w / wd) * Math.sin(wd * x));
}
const sp = (b, t0, k = 1, p = 'normal') => spring((b - t0) * k, ...PRESET[p]);
// A value with several targets: one spring per change. keys = [[beat, value], ...] sorted by beat.
function track(b, keys, p = 'normal') {
  keys = [...keys].sort((p, q) => p[0] - q[0]);          // keys in any order: each spring is one change in time
  let v = keys[0][1];
  for (let i = 1; i < keys.length; i++) v += (keys[i][1] - keys[i - 1][1]) * sp(b, keys[i][0], 1, p);
  return v;
}
// Tab or selection indicator that stretches: leading edge snappy, trailing edge normal.
function indicator(b, keys, width) {
  const lead = track(b, keys, 'snappy'), trail = track(b, keys, 'normal');
  return { left: Math.min(lead, trail), right: Math.max(lead, trail) + width };
}
// Text inside a morphing box: in just after the morph starts, out just before the next one. 0..1.
// Drive a rise or a clip with it, never opacity: nothing fades.
const swapIn = (b, tIn, tOut) => Math.min(clamp((b - tIn - 0.15) / 0.25), clamp((tOut - 0.2 - b) / 0.2));

// ---------- determinism helpers ----------
function mulberry32(seed) {             // seeded noise, never Math.random
  return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}

// ---------- layout: every format from one timeline, reframed, never cropped ----------
const FMT = { W: innerWidth, H: innerHeight, portrait: innerHeight > innerWidth * 1.2, square: Math.abs(innerWidth - innerHeight) < 40 };
const pick = (wide, square, portrait) => FMT.portrait ? portrait : FMT.square ? square : wide;

// ---------- DOM ----------
function h(tag, cls, parent, html, style) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  if (style) Object.assign(e.style, style);
  parent.appendChild(e);
  return e;
}
const px = v => v + 'px';
function place(e, x, y, w, hh) { e.style.left = px(x); e.style.top = px(y); if (w != null) e.style.width = px(w); if (hh != null) e.style.height = px(hh); return e; }   // 0 is a size
function pop(e, k, ox = '50%', oy = '50%') {    // grow from a point with the spring's overshoot
  e.style.transformOrigin = `${ox} ${oy}`;
  e.style.transform = `scale(${Math.max(0, k)})`;
  e.style.opacity = k > 0.001 ? 1 : 0;
}
// A line that draws itself: k 0..1 of an SVG path's length (lengths after document.fonts.ready).
function drawPath(path, k) {
  const L = path.getTotalLength();
  path.style.strokeDasharray = `${L} ${L}`;
  path.style.strokeDashoffset = `${L * (1 - clamp(k))}`;
}
// Colour change as a shape change: a flood circle grows from (x, y). k 0..1, r in px at k=1.
function flood(e, k, x, y, r) { e.style.clipPath = `circle(${Math.max(0, k) * r}px at ${x}px ${y}px)`; }

// Mask-line text: words rise out of a mask line. "*word" is the serif accent word.
function words(parent, text, cls) {
  const box = h('div', cls, parent), list = text.split(' ');
  box.ws = list.map((w, i) => {
    const m = h('span', 'm', box), inner = h('span', w.startsWith('*') ? 'acc' : '', m, w.replace(/\*/g, ''));
    if (i < list.length - 1) box.appendChild(document.createTextNode(' '));
    return inner;
  });
  return box;
}
// step = beats between words; show = true puts the line fully on screen (frame one / thumbnail rule)
function rise(box, b, t0, step = 1, show = false) {
  box.ws.forEach((w, i) => { const k = show ? 1 : sp(b, t0 + i * step); w.style.transform = `translateY(${(1 - k) * 115}%)`; });
}

// ---------- camera: one transform on one container, one move at a time, zoom in log space ----------
// keys = [[beat, {x, y, z}], ...]: centre of view in stage px, zoom z. Eased between keyframes.
function camera(b, keys) {
  let i = 0;
  while (i < keys.length - 1 && b >= keys[i + 1][0]) i++;
  const [b0, a] = keys[i], [b1, c] = keys[Math.min(i + 1, keys.length - 1)];
  const k = b1 > b0 ? easeIO(clamp((b - b0) / (b1 - b0))) : 1;
  const z = Math.exp(lerp(Math.log(a.z), Math.log(c.z), k));
  const x = lerp(a.x, c.x, k), y = lerp(a.y, c.y, k);
  return `translate(${FMT.W / 2}px, ${FMT.H / 2}px) scale(${z}) translate(${-x}px, ${-y}px)`;
}

// ---------- wiring for the renderer ----------
// draw(b) paints beat b; it may push image decodes into `pending`. PROBE = selector for moving things.
const pending = [];
function studio(draw, PROBE = '.card, .pill, .head .m > span, .dot, .cursor') {
  window.seek = async (t) => { pending.length = 0; draw(t / TLB); await Promise.all(pending); };
  // largest on-screen move (px per frame) of any probed element: the renderer doubles blur samples from 4 as it grows
  window.motion = async (t) => {
    const rects = () => [...document.querySelectorAll(PROBE)].map(e => {
      const r = e.getBoundingClientRect(); return r.width > 0 && getComputedStyle(e).opacity !== '0' ? r : null; });
    // within this frame's shutter, per element, in quarter frames: motion moves in both quarters of a half; a swap is one
    // jump beside a still quarter, and blur can't smooth a jump. Speed (px/frame) = 4 x the smaller quarter of the busier half
    const q = 0.25 / TL.fps, R = [];
    for (let k = -2; k <= 2; k++) { await window.seek(t + k * q); R.push(rects()); }
    const d = (p, r) => p && r ? Math.max(Math.abs(r.left - p.left), Math.abs(r.top - p.top), Math.abs(r.right - p.right), Math.abs(r.bottom - p.bottom)) : 0;
    return R[0].reduce((m, _, i) => { const s = [0, 1, 2, 3].map(k => d(R[k][i], R[k + 1][i]));
      return Math.max(m, 4 * Math.max(Math.min(s[0], s[1]), Math.min(s[2], s[3]))); }, 0);
  };
  window.seek(0);
}
