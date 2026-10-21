const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..'),catalog=JSON.parse(fs.readFileSync(path.join(root,'reports/improved_second/catalog.json')));
(async()=>{const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
try{const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>requests.push(r.url()));
await page.goto(pathToFileURL(path.join(root,'baseline.html')).href);
await page.waitForFunction(()=>document.querySelector('#map').width>1);
assert.equal(await page.evaluate(()=>qualityData.objectives.length),7);
assert.equal(await page.locator('#quality-x option').count(),7);
assert.equal(await page.locator('#quality-y option').count(),7);
await page.selectOption('#quality-x','max_altitude_excursion_m');
await page.selectOption('#quality-y','accumulated_altitude_deviation_m_s');
await page.selectOption('#flight-select','F034');await page.evaluate(()=>setTime(760));
for(const e of catalog.entries){
 await page.selectOption('#alternative-select',e.id);
 assert.deepEqual(await page.evaluate(()=>[selected,time,viewMode]),['F034',760,'final']);
 assert.ok((await page.textContent('#quality-status')).includes('second_pass'));
 assert.ok((await page.textContent('#endpoint-gaps')).includes('Dmax ≥ 150 m; Dtotal ≥ 600 m'));
 assert.ok((await page.textContent('#endpoint-gaps')).includes(`Selected gaps: ${e.endpoint_gaps_m.max_endpoint_deviation_m.toLocaleString('en-US')} m / ${e.endpoint_gaps_m.total_endpoint_deviation_m.toLocaleString('en-US')} m`));
 assert.ok((await page.textContent('#endpoint-gaps')).includes(`Changed aircraft vs reference: ${e.quality.changed_aircraft_count-15}`));
 assert.ok((await page.textContent('#target-excursions')).includes('F004 excursion'));
 assert.equal(await page.locator('#altitude-profile .reference-profile-line').count(),1);
}
const optimal=catalog.entries.find(e=>e.endpoint_gaps_m.max_endpoint_deviation_m===0&&e.endpoint_gaps_m.total_endpoint_deviation_m===0);
if(optimal){await page.selectOption('#alternative-select',optimal.id);assert.ok((await page.textContent('#endpoint-gaps')).includes('Both valid endpoint bounds attained'));}
const groups=await page.evaluate(()=>[...new Set(qualityData.entries.map(e=>e.group))].sort());assert.deepEqual(groups,['first_pass','reference','second_pass']);
for(const e of catalog.earlier_comparisons){
 const actual=await page.evaluate(id=>qualityEntries.get(id).dominated_by.filter(x=>x.startsWith('pass2-')),e.id);
 assert.deepEqual(actual,e.dominated_by_second_pass);
}
if(process.env.SCREENSHOT_DIR)await page.locator('#quality-panel').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'dtl-second-desktop.png')});
await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
const table=page.locator('#quality-metrics').locator('..').locator('..');
await table.evaluate(el=>{el.scrollLeft=el.scrollWidth;});assert.ok(await table.evaluate(el=>el.scrollLeft>0));
await page.selectOption('#alternative-select','reference');await page.evaluate(()=>setTime(330));if(optimal)await page.selectOption('#alternative-select',optimal.id);
assert.deepEqual(await page.evaluate(()=>[selected,time]),['F034',330]);
if(process.env.SCREENSHOT_DIR)await page.locator('#quality-panel').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'dtl-second-mobile.png')});
assert.deepEqual(errors,[]);assert.ok(requests.every(u=>u.startsWith('file:')));
console.log('PASS: three solution generations, all seven objective axes, scenario endpoint bounds/gaps, attained bounds, additional aircraft and targeted excursions, Python dominance, profiles, retained time/selection, mobile table scroll, desktop/mobile offline.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
