import fs from 'node:fs';
const OUT = new URL('.', import.meta.url).pathname;
const names = ['landscape', 'context', 'container', 'component', 'dynamic', 'state', 'deploy', 'llm'];
const sleep = ms => new Promise(r => setTimeout(r, ms));
let page;
for (let i = 0; i < 40 && !page; i++) { try { page = (await (await fetch('http://127.0.0.1:9333/json')).json()).find(t => t.type === 'page'); } catch {} if (!page) await sleep(1000); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (m, p={}) => new Promise((res, rej) => { const i = ++id; pending[i] = {res, rej}; ws.send(JSON.stringify({id: i, method: m, params: p})); });
const evalJs = async e => (await send('Runtime.evaluate', {expression: e, awaitPromise: true, returnByValue: true})).result?.value;
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending[m.id]) { m.error ? pending[m.id].rej(new Error(JSON.stringify(m.error))) : pending[m.id].res(m.result); delete pending[m.id]; } };
ws.onopen = async () => {
  try {
    await send('Page.enable'); await send('Runtime.enable');
    await send('Emulation.setDeviceMetricsOverride', {width: 2400, height: 1800, deviceScaleFactor: 1, mobile: false});
    for (const name of names) {
      await send('Page.navigate', {url: `http://localhost:8765/render.html?f=${name}.mmd`});
      let done = false;
      for (let i = 0; i < 40 && !done; i++) { await sleep(500); done = await evalJs('!!window.__done').catch(() => false); }
      const err = await evalJs('window.__err || ""');
      if (err) { console.log(name, 'ERROR', err); continue; }
      const box = JSON.parse(await evalJs("JSON.stringify((() => { const b = document.querySelector('#out svg').getBoundingClientRect(); return {x: b.x, y: b.y, w: b.width, h: b.height}; })())"));
      const shot = await send('Page.captureScreenshot', {format: 'png', clip: {x: box.x - 8, y: box.y - 8, width: box.w + 16, height: box.h + 16, scale: 3}, captureBeyondViewport: true});
      fs.writeFileSync(OUT + name + '.png', Buffer.from(shot.data, 'base64'));
      console.log(name, 'rendered', Math.round(box.w), 'x', Math.round(box.h));
    }
  } catch (e) { console.log('ERR', e.message); }
  ws.close(); process.exit(0);
};
setTimeout(() => { console.log('watchdog'); process.exit(2); }, 240000);
