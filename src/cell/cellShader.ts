/**
 * Ray-marched eukaryotic cell. Every organelle is a signed distance field in
 * "cell units" (the plasma membrane has radius ~0.93). A world-space cutting
 * plane slices everything, Goodsell-style, so the interior is visible.
 *
 * Styles (uStyle): 0 Illustrative, 1 Cinematic, 2 Fluorescence, 3 Cryo-ET, 4 Cel cartoon,
 * 5 Electron micrograph (a stained thin section), 6 Confocal (an optical section).
 * Material ids: 1 membrane, 2 nuclear envelope, 3 chromatin, 4 nucleolus,
 * 5 mitochondrion, 6 cristae, 7 endoplasmic reticulum, 8 Golgi, 9 ribosome,
 * 10 vesicle, 11 microtubule, 12 cytosolic protein, 13 centrosome,
 * 14 lipid droplet, 15 glycogen granule.
 * Cell archetypes come in as uniforms: nucleus position and size, membrane
 * boxiness, an optional lipid droplet, extra mitochondria and glycogen.
 */
export const cellVertex = `#version 300 es
in vec2 aPosition;
void main(){ gl_Position = vec4(aPosition, 0.0, 1.0); }
`;

export const cellFragment = `#version 300 es
precision highp float;
uniform vec2 uResolution;
uniform float uTime;
uniform vec3 uCamPos;
uniform vec3 uCamTarget;
uniform vec4 uCut;
uniform float uCutOn;
uniform float uStyle;
uniform vec4 uShowA;   // nucleus, chromatin, mitochondria, ER
uniform vec4 uShowB;   // golgi, ribosomes, vesicles, cytoskeleton
uniform vec4 uGainA;   // brightness per layer (1 = unchanged); the Virtual Cell sets these from data
uniform vec4 uGainB;
uniform float uCrowd;
uniform float uGlass;
uniform vec2 uPick;
uniform float uPickMode;
uniform float uHighlight;
uniform vec3 uNC;        // nucleus centre
uniform float uNR;       // nucleus radius
uniform vec3 uGC;        // Golgi centre
uniform float uBox;      // 0 round membrane → 1 polyhedral
uniform vec4 uDroplet;   // lipid droplet centre and radius (w = 0: none)
uniform float uMitoExtra;
uniform float uGlycogen;
out vec4 fragColor;

#define NC uNC
#define NR uNR
#define GC uGC
const vec3 MITO[7] = vec3[7](vec3(0.55, 0.36, 0.22), vec3(0.42, -0.46, 0.26), vec3(-0.22, -0.6, -0.22), vec3(0.58, -0.06, -0.42), vec3(-0.54, 0.44, -0.28), vec3(0.08, 0.66, -0.3), vec3(-0.16, -0.32, 0.66));
const vec3 MDIR[7] = vec3[7](vec3(-0.5, 0.8, 0.2), vec3(0.7, 0.6, -0.3), vec3(0.9, -0.3, 0.3), vec3(0.2, 0.6, 0.8), vec3(0.6, 0.7, 0.3), vec3(1.0, 0.1, 0.2), vec3(0.9, -0.4, 0.1));

float hash13(vec3 p){ p = fract(p * 0.1031); p += dot(p, p.zyx + 31.32); return fract((p.x + p.y) * p.z); }
vec3 hash33(vec3 p){ p = fract(p * vec3(0.1031, 0.1030, 0.0973)); p += dot(p, p.yxz + 33.33); return fract((p.xxy + p.yxx) * p.zyx); }
float vnoise(vec3 p){
  vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash13(i), hash13(i + vec3(1, 0, 0)), f.x), mix(hash13(i + vec3(0, 1, 0)), hash13(i + vec3(1, 1, 0)), f.x), f.y),
             mix(mix(hash13(i + vec3(0, 0, 1)), hash13(i + vec3(1, 0, 1)), f.x), mix(hash13(i + vec3(0, 1, 1)), hash13(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}
float sdCapsule(vec3 p, vec3 a, vec3 b, float r){ vec3 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); return length(pa - ba * h) - r; }
float gyroid(vec3 q){ return dot(sin(q), cos(q.yzx)); }

// Running nearest object: x distance, y material id, z per-instance seed.
void take(inout vec3 best, float d, float id, float seed){ if (d < best.x) best = vec3(d, id, seed); }

vec3 centrosome(){ return NC + normalize(vec3(0.62, -0.52, 0.36)) * (NR + 0.07); }

vec3 map(vec3 p){
  vec3 best = vec3(1e5, 0.0, 0.0);
  float r = length(p);
  if (r > 1.08) return vec3(r - 1.0, 0.0, 0.0);
  float t = uTime;

  // Plasma membrane: a softly lumpy, breathing lipid bilayer.
  float R = 0.93 + 0.03 * sin(3.1 * p.x + t * 0.25) * sin(2.3 * p.y + 1.3) * sin(2.7 * p.z + 0.7) + 0.025 * (vnoise(p * 4.0 + t * 0.03) - 0.5);
  vec3 pm = p * vec3(1.0, 1.07, 1.0);
  vec3 a4 = pm * pm; a4 *= a4;
  float dm = mix(length(pm), pow(a4.x + a4.y + a4.z, 0.25) * 1.08, uBox) - R;
  take(best, abs(dm) - 0.016 - 0.0025 * vnoise(p * 70.0), 1.0, 0.0);
  float inside = dm;

  // Lipid droplet: a single phospholipid monolayer around neutral lipid.
  float droplet = uDroplet.w > 0.0 ? length(p - uDroplet.xyz) - uDroplet.w : 1e5;
  if (uDroplet.w > 0.0) take(best, droplet, 14.0, 0.0);

  // Nucleus: double envelope pierced by pores, with chromatin and a nucleolus.
  vec3 pn = p - NC;
  float rn = length(pn * vec3(1.0, 1.06, 0.97));
  if (uShowA.x > 0.5) {
    vec3 dn = normalize(pn);
    float pore = abs(sin(dn.x * 23.0) * sin(dn.y * 23.0 + 1.3) * sin(dn.z * 23.0 + 2.1));
    float env = abs(rn - NR) - 0.011;
    env = max(env, (pore - 0.86) * 0.045);
    take(best, env, 2.0, 0.0);
    if (rn < NR) {
      vec3 cn = NC + vec3(0.1, 0.09, -0.06) * (NR / 0.37);
      take(best, length(p - cn) - 0.095 * (NR / 0.37) - 0.012 * vnoise(p * 30.0), 4.0, 0.0);
    }
  }
  if (uShowA.y > 0.5 && rn < NR + 0.01) {
    vec3 w = pn * 19.0 + 1.6 * vec3(vnoise(pn * 6.0), vnoise(pn * 6.0 + 7.1), vnoise(pn * 6.0 + 3.3)) + vec3(0.0, t * 0.02, 0.0);
    float g1 = gyroid(w), g2 = gyroid(w * 1.13 + vec3(1.7, 0.3, 2.9));
    float chrom = (length(vec2(g1, g2)) * 0.6 - 0.26) / 19.0;
    chrom = max(chrom, rn - NR + 0.022);
    take(best, chrom * 0.85, 3.0, fract(g1 * 3.1));
  }

  // Mitochondria: capsules whose interior folds into cristae.
  if (uShowA.z > 0.5) {
    for (int j = 0; j < 14; j++) {
      int i = j % 7;
      if (j >= 7 && uMitoExtra < 0.5) break;
      vec3 c = MITO[i];
      vec3 ax = normalize(MDIR[i]);
      if (j >= 7) { c = vec3(c.z, -c.y * 0.9, -c.x) * 0.92; ax = vec3(ax.z, -ax.y, -ax.x); }
      c += 0.012 * vec3(sin(t * 0.4 + float(j)), cos(t * 0.33 + float(j) * 1.7), sin(t * 0.27 + float(j) * 2.3));
      if (length(c - NC) < NR + 0.1 || (uDroplet.w > 0.0 && length(c - uDroplet.xyz) < uDroplet.w + 0.08)) continue;
      float len = 0.11 + 0.03 * fract(float(j) * 0.618);
      float body = sdCapsule(p, c - ax * len, c + ax * len, 0.058);
      if (body < 0.03) {
        float outer = abs(body) - 0.006;
        take(best, outer, 5.0, float(j));
        float along = dot(p - c, ax);
        float cristae = abs(sin(along * 95.0 + float(j))) / 95.0 - 0.0035;
        cristae = max(cristae, body + 0.016);
        take(best, cristae, 6.0, float(j));
      } else take(best, body, 5.0, float(j));
    }
  }

  // Endoplasmic reticulum: folded sheets layered around the nucleus.
  if (uShowA.w > 0.5 && rn > NR + 0.02 && rn < NR + 0.35 && droplet > 0.02) {
    vec3 dn = normalize(pn);
    float folds = rn + 0.035 * sin(dn.x * 9.0 + t * 0.1) * sin(dn.y * 8.0 + 1.0) + 0.02 * vnoise(p * 12.0);
    float sheet = abs(fract(folds * 26.0) - 0.5) / 26.0 - 0.0045;
    float band = abs(rn - NR - 0.185) - 0.12;
    float patchy = 0.25 - (sin(dn.x * 4.0 + 1.0) * sin(dn.z * 3.0 + 2.0) * 0.5 + 0.5);
    take(best, max(max(sheet, band), patchy * 0.15) * 0.8, 7.0, 0.0);
  }

  // Golgi apparatus: a curved stack of cisternae beside the nucleus.
  if (uShowB.x > 0.5 && length(p - GC) < 0.22 && droplet > 0.0) {
    vec3 ax = normalize(GC - NC);
    for (int k = 0; k < 5; k++) {
      float fk = float(k) - 2.0;
      vec3 q = p - (GC + ax * fk * 0.03);
      float h = dot(q, ax), rr = length(q - ax * h);
      float bowl = h + 2.2 * rr * rr;
      float disc = max(abs(bowl) - 0.0065, rr - (0.135 - abs(fk) * 0.016));
      take(best, disc * 0.7, 8.0, float(k));
    }
  } else if (uShowB.x > 0.5) take(best, length(p - GC) - 0.2, 8.0, 0.0);

  // Vesicles and lysosomes drifting through the cytoplasm.
  if (uShowB.z > 0.5) {
    for (int i = 0; i < 9; i++) {
      vec3 h = hash33(vec3(float(i) * 3.7, 1.3, 9.1));
      vec3 c = normalize(h - 0.5) * (0.52 + 0.3 * h.z) + 0.02 * sin(t * 0.3 + h * 6.28);
      if (length(c - NC) < NR + 0.1) c = NC + normalize(c - NC) * (NR + 0.12);
      if (uDroplet.w > 0.0 && length(c - uDroplet.xyz) < uDroplet.w + 0.05) continue;
      float rad = 0.025 + 0.025 * h.x;
      take(best, abs(length(p - c) - rad) - 0.004, 10.0, h.y);
    }
  }

  // Microtubules radiating from the centrosome.
  if (uShowB.w > 0.5) {
    vec3 cs = centrosome();
    take(best, length(p - cs) - 0.03, 13.0, 0.0);
    for (int i = 0; i < 11; i++) {
      float fi = float(i) + 0.5;
      float phi = acos(1.0 - 2.0 * fi / 11.0), th = 3.88322 * fi;
      vec3 d = vec3(sin(phi) * cos(th), sin(phi) * sin(th), cos(phi));
      if (dot(d, normalize(NC - cs)) > 0.2) d = normalize(d - 1.2 * normalize(NC - cs));
      take(best, max(sdCapsule(p, cs, cs + d * 1.3, 0.005), inside + 0.03), 11.0, 0.0);
    }
  }

  // Ribosomes and crowded cytosolic proteins, one per jittered grid cell.
  if ((uShowB.y > 0.5 || uCrowd > 0.5) && inside < -0.02) {
    float c = 0.05;
    vec3 id = floor(p / c), h = hash33(id + 11.0);
    vec3 centre = (id + 0.5) * c + (h - 0.5) * c * 0.38;
    bool cytoplasm = length((centre - NC) * vec3(1.0, 1.06, 0.97)) > NR + 0.03 && length(centre) < 0.86 && (uDroplet.w <= 0.0 || length(centre - uDroplet.xyz) > uDroplet.w + 0.02);
    if (cytoplasm) {
      if (h.x < 0.34 && uShowB.y > 0.5) take(best, (length(p - centre) - 0.0085) * 0.9, 9.0, h.z);
      else if (h.x > 0.42 && h.x < 0.82 && uCrowd > 0.5) {
        vec3 q = p - centre;
        float blob = length(q * vec3(1.0, 1.0 + h.y, 1.0)) - 0.0095 - 0.006 * h.z;
        take(best, blob * 0.85, 12.0, h.y);
      } else if (h.x >= 0.82 && uGlycogen > 0.5) {
        vec3 q = p - centre;
        float rosette = length(q) - 0.011 - 0.004 * sin(q.x * 900.0) * sin(q.y * 900.0) * sin(q.z * 900.0);
        take(best, rosette * 0.8, 15.0, h.z);
      }
    }
    take(best, c * 0.5, 0.0, 0.0);
  }

  // The cutaway plane removes everything on its positive side.
  if (uCutOn > 0.5) best.x = max(best.x, dot(p, uCut.xyz) - uCut.w);
  return best;
}

vec3 normalAt(vec3 p){
  const vec2 k = vec2(1.0, -1.0); float e = 0.0012;
  return normalize(k.xyy * map(p + k.xyy * e).x + k.yyx * map(p + k.yyx * e).x + k.yxy * map(p + k.yxy * e).x + k.xxx * map(p + k.xxx * e).x);
}
float occlusion(vec3 p, vec3 n){
  float o = 0.0, s = 1.0;
  for (int i = 1; i <= 5; i++) { float h = 0.012 * float(i * i); o += (h - map(p + n * h).x) * s; s *= 0.7; }
  return clamp(1.0 - 3.2 * o, 0.0, 1.0);
}
float softShadow(vec3 p, vec3 l){
  float res = 1.0, t = 0.01;
  for (int i = 0; i < 22; i++) { float h = map(p + l * t).x; res = min(res, 10.0 * h / t); t += clamp(h, 0.01, 0.08); if (res < 0.02 || t > 1.4) break; }
  return clamp(res, 0.0, 1.0);
}

vec3 palette(float id, float seed){
  if (id < 1.5) return vec3(0.98, 0.72, 0.5);
  if (id < 2.5) return vec3(0.93, 0.62, 0.66);
  if (id < 3.5) return mix(vec3(0.78, 0.36, 0.58), vec3(0.62, 0.32, 0.72), seed);
  if (id < 4.5) return vec3(0.52, 0.22, 0.46);
  if (id < 5.5) return vec3(0.96, 0.52, 0.36);
  if (id < 6.5) return vec3(1.0, 0.82, 0.46);
  if (id < 7.5) return vec3(0.5, 0.72, 0.95);
  if (id < 8.5) return mix(vec3(0.56, 0.84, 0.58), vec3(0.42, 0.74, 0.62), seed / 4.0);
  if (id < 9.5) return vec3(0.9, 0.36, 0.45);
  if (id < 10.5) return mix(vec3(0.78, 0.66, 1.0), vec3(1.0, 0.7, 0.86), seed);
  if (id < 11.5) return vec3(0.62, 0.9, 0.84);
  if (id < 12.5) return mix(mix(vec3(0.55, 0.7, 0.98), vec3(0.62, 0.9, 0.78), seed), vec3(0.98, 0.86, 0.6), step(0.8, seed));
  if (id < 13.5) return vec3(1.0, 0.9, 0.55);
  if (id < 14.5) return vec3(1.0, 0.93, 0.66);
  return vec3(0.72, 0.5, 0.86);
}
// Fluorescence channels, like a multi-label confocal image.
float layerGain(float id){
  if (id > 1.5 && id < 4.5) return uGainA.x;           // nuclear envelope, chromatin, nucleolus
  if (id > 4.5 && id < 6.5) return uGainA.z;           // mitochondria
  if (id > 6.5 && id < 7.5) return uGainA.w;           // ER
  if (id > 7.5 && id < 8.5) return uGainB.x;           // Golgi
  if (id > 8.5 && id < 9.5) return uGainB.y;           // ribosomes
  if (id > 9.5 && id < 10.5) return uGainB.z;          // vesicles
  if (id > 10.5 && id < 11.5) return uGainB.w;         // cytoskeleton
  return 1.0;
}

vec3 channel(float id){
  if (id < 1.5) return vec3(0.75, 0.25, 0.9);
  if (id < 4.5) return vec3(0.2, 0.42, 1.0);
  if (id < 6.5) return vec3(1.0, 0.22, 0.32);
  if (id < 7.5) return vec3(0.22, 1.0, 0.5);
  if (id < 8.5) return vec3(1.0, 0.85, 0.2);
  if (id < 9.5) return vec3(1.0, 0.5, 0.2);
  if (id < 10.5) return vec3(0.95, 0.4, 0.9);
  if (id < 11.5) return vec3(0.2, 0.95, 1.0);
  if (id < 12.5) return vec3(0.25, 0.3, 0.45);
  if (id < 13.5) return vec3(1.0, 1.0, 0.6);
  if (id < 14.5) return vec3(1.0, 0.75, 0.2);
  return vec3(0.6, 0.4, 1.0);
}

vec3 background(vec3 rd, vec2 uv){
  if ((uStyle > 1.5 && uStyle < 2.5) || uStyle > 5.5) return vec3(0.0);
  if (uStyle > 2.5 && uStyle < 3.5) return vec3(0.52 + 0.08 * (hash13(vec3(gl_FragCoord.xy, floor(uTime * 12.0))) - 0.5));
  if (uStyle > 4.5 && uStyle < 5.5) return vec3(0.8 + 0.04 * (vnoise(vec3(gl_FragCoord.xy * 0.05, 1.0)) - 0.5));
  vec3 deep = vec3(0.012, 0.018, 0.045), haze = uStyle > 3.5 ? vec3(0.12, 0.1, 0.3) : vec3(0.07, 0.1, 0.24);
  vec3 col = mix(haze, deep, smoothstep(0.0, 1.1, length(uv)));
  if (uStyle > 0.5 && uStyle < 1.5) {
    vec3 s = floor(rd * 260.0);
    float star = step(0.9965, hash13(s)) * hash13(s + 3.0);
    col += vec3(0.8, 0.88, 1.0) * star * 1.3;
    col += vec3(0.3, 0.2, 0.6) * pow(max(0.0, 1.0 - abs(rd.y + 0.2 * rd.x) * 2.2), 3.0) * 0.25 * vnoise(rd * 6.0);
  }
  return col;
}

void main(){
  vec2 frag = uPickMode > 0.5 ? uPick : gl_FragCoord.xy;
  vec2 uv = (frag - 0.5 * uResolution) / uResolution.y;
  vec3 ro = uCamPos;
  vec3 fw = normalize(uCamTarget - ro), rt = normalize(cross(fw, vec3(0.0, 1.0, 0.0))), up = cross(rt, fw);
  vec3 rd = normalize(fw * 1.7 + uv.x * rt + uv.y * up);

  float b = dot(ro, rd), c = dot(ro, ro) - 1.1 * 1.1, disc = b * b - c;
  vec3 col = background(rd, uv);
  float pickId = 0.0;
  if (disc > 0.0) {
    float t = max(0.0, -b - sqrt(disc)), tEnd = -b + sqrt(disc);
    vec3 acc = vec3(0.0), glow = vec3(0.0);
    float trans = 1.0, prevD = 1e5;
    bool nearMiss = false, hit = false;
    int layers = 0;
    vec3 m = vec3(0.0), p = ro;
    bool glassMembrane = (uGlass > 0.5 && (uStyle > 0.5 && uStyle < 2.5));
    for (int i = 0; i < 170; i++) {
      p = ro + rd * t;
      m = map(p);
      if (uStyle > 1.5 && uStyle < 2.5) glow += channel(m.y) * (m.y < 1.5 ? 0.0006 : 0.0015) / (0.012 + m.x * m.x * 900.0);
      if (uStyle > 5.5) { float pd = uCutOn > 0.5 ? dot(p, uCut.xyz) - uCut.w : 0.0; glow += channel(m.y) * exp(-pd * pd / 0.004) * 0.0011 / (0.012 + m.x * m.x * 900.0); }
      if (prevD < 0.0035 && m.x > prevD + 0.0004) nearMiss = true;
      prevD = m.x;
      if (m.x < 0.0005 + 0.0004 * t) {
        bool cutFace = uCutOn > 0.5 && abs(dot(p, uCut.xyz) - uCut.w) < 0.0025;
        if (glassMembrane && m.y < 1.5 && !cutFace && layers < 4) {
          vec3 n = normalAt(p);
          float fres = pow(1.0 - abs(dot(n, -rd)), 3.0);
          vec3 mc = uStyle < 1.5 ? mix(vec3(0.55, 0.7, 1.0), vec3(1.0, 0.75, 0.6), 0.35) * (0.12 + 1.2 * fres) : channel(1.0) * (0.15 + 1.4 * fres);
          float a = 0.12 + 0.5 * fres;
          acc += trans * a * mc; trans *= 1.0 - a;
          if (pickId == 0.0) pickId = 1.0;
          layers++; t += 0.04; prevD = 1e5; continue;
        }
        hit = true; break;
      }
      t += m.x;
      if (t > tEnd) break;
    }
    if (hit) {
      if (pickId == 0.0 || pickId == 1.0) pickId = m.y;
      bool cutFace = uCutOn > 0.5 && abs(dot(p, uCut.xyz) - uCut.w) < 0.0025;
      vec3 n = cutFace ? uCut.xyz : normalAt(p);
      if (dot(n, rd) > 0.0) n = -n;
      vec3 base = palette(m.y, m.z);
      float ao = occlusion(p, n);
      vec3 l = normalize(vec3(0.6, 0.75, 0.45));
      float diff = max(dot(n, l), 0.0);
      float facing = abs(dot(n, -rd));
      vec3 surf;
      if (uStyle < 0.5) {
        // Illustrative: flat Goodsell colour, deep occlusion, inked edges, pale cut faces.
        surf = base * (0.5 + 0.5 * ao) * (0.82 + 0.18 * diff);
        if (cutFace) surf = mix(base, vec3(1.0, 0.97, 0.9), 0.32) * (0.85 + 0.15 * ao);
        float edge = (nearMiss || facing < 0.22) ? 1.0 : 0.0;
        surf = mix(surf, base * 0.18, edge * 0.85);
      } else if (uStyle < 1.5) {
        // Cinematic: key light with soft shadows, wrapped subsurface glow and a cool rim.
        float sh = softShadow(p + n * 0.004, l);
        float wrap = max(0.0, (dot(n, l) + 0.45) / 1.45);
        vec3 h = normalize(l - rd);
        float spec = pow(max(dot(n, h), 0.0), 48.0) * 0.5;
        float rim = pow(1.0 - facing, 3.0);
        surf = base * (0.16 + 0.95 * wrap * mix(0.35, 1.0, sh)) * (0.35 + 0.65 * ao);
        surf += base * vec3(1.0, 0.55, 0.45) * 0.12 * (1.0 - facing);
        surf += vec3(1.0) * spec * sh + vec3(0.45, 0.65, 1.0) * rim * 0.45;
        if (m.y > 4.5 && m.y < 6.5) surf += vec3(1.0, 0.55, 0.25) * 0.1;
        if (cutFace) surf = base * (0.55 + 0.35 * ao) + base * 0.15;
      } else if (uStyle < 2.5) {
        // Fluorescence: emission only, brightest at silhouettes.
        surf = channel(m.y) * (0.35 + 0.9 * pow(1.0 - facing, 2.0)) * (0.6 + 0.4 * ao);
        if (cutFace) surf = channel(m.y) * 0.5;
      } else if (uStyle < 3.5) {
        // Cryo-ET: dense matter reads dark in a noisy grey tomogram.
        float dens = m.y < 2.5 || m.y == 5.0 || m.y == 7.0 ? 0.16 : m.y == 3.0 || m.y == 9.0 ? 0.24 : 0.36;
        surf = vec3(mix(dens, 0.5, cutFace ? 0.15 : 0.35 * facing)) * (0.75 + 0.25 * ao);
      } else if (uStyle < 4.5) {
        // Cel cartoon: three tones and bold contours.
        float band = diff > 0.6 ? 1.0 : diff > 0.25 ? 0.78 : 0.56;
        surf = base * band * (0.85 + 0.15 * ao) * 1.08;
        if (cutFace) surf = mix(base, vec3(1.0), 0.25);
        if (nearMiss || facing < 0.3) surf = vec3(0.04, 0.03, 0.08);
      } else if (uStyle < 5.5) {
        // Electron micrograph: the cut face is the thin section; heavy-metal stain marks membranes and dense matter.
        float id = m.y;
        float stain = id < 1.5 ? 0.15 : id < 2.5 ? 0.2 : id < 3.5 ? 0.26 + 0.14 * m.z : id < 4.5 ? 0.2 : id < 5.5 ? 0.22 : id < 6.5 ? 0.2 : id < 8.5 ? 0.27 : id < 9.5 ? 0.13 : id < 10.5 ? 0.3 : id < 11.5 ? 0.36 : id < 12.5 ? 0.5 : id < 13.5 ? 0.3 : id < 14.5 ? 0.5 : 0.1;
        if (uCutOn < 0.5) surf = vec3(mix(stain, 0.62, 0.45) * (0.75 + 0.25 * facing));
        else surf = vec3(cutFace ? stain : 0.6 + 0.04 * (m.z - 0.5));
      } else {
        // Confocal: only the optical section is in focus; out-of-plane matter fades into darkness.
        float pd = uCutOn > 0.5 ? dot(p, uCut.xyz) - uCut.w : 0.0;
        surf = channel(m.y) * (cutFace ? 0.85 : 0.55 * exp(-pd * pd / 0.0025)) * (0.7 + 0.3 * ao);
      }
      surf *= layerGain(m.y);
      if (abs(m.y - uHighlight) < 0.5 && uHighlight > 0.5) surf += vec3(0.55, 0.8, 1.0) * (0.15 + 0.5 * pow(1.0 - facing, 2.0));
      float fog = 1.0 - exp(-max(t - 1.2, 0.0) * 0.8);
      surf = mix(surf, col, fog * 0.5);
      col = surf;
    } else if (nearMiss && (uStyle < 0.5 || (uStyle > 3.5 && uStyle < 4.5))) {
      col = mix(col, uStyle < 0.5 ? vec3(0.05, 0.04, 0.08) : vec3(0.04, 0.03, 0.08), 0.75);
    }
    col = acc + trans * col + glow;
  }

  if (uPickMode > 0.5) { fragColor = vec4(pickId / 32.0, 0.0, 0.0, 1.0); return; }

  if ((uStyle > 2.5 && uStyle < 3.5) || (uStyle > 4.5 && uStyle < 5.5)) {
    float g = dot(col, vec3(0.333));
    col = vec3(g) + (hash13(vec3(gl_FragCoord.xy * 1.3, uStyle > 4.5 ? 1.0 : floor(uTime * 12.0))) - 0.5) * (uStyle > 4.5 ? 0.07 : 0.1);
  }
  col = col / (1.0 + col * 0.25);
  col = pow(col, vec3(0.92));
  col *= mix(0.6, 1.0, smoothstep(1.2, 0.35, length(uv)));
  fragColor = vec4(col, 1.0);
}
`;
