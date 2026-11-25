/**
 * Ray-marched view of a measured EM volume (R8 3-D texture) and its per-voxel compartment classes (R8, nearest).
 * World box: centred on the origin with half extents uBox; data x, y, z map to world x, y (up), z.
 * The cut removes the camera-side part along one axis; where the cut face meets a cell, the raw EM signal is drawn.
 * Modes: 0 lit compartment surfaces, 1 EM density, 2 fluorescence-style emission (Cell Painting stain model).
 */
export const CLASS_SLOTS = 16;

export const volumeVertex = `#version 300 es
in vec2 aPosition;
void main() { gl_Position = vec4(aPosition, 0.0, 1.0); }`;

export const volumeFragment = `#version 300 es
precision highp float;
precision highp sampler3D;
uniform sampler3D uEM, uCls, uField, uDetail;
uniform vec3 uDetLo, uDetHi, uFieldColor, uActColor;   // detail region (world box); colours of the concentration field and of compartment activity
uniform float uDetOn, uFieldGain, uImage;              // uImage: 1 when a measured image exists for this geometry
uniform int uSelected;                                 // selected compartment class, -1 none
uniform float uActivity[${CLASS_SLOTS}];               // modelled activity per class, 0…1
uniform vec2 uResolution;
uniform vec3 uCamPos, uCamTarget, uBox, uDims;
uniform vec3 uCutLo, uCutHi;      // kept region of the box
uniform int uCutAxis;             // -1 none
uniform float uCutAt;             // world coordinate of the cut face
uniform float uFace, uInvert, uMode, uTint, uGain, uSteps, uShift;   // uShift: horizontal offset of the view centre, in uv units
uniform float uShow[${CLASS_SLOTS}];
uniform vec3 uColor[${CLASS_SLOTS}];
uniform vec3 uPaint[${CLASS_SLOTS}];   // stain emission per class (mode 2)
out vec4 outColor;

vec3 tc(vec3 p) { return p / uBox * 0.5 + 0.5; }
int cls(vec3 p) { return int(texture(uCls, tc(p)).r * 255.0 + 0.5); }
float em(vec3 p) {
  if (uDetOn > 0.5 && all(greaterThanEqual(p, uDetLo)) && all(lessThanEqual(p, uDetHi))) return texture(uDetail, (p - uDetLo) / (uDetHi - uDetLo)).r;   // finer pyramid level where one is loaded
  return texture(uEM, tc(p)).r;
}
float same(vec3 p, int c) { return cls(p) == c ? 1.0 : 0.0; }
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

void main() {
  vec2 uv = (gl_FragCoord.xy * 2.0 - uResolution) / uResolution.y; uv.x += uShift;
  vec3 ro = uCamPos, fw = normalize(uCamTarget - ro), rt = normalize(cross(fw, vec3(0.0, 1.0, 0.0))), up = cross(rt, fw);
  vec3 rd = normalize(fw * 1.7 + uv.x * rt + uv.y * up);
  float vignette = 1.0 - 0.35 * dot(uv * 0.55, uv * 0.55);
  vec3 bg = uMode > 1.5 ? vec3(0.0) : mix(vec3(0.018, 0.02, 0.024), vec3(0.042, 0.046, 0.054), 0.5 + 0.5 * uv.y) * vignette;   // neutral graphite: the cell supplies the colour
  vec3 inv = 1.0 / rd, t0 = (uCutLo - ro) * inv, t1 = (uCutHi - ro) * inv;
  vec3 tn = min(t0, t1), tf = max(t0, t1);
  float tNear = max(max(tn.x, tn.y), max(tn.z, 0.0)), tFar = min(tf.x, min(tf.y, tf.z));
  if (tNear >= tFar) { outColor = vec4(bg, 1.0); return; }
  vec3 voxel = 2.0 * uBox / uDims;
  float ds = max(min(voxel.x, min(voxel.y, voxel.z)), (tFar - tNear) / uSteps);
  vec3 col = vec3(0.0); float alpha = 0.0;
  vec3 light = normalize(vec3(0.4, 0.85, 0.35));

  // The cut face: the measured EM signal itself, wherever the face passes through a cell.
  vec3 p0 = ro + rd * (tNear + ds * 0.02);
  bool onFace = uCutAxis >= 0 && abs((uCutAxis == 0 ? p0.x : uCutAxis == 1 ? p0.y : p0.z) - uCutAt) < ds * 0.6;
  if (onFace && uFace > 0.5 && uMode < 1.5) {
    int c = cls(p0);
    if (c != 0) {
      float on = uShow[c] > 0.0 ? uTint : 0.0;
      if (uImage > 0.5) {
        float v = em(p0); v = mix(v, 1.0 - v, uInvert);
        vec3 g = vec3(pow(v, 0.9));
        col = mix(g, g * (0.42 + uColor[c] * 1.15), on);
      } else col = uColor[c] * (0.16 + 0.3 * on);            // no image for this geometry: flat class colour, never a fake micrograph
      col += uActColor * uActivity[c] * 0.55;
      if (c == uSelected) col = mix(col, vec3(0.45, 0.95, 1.0), 0.22);
      alpha = 1.0;
    }
  }

  int prev = -1; float t = tNear + ds * (uMode > 0.5 ? 0.3 + 0.5 * hash(gl_FragCoord.xy) : 0.5);   // jitter hides banding in the translucent modes
  vec3 glow = vec3(0.0); float fieldGlow = 0.0;
  for (int i = 0; i < 700 && alpha < 0.985 && t < tFar; i++, t += ds) {
    vec3 p = ro + rd * t;
    int c = cls(p);
    if (uFieldGain > 0.0) fieldGlow += texture(uField, tc(p)).r * ds * (1.0 - alpha);
    if (uMode > 1.5) {                                   // stain emission, optically thin
      glow += uPaint[c] * ds;
    } else if (uMode > 0.5) {                            // EM density: stained matter inside cells
      if (c != 0) {
        float v = em(p), a = smoothstep(0.42, 0.95, v) * uGain * 0.35;
        col += (1.0 - alpha) * a * mix(vec3(0.55, 0.62, 0.8), vec3(1.0, 0.97, 0.9), v); alpha += (1.0 - alpha) * a;
      }
    } else if (c != prev && c > 0 && uShow[c] > 0.0) {   // entering a compartment: a lit surface
      vec3 e = voxel * 1.5;
      vec3 n = vec3(same(p + vec3(e.x, 0, 0), c) - same(p - vec3(e.x, 0, 0), c), same(p + vec3(0, e.y, 0), c) - same(p - vec3(0, e.y, 0), c), same(p + vec3(0, 0, e.z), c) - same(p - vec3(0, 0, e.z), c));
      n = dot(n, n) > 0.0 ? -normalize(n) : -rd;
      float diffuse = max(dot(n, light), 0.0), rim = pow(1.0 - abs(dot(n, rd)), 2.5);
      float spec = pow(max(dot(reflect(-light, n), -rd), 0.0), 24.0);
      float depth = exp(-(t - tNear) * 0.55);            // depth cue: far structures recede
      vec3 lit = uColor[c] * (0.26 + 0.74 * diffuse) + uColor[c] * rim * 0.45 + vec3(spec * 0.35);
      lit += uActColor * uActivity[c] * (0.5 + 0.9 * rim);   // modelled activity: the only glow besides the selection
      if (c == uSelected) lit = mix(lit, vec3(0.45, 0.95, 1.0), 0.18) + vec3(0.35, 0.9, 1.0) * rim * 0.9;
      float a = c == uSelected ? max(uShow[c], 0.55) : uShow[c];
      col += (1.0 - alpha) * a * lit * (0.45 + 0.55 * depth); alpha += (1.0 - alpha) * a;
    }
    prev = c;
  }
  if (uMode > 1.5) { col = 1.0 - exp(-glow * uGain * 60.0); alpha = 1.0; }
  vec3 outc = col + (1.0 - alpha) * bg;
  if (uFieldGain > 0.0) outc += uFieldColor * (1.0 - exp(-fieldGlow * uFieldGain));
  outColor = vec4(outc, 1.0);
}`;

/** Molecules far away: computed positions (world coordinates) as soft discs coloured by species. */
export const pointVertex = `#version 300 es
in vec3 aPoint;
in float aAge;          // 0 = current frame, 1 = oldest trail sample
in float aState;        // 0 free, 1 bound to a compartment, 2 in a complex, 4 event marker, 5 selected
in vec3 aColor;
uniform vec3 uCamPos, uCamTarget, uCutLo, uCutHi;
uniform vec2 uResolution;
uniform float uSize, uShift;
out float vAge; out float vState; out vec3 vColor;
void main() {
  vec3 fw = normalize(uCamTarget - uCamPos), rt = normalize(cross(fw, vec3(0.0, 1.0, 0.0))), up = cross(rt, fw);
  vec3 d = aPoint - uCamPos; float z = dot(d, fw);
  bool kept = all(greaterThanEqual(aPoint, uCutLo - 1e-4)) && all(lessThanEqual(aPoint, uCutHi + 1e-4));
  vAge = aAge; vState = aState; vColor = aColor;
  if (z <= 1e-5 || !kept) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 0.0; return; }
  float aspect = uResolution.x / uResolution.y;
  gl_Position = vec4((dot(d, rt) * 1.7 / z - uShift) / aspect, dot(d, up) * 1.7 / z, 0.0, 1.0);
  gl_PointSize = aState > 3.5 ? clamp(uSize * uResolution.y / z * 3.0, 22.0, 56.0) : clamp(uSize * uResolution.y / z * mix(1.0, 0.45, aAge) * (1.0 + 0.5 * min(aState, 1.0)), 1.5, 40.0);
}`;

export const pointFragment = `#version 300 es
precision highp float;
in float vAge; in float vState; in vec3 vColor;
out vec4 outColor;
void main() {
  float r = length(gl_PointCoord - 0.5) * 2.0;
  if (r > 1.0) discard;
  if (vState > 3.5) {                                      // event or selection marker: a crisp ring with a soft halo, never a filled disc
    float ringM = smoothstep(0.09, 0.0, abs(r - 0.62)), halo = smoothstep(1.0, 0.62, r) * 0.22, tick = vState > 4.5 ? smoothstep(0.12, 0.0, r) : 0.0;
    outColor = vec4(vColor, max(max(ringM, halo), tick) * (1.0 - 0.75 * vAge)); return;
  }
  float core = smoothstep(1.0, 0.0, r);
  vec3 c = vState > 1.5 ? mix(vColor, vec3(1.0), 0.55) : vState > 0.5 ? mix(vColor, vec3(1.0, 0.86, 0.3), 0.7) : vColor;
  float ring = vState > 0.5 ? smoothstep(0.25, 0.0, abs(r - 0.78)) * 0.9 : 0.0;
  outColor = vec4(c + 0.55 * core * core, max(core, ring) * mix(0.95, 0.12, vAge));
}`;

/**
 * Molecules up close: every atom as a shaded sphere impostor at its true size. One instance per molecule
 * (position, orientation quaternion, tint); one vertex per atom (local position and radius in world units, colour).
 */
export const atomVertex = `#version 300 es
in vec4 aAtom;          // xyz local (world units), w radius
in vec3 aAtomColor;     // alpha-free element colour; carbon is (-1) to take the molecule tint
in vec3 iPos;
in vec4 iQuat;
in vec4 iTint;          // rgb tint, a = state
uniform vec3 uCamPos, uCamTarget, uCutLo, uCutHi;
uniform vec2 uResolution;
uniform vec2 uDepthRange;   // near, far for the logarithmic depth
uniform float uShift;
out vec3 vColor; out float vRadius; out float vZ; out float vState;
vec3 rotate(vec3 v, vec4 q) { return v + 2.0 * cross(q.xyz, cross(q.xyz, v) + q.w * v); }
void main() {
  vec3 fw = normalize(uCamTarget - uCamPos), rt = normalize(cross(fw, vec3(0.0, 1.0, 0.0))), up = cross(rt, fw);
  vec3 d = (iPos - uCamPos) + rotate(aAtom.xyz, iQuat);
  float z = dot(d, fw);
  bool kept = all(greaterThanEqual(iPos, uCutLo - 1e-4)) && all(lessThanEqual(iPos, uCutHi + 1e-4));
  vColor = aAtomColor.r < 0.0 ? iTint.rgb : mix(aAtomColor, iTint.rgb, 0.12);
  vRadius = aAtom.w; vZ = z; vState = iTint.a;
  if (z <= uDepthRange.x || !kept) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 0.0; return; }
  float aspect = uResolution.x / uResolution.y;
  float depth = log(z / uDepthRange.x) / log(uDepthRange.y / uDepthRange.x);
  gl_Position = vec4((dot(d, rt) * 1.7 / z - uShift) / aspect, dot(d, up) * 1.7 / z, depth * 2.0 - 1.0, 1.0);
  gl_PointSize = max(1.0, aAtom.w * 1.7 / z * uResolution.y);
}`;

export const atomFragment = `#version 300 es
precision highp float;
in vec3 vColor; in float vRadius; in float vZ; in float vState;
uniform vec2 uDepthRange;
out vec4 outColor;
void main() {
  vec2 q = (gl_PointCoord - 0.5) * 2.0; q.y = -q.y;
  float r2 = dot(q, q);
  if (r2 > 1.0) discard;
  vec3 n = vec3(q, sqrt(1.0 - r2));                       // view-space normal of the sphere
  vec3 l = normalize(vec3(0.45, 0.7, 0.55));
  float diffuse = max(dot(n, l), 0.0), spec = pow(max(dot(reflect(-l, n), vec3(0.0, 0.0, 1.0)), 0.0), 32.0);
  float edge = smoothstep(0.0, 0.5, n.z);                 // soft silhouette darkening gives depth between atoms
  vec3 c = vColor * (0.22 + 0.78 * diffuse) * (0.55 + 0.45 * edge) + vec3(spec * 0.4);
  if (vState > 1.5) c += vec3(0.08, 0.07, 0.02);
  float z = max(vZ - vRadius * n.z, uDepthRange.x);
  gl_FragDepth = clamp(log(z / uDepthRange.x) / log(uDepthRange.y / uDepthRange.x), 0.0, 1.0);
  outColor = vec4(c, 1.0);
}`;

/** Lines in world coordinates: the bounds of the acquired volume and the path of the followed molecule. */
export const lineVertex = `#version 300 es
in vec3 aPoint;
in float aAlpha;
uniform vec3 uCamPos, uCamTarget;
uniform vec2 uResolution;
uniform float uShift;
out float vAlpha;
void main() {
  vec3 fw = normalize(uCamTarget - uCamPos), rt = normalize(cross(fw, vec3(0.0, 1.0, 0.0))), up = cross(rt, fw);
  vec3 d = aPoint - uCamPos; float z = max(dot(d, fw), 1e-5);
  vAlpha = aAlpha;
  gl_Position = vec4((dot(d, rt) * 1.7 / z - uShift) / (uResolution.x / uResolution.y), dot(d, up) * 1.7 / z, 0.0, 1.0);
}`;

export const lineFragment = `#version 300 es
precision highp float;
in float vAlpha;
uniform vec3 uLineColor;
out vec4 outColor;
void main() { outColor = vec4(uLineColor, vAlpha); }`;
