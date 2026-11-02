/**
 * Simulated micrograph. Each pixel is the projected density of Gaussian beads,
 * summed over the particles near it, which is how a transmission image is formed
 * (a projection of the specimen). The contrast, defocus fringes and shot noise
 * are simple approximations chosen to look like the technique; this is an
 * illustration derived from coordinates, not a physics-grade image simulation.
 *
 * uScene: 0 a field of randomly oriented copies of one particle, 1 one object.
 * uMode: 0 cryo-EM, 1 negative stain, 2 illustrated (flat Goodsell-like fills).
 */
export const micrographVertex = `#version 300 es
in vec2 aPosition;
void main(){ gl_Position = vec4(aPosition, 0.0, 1.0); }
`;

export const micrographFragment = `#version 300 es
precision highp float;
uniform vec2 uResolution;
uniform vec2 uPan;          // field centre, Å
uniform float uField;       // field height, Å
uniform vec4 uBeads[120];   // x, y, z, sigma (Å)
uniform float uWeights[120];
uniform int uCount;
uniform float uRadius;      // particle bounding radius, Å
uniform float uSpacing;     // lattice spacing, Å
uniform float uFill;        // fraction of lattice sites occupied
uniform float uScene;
uniform float uMode;
uniform float uGain;
uniform float uNoise;
uniform float uDefocus;
uniform float uSeed;
uniform float uPaper;
out vec4 fragColor;

uint pcg(uint v){ uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u; return (w >> 22u) ^ w; }
float rand(ivec2 c, uint salt){ return float(pcg(uint(c.x + 40000) + pcg(uint(c.y + 40000) + pcg(salt)))) / 4294967295.0; }
float vnoise(vec2 p){
  vec2 i = floor(p), f = fract(p), u = f * f * (3.0 - 2.0 * f);
  ivec2 c = ivec2(i);
  return mix(mix(rand(c, 91u), rand(c + ivec2(1, 0), 91u), u.x), mix(rand(c + ivec2(0, 1), 91u), rand(c + ivec2(1, 1), 91u), u.x), u.y);
}

// A uniformly random rotation from three random numbers (Shoemake's method).
mat3 rotation(vec3 u){
  float a = sqrt(1.0 - u.x), b = sqrt(u.x), t1 = 6.2831853 * u.y, t2 = 6.2831853 * u.z;
  vec4 q = vec4(a * sin(t1), a * cos(t1), b * sin(t2), b * cos(t2));
  float x = q.x, y = q.y, z = q.z, w = q.w;
  return mat3(1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y + z * w), 2.0 * (x * z - y * w),
              2.0 * (x * y - z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z + x * w),
              2.0 * (x * z + y * w), 2.0 * (y * z - x * w), 1.0 - 2.0 * (x * x + y * y));
}

// Projected density of one particle at offset d from its centre: sharp and blurred terms.
vec2 particle(vec2 d, mat3 R, float broaden){
  vec2 acc = vec2(0.0);
  for (int i = 0; i < 120; i++) {
    if (i >= uCount) break;
    vec4 b = uBeads[i];
    vec2 c = (R * b.xyz).xy;
    vec2 r = d - c;
    float r2 = dot(r, r), s = b.w, sb = b.w + broaden;
    acc.x += uWeights[i] * exp(-r2 / (2.0 * s * s));
    acc.y += uWeights[i] * exp(-r2 / (2.0 * sb * sb)) * (s * s) / (sb * sb);
  }
  return acc;
}

void main(){
  vec2 world = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y * uField + uPan;
  vec2 dens = vec2(0.0);
  float best = 0.0, hue = 0.0;
  float broaden = uMode > 0.5 && uMode < 1.5 ? 9.0 : 16.0;
  if (uScene < 0.5) {
    ivec2 cell = ivec2(floor(world / uSpacing));
    for (int dy = -1; dy <= 1; dy++) for (int dx = -1; dx <= 1; dx++) {
      ivec2 c = cell + ivec2(dx, dy);
      uint salt = uint(uSeed);
      if (rand(c, salt + 1u) > uFill) continue;
      vec2 centre = (vec2(c) + 0.5 + (vec2(rand(c, salt + 2u), rand(c, salt + 3u)) - 0.5) * 0.35) * uSpacing;
      vec2 d = world - centre;
      if (length(d) > uRadius + 3.0 * broaden) continue;
      mat3 R = rotation(vec3(rand(c, salt + 4u), rand(c, salt + 5u), rand(c, salt + 6u)));
      vec2 p = particle(d, R, broaden);
      dens += p;
      if (p.x > best) { best = p.x; hue = rand(c, salt + 7u); }
    }
  } else {
    dens = particle(world, mat3(1.0), broaden);
    best = dens.x;
  }
  dens *= uGain;

  vec3 col;
  // Shot noise, Box–Muller from a fixed per-pixel seed so the exposure is still.
  ivec2 px = ivec2(gl_FragCoord.xy);
  float n = sqrt(-2.0 * log(max(rand(px, 11u), 1e-6))) * cos(6.2831853 * rand(px, 13u));
  float ice = (vnoise(world / 700.0) - 0.5) * 0.06 + (vnoise(world / 160.0) - 0.5) * 0.025;
  if (uMode < 0.5) {
    // Cryo-EM: protein scatters more than vitreous ice and reads darker; defocus adds a pale fringe.
    float contrast = dens.x - uDefocus * 1.15 * dens.y;
    float g = 0.56 + ice - 0.22 * contrast + n * uNoise;
    col = vec3(g);
  } else if (uMode < 1.5) {
    // Negative stain: heavy-metal stain fills the space around particles, which stay pale.
    float s = smoothstep(0.08, 0.7, dens.y * 1.4);
    float rim = s * (1.0 - s) * 4.0;
    float g = 0.17 + ice * 0.6 + 0.62 * s - 0.12 * rim + 0.18 * smoothstep(0.2, 1.4, dens.x) + n * uNoise * 0.8;
    col = vec3(g);
  } else {
    // Illustrated: flat pastel fill per particle with an ink outline and gentle core shading.
    vec3 paper = uPaper > 0.5 ? vec3(0.96, 0.93, 0.87) : vec3(0.035, 0.05, 0.11);
    vec3 pastel = mix(vec3(0.62, 0.74, 0.98), vec3(0.96, 0.66, 0.6), step(0.33, hue));
    pastel = mix(pastel, vec3(0.62, 0.86, 0.7), step(0.66, hue));
    if (uScene > 0.5) pastel = vec3(0.86, 0.6, 0.82);
    float level = 0.32, f = dens.x;
    float edge = abs(f - level) / max(fwidth(f), 1e-4);
    col = paper;
    if (f > level) col = pastel * (0.82 + 0.18 * smoothstep(level, level * 4.0, f));
    col = mix(uPaper > 0.5 ? vec3(0.12, 0.09, 0.16) : vec3(0.02, 0.02, 0.05), col, smoothstep(0.6, 1.6, edge));
    col += uPaper > 0.5 ? vec3(0.0) : vec3(0.35, 0.5, 0.9) * dens.y * 0.05;
  }
  vec2 uv = gl_FragCoord.xy / uResolution - 0.5;
  col *= 1.0 - 0.22 * dot(uv, uv) * (uMode > 1.5 ? 0.6 : 1.0);
  fragColor = vec4(col, 1.0);
}
`;
