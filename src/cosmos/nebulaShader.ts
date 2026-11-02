/**
 * Full-screen deep-space backdrop: a soft galactic haze, one sparse star field
 * and a lantern of light that drifts after the pointer and gently lights the
 * gas around it. Stars use an integer hash, so the field never visibly tiles.
 * uVariant picks the palette: 0 Stellar (violet haze, ember core),
 * 1 Abyss (teal star dust), 2 Scientific (near-black, very quiet).
 */
export const nebulaVertex = `#version 300 es
in vec2 aPosition;
void main(){ gl_Position = vec4(aPosition, 0.0, 1.0); }
`;

export const nebulaFragment = `#version 300 es
precision highp float;
uniform vec2 uResolution;
uniform float uTime;
uniform vec2 uPointer;      // eased pointer, 0–1, origin bottom-left
uniform float uPointerGlow; // 0 when the pointer is away, 1 while it moves
uniform float uVariant;
out vec4 fragColor;

uint pcg(uint v){ uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u; return (w >> 22u) ^ w; }
float rand(uvec2 p){ return float(pcg(p.x + pcg(p.y))) / 4294967295.0; }
float rand(uvec2 p, uint salt){ return float(pcg(p.x + pcg(p.y + pcg(salt)))) / 4294967295.0; }

float vnoise(vec2 p){
  vec2 i = floor(p), f = fract(p), u = f * f * (3.0 - 2.0 * f);
  uvec2 c = uvec2(ivec2(i) + 32768);
  return mix(mix(rand(c), rand(c + uvec2(1, 0)), u.x), mix(rand(c + uvec2(0, 1)), rand(c + uvec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p){
  float v = 0.0, a = 0.5; mat2 r = mat2(0.8, -0.6, 0.6, 0.8);
  for (int i = 0; i < 4; i++) { v += a * vnoise(p); p = r * p * 2.02 + 17.0; a *= 0.5; }
  return v;
}

// Sparse stars: each large cell holds at most one star at a random position.
vec3 starLayer(vec2 px, float cell, float density, float t, vec2 light, float lightR){
  vec2 g = px / cell;
  uvec2 id = uvec2(ivec2(floor(g)) + 32768);
  if (rand(id, 3u) > density) return vec3(0.0);
  vec2 centre = (floor(g) + vec2(rand(id, 5u), rand(id, 7u))) * cell;
  float d = length(px - centre);
  float size = mix(0.6, 1.6, pow(rand(id, 11u), 3.0));
  float bright = mix(0.25, 1.0, pow(rand(id, 13u), 4.0));
  float tw = 0.75 + 0.25 * sin(t * mix(0.3, 1.1, rand(id, 17u)) + rand(id, 19u) * 6.283);
  float near = exp(-pow(length(centre / uResolution.y - light) / lightR, 2.0));
  float core = exp(-d * d / (size * size));
  float halo = exp(-d / (size * 5.0)) * 0.12 * bright;
  vec3 tint = mix(vec3(0.78, 0.86, 1.0), vec3(1.0, 0.9, 0.82), step(0.82, rand(id, 23u)));
  return tint * (core + halo) * bright * tw * (1.0 + 1.2 * near);
}

void main(){
  vec2 frag = gl_FragCoord.xy;
  float aspect = uResolution.x / uResolution.y;
  vec2 p = (frag / uResolution - 0.5) * vec2(aspect, 1.0);
  vec2 light = (uPointer - 0.5) * vec2(aspect, 1.0);
  float t = uTime;

  // A broad, slow galactic band of haze.
  float ang = uVariant < 0.5 ? 0.38 : uVariant < 1.5 ? 0.6 : 0.5;
  vec2 q = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * p;
  vec2 drift = vec2(t * 0.004, t * 0.0015);
  vec2 warp = vec2(fbm(q * 1.2 + drift), fbm(q * 1.2 + vec2(4.1, 2.7) - drift));
  // The lantern stirs the gas very slightly, like breath on fog.
  vec2 toLight = p - light;
  float lantern = exp(-dot(toLight, toLight) / 0.09);
  warp += vec2(-toLight.y, toLight.x) * lantern * 0.25 * uPointerGlow;
  float gas = fbm(q * 1.7 + 1.8 * warp + drift * 2.0);
  float band = exp(-pow((q.y + (gas - 0.5) * 0.22) / 0.3, 2.0));
  float wide = exp(-pow(q.y / 0.75, 2.0));
  float dust = smoothstep(0.5, 0.78, fbm(q * 3.4 + warp * 2.5));

  vec3 deep, haze, glow, core;
  if (uVariant < 0.5) { deep = vec3(0.008, 0.010, 0.030); haze = vec3(0.07, 0.08, 0.26); glow = vec3(0.30, 0.22, 0.62); core = vec3(0.85, 0.52, 0.42); }
  else if (uVariant < 1.5) { deep = vec3(0.004, 0.014, 0.028); haze = vec3(0.03, 0.12, 0.22); glow = vec3(0.12, 0.34, 0.50); core = vec3(0.55, 0.75, 0.9); }
  else { deep = vec3(0.010, 0.012, 0.018); haze = vec3(0.04, 0.05, 0.08); glow = vec3(0.09, 0.11, 0.17); core = vec3(0.3, 0.33, 0.4); }

  vec3 col = deep + haze * wide * (0.4 + 0.6 * gas);
  col += glow * band * smoothstep(0.3, 0.85, gas) * 0.7;
  vec2 cc = q - vec2(0.18, 0.0);
  col += core * exp(-dot(cc * vec2(1.0, 2.6), cc * vec2(1.0, 2.6)) * 7.0) * (0.3 + 0.5 * gas) * 0.6;
  col *= 1.0 - 0.45 * dust * band;

  // The lantern itself: a soft, cool-to-warm light that brightens the haze it touches.
  float glowK = lantern * uPointerGlow;
  col += (glow * 0.5 + vec3(0.10, 0.12, 0.22)) * glowK * (0.35 + 0.65 * gas) * 0.55;
  col += vec3(0.5, 0.6, 1.0) * exp(-dot(toLight, toLight) / 0.004) * 0.05 * uPointerGlow;

  // Stars: one sparse field plus a few brighter beacons, in pixel space so they stay crisp.
  float scale = uResolution.y / 900.0;
  col += starLayer(frag, 34.0 * scale, uVariant > 1.5 ? 0.18 : 0.3, t, light, 0.25) * 0.55;
  col += starLayer(frag + 977.0, 90.0 * scale, 0.35, t * 0.7, light, 0.25) * 0.9;
  col += starLayer(frag + 3301.0, 220.0 * scale, 0.5, t * 0.5, light, 0.25) * 1.2;

  col *= mix(0.6, 1.0, smoothstep(1.3, 0.25, length(p * vec2(0.75, 1.0))));
  col = col / (1.0 + col * 0.4);
  fragColor = vec4(col, 1.0);
}
`;
