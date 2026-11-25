// Headless Chrome driver for the development preview: node scripts/cdp-driver.mjs <scenario.mjs> [width height]
// Screenshots go to $SHOTS (default: the system temp directory). The scenario's default export receives `page`.
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const [scenario, W = '1440', H = '900'] = process.argv.slice(2);
const shots = process.env.SHOTS || fs.mkdtempSync(path.join(os.tmpdir(), 'fold-shots-')), profile = fs.mkdtempSync(path.join(os.tmpdir(), 'fold-chrome-')), port = 9333 + Math.floor(Math.random() * 500);
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, `--window-size=${W},${H}`, '--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--hide-scrollbars', '--no-first-run', '--disable-extensions', 'about:blank'], {stdio: 'ignore'});
const sleep = ms => new Promise(r => setTimeout(r, ms));
let target;
for (let i = 0; i < 40 && !target; i++) { await sleep(250); try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(t => t.type === 'page'); } catch {} }
const ws = new WebSocket(target.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
let id = 0; const pending = new Map(), logs = [];
ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
  if (d.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(d.params.type)) logs.push(d.params.type + ': ' + d.params.args.map(a => a.value ?? a.description ?? '').join(' ').slice(0, 400));
  if (d.method === 'Runtime.exceptionThrown') logs.push('EXCEPTION: ' + (d.params.exceptionDetails.exception?.description ?? d.params.exceptionDetails.text).slice(0, 600)); };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({id: i, method, params})); });
await send('Runtime.enable'); await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', {width: +W, height: +H, deviceScaleFactor: 1, mobile: false});
const page = {
  logs, sleep,
  goto: async url => { await send('Page.navigate', {url}); await sleep(1500); },
  eval: async expr => { const r = await send('Runtime.evaluate', {expression: expr, awaitPromise: true, returnByValue: true}); if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description ?? 'eval failed'); return r.result?.result?.value; },
  shot: async name => { const r = await send('Page.captureScreenshot', {format: 'png'}); fs.mkdirSync(shots, {recursive: true}); fs.writeFileSync(path.join(shots, name + '.png'), Buffer.from(r.result.data, 'base64')); console.log('shot', name); },
  // click the first visible element matching a selector whose text (or title / aria-label) contains `text`
  click: async (selector, text = '') => { const ok = await page.eval(`(() => { const t = ${JSON.stringify(text)}; const el = [...document.querySelectorAll(${JSON.stringify(selector)})].find(e => e.offsetParent !== null && (!t || (e.textContent + ' ' + (e.title || '') + ' ' + (e.getAttribute('aria-label') || '')).includes(t))); if (!el) return false; el.click(); return true; })()`); if (!ok) console.log('  !! not found:', selector, text); await sleep(350); return ok; },
  set: async (selector, value, nth = 0) => page.eval(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(selector)})].filter(e => e.offsetParent !== null)[${nth}]; if (!el) return false; const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(String(value))}); el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); return true; })()`),
  mouse: async (type, x, y, extra = {}) => send('Input.dispatchMouseEvent', {type, x, y, button: 'left', clickCount: 1, ...extra}),
  clickAt: async (x, y) => { await page.mouse('mousePressed', x, y); await page.mouse('mouseReleased', x, y); await sleep(300); },
  drag: async (x0, y0, x1, y1) => { await page.mouse('mousePressed', x0, y0); for (let i = 1; i <= 8; i++) await page.mouse('mouseMoved', x0 + (x1 - x0) * i / 8, y0 + (y1 - y0) * i / 8, {buttons: 1}); await page.mouse('mouseReleased', x1, y1); await sleep(300); },
  wheel: async (x, y, deltaY) => { await send('Input.dispatchMouseEvent', {type: 'mouseWheel', x, y, deltaX: 0, deltaY}); await sleep(120); },
  key: async key => { await send('Input.dispatchKeyEvent', {type: 'keyDown', key, text: key.length === 1 ? key : undefined}); await send('Input.dispatchKeyEvent', {type: 'keyUp', key}); await sleep(250); },
  text: async selector => page.eval(`[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e => e.offsetParent !== null).map(e => e.innerText.replace(/\\s+/g, ' ').trim()).join(' | ')`),
  waitFor: async (expr, ms = 30000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (await page.eval(expr)) return true; await sleep(300); } console.log('  !! timeout waiting for', expr.slice(0, 80)); return false; },
};
try { await (await import(path.resolve(scenario))).default(page); } catch (e) { console.log('SCENARIO ERROR', e.message); }
if (logs.length) console.log('--- console ---\n' + [...new Set(logs)].slice(0, 25).join('\n'));
ws.close(); chrome.kill();
