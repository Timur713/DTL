// Offline integration checks for saved comparison, profiles and accepted-history replay.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..');
const replay=JSON.parse(fs.readFileSync(path.join(root,'reports/replay.json'),'utf8'));
const lines=fs.readFileSync(path.join(root,'reports/planned/trajectories.csv'),'utf8').trim().split(/\r?\n/);
const keys=lines.shift().split(',');
const references=lines.map(row=>Object.fromEntries(row.split(',').map((v,i)=>[keys[i],keys[i]==='flight_id'?v:Number(v)]))).filter(r=>[0,100,230,400,833,1200].includes(r.time_s));
const near=(a,b,e=1e-7)=>assert.ok(Math.abs(a-b)<e,`${a} != ${b}`);
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1060}}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>requests.push(r.url()));
  await page.goto(pathToFileURL(process.env.HTML_PATH||path.join(root,'baseline.html')).href);
  await page.waitForFunction(()=>document.querySelector('#map').width>1);
  assert.equal(await page.locator('#baseline-total').textContent(),'12');
  assert.equal(await page.locator('#final-total').textContent(),'0');
  assert.equal(await page.locator('#final-unresolved').textContent(),'0');
  assert.equal(await page.locator('#search-steps button').count(),22);
  assert.equal(await page.locator('#changed-aircraft tr').count(),15);
  assert.equal(await page.locator('#changed-aircraft .terminal-row').count(),5);
  assert.ok(await page.evaluate(()=>planning.final_matches_saved));
  await page.locator('#flight-select').selectOption('F020');await page.evaluate(()=>setTime(230));
  assert.equal(await page.evaluate(()=>positionAt(flightById.get('F020'),time).z),8100);
  await page.click('#view-final');
  assert.equal(await page.evaluate(()=>time),230);
  assert.equal(await page.locator('#flight-select').inputValue(),'F020');
  assert.equal(await page.evaluate(()=>positionAt(flightById.get('F020'),time).z),8300);
  assert.equal(await page.evaluate(()=>currentVz(flightById.get('F020'),time)),10);
  assert.equal(await page.evaluate(()=>activeRun.events.length),0);
  assert.equal(await page.evaluate(()=>currentParticipants.size),0);
  assert.ok((await page.textContent('#view-status')).includes('independently verified'));
  assert.ok(await page.locator('#view-status').evaluate(el=>el.classList.contains('good')));
  for(const id of ['profile-select','mode-select','variant-select'])assert.ok(await page.locator('#'+id).isDisabled());
  for(const id of ['altitude-profile','speed-profile']){
   assert.equal(await page.locator('#'+id+' .baseline-profile-line').count(),1);
   assert.equal(await page.locator('#'+id+' .planned-profile-line').count(),1);
   assert.equal(await page.locator('#'+id+' .simulation-cursor').getAttribute('data-time'),'230');
  }
  assert.ok((await page.textContent('#profile-stats')).includes('Maximum altitude deviation: 300 m'));
  assert.ok((await page.textContent('#profile-stats')).includes('Remaining destination distance: 0 m'));
  assert.ok((await page.textContent('#profile-now')).includes('10.00 m/s'));
  assert.equal(await page.locator('#phase-list .current-phase').count(),1);
  assert.ok((await page.textContent('#details')).includes('10.00 m/s'));
  // Compare all aircraft with the independently prepared Python CSV at six times.
  for(const t of [0,100,230,400,833,1200]){
   await page.evaluate(t=>setTime(t),t);
   const actual=await page.evaluate(()=>flights.map(f=>({flight_id:f.flight_id,...positionAt(f,time),vz:currentVz(f,time)})));
   for(const a of actual){const expected=references.find(r=>r.flight_id===a.flight_id&&r.time_s===t);near(a.x,expected.x_m);near(a.y,expected.y_m);near(a.z,expected.alt_m);near(a.vz,expected.vz_mps);}
  }
  // Zones follow the planned altitude; horizontal coordinates remain unchanged.
  await page.locator('#flight-select').selectOption('F034');
  assert.equal(await page.evaluate(()=>zoneGeometry().targetSection),0);
  assert.equal(await page.evaluate(()=>zoneGeometry().threatSection),0);
  assert.ok((await page.textContent('#profile-stats')).includes('Remaining destination distance: 6,300 m'));
  await page.click('#view-baseline');
  assert.ok(await page.evaluate(()=>zoneGeometry().targetSection>0));
  const selectedNominal=await page.evaluate(()=>activeRun.id);assert.equal(selectedNominal,'metric__nominal__base');
  // Baseline alternative settings are restored when leaving the fixed planned scope.
  await page.selectOption('#profile-select','feet_reference');await page.selectOption('#mode-select','bounded_stress');await page.selectOption('#variant-select','threat_10000');
  const alternative=await page.evaluate(()=>activeRun.id);
  assert.ok(await page.locator('#profile-content').isHidden());
  await page.click('#view-final');assert.equal(await page.locator('#mode-select').inputValue(),'nominal');
  await page.click('#view-baseline');assert.equal(await page.evaluate(()=>activeRun.id),alternative);
  await page.click('#view-final');
  // Simulation time and search iteration are orthogonal, including when paused.
  await page.evaluate(()=>setTime(555.25));
  for(const step of replay.steps){
   await page.locator(`#search-steps button[data-step="${step.index}"]`).click();
   assert.equal(await page.evaluate(()=>time),555.25);
   assert.equal(await page.evaluate(()=>playing),false);
   assert.equal(await page.evaluate(()=>replayStep),step.index);
   assert.equal(await page.evaluate(()=>activeRun.events.length),step.violation_count);
   assert.equal(await page.locator('.event-row').count(),step.violation_count);
   assert.equal(await page.locator('#event-marks button').count(),step.violation_count);
   assert.ok((await page.textContent('#repair-details')).includes(`${step.zone_count} / ${step.pair_count}`));
   assert.ok((await page.textContent('#view-status')).includes('Search candidate'));
   assert.ok(!(await page.locator('#view-status').evaluate(el=>el.classList.contains('good'))));
   if(step.repair){assert.equal(await page.locator('#flight-select').inputValue(),step.repair.flight_id);assert.ok((await page.textContent('#repair-details')).replaceAll(',','').includes(String(step.repair.offset_m)));}
  }
  // Step 20 is an actual equal-count move; its replacement pair is precomputed.
  await page.locator('#search-steps button[data-step="20"]').click();
  assert.ok((await page.textContent('#step-explanation')).includes('Equal-count'));
  assert.ok((await page.textContent('#repair-details')).includes('0 / 1'));
  assert.deepEqual(await page.evaluate(()=>activeRun.events[0].participants),['F004','F034']);
  const halo=await page.evaluate(()=>{const radii=[],arc=ctx.arc;ctx.arc=function(x,y,r,...rest){radii.push(r);return arc.call(this,x,y,r,...rest)};try{drawEventHalo({x:100,y:100},'F004')}finally{ctx.arc=arc}return radii;});
  assert.ok(halo.includes(31));
  await page.locator('.event-row').first().click();
  assert.equal(await page.evaluate(()=>time),await page.evaluate(()=>selectedEvent.representative_s));
  assert.ok(await page.evaluate(()=>currentParticipants.has('F004')&&currentParticipants.has('F034')));
  // Seeking through an iteration keeps that iteration's schedule, including rewind.
  await page.evaluate(()=>setTime(0));assert.equal(await page.evaluate(()=>replayStep),20);
  const value=await page.evaluate(()=>verticalAt(versionFor('F004'),400).z);
  await page.evaluate(()=>setTime(1200));await page.evaluate(()=>setTime(400));
  assert.equal(await page.evaluate(()=>verticalAt(versionFor('F004'),400).z),value);
  await page.evaluate(()=>setTime(230));
  const profile=page.locator('#altitude-profile');await profile.focus();await page.keyboard.press('ArrowRight');near(await page.evaluate(()=>time),240);
  assert.equal(await page.evaluate(()=>replayStep),20);
  // Table includes excursions that return and signed terminal offsets for all 15 IDs.
  for(const row of replay.changed_aircraft){
   const values=await page.locator(`#changed-aircraft tr[data-flight-id="${row.flight_id}"] td`).allTextContents();
   assert.equal(Number(values[1].replaceAll(',','')),row.max_altitude_deviation_m);
   assert.equal(Number(values[2].replaceAll(',','')),row.largest_accepted_deviation_m);
   assert.equal(Number(values[3].replaceAll(',','')),row.terminal_altitude_offset_m);
   assert.equal(Number(values[4].replaceAll(',','')),row.remaining_destination_distance_m);
  }
  await page.locator('#changed-aircraft tr[data-flight-id="F034"] button').click();
  assert.equal(await page.evaluate(()=>viewMode),'final');assert.equal(await page.locator('#flight-select').inputValue(),'F034');
  // Playback remains operational in the final plan; search selection pauses without seeking.
  await page.clock.install();await page.locator('#reset').click();await page.selectOption('#speed','60');await page.click('#play');await page.clock.runFor(1000);
  assert.ok(await page.evaluate(()=>time>58&&time<=60));
  await page.click('#play');const paused=await page.evaluate(()=>time);await page.clock.runFor(500);near(await page.evaluate(()=>time),paused);
  await page.click('#view-baseline');near(await page.evaluate(()=>time),paused);await page.click('#view-final');near(await page.evaluate(()=>time),paused);
  if(process.env.SCREENSHOT_DIR){await page.evaluate(()=>setTime(400));await page.locator('#profiles-panel').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'dtl-profiles-desktop.png')});await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'dtl-comparison-desktop.png'),fullPage:true});}
  await page.setViewportSize({width:390,height:844});await page.clock.runFor(200);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('#search-steps button[data-step="20"]').click();await page.evaluate(()=>setTime(420));
  assert.equal(await page.locator('#altitude-profile').getAttribute('data-flight-id'),'F004');
  assert.ok(await page.locator('#changed-aircraft').isVisible());
  assert.ok(await page.evaluate(()=>document.querySelector('#altitude-profile').getBoundingClientRect().width<390));
  if(process.env.SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'dtl-comparison-mobile.png'),fullPage:true});
  assert.equal(errors.length,0,errors.join('\n'));assert.ok(requests.every(u=>u.startsWith('file:')),requests.join('\n'));
  console.log('PASS: 12→0 comparison, 40 aircraft vs Python CSV, synchronized profiles/phases, all 22 replay steps, step-20 plateau, selection/halos, zones, locked nominal scope, baseline restoration, playback/seek, table, desktop/mobile and offline.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
