// Rendering and saved-motion evaluation only. All event intervals come from Python.
function currentPlanStep(){return planning.steps[viewMode==='final'?planning.steps.length-1:replayStep];}
function versionFor(fid,profile=false){
  if(!planning)return null;
  if(qualityData&&selectedAlternative!=='reference'&&(viewMode==='final'||(profile&&viewMode==='baseline'))){const entry=selectedQualityEntry();return qualityData.versions[entry.fleet_versions[planFlightIndex.get(fid)]];}
  const step=(profile&&viewMode==='baseline')?planning.steps[planning.steps.length-1]:currentPlanStep();
  return planning.versions[step.fleet_versions[planFlightIndex.get(fid)]];
}
function verticalAt(version,t){
  const pieces=version.segments,p=pieces.find(p=>p.start_s<=t&&t<p.end_s)||pieces[pieces.length-1],dt=t-p.start_s;
  return {z:p.alt_start_m+p.vz_start_mps*dt+p.az_mps2*dt*dt/2,vz:p.vz_start_mps+p.az_mps2*dt,phase:p};
}
function currentVz(f,t){return viewMode==='baseline'||!planning?f.vz_mps:verticalAt(versionFor(f.flight_id),t).vz;}
const nominalScope=()=>['profile-select','mode-select','variant-select'].map(id=>$(id).value).join('/')==='metric/nominal/base';
let profileCache='',historyCache='',profilePlots=[],searchCursor=null;
function setViewMode(mode){
  if(!planning||!['baseline','final','replay'].includes(mode))return;
  if(viewMode==='baseline'&&mode!=='baseline')savedBaselineSelection=['profile-select','mode-select','variant-select'].map(id=>$(id).value);
  viewMode=mode;
  const ids=['profile-select','mode-select','variant-select'];
  if(mode==='baseline'&&savedBaselineSelection)ids.forEach((id,i)=>$(id).value=savedBaselineSelection[i]);
  if(mode!=='baseline')ids.forEach((id,i)=>$(id).value=['metric','nominal','base'][i]);
  ids.forEach(id=>$(id).disabled=mode!=='baseline');
  profileCache='';chooseRun();
}
function selectSearchStep(index){
  if(!planning||!Number.isInteger(index)||index<0||index>=planning.steps.length)return;
  replayStep=index;playing=false;updatePlay();
  const repair=planning.steps[index].repair;
  if(repair){selected=repair.flight_id;$('flight-select').value=selected;}
  historyCache='';setViewMode('replay');
}
const SVG_NS='http://www.w3.org/2000/svg';
function svgNode(tag,attrs={},text=null){const n=document.createElementNS(SVG_NS,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==null)n.textContent=text;return n;}
function svgText(svg,x,y,text,extra={}){svg.append(svgNode('text',{x,y,fill:'#a9b8cb','font-size':11,...extra},text));}
function pathFor(points,x,y){return points.map(([t,v],i)=>`${i?'L':'M'}${x(t).toFixed(2)},${y(v).toFixed(2)}`).join(' ');}
function buildProfile(id,version,field){
  const svg=$(id),W=Math.max(260,svg.getBoundingClientRect().width),H=205,L=57,R=17,T=18,B=29;
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.replaceChildren();
  const f=flightById.get(selected),samples=version.profile.time_s,planned=version.profile[field];
  const base=samples.map(t=>field==='alt_m'?f.alt_m+f.vz_mps*t:f.vz_mps),factor=field==='alt_m'?1000:1;
  const referenceVersion=planning.versions[planning.steps[planning.steps.length-1].fleet_versions[planFlightIndex.get(selected)]],showReference=selectedAlternative!=='reference'&&viewMode!=='replay',refValues=showReference?referenceVersion.profile[field]:[];
  let lo=Math.min(...planned,...base,...refValues),hi=Math.max(...planned,...base,...refValues),padding=Math.max(field==='alt_m'?100:1,(hi-lo)*.12);
  lo-=padding;hi+=padding;
  const x=t=>L+t/DURATION*(W-L-R),y=v=>H-B-(v-lo)/(hi-lo)*(H-T-B);
  svg.dataset.flightId=selected;svg.dataset.overlay=viewMode==='replay'?`step-${replayStep}`:'final';
  for(const phase of version.segments){
    svg.append(svgNode('rect',{x:x(phase.start_s),y:T,width:Math.max(0,x(phase.end_s)-x(phase.start_s)),height:H-T-B,
      fill:phase.kind==='climb'?'#675587':phase.kind==='descent'?'#315d81':phase.kind==='hold'?'#284a3a':'#142438',opacity:.36,'data-phase':phase.label}));
  }
  for(let i=0;i<=4;i++){const value=lo+(hi-lo)*i/4;svg.append(svgNode('line',{x1:L,x2:W-R,y1:y(value),y2:y(value),stroke:'#34445a','stroke-width':.6}));svgText(svg,L-7,y(value)+4,fmt(value/factor,field==='alt_m'?2:1),{'text-anchor':'end'});}
  for(const t of W<430?[0,600,1200]:[0,300,600,900,1200])svgText(svg,x(t),H-7,`${String(Math.floor(t/60)).padStart(2,'0')}:00`,{'text-anchor':'middle'});
  svg.append(svgNode('path',{d:pathFor(samples.map((t,i)=>[t,base[i]]),x,y),fill:'none',stroke:'#c2cbd8','stroke-width':2,'stroke-dasharray':'5 4',class:'baseline-profile-line'}));
  if(showReference)svg.append(svgNode('path',{d:pathFor(referenceVersion.profile.time_s.map((t,i)=>[t,refValues[i]]),x,y),fill:'none',stroke:'#fbbf24','stroke-width':1.8,'stroke-dasharray':'3 3',class:'reference-profile-line'}));
  svg.append(svgNode('path',{d:pathFor(samples.map((t,i)=>[t,planned[i]]),x,y),fill:'none',stroke:'#87dfef','stroke-width':2.3,class:'planned-profile-line'}));
  const cursor=svgNode('line',{x1:x(time),x2:x(time),y1:T,y2:H-B,stroke:'#fff','stroke-width':1.2,class:'simulation-cursor'}),dot=svgNode('circle',{cx:x(time),cy:T,r:4,fill:'#87dfef',stroke:'#0b1220',class:'profile-now-dot'});
  svg.append(cursor,dot);return {svg,x,y,cursor,dot,field,L,R,W};
}
function renderProfiles(){
  const supported=viewMode!=='baseline'||nominalScope();
  $('profile-content').hidden=!supported;
  $('profile-scope-note').textContent=supported?'Horizontal motion is identical in both schedules. Profile overlay: saved nominal motion only.':'Planned profiles are restricted to metric / nominal / base. Select Final plan or return the baseline selectors to that configuration.';
  if(!supported){profileCache='';return;}
  const version=versionFor(selected,true),W=$('altitude-profile').getBoundingClientRect().width;
  const key=[selected,viewMode,replayStep,selectedAlternative,W].join('|');
  if(profileCache!==key){
    profileCache=key;
    $('profiles-title').textContent=`${selected} · altitude and vertical speed`;
    $('profile-reference-key').hidden=selectedAlternative==='reference'||viewMode==='replay';
    $('profile-plan-label').textContent=viewMode==='replay'?`━ Search candidate · step ${replayStep}`:selectedAlternative==='reference'?'━ Unchanged reference':`━ Verified alternative ${selectedAlternative}`;
    profilePlots=[buildProfile('altitude-profile',version,'alt_m'),buildProfile('speed-profile',version,'vz_mps')];
    $('profile-stats').replaceChildren(...[
      `Maximum altitude deviation: ${fmt(version.max_altitude_deviation_m,0)} m`,
      `Terminal altitude offset: ${fmt(version.terminal_altitude_offset_m,0)} m`,
      `Remaining destination distance: ${fmt(version.remaining_destination_distance_m,0)} m`
    ].map(text=>{const span=document.createElement('span');span.textContent=text;return span;}));
    $('phase-list').replaceChildren(...version.segments.map(p=>{const span=document.createElement('span');span.className='phase-item';span.dataset.start=p.start_s;span.dataset.end=p.end_s;span.textContent=`${fmt(p.start_s,0)}–${fmt(p.end_s,0)} s · ${p.label}`;return span;}));
  }
  const p=verticalAt(version,time),baseline=baselinePositionAt(flightById.get(selected),time);
  for(const plot of profilePlots){const xx=plot.x(time);plot.cursor.setAttribute('x1',xx);plot.cursor.setAttribute('x2',xx);plot.cursor.dataset.time=String(time);plot.dot.setAttribute('cx',xx);plot.dot.setAttribute('cy',plot.y(plot.field==='alt_m'?p.z:p.vz));}
  $('profile-now').textContent=`Simulation ${$('clock').textContent} · baseline ${fmt(baseline.z/1000,3)} km / ${fmt(flightById.get(selected).vz_mps,2)} m/s · overlay ${fmt(p.z/1000,3)} km / ${fmt(p.vz,2)} m/s · ${p.phase.label}`;
  for(const el of $('phase-list').children)el.classList.toggle('current-phase',Number(el.dataset.start)<=time&&(time<Number(el.dataset.end)||(time===DURATION&&Number(el.dataset.end)===DURATION)));
}
function buildSearchChart(){
  const svg=$('search-chart'),W=Math.max(260,svg.getBoundingClientRect().width),H=170,L=34,R=18,T=14,B=30;
  svg.replaceChildren();svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
  const last=planning.steps.length-1,max=Math.max(1,...planning.steps.flatMap(s=>[s.zone_count,s.pair_count]));
  const x=i=>L+i/last*(W-L-R),y=v=>H-B-v/max*(H-T-B);
  for(let v=0;v<=max;v+=3){svg.append(svgNode('line',{x1:L,x2:W-R,y1:y(v),y2:y(v),stroke:'#34445a'}));svgText(svg,L-8,y(v)+4,String(v),{'text-anchor':'end'});}
  for(const [field,color] of [['zone_count','#fbbf24'],['pair_count','#c3a6ec']]){
    svg.append(svgNode('path',{d:pathFor(planning.steps.map(s=>[s.index,s[field]]),x,y),fill:'none',stroke:color,'stroke-width':2}));
    for(const step of planning.steps){const dot=svgNode('circle',{cx:x(step.index),cy:y(step[field]),r:5,fill:color,tabindex:0,role:'button','aria-label':`Step ${step.index}: ${step.zone_count} zone and ${step.pair_count} pair events`});dot.onclick=()=>selectSearchStep(step.index);dot.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();selectSearchStep(step.index);}};svg.append(dot);}
  }
  for(const i of W<430?[0,5,10,15,20,21]:[0,3,6,9,12,15,18,21])svgText(svg,x(i),H-8,String(i),{'text-anchor':'middle'});
  searchCursor=svgNode('line',{x1:x(replayStep),x2:x(replayStep),y1:T,y2:H-B,stroke:'#fff','stroke-dasharray':'3 3'});svg.append(searchCursor);
  searchCursor.dataset.width=W;searchCursor.dataset.left=L;searchCursor.dataset.right=R;
}
function renderHistory(){
  const key=[replayStep,viewMode,$('search-chart').getBoundingClientRect().width].join('|');
  if(historyCache===key)return;historyCache=key;buildSearchChart();
  const step=planning.steps[replayStep],repair=step.repair;
  $('search-slider').value=String(replayStep);$('search-step-label').textContent=`Step ${replayStep} / ${planning.steps.length-1}`;
  for(const button of $('search-steps').children)button.setAttribute('aria-pressed',String(viewMode==='replay'&&Number(button.dataset.step)===replayStep));
  const rows=[['Changed aircraft',repair?.flight_id||'None · initial baseline'],['Altitude offset',repair?`${fmt(repair.offset_m,0)} m`:'—'],
    ['Maneuver starts',repair?`${fmt(repair.start_s,0)} s`:'—'],['Transition complete',step.timing?`${fmt(step.timing.transition_end_s,0)} s`:'—'],['Return complete',step.timing?(step.timing.return_end_s===null?'Terminal hold':`${fmt(step.timing.return_end_s,0)} s`):'—'],['Return starts',repair?(repair.return_start_s===null?'No return · terminal hold':`${fmt(repair.return_start_s,0)} s`):'—'],
    ['Removed zone / pair events',repair?`${repair.removed_unary_events} / ${repair.removed_pair_events}`:'—'],['Introduced pair events',repair?String(repair.introduced_pair_events):'—'],
    ['Remaining zone / pair events',`${step.zone_count} / ${step.pair_count}`],['Unresolved checks',String(step.unresolved_count)]];
  $('repair-details').replaceChildren(...rows.map(([label,value])=>{const group=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;group.append(dt,dd);return group;}));
  $('step-explanation').textContent=repair?.plateau_move?'Equal-count move at step 20: F004 changes altitude/timing, replacing the blocking pair while one pair event remains. Step 21 then changes F034 and removes it.':replayStep===0?`Step 0 is the original fleet: ${step.zone_count} zone events and ${step.pair_count} pair events.`:replayStep===planning.steps.length-1?'Reconstructed controls match segments.json exactly. This replay view remains labeled a search candidate; use Final plan for the independent final safety status.':'Accepted search candidate, potentially unsafe. Counts cover the entire horizon, independently of the simulation clock. Removed counts refer to replaced incident events; introduced counts refer to the replacement schedule.';
}
function renderComparison(){
  if(!planning)return;
  for(const mode of ['baseline','final','replay'])$('view-'+mode).setAttribute('aria-pressed',String(viewMode===mode));
  const final=selectedQualityEntry()?.verification||planning.final_verification;
  $('view-status').classList.toggle('good',viewMode==='final');
  $('view-status').textContent=viewMode==='final'?`Final plan · independently verified · ${final.violation_count} nominal violations · ${final.unresolved_count} unresolved`:viewMode==='replay'?`Search candidate · step ${replayStep} · potentially unsafe · not final safety status`:'Baseline · original source trajectories';
  $('view-scope').textContent=viewMode==='baseline'?'Baseline profile, stress and radii controls apply below. The saved comparison above is metric / nominal / base.':'Locked to metric / nominal / base, 0–1200 s. Alternative profiles, radii and bounded stress are not verified for these schedules.';
  $('view-tag').textContent=viewMode==='baseline'?'BASELINE / NO MANEUVERS':viewMode==='final'?'FINAL / VERIFIED NOMINAL':`SEARCH CANDIDATE / STEP ${replayStep}`;
  $('analysis-heading').textContent=viewMode==='baseline'?'Baseline prediction under the selected rules · no maneuvers':viewMode==='final'?'Final plan · precomputed continuous verification':`Search candidate step ${replayStep} · precomputed continuous findings`;
  if(viewMode==='final'&&selectedAlternative!=='reference'){$('view-status').textContent=`Alternative ${selectedAlternative} · independently verified · ${final.violation_count} nominal violations · ${final.unresolved_count} unresolved`;$('view-tag').textContent='ALTERNATIVE / VERIFIED NOMINAL';$('analysis-heading').textContent=`${selectedAlternative} · independent continuous verification`;}
  renderProfiles();renderHistory();renderQuality();
}
function initComparison(){
  if(!planning)return;
  initQuality();
  for(const id of ['comparison-panel','profiles-panel','search-panel','changes-panel'])$(id).hidden=false;
  $('baseline-total').textContent=planning.steps[0].violation_count;$('final-total').textContent=planning.final_verification.violation_count;$('final-unresolved').textContent=planning.final_verification.unresolved_count;
  $('history-scope').textContent=planning.history_scope;
  $('search-slider').max=String(planning.steps.length-1);
  for(const mode of ['baseline','final','replay'])$('view-'+mode).onclick=()=>setViewMode(mode);
  $('search-slider').oninput=e=>selectSearchStep(Number(e.target.value));
  $('search-steps').replaceChildren(...planning.steps.map(step=>{const b=document.createElement('button');b.textContent=String(step.index);b.dataset.step=step.index;b.title=step.repair?`Step ${step.index} · ${step.repair.flight_id} · ${step.zone_count} zone / ${step.pair_count} pair`:'Step 0 · original fleet';b.setAttribute('aria-label',b.title);if(step.repair?.plateau_move)b.className='plateau';b.onclick=()=>selectSearchStep(step.index);return b;}));
  $('changed-aircraft').replaceChildren(...planning.changed_aircraft.map(row=>{
    const tr=document.createElement('tr');tr.dataset.flightId=row.flight_id;if(row.terminal_altitude_offset_m)tr.className='terminal-row';
    const td=document.createElement('td'),button=document.createElement('button');button.textContent=row.flight_id;button.onclick=()=>{selected=row.flight_id;$('flight-select').value=selected;setViewMode('final');};td.append(button);tr.append(td);
    for(const value of [fmt(row.max_altitude_deviation_m,0),fmt(row.largest_accepted_deviation_m,0),fmt(row.terminal_altitude_offset_m,0),fmt(row.remaining_destination_distance_m,0),row.repair_steps.join(', ')]){const td=document.createElement('td');td.textContent=value;tr.append(td);}return tr;
  }));
  for(const id of ['altitude-profile','speed-profile']){
    $(id).onclick=e=>{const p=profilePlots.find(p=>p.svg.id===id);if(!p)return;const r=p.svg.getBoundingClientRect();setTime(Math.max(0,Math.min(DURATION,(e.clientX-r.left-p.L)/(p.W-p.L-p.R)*DURATION)));};
    $(id).onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();setTime(e.key==='Home'?0:e.key==='End'?DURATION:time+(e.key==='ArrowLeft'?-10:10));}};
  }
  new ResizeObserver(()=>{profileCache='';historyCache='';renderComparison();}).observe($('profiles-panel'));
}
