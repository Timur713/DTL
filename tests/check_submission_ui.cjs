// Reviewer tour and delivered-plan coherence under standalone file:// operation.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..');
const evidence=JSON.parse(fs.readFileSync(path.join(root,'submission/evidence.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>requests.push(r.url()));
  await page.goto(pathToFileURL(path.join(root,'baseline.html')).href);
  await page.waitForFunction(()=>document.querySelector('#map').width>1);
  assert.ok(await page.locator('#submission-panel').isVisible());
  assert.deepEqual(await page.evaluate(()=>DATA.submission),evidence);
  assert.equal(await page.evaluate(()=>viewMode),'baseline');
  assert.ok((await page.textContent('#submission-metrics')).includes('12 → 0'));
  assert.ok((await page.textContent('#submission-excursion')).includes('F031'));
  assert.ok((await page.textContent('#submission-sensitivity')).includes('16 events'));
  assert.ok((await page.textContent('#submission-sensitivity')).includes('298 m separation'));
  const links=await page.locator('#submission-panel a').evaluateAll(els=>els.map(e=>e.getAttribute('href')));
  for(const link of links)assert.ok(fs.existsSync(path.join(root,link)),link);
  await page.evaluate(()=>setTime(230));await page.selectOption('#flight-select','F020');
  await page.click('#show-recommended');
  assert.equal(await page.evaluate(()=>selectedAlternative),evidence.selected_id);
  assert.equal(await page.evaluate(()=>viewMode),'final');
  assert.equal(await page.evaluate(()=>time),230);
  assert.equal(await page.locator('#flight-select').inputValue(),'F020');
  assert.equal(await page.evaluate(()=>activeRun.events.length),0);
  await page.click('#show-endpoint-proof');
  assert.equal(await page.evaluate(()=>time),1200);
  assert.equal(await page.evaluate(()=>playing),false);
  const endpoints=await page.evaluate(()=>DATA.submission.endpoint_bounds.disjoint_pairs.map(pair=>{
    const [a,b]=pair.aircraft.map(id=>positionAt(flightById.get(id),DURATION));
    return {horizontal:Math.hypot(a.x-b.x,a.y-b.y),vertical:Math.abs(a.z-b.z)};
  }));
  assert.equal(endpoints.length,2);
  for(const pair of endpoints){assert.ok(pair.horizontal<9260);assert.equal(pair.vertical,300);}
  await page.click('#show-climb-proof');
  assert.equal(await page.locator('#flight-select').inputValue(),'F031');
  assert.equal(await page.evaluate(()=>time),evidence.excursion_bounds.strongest.time_s);
  assert.equal(await page.evaluate(()=>playing),false);
  assert.ok(await page.evaluate(()=>positionAt(flightById.get(selected),time).z>=DATA.submission.excursion_bounds.strongest.required_altitude_lower_m));
  await page.click('#show-original-conflict');
  assert.equal(await page.evaluate(()=>viewMode),'baseline');
  assert.equal(await page.evaluate(()=>activeRun.id),'metric__nominal__base');
  assert.ok(await page.evaluate(()=>currentParticipants.size>0));
  assert.equal(await page.evaluate(()=>playing),false);
  assert.equal(await page.evaluate(()=>flights.length),40);
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:'/tmp/dtl-submission-desktop.png'});
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:'/tmp/dtl-submission-mobile.png'});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.click('#show-recommended');
  assert.equal(await page.evaluate(()=>selectedAlternative),evidence.selected_id);
  assert.equal(await page.evaluate(()=>activeRun.events.length),0);
  assert.deepEqual(errors,[]);
  assert.ok(requests.every(url=>url.startsWith('file:')));
  console.log('Submission browser suite passed: coherent exports, proof tour, nominal scope, offline desktop/mobile.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
