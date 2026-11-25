import {forwardRef, useEffect, useImperativeHandle, useRef, useState} from 'react';
import {fitCanvas, fullscreenQuad, type Quad} from '../../cosmos/gl';
import {boxOf, cutBounds, enter, eye, FOCAL, orientation, ray, toUm, toWorld, viewOf, type Camera, type Cut, type Vec3} from './emGeometry';
import {atomFragment, atomVertex, CLASS_SLOTS, lineFragment, lineVertex, pointFragment, pointVertex, volumeFragment, volumeVertex} from './volumeShader';

export interface VolumeView {mode: 'organelles' | 'density' | 'painting'; cut: Cut; face: boolean; invert: boolean; tint: number; gain: number; show: number[]; colors: Vec3[]; paint: Vec3[]; quality: 'balanced' | 'high';
  /** Kept part of the volume as fractions of each axis (on top of the cut). */
  clip?: {lo: Vec3; hi: Vec3};
  /** Selected compartment class (highlighted), or −1. */
  selected?: number;
  /** Modelled activity per class, 0…1, drawn as emission in `activityColor`. */
  activity?: number[]; activityColor?: Vec3;
  /** Outline of the acquired volume. */
  bounds?: boolean;
  /** Concentration field drawn from the texture given to `setField`: gain 0 hides it. */
  field?: {gain: number; color: Vec3} | null;
  /** Path of the followed molecule over the buffered frames. */
  trail?: boolean;
  /** False when the geometry has no measured image (illustrative contexts). */
  hasImage?: boolean}
/** One molecule species as drawn up close: atoms (x, y, z, radius in Å, then r, g, b; r < 0 = take the species colour). */
export interface MoleculeModel {atoms: Float32Array; extentNm: number; color: Vec3; ids?: Int32Array}
/**
 * Computed particle frames in world coordinates. The parent advances `index`; only computed frames are ever drawn.
 * state: 0 free, 1 bound to a compartment, 2 in a complex, 3 absent (not yet made, or decayed). pairs: flat [lead, follower, …] per frame.
 * markers: events to show at the current time, flat [x, y, z (world), age 0…1, r, g, b] each.
 */
export interface Playback {frames: Float32Array[]; state: Uint8Array[]; pairs: Int32Array[]; owner: Uint8Array; colors: Vec3[]; index: number; dirty: boolean; playing: boolean; markers?: Float32Array;
  /** Frames are independent snapshots (positions are redrawn, not moved): no trail links one frame to the next. */
  snapshots?: boolean}
export interface DetailRegion {dims: Vec3; originUm: Vec3; sizeUm: Vec3}
export interface VolumeHandle {
  upload(kind: 'em' | 'classes', z0: number, z1: number, bytes: Uint8Array): void;
  setModels(models: (MoleculeModel | null)[]): void;
  /** Fly to one molecule and keep it centred (null releases the camera). The first preferred molecule on the visible side of the cut is taken, else any visible one. */
  inspect(prefer: number[] | null): number | null;
  home(): void;
  snapshot(): string;
  /** A coarse scalar field over the whole volume (R8, x fastest), or null to remove it. */
  setField(dims: Vec3 | null, bytes?: Uint8Array): void;
  /** A finer-level region of the measured image; slabs follow through `uploadDetail`. Null removes it. */
  setDetail(region: DetailRegion | null): void;
  uploadDetail(z0: number, z1: number, bytes: Uint8Array): void;
  getCamera(): Camera;
  /** Move the camera without reporting it back through onCamera (used to mirror another stage). */
  setCamera(camera: Camera): void;
  /** Fly to a point (µm) at a viewing distance given in µm across the view. */
  flyTo(um: Vec3, spanUm: number): void;
}
const TRAIL = 10, ATOM_BUDGET = 1_400_000, ATOMIC_PX = 5;

function program(gl: WebGL2RenderingContext, vertex: string, fragment: string) {
  const p = gl.createProgram()!;
  for (const [type, source] of [[gl.VERTEX_SHADER, vertex], [gl.FRAGMENT_SHADER, fragment]] as const) {
    const s = gl.createShader(type)!; gl.shaderSource(s, source); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) ?? 'Shader compilation failed.');
    gl.attachShader(p, s);
  }
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p) ?? 'Shader link failed.');
  return p;
}
const HOME: Camera = {yaw: 0.5, pitch: 0.7, distance: 2.25, target: [0, 0, 0]};

/**
 * WebGL2 stage for a measured EM volume and the molecules simulated inside it. Drag to orbit, shift-drag to pan,
 * scroll to zoom from the whole cell down to single atoms, click the cut face to pick a point in the cell.
 */
const VolumeStage = forwardRef<VolumeHandle, {dims: Vec3; sizeUm: Vec3; view: VolumeView; playback: React.RefObject<Playback>; onPick?: (um: Vec3) => void; onHover?: (um: Vec3 | null) => void; onScale?: (pxPerMicron: number) => void; onAtomic?: (count: number) => void; insetRight?: number;
  /** Every camera change made here by the user or a flight (not by setCamera). */
  onCamera?: (camera: Camera) => void;
  /** A click that was not on the cut face and not on an atom: the ray under the cursor, for picking compartments or molecules. */
  onRay?: (ray: {origin: Vec3; direction: Vec3}, world: {box: Vec3}) => void;
  label?: string;
  /** A click on an atom of the followed molecule: its index in the structure (through the model's ids), or null for a miss. */
  onAtom?: (hit: {particle: number; atom: number} | null) => void}>(
function VolumeStage({dims, sizeUm, view, playback, onPick, onHover, onScale, onAtomic, onAtom, onCamera, onRay, label, insetRight = 0}, handle) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const state = useRef({view, dirty: true, moving: 0, insetRight, onAtom, onPick, onHover, onScale, onAtomic, onCamera, onRay, follow: null as number | null, flight: null as {from: Camera; distance: number; start: number; target?: Vec3} | null});
  const camera = useRef<Camera>({...HOME, target: [...HOME.target] as Vec3});
  const api = useRef<Partial<VolumeHandle>>({});
  const pending = useRef<{uploads: Parameters<VolumeHandle['upload']>[]; models: (MoleculeModel | null)[] | null; camera: Camera | null}>({uploads: [], models: null, camera: null});
  const [failure, setFailure] = useState('');
  Object.assign(state.current, {view, dirty: true, insetRight, onAtom, onPick, onHover, onScale, onAtomic, onCamera, onRay});
  useImperativeHandle(handle, () => ({
    upload: (...a) => { if (api.current.upload) api.current.upload(...a); else pending.current.uploads.push(a); },
    setModels: m => { if (api.current.setModels) api.current.setModels(m); else pending.current.models = m; },
    inspect: p => api.current.inspect?.(p) ?? null, home: () => api.current.home?.(), snapshot: () => api.current.snapshot?.() ?? '',
    setField: (d, b) => api.current.setField?.(d, b), setDetail: r => api.current.setDetail?.(r), uploadDetail: (...a) => api.current.uploadDetail?.(...a),
    getCamera: () => ({...camera.current, target: [...camera.current.target] as Vec3}),
    setCamera: c => { if (api.current.setCamera) api.current.setCamera(c); else pending.current.camera = c; },
    flyTo: (um, span) => api.current.flyTo?.(um, span),
  }), []);

  useEffect(() => {
    const element = canvas.current!, box = boxOf(sizeUm), worldPerNm = 2 / Math.max(...sizeUm) / 1000;
    let quad: Quad, points: WebGLProgram, atoms: WebGLProgram, lines: WebGLProgram;
    try {
      quad = fullscreenQuad(element, volumeVertex, volumeFragment, {preserveDrawingBuffer: false});
      points = program(quad.gl, pointVertex, pointFragment); atoms = program(quad.gl, atomVertex, atomFragment); lines = program(quad.gl, lineVertex, lineFragment);
    } catch (e) { setFailure(String(e)); return; }
    const {gl} = quad;
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    const textures = (['em', 'classes'] as const).map((kind, unit) => {
      const t = gl.createTexture()!; gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_3D, t);
      gl.texStorage3D(gl.TEXTURE_3D, 1, gl.R8, dims[0], dims[1], dims[2]);
      const filter = kind === 'em' ? gl.LINEAR : gl.NEAREST;
      gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MIN_FILTER, filter); gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MAG_FILTER, filter);
      for (const w of [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T, gl.TEXTURE_WRAP_R]) gl.texParameteri(gl.TEXTURE_3D, w, gl.CLAMP_TO_EDGE);
      return t;
    });
    api.current.upload = (kind, z0, z1, bytes) => {
      gl.activeTexture(gl.TEXTURE0 + (kind === 'em' ? 0 : 1));
      gl.texSubImage3D(gl.TEXTURE_3D, 0, 0, 0, z0, dims[0], dims[1], z1 - z0, gl.RED, gl.UNSIGNED_BYTE, bytes);
      state.current.dirty = true;
    };
    // Optional textures: a coarse concentration field (unit 2) and a finer-level region of the image (unit 3).
    const extra: {field: WebGLTexture | null; detail: WebGLTexture | null; detailDims: Vec3; detailLo: Vec3; detailHi: Vec3} = {field: null, detail: null, detailDims: [1, 1, 1], detailLo: [0, 0, 0], detailHi: [0, 0, 0]};
    const volumeTexture = (unit: number, d: Vec3) => {
      const t = gl.createTexture()!; gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_3D, t);
      gl.texStorage3D(gl.TEXTURE_3D, 1, gl.R8, d[0], d[1], d[2]);
      gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      for (const w of [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T, gl.TEXTURE_WRAP_R]) gl.texParameteri(gl.TEXTURE_3D, w, gl.CLAMP_TO_EDGE);
      return t;
    };
    let fieldDims: Vec3 = [0, 0, 0];
    api.current.setField = (d, bytes) => {
      if (!d || !bytes) { if (extra.field) gl.deleteTexture(extra.field); extra.field = null; fieldDims = [0, 0, 0]; state.current.dirty = true; return; }
      if (!extra.field || d.some((v, i) => v !== fieldDims[i])) { if (extra.field) gl.deleteTexture(extra.field); extra.field = volumeTexture(2, d); fieldDims = [...d] as Vec3; }
      gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_3D, extra.field);
      gl.texSubImage3D(gl.TEXTURE_3D, 0, 0, 0, 0, d[0], d[1], d[2], gl.RED, gl.UNSIGNED_BYTE, bytes);
      state.current.dirty = true;
    };
    api.current.setDetail = region => {
      if (extra.detail) gl.deleteTexture(extra.detail);
      extra.detail = null;
      if (region) {
        extra.detail = volumeTexture(3, region.dims); extra.detailDims = region.dims;
        const hiUm = region.originUm.map((v, i) => v + region.sizeUm[i]) as Vec3;
        extra.detailLo = toWorld(region.originUm, sizeUm, box) as Vec3; extra.detailHi = toWorld(hiUm, sizeUm, box) as Vec3;
      }
      state.current.dirty = true;
    };
    api.current.uploadDetail = (z0, z1, bytes) => {
      if (!extra.detail) return;
      gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_3D, extra.detail);
      gl.texSubImage3D(gl.TEXTURE_3D, 0, 0, 0, z0, extra.detailDims[0], extra.detailDims[1], z1 - z0, gl.RED, gl.UNSIGNED_BYTE, bytes);
      state.current.dirty = true;
    };
    // A 1-voxel placeholder keeps the optional samplers complete when nothing is loaded.
    const blank = [2, 3].map(unit => { const t = volumeTexture(unit, [1, 1, 1]); gl.texSubImage3D(gl.TEXTURE_3D, 0, 0, 0, 0, 1, 1, 1, gl.RED, gl.UNSIGNED_BYTE, new Uint8Array([0])); return t; });
    const lineBuffer = gl.createBuffer()!, lineArray = gl.createVertexArray()!;
    let lineScratch = new Float32Array(24 * 4);

    // Far molecules: one soft disc each (position, age, state, colour).
    const pointBuffer = gl.createBuffer()!, pointArray = gl.createVertexArray()!;
    gl.bindVertexArray(pointArray); gl.bindBuffer(gl.ARRAY_BUFFER, pointBuffer);
    const attribute = (prog: WebGLProgram, name: string, size: number, stride: number, offset: number, divisor = 0) => {
      const l = gl.getAttribLocation(prog, name);
      if (l >= 0) { gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, size, gl.FLOAT, false, stride, offset); gl.vertexAttribDivisor(l, divisor); }
    };
    attribute(points, 'aPoint', 3, 32, 0); attribute(points, 'aAge', 1, 32, 12); attribute(points, 'aState', 1, 32, 16); attribute(points, 'aColor', 3, 32, 20);
    gl.bindVertexArray(lineArray); gl.bindBuffer(gl.ARRAY_BUFFER, lineBuffer);
    attribute(lines, 'aPoint', 3, 16, 0); attribute(lines, 'aAlpha', 1, 16, 12);
    gl.bindVertexArray(null);
    let scratch = new Float32Array(0);

    // Near molecules: instanced atoms. One vertex array per species; the instance buffer is shared and refilled per draw.
    const instanceBuffer = gl.createBuffer()!;
    let models: ({array: WebGLVertexArrayObject; buffer: WebGLBuffer; count: number; extent: number; color: Vec3; data: Float32Array; ids?: Int32Array} | null)[] = [];
    let lastShown = new Float32Array(0);
    let instances = new Float32Array(0);
    api.current.setModels = list => {
      models.forEach(m => { if (m) { gl.deleteVertexArray(m.array); gl.deleteBuffer(m.buffer); } });
      models = list.map(m => {
        if (!m) return null;
        const n = m.atoms.length / 7, data = new Float32Array(m.atoms);
        for (let i = 0; i < n; i++) for (let k = 0; k < 4; k++) data[i * 7 + k] *= worldPerNm / 10;      // Å → world
        const array = gl.createVertexArray()!, buffer = gl.createBuffer()!;
        gl.bindVertexArray(array); gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
        attribute(atoms, 'aAtom', 4, 28, 0); attribute(atoms, 'aAtomColor', 3, 28, 16);
        gl.bindBuffer(gl.ARRAY_BUFFER, instanceBuffer);
        attribute(atoms, 'iPos', 3, 44, 0, 1); attribute(atoms, 'iQuat', 4, 44, 12, 1); attribute(atoms, 'iTint', 4, 44, 28, 1);
        return {array, buffer, count: n, extent: m.extentNm * worldPerNm, color: m.color, data, ids: m.ids};
      });
      gl.bindVertexArray(null); state.current.dirty = true;
    };
    pending.current.uploads.splice(0).forEach(a => api.current.upload!(...a));
    if (pending.current.models) { api.current.setModels(pending.current.models); pending.current.models = null; }
    let restored = false;
    if (pending.current.camera) { camera.current = {...pending.current.camera, target: [...pending.current.camera.target] as Vec3}; pending.current.camera = null; restored = true; }

    let frame = 0, sharp = false, lastScale = 0, lastAtomic = -1;
    const position = (play: Playback, index: number, particle: number, out: Vec3) => {
      const f = play.frames[index]; out[0] = f[particle * 3]; out[1] = f[particle * 3 + 1]; out[2] = f[particle * 3 + 2]; return out;
    };
    const draw = (now: number, still = false) => {
      const s = state.current, v = s.view, play = playback.current, c = camera.current;
      const index = play?.frames.length ? Math.min(play.index, play.frames.length - 1) : -1;
      const following = s.follow !== null && index >= 0 && s.follow < play!.owner.length;
      if (following) position(play!, index, s.follow!, c.target);
      if (s.flight && (following || s.flight.target)) {
        const k = Math.min(1, (now - s.flight.start) / (s.flight.target ? 900 : 1400)), e = 1 - Math.pow(1 - k, 4);
        c.distance = Math.exp(Math.log(s.flight.from.distance) + (Math.log(s.flight.distance) - Math.log(s.flight.from.distance)) * e);
        if (s.flight.target) c.target = s.flight.from.target.map((v, i) => v + (s.flight!.target![i] - v) * e) as Vec3;
        s.moving = now; if (k >= 1) s.flight = null;
        s.onCamera?.({...c, target: [...c.target] as Vec3});
      }
      const moving = now - s.moving < 180, animated = !still && (moving || !!play?.playing);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      fitCanvas(element, animated ? dpr * (v.quality === 'high' ? 0.7 : 0.5) : dpr * (v.quality === 'high' ? 1 : 0.8));
      gl.viewport(0, 0, element.width, element.height);
      const e = eye(c), {lo, hi, face} = cutBounds(v.cut, box, viewOf(c));
      if (v.clip) for (let i = 0; i < 3; i++) { lo[i] = Math.max(lo[i], (v.clip.lo[i] * 2 - 1) * box[i]); hi[i] = Math.min(hi[i], (v.clip.hi[i] * 2 - 1) * box[i]); }

      gl.disable(gl.BLEND); gl.disable(gl.DEPTH_TEST); gl.depthMask(true); gl.clear(gl.DEPTH_BUFFER_BIT);
      gl.useProgram(quad.program);
      gl.uniform1i(quad.uniform('uEM'), 0); gl.uniform1i(quad.uniform('uCls'), 1); gl.uniform1i(quad.uniform('uField'), 2); gl.uniform1i(quad.uniform('uDetail'), 3);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_3D, textures[0]); gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_3D, textures[1]);
      gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_3D, extra.field ?? blank[0]); gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_3D, extra.detail ?? blank[1]);
      gl.uniform1f(quad.uniform('uDetOn'), extra.detail ? 1 : 0); gl.uniform3f(quad.uniform('uDetLo'), ...extra.detailLo); gl.uniform3f(quad.uniform('uDetHi'), ...extra.detailHi);
      gl.uniform1f(quad.uniform('uFieldGain'), extra.field && v.field ? v.field.gain : 0); gl.uniform3f(quad.uniform('uFieldColor'), ...(v.field?.color ?? [0, 0, 0]));
      gl.uniform1f(quad.uniform('uImage'), v.hasImage === false ? 0 : 1); gl.uniform1i(quad.uniform('uSelected'), v.selected ?? -1);
      gl.uniform3f(quad.uniform('uActColor'), ...(v.activityColor ?? [0, 0, 0]));
      gl.uniform1fv(quad.uniform('uActivity[0]'), new Float32Array(CLASS_SLOTS).map((_, i) => v.activity?.[i] ?? 0));
      gl.uniform2f(quad.uniform('uResolution'), element.width, element.height);
      gl.uniform3f(quad.uniform('uCamPos'), ...e); gl.uniform3f(quad.uniform('uCamTarget'), ...c.target);
      gl.uniform3f(quad.uniform('uBox'), ...box); gl.uniform3f(quad.uniform('uDims'), ...dims);
      gl.uniform3f(quad.uniform('uCutLo'), ...lo); gl.uniform3f(quad.uniform('uCutHi'), ...hi);
      gl.uniform1i(quad.uniform('uCutAxis'), v.cut.axis); gl.uniform1f(quad.uniform('uCutAt'), face);
      gl.uniform1f(quad.uniform('uFace'), v.face ? 1 : 0); gl.uniform1f(quad.uniform('uInvert'), v.invert ? 1 : 0);
      gl.uniform1f(quad.uniform('uMode'), v.mode === 'painting' ? 2 : v.mode === 'density' ? 1 : 0); gl.uniform1f(quad.uniform('uTint'), v.tint); gl.uniform1f(quad.uniform('uGain'), v.gain);
      const shift = s.insetRight / Math.max(1, element.clientHeight);          // centre the cell in the area left of the panel
      gl.uniform1f(quad.uniform('uSteps'), animated ? 360 : 640); gl.uniform1f(quad.uniform('uShift'), shift);
      const triples = (list: Vec3[]) => new Float32Array(CLASS_SLOTS * 3).map((_, i) => list[Math.floor(i / 3)]?.[i % 3] ?? 0);
      gl.uniform1fv(quad.uniform('uShow[0]'), new Float32Array(CLASS_SLOTS).map((_, i) => v.show[i] ?? 0));
      gl.uniform3fv(quad.uniform('uColor[0]'), triples(v.colors)); gl.uniform3fv(quad.uniform('uPaint[0]'), triples(v.paint));
      quad.draw();

      let atomic = 0;
      if (play && index >= 0) {
        const n = play.owner.length, frame0 = play.frames[index], st = play.state[index], pairs = play.pairs[index];
        // Where each molecule is drawn: complexes sit side by side (schematic; no docking pose is computed).
        const shown = new Float32Array(frame0); lastShown = shown;
        for (let k = 0; k < pairs.length; k += 2) {
          const a = pairs[k], b = pairs[k + 1], q = orientation(a * 7919 + 13), ra = models[play.owner[a]]?.extent ?? 0, rb = models[play.owner[b]]?.extent ?? 0;
          const dx = 1 - 2 * (q[1] * q[1] + q[2] * q[2]), dy = 2 * (q[0] * q[1] + q[2] * q[3]), dz = 2 * (q[0] * q[2] - q[1] * q[3]);
          shown[a * 3] -= dx * ra * 0.75; shown[a * 3 + 1] -= dy * ra * 0.75; shown[a * 3 + 2] -= dz * ra * 0.75;
          shown[b * 3] += dx * rb * 0.75; shown[b * 3 + 1] += dy * rb * 0.75; shown[b * 3 + 2] += dz * rb * 0.75;
        }
        // Level of detail: molecules large enough on screen get every atom, nearest first, within a fixed budget.
        const fw = [c.target[0] - e[0], c.target[1] - e[1], c.target[2] - e[2]], fl = Math.hypot(fw[0], fw[1], fw[2]);
        const near: {i: number; z: number}[] = [], detail = new Uint8Array(n);
        for (let i = 0; i < n; i++) {
          const m = models[play.owner[i]]; if (!m || st[i] === 3) continue;
          const z = ((shown[i * 3] - e[0]) * fw[0] + (shown[i * 3 + 1] - e[1]) * fw[1] + (shown[i * 3 + 2] - e[2]) * fw[2]) / fl;
          if (z > 0 && m.extent * FOCAL / z * element.height > ATOMIC_PX) near.push({i, z});
        }
        near.sort((a, b) => a.z - b.z);
        let budget = ATOM_BUDGET;
        for (const {i} of near) { const m = models[play.owner[i]]!; if (budget < m.count) break; budget -= m.count; detail[i] = 1; atomic++; }

        const trail = play.snapshots ? 1 : Math.min(TRAIL, index + 1);
        const marks = play.markers?.length ? play.markers.length / 7 : 0;
        if (scratch.length < (n * TRAIL + marks + 1) * 8) scratch = new Float32Array((n * TRAIL + marks + 1) * 8);
        let o = 0;
        for (let k = trail - 1; k >= 0; k--) {                        // oldest first so the current frame is drawn on top
          const f = k === 0 ? shown : play.frames[index - k], b = play.state[index - k];
          for (let i = 0; i < n; i++) {
            if (detail[i] || b[i] === 3) continue;
            const col = play.colors[play.owner[i]] ?? [1, 1, 1];
            scratch[o++] = f[i * 3]; scratch[o++] = f[i * 3 + 1]; scratch[o++] = f[i * 3 + 2]; scratch[o++] = trail > 1 ? k / (TRAIL - 1) : 0; scratch[o++] = b[i];
            scratch[o++] = col[0]; scratch[o++] = col[1]; scratch[o++] = col[2];
          }
        }
        for (let k = 0; k < marks; k++) {                             // events at this moment: rings, drawn over the molecules
          const mk = play.markers!; scratch.set([mk[k * 7], mk[k * 7 + 1], mk[k * 7 + 2], mk[k * 7 + 3], 4, mk[k * 7 + 4], mk[k * 7 + 5], mk[k * 7 + 6]], o); o += 8;
        }
        if (s.follow !== null && s.follow < n && !detail[s.follow] && st[s.follow] !== 3) { scratch.set([shown[s.follow * 3], shown[s.follow * 3 + 1], shown[s.follow * 3 + 2], 0, 5, 0.45, 0.95, 1], o); o += 8; }
        gl.useProgram(points); gl.bindVertexArray(pointArray); gl.bindBuffer(gl.ARRAY_BUFFER, pointBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, scratch.subarray(0, o), gl.DYNAMIC_DRAW);
        const u = (prog: WebGLProgram, name: string) => gl.getUniformLocation(prog, name);
        gl.uniform3f(u(points, 'uCamPos'), ...e); gl.uniform3f(u(points, 'uCamTarget'), ...c.target); gl.uniform3f(u(points, 'uCutLo'), ...lo); gl.uniform3f(u(points, 'uCutHi'), ...hi);
        gl.uniform2f(u(points, 'uResolution'), element.width, element.height); gl.uniform1f(u(points, 'uSize'), 0.022); gl.uniform1f(u(points, 'uShift'), shift);
        gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.drawArrays(gl.POINTS, 0, o / 8);

        if (atomic) {
          gl.disable(gl.BLEND); gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL);
          gl.useProgram(atoms);
          gl.uniform3f(u(atoms, 'uCamPos'), ...e); gl.uniform3f(u(atoms, 'uCamTarget'), ...c.target); gl.uniform3f(u(atoms, 'uCutLo'), ...lo); gl.uniform3f(u(atoms, 'uCutHi'), ...hi);
          gl.uniform2f(u(atoms, 'uResolution'), element.width, element.height); gl.uniform2f(u(atoms, 'uDepthRange'), c.distance * 0.02, c.distance * 60 + 6); gl.uniform1f(u(atoms, 'uShift'), shift);
          if (instances.length < atomic * 11) instances = new Float32Array(atomic * 11);
          models.forEach((m, species) => {
            if (!m) return;
            let k = 0;
            for (let i = 0; i < n; i++) {
              if (!detail[i] || play.owner[i] !== species || st[i] === 3) continue;
              const q = orientation(i), col = play.colors[species] ?? m.color;
              instances.set([shown[i * 3], shown[i * 3 + 1], shown[i * 3 + 2], q[0], q[1], q[2], q[3], col[0], col[1], col[2], st[i]], k * 11); k++;
            }
            if (!k) return;
            gl.bindVertexArray(m.array); gl.bindBuffer(gl.ARRAY_BUFFER, instanceBuffer);
            gl.bufferData(gl.ARRAY_BUFFER, instances.subarray(0, k * 11), gl.DYNAMIC_DRAW);
            gl.drawArraysInstanced(gl.POINTS, 0, m.count, k);
          });
          gl.disable(gl.DEPTH_TEST);
        }
        gl.bindVertexArray(null);
      }
      // Lines: the outline of the acquired volume, and the path of the followed molecule through the buffered frames.
      const uL = (name: string) => gl.getUniformLocation(lines, name);
      const strip = (count: number, mode: number, color: Vec3) => {
        gl.useProgram(lines); gl.bindVertexArray(lineArray); gl.bindBuffer(gl.ARRAY_BUFFER, lineBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, lineScratch.subarray(0, count * 4), gl.DYNAMIC_DRAW);
        gl.uniform3f(uL('uCamPos'), ...e); gl.uniform3f(uL('uCamTarget'), ...c.target); gl.uniform2f(uL('uResolution'), element.width, element.height);
        gl.uniform1f(uL('uShift'), shift); gl.uniform3f(uL('uLineColor'), ...color);
        gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.drawArrays(mode, 0, count); gl.bindVertexArray(null);
      };
      const fwd = [c.target[0] - e[0], c.target[1] - e[1], c.target[2] - e[2]];
      const ahead = (x: number, y: number, z: number) => (x - e[0]) * fwd[0] + (y - e[1]) * fwd[1] + (z - e[2]) * fwd[2] > 1e-6;
      if (v.bounds && v.mode !== 'painting') {
        let k = 0;
        const edge = (a: Vec3, b: Vec3) => { if (ahead(...a) && ahead(...b)) { lineScratch.set([...a, 0.5, ...b, 0.5], k * 4); k += 2; } };
        for (const sa of [-1, 1]) for (const sb of [-1, 1]) {
          edge([-box[0], sa * box[1], sb * box[2]], [box[0], sa * box[1], sb * box[2]]);
          edge([sa * box[0], -box[1], sb * box[2]], [sa * box[0], box[1], sb * box[2]]);
          edge([sa * box[0], sb * box[1], -box[2]], [sa * box[0], sb * box[1], box[2]]);
        }
        if (k) strip(k, gl.LINES, [0.55, 0.62, 0.7]);
      }
      if (v.trail && play && index > 0 && s.follow !== null && s.follow < play.owner.length) {
        const i = s.follow, first = Math.max(0, index - 480);
        if (lineScratch.length < (index - first + 1) * 4) lineScratch = new Float32Array((index - first + 1) * 4 + 96);
        let k = 0;
        for (let fi = first; fi <= index; fi++) {
          const f = play.frames[fi];
          if (play.state[fi][i] === 3 || !ahead(f[i * 3], f[i * 3 + 1], f[i * 3 + 2])) { if (k > 1) strip(k, gl.LINE_STRIP, [0.45, 0.95, 1]); k = 0; continue; }
          lineScratch.set([f[i * 3], f[i * 3 + 1], f[i * 3 + 2], 0.15 + 0.75 * (fi - first) / Math.max(1, index - first)], k * 4); k++;
        }
        if (k > 1) strip(k, gl.LINE_STRIP, [0.45, 0.95, 1]);
      }
      sharp = !animated; s.dirty = false;
      const px = (element.clientHeight / 2) * FOCAL / c.distance * (2 / Math.max(...sizeUm));
      if (s.onScale && Math.abs(px - lastScale) > lastScale * 0.02) { lastScale = px; s.onScale(px); }
      if (atomic !== lastAtomic) { lastAtomic = atomic; s.onAtomic?.(atomic); }
    };
    const render = (now: number) => {
      frame = requestAnimationFrame(render);
      if (document.hidden || !element.isConnected || element.offsetParent === null) return;
      const s = state.current, play = playback.current;
      if (play?.dirty) { s.dirty = true; play.dirty = false; }
      if (s.flight) s.dirty = true;
      const animated = now - s.moving < 180 || !!play?.playing;
      if (!s.dirty && (animated || sharp)) return;
      draw(now);
    };
    frame = requestAnimationFrame(render);
    const touch = (report = true) => { state.current.moving = performance.now(); state.current.dirty = true; sharp = false; if (report) state.current.onCamera?.({...camera.current, target: [...camera.current.target] as Vec3}); };
    api.current.setCamera = c => { state.current.flight = null; camera.current = {...c, target: [...c.target] as Vec3}; touch(false); };
    api.current.flyTo = (um, span) => {
      const s = state.current; s.follow = null;
      s.flight = {from: {...camera.current, target: [...camera.current.target] as Vec3}, target: toWorld(um, sizeUm, box) as Vec3, distance: Math.max(2.5e-4, Math.min(7, span * (2 / Math.max(...sizeUm)) * FOCAL / 2)), start: performance.now()};
      touch(false);
    };
    api.current.inspect = prefer => {
      const s = state.current, play = playback.current;
      s.follow = null;
      if (prefer && play?.frames.length) {
        const index = Math.min(play.index, play.frames.length - 1), f = play.frames[index], n = play.owner.length;
        const {lo, hi} = cutBounds(s.view.cut, box, viewOf(camera.current));
        const present = play.state[index];
        const visible = (i: number) => i >= 0 && i < n && present[i] !== 3 && [0, 1, 2].every(k => f[i * 3 + k] >= lo[k] && f[i * 3 + k] <= hi[k]);
        let particle = prefer.find(visible) ?? -1;
        for (let i = 0; particle < 0 && i < n; i++) if (visible(i)) particle = i;
        if (particle < 0) particle = prefer[0] ?? 0;
        s.follow = particle;
        const m = models[play.owner[particle]];
        s.flight = {from: {...camera.current}, distance: Math.max(3e-4, (m?.extent ?? 5 * worldPerNm) * 2.8), start: performance.now()};
      }
      touch();
      return s.follow;
    };
    // The whole volume in view whatever the shape of the viewport: a narrow viewport steps back.
    const homeCamera = (): Camera => { const aspect = element.clientWidth / Math.max(1, element.clientHeight); return {...HOME, distance: HOME.distance * Math.max(1, 1.35 / Math.max(0.3, aspect)), target: [...HOME.target] as Vec3}; };
    api.current.home = () => { state.current.follow = null; state.current.flight = null; camera.current = homeCamera(); touch(); };
    if (!restored) camera.current = homeCamera();
    api.current.snapshot = () => { draw(performance.now(), true); const url = element.toDataURL('image/png'); state.current.dirty = true; sharp = false; return url; };

    const pick = (x: number, y: number): Vec3 | null => {
      const rect = element.getBoundingClientRect(), v = state.current.view;
      const r = ray(camera.current, ((x - rect.left) * 2 - rect.width + state.current.insetRight) / rect.height, (rect.height - (y - rect.top) * 2) / rect.height);
      const hit = enter(r.origin, r.direction, v.cut, box, viewOf(camera.current));
      return hit?.onFace ? toUm(hit.point, sizeUm, box) : null;
    };
    /** The atom of the followed molecule under the cursor: nearest to the camera among those the ray passes through. */
    const pickAtom = (x: number, y: number) => {
      const s = state.current, play = playback.current, i = s.follow;
      if (i === null || !play?.frames.length || lastShown.length < (i + 1) * 3) return null;
      const m = models[play.owner[i]]; if (!m) return null;
      const rect = element.getBoundingClientRect();
      const r = ray(camera.current, ((x - rect.left) * 2 - rect.width + s.insetRight) / rect.height, (rect.height - (y - rect.top) * 2) / rect.height);
      const q = orientation(i), o = [lastShown[i * 3] - r.origin[0], lastShown[i * 3 + 1] - r.origin[1], lastShown[i * 3 + 2] - r.origin[2]];
      let best = -1, bestT = Infinity;
      for (let k = 0; k < m.count; k++) {
        const vx = m.data[k * 7], vy = m.data[k * 7 + 1], vz = m.data[k * 7 + 2], rad = m.data[k * 7 + 3];
        const cx = q[1] * vz - q[2] * vy + q[3] * vx, cy = q[2] * vx - q[0] * vz + q[3] * vy, cz = q[0] * vy - q[1] * vx + q[3] * vz;      // v + 2 q × (q × v + w v)
        const px = o[0] + vx + 2 * (q[1] * cz - q[2] * cy), py = o[1] + vy + 2 * (q[2] * cx - q[0] * cz), pz = o[2] + vz + 2 * (q[0] * cy - q[1] * cx);
        const t = px * r.direction[0] + py * r.direction[1] + pz * r.direction[2];
        if (t <= 0 || t >= bestT) continue;
        const d2 = px * px + py * py + pz * pz - t * t;
        if (d2 < rad * rad) { best = k; bestT = t; }
      }
      return best < 0 ? null : {particle: i, atom: m.ids ? m.ids[best] : best};
    };
    let drag: {x: number; y: number; moved: boolean; pan: boolean} | null = null;
    const down = (e: PointerEvent) => { drag = {x: e.clientX, y: e.clientY, moved: false, pan: e.shiftKey || e.button === 2}; element.setPointerCapture(e.pointerId); };
    const move = (e: PointerEvent) => {
      if (!drag) { state.current.onHover?.(pick(e.clientX, e.clientY)); return; }
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y, c = camera.current;
      if (Math.abs(dx) + Math.abs(dy) > 2) drag.moved = true;
      drag.x = e.clientX; drag.y = e.clientY;
      if (drag.pan) {
        state.current.follow = null;
        const k = c.distance / FOCAL * 2 / element.clientHeight, sy = Math.sin(c.yaw), cy = Math.cos(c.yaw);
        c.target = [Math.max(-box[0], Math.min(box[0], c.target[0] - dx * k * cy - dy * k * sy * Math.sin(c.pitch))), c.target[1], Math.max(-box[2], Math.min(box[2], c.target[2] + dx * k * sy - dy * k * cy * Math.sin(c.pitch)))];
      } else { c.yaw -= dx * 0.006; c.pitch = Math.max(-1.5, Math.min(1.5, c.pitch + dy * 0.006)); }
      touch();
    };
    const up = (e: PointerEvent) => {
      if (drag && !drag.moved) {
        const s = state.current, hit = s.follow !== null ? pickAtom(e.clientX, e.clientY) : null;
        if (s.follow !== null && hit) s.onAtom?.(hit);
        else {
          if (s.follow !== null) s.onAtom?.(null);
          const um = pick(e.clientX, e.clientY);
          if (um && s.onPick) s.onPick(um);
          const rect = element.getBoundingClientRect();
          s.onRay?.(ray(camera.current, ((e.clientX - rect.left) * 2 - rect.width + s.insetRight) / rect.height, (rect.height - (e.clientY - rect.top) * 2) / rect.height), {box});
        }
      }
      drag = null;
    };
    const wheel = (e: WheelEvent) => { e.preventDefault(); state.current.flight = null; const c = camera.current; c.distance = Math.max(2.5e-4, Math.min(7, c.distance * Math.exp(e.deltaY * 0.0014))); touch(); };
    const leave = () => state.current.onHover?.(null);
    const menu = (e: Event) => e.preventDefault();
    element.addEventListener('pointerdown', down); element.addEventListener('pointermove', move); element.addEventListener('pointerup', up);
    element.addEventListener('wheel', wheel, {passive: false}); element.addEventListener('pointerleave', leave); element.addEventListener('contextmenu', menu);
    const resize = new ResizeObserver(() => { state.current.dirty = true; sharp = false; });
    resize.observe(element);
    return () => {
      cancelAnimationFrame(frame); resize.disconnect(); api.current = {};
      element.removeEventListener('pointerdown', down); element.removeEventListener('pointermove', move); element.removeEventListener('pointerup', up);
      element.removeEventListener('wheel', wheel); element.removeEventListener('pointerleave', leave); element.removeEventListener('contextmenu', menu);
      textures.forEach(t => gl.deleteTexture(t)); blank.forEach(t => gl.deleteTexture(t)); if (extra.field) gl.deleteTexture(extra.field); if (extra.detail) gl.deleteTexture(extra.detail);
      gl.deleteBuffer(pointBuffer); gl.deleteVertexArray(pointArray); gl.deleteBuffer(instanceBuffer); gl.deleteBuffer(lineBuffer); gl.deleteVertexArray(lineArray); gl.deleteProgram(lines);
      models.forEach(m => { if (m) { gl.deleteVertexArray(m.array); gl.deleteBuffer(m.buffer); } });
      gl.deleteProgram(points); gl.deleteProgram(atoms);
      quad.dispose();
    };
  }, [dims[0], dims[1], dims[2], sizeUm[0], sizeUm[1], sizeUm[2]]);

  return <div className="cell-stage">
    <canvas ref={canvas} aria-label={label ?? 'Three-dimensional view of a cell with simulated molecules. Drag to orbit, shift-drag to pan, scroll to zoom from the cell to single atoms, click a compartment or a molecule to select it.'}/>
    {failure && <div className="cell-failure"><strong>The volume renderer needs WebGL2.</strong><span>{failure}</span></div>}
  </div>;
});
export default VolumeStage;
