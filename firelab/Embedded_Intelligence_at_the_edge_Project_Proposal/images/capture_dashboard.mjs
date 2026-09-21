import fs from 'node:fs';
const sleep = ms => new Promise(r => setTimeout(r, ms));
let page;
for (let i = 0; i < 40 && !page; i++) { try { page = (await (await fetch('http://127.0.0.1:9333/json')).json()).find(t => t.type === 'page'); } catch {} if (!page) await sleep(1000); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (m, p={}) => new Promise((res, rej) => { const i = ++id; pending[i] = {res, rej}; ws.send(JSON.stringify({id: i, method: m, params: p})); });
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending[m.id]) { m.error ? pending[m.id].rej(new Error(JSON.stringify(m.error))) : pending[m.id].res(m.result); delete pending[m.id]; } };
ws.onopen = async () => {
  try {
    await send('Page.enable');
    await send('Emulation.setDeviceMetricsOverride', {width: 1600, height: 1100, deviceScaleFactor: 1, mobile: false});
    await send('Page.navigate', {url: 'http://localhost:8090/'});
    await sleep(7000);
    const box = (await send('Runtime.evaluate', {expression: "JSON.stringify((() => { const r = [...document.querySelectorAll('tbody tr')].find(t => t.textContent.trim().startsWith('A3505')); if (!r) return null; const b = r.getBoundingClientRect(); return {x: b.left + b.width * 0.3, y: b.top + b.height / 2}; })())", returnByValue: true})).result.value;
    console.log('row at', box);
    if (box) { const {x, y} = JSON.parse(box);
      await send('Input.dispatchMouseEvent', {type: 'mouseMoved', x, y});
      await send('Input.dispatchMouseEvent', {type: 'mousePressed', x, y, button: 'left', clickCount: 1});
      await send('Input.dispatchMouseEvent', {type: 'mouseReleased', x, y, button: 'left', clickCount: 1}); }
    await sleep(5000);
    const shot = await send('Page.captureScreenshot', {format: 'png'});
    fs.writeFileSync(new URL('./dashboard.png', import.meta.url).pathname, Buffer.from(shot.data, 'base64'));
    console.log('dashboard captured');
    await send('Page.navigate', {url: 'about:blank'}); await sleep(500);
  } catch (e) { console.log('ERR', e.message); }
  ws.close(); process.exit(0);
};
setTimeout(() => { console.log('watchdog'); process.exit(2); }, 90000);
