// Optional browser verification. Usage is documented in README.md.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const rows = fs.readFileSync(path.join(root, 'flights.csv'), 'utf8').trim().split(/\r?\n/);
const headers = rows.shift().split(',');
const source = rows.map(row => Object.fromEntries(row.split(',').map((v, i) => [headers[i], i ? Number(v) : v])));
const scenario = JSON.parse(fs.readFileSync(path.join(root, 'scenario.json'), 'utf8'));
const near = (actual, expected, epsilon = 1e-7) => assert.ok(Math.abs(actual - expected) < epsilon, `${actual} != ${expected}`);

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1060 } });
    const errors = [], requests = [];
    page.on('pageerror', error => errors.push(String(error)));
    page.on('request', request => requests.push(request.url()));
    await page.goto(pathToFileURL(process.env.HTML_PATH || path.join(root, 'baseline.html')).href);
    await page.waitForFunction(() => document.querySelector('#map').width > 1);
    assert.equal(await page.locator('#flight-select option').count(), 40);
    const initial = await page.evaluate(() => ({ flights: DATA.flights, scenario: DATA.scenario, positions: flights.map(f => positionAt(f, 0)) }));
    assert.deepEqual(initial.flights, source);
    assert.deepEqual(initial.scenario, scenario);
    source.forEach((f, i) => { near(initial.positions[i].x, f.x_m); near(initial.positions[i].y, f.y_m); near(initial.positions[i].z, f.alt_m); });

    for (const t of [1200, 600, 100, 0, 833.3333333333334]) {
      await page.locator('#time-slider').evaluate((el, t) => { el.value = String(t); el.dispatchEvent(new Event('input', { bubbles: true })); }, t);
      const snapshot = await page.evaluate(() => ({ time, positions: flights.map(f => positionAt(f, time)), drone: positionAt(threat, time), count: flights.length }));
      // A range input quantizes to its 0.01 s step; use its actual time.
      assert.equal(snapshot.count, 40);
      source.forEach((f, i) => { near(snapshot.positions[i].x, f.x_m + f.vx_mps * snapshot.time); near(snapshot.positions[i].y, f.y_m + f.vy_mps * snapshot.time); near(snapshot.positions[i].z, f.alt_m + f.vz_mps * snapshot.time); });
      near(snapshot.drone.x, scenario.hostile_object.x_m + scenario.hostile_object.vx_mps * snapshot.time);
      near(snapshot.drone.y, scenario.hostile_object.y_m + scenario.hostile_object.vy_mps * snapshot.time);
      near(snapshot.drone.z, 4000);
    }
    const pass = await page.evaluate(() => positionAt(threat, 2500 / 3));
    near(pass.x, scenario.target.x_m); near(pass.y, scenario.target.y_m); near(pass.z, 4000);
    await page.evaluate(() => setTime(1200));
    const end = await page.evaluate(() => ({ count: flights.length, outside: flights.filter(f => outside(positionAt(f, time))).length, drone: positionAt(threat, time) }));
    assert.ok(end.outside > 0); assert.equal(end.count, 40); near(end.drone.x, 55200); near(end.drone.y, -36400);
    assert.equal(await page.locator('#clock').textContent(), '20:00');

    // Verify drawTrail actually draws from the source to the current time, including rewind.
    for (const t of [1200, 300, 0]) {
      const drawn = await page.evaluate(t => {
        setTime(t);
        const commands = [], move = ctx.moveTo, lineTo = ctx.lineTo;
        ctx.moveTo = (x, y) => commands.push(['move', x, y]); ctx.lineTo = (x, y) => commands.push(['line', x, y]);
        try { drawTrail(flights[0]); } finally { ctx.moveTo = move; ctx.lineTo = lineTo; }
        return { commands, start: screen(positionAt(flights[0], 0)), end: screen(positionAt(flights[0], time)) };
      }, t);
      near(drawn.commands[0][1], drawn.start.x); near(drawn.commands[0][2], drawn.start.y);
      near(drawn.commands[1][1], drawn.end.x); near(drawn.commands[1][2], drawn.end.y);
    }

    await page.locator('#flight-select').selectOption('F040');
    assert.equal(await page.locator('#selection-title').textContent(), 'F040');
    const distances = await page.evaluate(() => { const f=flightById.get(selected), p=positionAt(f,time), d=positionAt(threat,time);return {drone:Math.hypot(p.x-d.x,p.y-d.y,p.z-d.z)/1000,target:Math.hypot(p.x-target.x_m,p.y-target.y_m,p.z-rules.zones.target.center_alt_m)/1000}; });
    const f = source[39], d = scenario.hostile_object;
    near(distances.drone, Math.hypot(f.x_m-d.x_m,f.y_m-d.y_m,f.alt_m-d.alt_m)/1000);
    near(distances.target, Math.hypot(f.x_m-scenario.target.x_m,f.y_m-scenario.target.y_m,f.alt_m)/1000);
    const targetDetail = await page.evaluate(() => [...document.querySelectorAll('#details dt')].find(el=>el.textContent==='До цели (3D)').nextElementSibling.textContent);
    const displayedTarget = Number(targetDetail.replace(/\s|км/g,'').replace(',','.'));
    near(displayedTarget, distances.target, 0.00051);
    await page.locator('#labels').uncheck(); await page.locator('#trails').uncheck();
    await page.locator('#labels').check(); await page.locator('#trails').check();
    await page.locator('#fit-all').click();
    assert.ok(await page.evaluate(() => [...flights,threat].every(f=>[0,DURATION].every(t=>{const s=screen(positionAt(f,t));return s.x>10&&s.x<width-10&&s.y>10&&s.y<height-10;}))));
    const scale = await page.evaluate(() => view.scale);
    await page.locator('#zoom-in').click(); assert.ok(await page.evaluate(() => view.scale) > scale);
    const beforePan = await page.evaluate(() => view.x), rect = await page.locator('#map').boundingBox();
    await page.mouse.move(rect.x+200, rect.y+200); await page.mouse.down(); await page.mouse.move(rect.x+270, rect.y+220); await page.mouse.up();
    assert.notEqual(await page.evaluate(() => view.x), beforePan);
    await page.locator('#fit-area').click();
    const marker = await page.evaluate(() => screen(positionAt(flights[0],time)));
    await page.mouse.click(rect.x+marker.x,rect.y+marker.y);
    assert.equal(await page.locator('#flight-select').inputValue(), 'F001');

    // Real UI pause and speed controls; use a virtual clock for deterministic timing.
    await page.clock.install();
    for (const multiplier of [1,10,30,60]) {
      await page.locator('#reset').click(); await page.locator('#speed').selectOption(String(multiplier)); await page.locator('#play').click();
      await page.clock.runFor(1000);
      const elapsed = await page.evaluate(() => time);
      assert.ok(Math.abs(elapsed-multiplier)<multiplier*.04, `speed ${multiplier}: ${elapsed}`);
      await page.locator('#play').click(); const paused = await page.evaluate(() => time);
      await page.clock.runFor(1000); near(await page.evaluate(() => time), paused);
    }
    // The clock formula is independent of how often frames arrive.
    const cadences = await page.evaluate(() => {
      const simulate = ticks => {time=0;playing=true;speed=30;anchorTime=0;anchorWall=100;for(const tick of ticks)updateClock(tick);return positionAt(flights[0],time);};
      const a=simulate([10100]),b=simulate([200,500,1000,2500,7000,10100]);playing=false;updatePlay();return [a,b];
    });
    assert.deepEqual(cadences[0], cadences[1]);
    await page.locator('#reset').click(); await page.locator('#speed').selectOption('60');
    await page.evaluate(() => setTime(1199)); await page.locator('#play').click(); await page.clock.runFor(1000);
    assert.deepEqual(await page.evaluate(() => ({time,playing})),{time:1200,playing:false});
    await page.locator('#reset').click(); await page.locator('#fit-all').click(); await page.evaluate(() => setTime(1200));
    if (process.env.SCREENSHOT_PATH) await page.screenshot({path:process.env.SCREENSHOT_PATH,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth<=window.innerWidth));
    assert.equal(errors.length, 0, errors.join('\n'));
    assert.ok(requests.every(url => url.startsWith('file:')), requests.join('\n'));
    console.log(`PASS: 40 flights, source data, t=0/1200, rewind/trails, pause, 1/10/30/60×, frame independence, bounds (${end.outside} flights outside at t=1200), drone target passage, selection/distances, fit/zoom/pan, mobile, offline, no JS errors.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
