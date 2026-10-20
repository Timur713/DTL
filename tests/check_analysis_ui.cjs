// Usage: PLAYWRIGHT_MODULE=... HTML_PATH=/path/to/generated.html node tests/check_analysis_ui.cjs
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1060}}),errors=[],requests=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>requests.push(r.url()));
 await page.goto(pathToFileURL(process.env.HTML_PATH||path.resolve(__dirname,'../baseline.html')).href);
 await page.waitForFunction(()=>document.querySelector('#map').width>1);
 const runs=await page.evaluate(()=>DATA.analysis.runs.map(r=>({id:r.id,profile:r.profile_id,mode:r.mode_id,variant:r.variant_id,summary:r.summary})));
 assert.equal(runs.length,20);
 for(const run of runs){
  await page.selectOption('#profile-select',run.profile);await page.selectOption('#mode-select',run.mode);await page.selectOption('#variant-select',run.variant);
  assert.ok((await page.textContent('#run-metadata')).includes(run.id));
  assert.deepEqual(await page.locator('#analysis-summary strong').allTextContents(),[run.summary.event_count,run.summary.aircraft_pair_count,run.summary.affected_flight_count,run.summary.initial_event_count].map(String));
  assert.equal(await page.locator('.event-row').count(),run.summary.event_count);
  assert.equal(await page.locator('#event-marks button').count(),run.summary.event_count);
 }
 await page.selectOption('#profile-select','metric');await page.selectOption('#mode-select','nominal');await page.selectOption('#variant-select','base');
 // Target sphere: altitude controls the section, while event states come from Python.
 await page.selectOption('#flight-select','F020');await page.evaluate(()=>setTime(9.603));
 assert.equal(await page.evaluate(()=>zoneGeometry().targetSection),0);
 assert.ok((await page.textContent('#zone-note')).includes('Цель: на этой высоте зоны нет'));
 assert.ok((await page.textContent('#thresholds')).includes('Цель: 3D <'));
 assert.deepEqual(await page.evaluate(()=>activeRun.events.filter(e=>e.type==='aircraft_target').flatMap(e=>e.flight_ids).sort()),['F012','F013','F023','F026']);
 assert.ok(await page.evaluate(()=>activeRun.events.some(e=>e.type==='aircraft_aircraft'&&e.flight_ids.includes('F020'))));
 assert.deepEqual(await page.evaluate(()=>[3000,5000,8100].map(z=>zoneGeometry(0,z).targetSection)),[4000,0,0]);
 // Inspect the actual canvas calls: at z=3000 draw the 4000 m section, not a 5000 m disk.
 await page.selectOption('#flight-select','F040');await page.evaluate(()=>setTime(0));
 const drawnTarget=await page.evaluate(()=>{const radii=[],original=ctx.arc;ctx.arc=function(x,y,r,...rest){radii.push(r/view.scale);return original.call(this,x,y,r,...rest);};try{drawZones();}finally{ctx.arc=original;}return radii[0];});
 assert.ok(Math.abs(drawnTarget-4000)<1e-7);
 await page.selectOption('#event-type','aircraft_target');await page.locator('.event-row').first().click();
 assert.equal(await page.evaluate(()=>selectedEvent.rule_id),'target_sphere');
 assert.equal(await page.evaluate(()=>playing),false);
 assert.ok((await page.textContent('#event-details')).includes('Расстояние 3D'));
 assert.ok(await page.evaluate(()=>zoneGeometry().targetSection>0));
 await page.selectOption('#event-type','all');
 // Reset selection before testing automatic halos without a selected event.
 await page.evaluate(()=>chooseRun());
 const e=await page.evaluate(()=>activeRun.events.find(e=>!e.start_inclusive&&e.start_s>0&&e.end_s>e.start_s));assert.ok(e,'needs a future open interval');
 // Strict endpoints are evaluated directly from saved flags, with no geometry epsilon.
 // Current halos appear from saved intervals without selecting any event.
 await page.evaluate(t=>setTime(t),e.representative_s);
 const halo=await page.evaluate(()=>{const commands=[],arc=ctx.arc;ctx.arc=function(...args){commands.push(args);return arc.apply(this,args);};try{render();}finally{ctx.arc=arc;}return {selected:selectedEvent,ids:[...currentParticipants],expected:[...new Set(activeRun.events.filter(e=>eventStatus(e)==='current').flatMap(e=>e.participants))],rings:commands.filter(args=>args[2]===20).length};});
 assert.equal(halo.selected,null);assert.deepEqual(halo.ids,halo.expected);assert.ok(e.participants.every(id=>halo.ids.includes(id)));assert.ok(halo.rings>0);
 const statuses=await page.evaluate(e=>[eventStatus(e,e.start_s),eventStatus(e,e.representative_s),eventStatus(e,e.end_s)],e);
 assert.deepEqual(statuses,['future','current',e.end_inclusive?'current':'past']);
 for(const t of [e.start_s,e.representative_s,e.end_s]){
  await page.evaluate(t=>setTime(t),t);
  const status=await page.evaluate(id=>eventStatus(activeRun.events.find(e=>e.id===id)),e.id);
  const row=page.locator('.event-row').filter({hasText:e.participants.join(' / ')}).first();
  // Every row's displayed state must follow its own interval, including endpoints.
  assert.ok(await page.evaluate(()=>[...document.querySelectorAll('.event-row')].every(b=>b.dataset.status===eventStatus(activeRun.events.find(e=>e.id===b.dataset.eventId)))));
  assert.ok(['future','current','past'].includes(status));
 }
 await page.evaluate(()=>setTime(0));await page.click('#play');
 await page.locator('#event-marks button').first().click();
 assert.equal(await page.evaluate(()=>playing),false);
 assert.equal(await page.evaluate(()=>time),await page.evaluate(()=>selectedEvent.representative_s));
 assert.equal(await page.evaluate(()=>eventStatus(selectedEvent)),'current');
 assert.ok(await page.evaluate(()=>participantPoints(selectedEvent).every(p=>{const s=screen(p);return s.x>20&&s.x<width-20&&s.y>20&&s.y<height-20;})));
 assert.ok((await page.textContent('#event-details')).includes(e.rule_id));
 assert.ok((await page.textContent('#event-details')).includes('Номинальные центры'));
 assert.ok(await page.evaluate(()=>eventParticipants.size===selectedEvent.participants.length));
 await page.locator('.event-row').first().click();
 assert.equal(await page.evaluate(()=>playing),false);
 assert.equal(await page.evaluate(()=>time),await page.evaluate(()=>selectedEvent.representative_s));
 assert.deepEqual(await page.evaluate(()=>{const e={start_s:0,end_s:1200,start_inclusive:true,end_inclusive:true};return [eventStatus(e,0),eventStatus(e,1200)];}),['current','current']);
 for(const type of ['aircraft_aircraft','aircraft_threat','aircraft_target','altitude','motion']){
  await page.selectOption('#event-type',type);
  assert.equal(await page.locator('.event-row').count(),await page.evaluate(t=>activeRun.events.filter(e=>e.type===t).length,type));
 }
 await page.selectOption('#event-type','all');
 const flight=await page.evaluate(()=>flights[0].flight_id);await page.selectOption('#event-flight',flight);
 assert.equal(await page.locator('.event-row').count(),await page.evaluate(id=>activeRun.events.filter(e=>e.flight_ids.includes(id)).length,flight));
 await page.selectOption('#event-flight','all');
 for(const status of ['current','future','past']){await page.selectOption('#event-status',status);assert.equal(await page.locator('.event-row').count(),await page.evaluate(s=>activeRun.events.filter(e=>eventStatus(e)===s).length,status));}
 await page.selectOption('#event-status','all');await page.selectOption('#mode-select','bounded_stress');
 const geometry=await page.evaluate(()=>{const a=zoneGeometry(0),b=zoneGeometry(1200),c=zoneGeometry(0),q=activeRun.thresholds;return {a,b,c,q,high:zoneGeometry(0,positionAt(threat,0).z+a.threatRadius).threatSection};});
 assert.deepEqual(geometry.a,geometry.c);assert.equal(geometry.high,0);
 assert.equal(geometry.a.threatRadius,geometry.q.threat_radius_m+240);
 assert.equal(geometry.b.threatRadius,geometry.q.threat_radius_m+2880);
 assert.equal(geometry.a.targetRadius,geometry.q.target_radius_m+120);
 assert.equal(geometry.b.targetRadius,geometry.q.target_radius_m+1440);
 const targetSections=await page.evaluate(()=>{const radius=zoneGeometry(1200).targetRadius,alt=activeRun.thresholds.target_alt_m;return {high:zoneGeometry(1200,alt+radius).targetSection,low:zoneGeometry(1200,alt+3000).targetSection};});
 assert.equal(targetSections.high,0);
 assert.ok(Math.abs(targetSections.low-Math.sqrt(6440**2-3000**2))<1e-7);
 assert.ok((await page.textContent('#nominal-comparison')).includes('не складываются'));
 for(const t of [0,1200,0]){await page.evaluate(t=>setTime(t),t);assert.ok((await page.textContent('#uncertainty')).includes(t===1200?'1 300':'100'));}
 // Missing optional metric fields and arbitrary IDs remain safe text.
 await page.evaluate(()=>{const base=activeRun.events[0];jumpToEvent({...base,id:'<img src=x onerror=alert(1)>',metrics:{},thresholds:{}});});
 assert.equal(await page.locator('#event-details img').count(),0);
 assert.ok((await page.textContent('#event-metadata')).includes('<img src=x'));
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(100);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 if(process.env.SCREENSHOT_PATH)await page.screenshot({path:process.env.SCREENSHOT_PATH,fullPage:true});
 assert.equal(errors.length,0,errors.join('\n'));assert.ok(requests.every(u=>u.startsWith('file:')),requests.join('\n'));
 console.log('PASS: 20 runs, JSON counts, strict intervals, timeline/list jump and pause, participant fit, filters, stress zones/rewind, optional metrics, safe IDs, mobile, offline, no JS errors.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
