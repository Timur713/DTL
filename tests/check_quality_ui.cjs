const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..'),catalog=JSON.parse(fs.readFileSync(path.join(root,'reports/improved/catalog.json'),'utf8'));
const second=JSON.parse(fs.readFileSync(path.join(root,'reports/improved_second/catalog.json'),'utf8'));catalog.entries.push(...second.entries);
const near=(a,b,e=1e-7)=>assert.ok(Math.abs(a-b)<e,`${a} != ${b}`);
(async()=>{const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
try{const page=await browser.newPage({viewport:{width:1440,height:1060}}),errors=[],requests=[];page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>requests.push(r.url()));
await page.goto(pathToFileURL(process.env.HTML_PATH||path.join(root,'baseline.html')).href);await page.waitForFunction(()=>document.querySelector('#map').width>1);
assert.equal(await page.locator('#alternative-select option').count(),catalog.entries.length);
assert.equal(await page.locator('#alternative-select').inputValue(),'reference');
assert.equal(await page.locator('#quality-solutions tr').count(),catalog.entries.length);
assert.ok((await page.textContent('#quality-panel')).includes('not airport arrival'));
assert.equal(await page.locator('#quality-metrics tr').count(),7);
await page.selectOption('#flight-select','F034');await page.evaluate(()=>setTime(1100));
const values=async()=>page.evaluate(()=>({selected,time,playing,mode:viewMode,alt:selectedAlternative,z:positionAt(flightById.get(selected),time).z}));
for(const entry of catalog.entries){
 await page.selectOption('#alternative-select',entry.id);const state=await values();assert.equal(state.selected,'F034');assert.equal(state.time,1100);assert.equal(state.mode,'final');assert.equal(state.alt,entry.id);
 assert.ok((await page.textContent('#view-status')).includes('verified'));assert.equal(await page.evaluate(()=>activeRun.events.length),0);
 assert.equal(await page.evaluate(()=>currentParticipants.size),0);
 assert.ok(await page.locator('#mode-select').isDisabled());assert.equal(await page.locator('#mode-select').inputValue(),'nominal');
 for(const [key,value] of Object.entries(entry.differences_from_reference)){
  const cells=await page.locator(`#quality-metrics tr[data-metric="${key}"] td`).allTextContents();
  near(Number(cells[2].replaceAll(',','')),entry.quality[key],.00051);near(Number(cells[3].replaceAll(',','')),value,.00051);
 }
 assert.ok((await page.textContent('#experimental-score')).includes(entry.experimental_J.value.toLocaleString('en-US',{minimumFractionDigits:6,maximumFractionDigits:6})));
 if(!entry.is_reference){assert.equal(await page.locator('#altitude-profile .reference-profile-line').count(),1);assert.equal(await page.locator('#speed-profile .reference-profile-line').count(),1);}
 const file=entry.is_reference?path.join(root,'reports/planned/segments.json'):path.join(root,'reports',entry.group==='second_pass'?'improved_second':'improved',entry.segments_file);
 const definitions=JSON.parse(fs.readFileSync(file,'utf8')).trajectories;
 for(const time of [0,550,850,1200]){
  await page.evaluate(t=>setTime(t),time);
  const actual=await page.evaluate(()=>flights.map(f=>({id:f.flight_id,z:positionAt(f,time).z,vz:currentVz(f,time)})));
  for(const row of actual){const d=definitions.find(d=>d.flight_id===row.id);let elapsed=0,z=d.initial_state.alt_m,vz=d.initial_state.vz_mps;for(const seg of d.segments){const dt=Math.min(seg.duration_s,Math.max(0,time-elapsed));z+=vz*dt+seg.az_mps2*dt*dt/2;vz+=seg.az_mps2*dt;elapsed+=dt;if(elapsed>=time)break;}near(row.z,z);near(row.vz,vz);if(time===1200)near(row.vz,0);}
 }
 await page.evaluate(()=>setTime(1100));
}
const best=catalog.entries.filter(e=>!e.is_reference).sort((a,b)=>a.quality.max_endpoint_deviation_m-b.quality.max_endpoint_deviation_m||a.quality.total_endpoint_deviation_m-b.quality.total_endpoint_deviation_m)[0];
await page.selectOption('#alternative-select',best.id);assert.ok((await values()).z<9900);
await page.selectOption('#quality-x','changed_aircraft_count');await page.selectOption('#quality-y','reversal_count');
assert.equal(await page.locator('#quality-scatter circle').count(),catalog.entries.length);
await page.locator('#quality-scatter circle[data-solution="reference"]').focus();await page.locator('#quality-scatter circle[data-solution="reference"]').press('Enter');assert.equal(await page.locator('#alternative-select').inputValue(),'reference');
near((await values()).z,9900);
await page.selectOption('#alternative-select',best.id);
await page.click('#view-baseline');assert.ok(await page.evaluate(()=>selectedAlternative!=='reference'));await page.selectOption('#mode-select','bounded_stress');assert.ok(await page.locator('#profile-content').isHidden());
await page.click('#view-final');assert.equal(await page.locator('#mode-select').inputValue(),'nominal');
await page.locator('#search-steps button[data-step="20"]').click();assert.equal(await page.evaluate(()=>viewMode),'replay');assert.ok((await page.textContent('#quality-status')).includes('reference search replay'));assert.ok(!(await page.locator('#view-status').evaluate(el=>el.classList.contains('good'))));
await page.selectOption('#alternative-select',best.id);assert.equal(await page.evaluate(()=>viewMode),'final');
await page.clock.install();await page.selectOption('#speed','30');await page.evaluate(()=>setTime(100));await page.click('#play');await page.clock.runFor(1000);
const switched=await page.evaluate(()=>{const before=time;selectAlternative('reference');return {before,after:time,playing};});assert.equal(switched.playing,true);near(switched.after,switched.before);await page.click('#play');
if(process.env.SCREENSHOT_DIR){await page.selectOption('#alternative-select',best.id);await page.locator('#quality-panel').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'dtl-quality-desktop.png')});}
await page.setViewportSize({width:390,height:844});await page.clock.runFor(100);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
await page.selectOption('#alternative-select',best.id);assert.equal(await page.locator('#altitude-profile .reference-profile-line').count(),1);
if(process.env.SCREENSHOT_DIR)await page.locator('#quality-panel').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'dtl-quality-mobile.png')});
assert.equal(errors.length,0,errors.join('\n'));assert.ok(requests.every(u=>u.startsWith('file:')),requests.join('\n'));
console.log('PASS: reference/alternatives, seven objectives and Python deltas, scores, all 40 saved motions/zero terminal vz, reference overlays, verification, time/selection/playback retention, scatter, replay distinction, nominal scope, desktop/mobile and offline.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
