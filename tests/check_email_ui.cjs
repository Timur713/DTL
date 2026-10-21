// The compact, six-file package must tell the story and preserve actual motion.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..'),directory=process.env.EMAIL_DIR||path.join(root,'email_delivery');
const document=JSON.parse(fs.readFileSync(path.join(directory,'segments.json'),'utf8'));
const report=JSON.parse(fs.readFileSync(path.join(directory,'verification.json'),'utf8'));
const lines=fs.readFileSync(path.join(directory,'trajectories.csv'),'utf8').trim().split(/\r?\n/),keys=lines.shift().split(',');
const references=lines.map(row=>Object.fromEntries(row.split(',').map((v,i)=>[keys[i],['flight_id','time_exact_s'].includes(keys[i])?v:Number(v)]))).filter(r=>[0,100,230,440,600,1200].includes(r.time_s));
const near=(a,b,e=1e-7)=>assert.ok(Math.abs(a-b)<e,`${a} != ${b}`);
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>requests.push(r.url()));
  await page.goto(pathToFileURL(path.join(directory,'START_HERE.html')).href);
  await page.waitForFunction(()=>document.querySelector('#map').width>1&&!!profilePlot);
  assert.equal(await page.evaluate(()=>mode),'plan');
  assert.equal(await page.locator('#flight-select option').count(),40);
  assert.equal(await page.evaluate(()=>DATA.verification.verified_safe),true);
  assert.deepEqual(await page.evaluate(()=>DATA.verification),report.certificate);
  assert.deepEqual(await page.evaluate(()=>DATA.quality),report.quality);
  assert.equal(await page.locator('#github-link').getAttribute('href'),'https://github.com/Timur713/DTL');
  assert.ok((await page.textContent('#current-state')).includes('0 violations over 20 minutes'));
  assert.ok((await page.textContent('#map-caption')).includes('all 40 simulated'));
  assert.equal(await page.locator('#event-track button').count(),12);
  assert.equal(await page.locator('#profile .safe-profile').count(),1);
  assert.equal(await page.locator('#profile .original-profile').count(),1);
  // A first-time reviewer finds the tour before the map and can compare without
  // losing the moment. Both live altitude readings remain visible in either mode.
  assert.ok(await page.evaluate(()=>document.querySelector('.tour').getBoundingClientRect().top<document.querySelector('.workspace').getBoundingClientRect().top));
  const initial=await page.evaluate(()=>({time,selected,original:originalAt(byId.get(selected),time).z,planned:plannedAt(byId.get(selected),time).z}));
  const heightPlan=await page.evaluate(()=>({point:screen(positionAt(byId.get(selected))),camera:{...camera}}));
  const readAltitude=async id=>Number((await page.textContent(id)).replace(/[^\d.-]/g,''));
  near(await readAltitude('#original-altitude'),initial.original,.5);
  near(await readAltitude('#planned-altitude'),initial.planned,.5);
  await page.click('#compare-story');
  assert.equal(await page.evaluate(()=>mode),'original');
  const heightOriginal=await page.evaluate(()=>({point:screen(positionAt(byId.get(selected))),camera:{...camera}}));
  assert.deepEqual(heightOriginal.camera,heightPlan.camera);
  near(heightOriginal.point.x,heightPlan.point.x);
  near(heightOriginal.point.y-heightPlan.point.y,3*(initial.planned-initial.original)*heightPlan.camera.scale);
  assert.ok(Math.abs(heightOriginal.point.y-heightPlan.point.y)>20);
  assert.deepEqual(await page.evaluate(()=>({time,selected})),{time:initial.time,selected:initial.selected});
  assert.ok(await page.locator('#original-reading').evaluate(e=>e.classList.contains('selected-reading')));
  near(await readAltitude('#planned-altitude'),initial.planned,.5);
  await page.click('#compare-story');assert.equal(await page.evaluate(()=>mode),'plan');
  await page.click('#view-top');
  const topPlan=await page.evaluate(()=>screen(positionAt(byId.get(selected))));
  await page.click('#mode-original');
  const topOriginal=await page.evaluate(()=>screen(positionAt(byId.get(selected))));
  near(topOriginal.x,topPlan.x);near(topOriginal.y,topPlan.y);
  await page.click('#mode-plan');await page.click('#view-height');
  assert.ok((await page.textContent('#maneuver-cost')).includes('6,150 m'));
  // Every plane, six times, matches the independent Python trajectory output.
  for(const t of [0,100,230,440,600,1200]){
   await page.evaluate(t=>seek(t),t);
   const actual=await page.evaluate(()=>flights.map(f=>({id:f.flight_id,...positionAt(f)})));
   assert.equal(actual.length,40);
   for(const a of actual){const expected=references.find(r=>r.flight_id===a.id&&r.time_s===t);near(a.x,expected.x_m);near(a.y,expected.y_m);near(a.z,expected.alt_m);near(a.vz,expected.vz_mps);}
   const focus=references.find(r=>r.flight_id===initial.selected&&r.time_s===t);
   near(await readAltitude('#planned-altitude'),focus.alt_m,.5);
  }
  await page.click('#story-conflict');
  assert.equal(await page.evaluate(()=>mode),'original');
  assert.ok(await page.evaluate(()=>activeEvents().length>0));
  assert.ok((await page.textContent('#current-state')).includes('active violation'));
  assert.ok(await page.evaluate(()=>qualities.get(selected).changed));
  const before=await page.evaluate(()=>({selected,time,z:positionAt(byId.get(selected)).z}));
  await page.click('#mode-plan');
  assert.equal(await page.evaluate(()=>selected),before.selected);assert.equal(await page.evaluate(()=>time),before.time);
  assert.ok(await page.evaluate(()=>positionAt(byId.get(selected)).z!==originalAt(byId.get(selected),time).z));
  assert.equal(await page.evaluate(()=>activeEvents().length),0);
  await page.click('#story-avoidance');
  assert.equal(await page.evaluate(()=>selected),'F031');
  assert.equal(await page.evaluate(()=>playing),false);
  assert.ok(await page.evaluate(()=>positionAt(byId.get(selected)).z>=witness.required_altitude_lower_m));
  assert.ok((await page.textContent('#insight-copy')).includes('8,679.45'));
  const referenceDistance=await page.evaluate(()=>{const p=plannedAt(byId.get(selected),time),d=positionAt(threat);return Math.hypot(p.x-d.x,p.y-d.y,p.z-d.z);});
  assert.ok((await page.textContent('#flight-detail')).includes(Math.round(referenceDistance).toLocaleString('en-US')));
  await page.click('#story-endpoints');
  assert.equal(await page.evaluate(()=>time),1200);
  const endpoint=await page.evaluate(()=>DATA.endpoint_bounds.disjoint_pairs.map(p=>p.aircraft.map(id=>({original:byId.get(id).alt_m,...positionAt(byId.get(id))}))));
  for(const [a,b] of endpoint){near(Math.abs(a.z-b.z),300);near(Math.abs(a.z-a.original),150);near(Math.abs(b.z-b.original),150);}
  assert.ok((await page.textContent('#insight-copy')).includes('600 m'));
  // At 421 s both endpoint-pair aircraft have separate drone events, but their
  // mutual pair event has not started. Do not paint their connector as a pair loss.
  await page.click('#mode-original');await page.evaluate(()=>seek(421));
  const separate=await page.evaluate(()=>{const events=activeEvents();relation(events);return {color:ctx.fillStyle,zoneIds:events.filter(e=>e.type==='aircraft_threat').flatMap(e=>e.participants),pair:events.some(e=>e.type==='aircraft_aircraft'&&e.participants.includes('F018')&&e.participants.includes('F034'))};});
  assert.ok(separate.zoneIds.includes('F018')&&separate.zoneIds.includes('F034'));
  assert.equal(separate.pair,false);assert.equal(separate.color,'#647ba0');
  await page.evaluate(()=>{seek(430);relation(activeEvents())});assert.equal(await page.evaluate(()=>ctx.fillStyle),'#c64d60');
  await page.click('#mode-plan');
  // The user can choose every aircraft, including ones the camera previously hid.
  for(const f of document.trajectories){await page.selectOption('#flight-select',f.flight_id);assert.equal(await page.locator('#profile').getAttribute('data-flight-id'),f.flight_id);assert.ok((await page.textContent('#insight-title')).startsWith(f.flight_id+':'));}
  await page.click('#fit-all');
  assert.ok(await page.evaluate(()=>flights.every(f=>{const p=screen(positionAt(f));return p.x>10&&p.x<width-10&&p.y>10&&p.y<height-10;})));
  const scale=await page.evaluate(()=>camera.scale);await page.click('#zoom-in');assert.ok(await page.evaluate(()=>camera.scale)>scale);
  const rect=await page.locator('#map').boundingBox(),oldX=await page.evaluate(()=>camera.x);
  await page.mouse.move(rect.x+150,rect.y+150);await page.mouse.down();await page.mouse.move(rect.x+200,rect.y+180);await page.mouse.up();
  assert.notEqual(await page.evaluate(()=>camera.x),oldX);
  await page.locator('#map').focus();await page.keyboard.press('+');
  // Pause, speed and seeking are stable under a virtual animation clock.
  await page.clock.install();await page.evaluate(()=>seek(100));await page.selectOption('#speed','30');await page.click('#play');
  await page.clock.runFor(1000);near(await page.evaluate(()=>time),130,.6);
  await page.click('#play');const paused=await page.evaluate(()=>time);await page.clock.runFor(1000);near(await page.evaluate(()=>time),paused);
  await page.selectOption('#speed','60');await page.click('#play');await page.clock.runFor(1000);near(await page.evaluate(()=>time),paused+60,1);
  await page.locator('#time-slider').fill('250');assert.equal(await page.evaluate(()=>playing),false);near(await page.evaluate(()=>time),250);
  const urls=await page.locator('a').evaluateAll(links=>links.map(a=>a.getAttribute('href')));
  for(const url of urls)if(!url.startsWith('https:'))assert.ok(fs.existsSync(path.join(directory,url)),url);
  await page.click('#story-avoidance');await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:'/tmp/dtl-email-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.ok(await page.evaluate(()=>document.querySelector('.playback').getBoundingClientRect().top<document.querySelector('.inspector').getBoundingClientRect().top));
  assert.ok(await page.evaluate(()=>Array.from(document.querySelectorAll('.tour button')).every(e=>e.getBoundingClientRect().width>80)));
  await page.screenshot({path:'/tmp/dtl-email-mobile.png',fullPage:true});
  await page.click('#story-conflict');assert.ok(await page.evaluate(()=>activeEvents().length>0));
  await page.click('#mode-plan');assert.equal(await page.evaluate(()=>activeEvents().length),0);
  assert.deepEqual(errors,[]);assert.ok(requests.every(url=>url.startsWith('file:')));
  console.log('PASS: compact package opens on safe plan; all 40 trajectories, comparison, three guided moments, profiles, event intervals, camera, playback, links, GitHub, desktop/mobile, offline.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
