// Open → Explore → Run → Inspect → Compare in the development preview, then the light-pulse experiment.
// Needs the worker on 1425 and Vite on 5176 (see AGENTS.md). node scripts/cdp-driver.mjs scripts/walkthrough-workspace.mjs 1440 900
export default async p => {
  await p.goto('http://127.0.0.1:5176/'); await p.sleep(2500);
  await p.eval(`(() => { const m = document.querySelector('.modal'); const b = m && [...m.querySelectorAll('button')].find(b => !b.textContent.trim()); if (b) b.click(); })()`);
  await p.click('.nav-item', 'Cell Explorer');
  await p.waitFor(`!!document.querySelector('.ws-view canvas') && !document.querySelector('.ws-chips .spin')`, 90000); await p.sleep(2000); await p.shot('1-open');
  const box = await p.eval(`(() => { const r = document.querySelector('.ws-pane.a canvas').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()`);
  await p.clickAt(box[0] + box[2] / 2, box[1] + box[3] / 2 + 10); await p.click('.ws-right .ws-btn', 'Isolate'); await p.sleep(800); await p.shot('2-isolate');
  await p.click('.ws-right .ws-btn', 'Show all');
  if (!(await p.eval(`!!document.querySelector('.ws-left')`))) await p.key('l');
  await p.click('.ws-left .ws-tabs button', 'Experiment'); await p.set('.ws-card select', 'preset:gfp', 0);
  await p.click('.ws-left .ws-btn', 'Add another molecule'); await p.click('.ws-pair .ws-switch', 'Off');
  await p.click('.ws-go', 'Release'); await p.waitFor(`!!document.querySelector('.ws-dock .ws-clock')`, 40000); await p.sleep(8000); await p.shot('3-run');
  await p.click('.ws-tabs.dock button', 'Events'); await p.click('.ws-events button'); await p.sleep(2500); await p.shot('4-inspect');
  console.log('event:', (await p.text('.ws-right')).slice(0, 200));
  await p.key('h'); await p.click('.ws-timeline .ws-btn', 'Branch'); await p.set('.ws-pair .ws-grid.three input', '20000', 1);
  await p.click('.ws-go', ''); await p.sleep(6000); await p.click('.ws-timeline .ws-btn', 'Compare side by side'); await p.sleep(16000); await p.shot('5-compare');
  console.log('compare:', (await p.text('.ws-dock-body .ws-table')).slice(0, 300));
  await p.set('.ws-context select', 'ecoli-bw29655-ccasr'); await p.sleep(2500); await p.click('.ws-seg button', 'Light pulse');
  await p.waitFor(`!!document.querySelector('.ws-strip')`, 90000);
  await p.set('.ws-left select[aria-label="Run a measured schedule"]', 'dynamic-green'); await p.click('.ws-go', 'Run the light program'); await p.sleep(5000); await p.shot('6-held-out');
  console.log('held out:', (await p.text('.ws-dock-body .ws-table')).slice(0, 400));
  await p.click('.ws-saved button'); await p.sleep(4000); console.log('reopened:', await p.text('.ws-dock-body .ws-ok'));
  console.log('errors:', await p.text('.ws-error'));
};
