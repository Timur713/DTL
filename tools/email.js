// Display saved motion and Python-certified event intervals. No JS conflict detector.
'use strict';
const DATA=JSON.parse(document.getElementById('email-data').textContent);
const $=id=>document.getElementById(id),T=DATA.duration_s;
const flights=DATA.flights,byId=new Map(flights.map(f=>[f.flight_id,f]));
const qualities=new Map(DATA.quality.per_aircraft.map(q=>[q.flight_id,q]));
const threat=DATA.scenario.hostile_object,target={...DATA.scenario.target,alt_m:DATA.rules.zones.target.center_alt_m,vx_mps:0,vy_mps:0,vz_mps:0};
const limits=DATA.scenario.airspace,thresholds=DATA.verification.thresholds;
const witness=DATA.excursion_bounds.strongest;
let mode='plan',selected=witness.flight_id,time=witness.time_s,playing=false,speed=30,anchorTime=time,anchorWall=0;
let story='avoidance',secondary=[],cameraMode='focus',camera={x:0,y:0,scale:1};
let heightView=true;
const heightFactor=()=>heightView?3:0;
const displayNorth=p=>p.y+heightFactor()*(p.z||0);
let width=1,height=1,profilePlot=null,profileKey='',drag=null;
const canvas=$('map'),ctx=canvas.getContext('2d');
const fmt=(n,d=0)=>(Object.is(n,-0)?0:n).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const clock=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${String(Math.floor(t%60)).padStart(2,'0')}`;
function originalAt(f,t){return {x:f.x_m+f.vx_mps*t,y:f.y_m+f.vy_mps*t,z:f.alt_m+f.vz_mps*t,vz:f.vz_mps};}
function plannedAt(f,t){
 const p=originalAt(f,t),pieces=DATA.profiles[f.flight_id].segments;
 const segment=pieces.find(s=>s.start_s<=t&&t<s.end_s)||pieces[pieces.length-1],dt=t-segment.start_s;
 p.z=segment.alt_start_m+segment.vz_start_mps*dt+segment.az_mps2*dt*dt/2;
 p.vz=segment.vz_start_mps+segment.az_mps2*dt;return p;
}
const positionAt=(f,t=time)=>f.flight_id&&mode==='plan'?plannedAt(f,t):originalAt(f,t);
function eventActive(e,t=time){return (t>e.start_s||t===e.start_s&&e.start_inclusive)&&(t<e.end_s||t===e.end_s&&e.end_inclusive);}
function activeEvents(){return mode==='plan'?[]:DATA.baseline.events.filter(e=>eventActive(e));}
const screen=p=>({x:width/2+(p.x-camera.x)*camera.scale,y:height/2-(displayNorth(p)-camera.y)*camera.scale});
const world=p=>({x:camera.x+(p.x-width/2)/camera.scale,y:camera.y-(p.y-height/2)/camera.scale});
function fitPoints(points,minSpan=25000){
 const xs=points.map(p=>p.x),ys=points.map(displayNorth),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
 camera={x:(xmin+xmax)/2,y:(ymin+ymax)/2,scale:Math.min(Math.max(1,width-90)/Math.max(minSpan,xmax-xmin+22000),Math.max(1,height-65)/Math.max(minSpan,ymax-ymin+18000))};
}
function updateCamera(){
 // Frame both alternatives so switching plan cannot recenter away the difference.
 const both=f=>[originalAt(f,time),plannedAt(f,time)];
 if(cameraMode==='all')fitPoints([...flights.flatMap(both),positionAt(threat),positionAt(target)],100000);
 else if(cameraMode==='focus')fitPoints([...both(byId.get(selected)),...(secondary.length?secondary.flatMap(id=>both(byId.get(id))):[positionAt(threat)])]);
}
function line(a,b,color,width=1,dash=[]){ctx.beginPath();ctx.setLineDash(dash);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();ctx.setLineDash([]);}
function niceStep(n){const p=10**Math.floor(Math.log10(n)),q=n/p;return (q<=1?1:q<=2?2:q<=5?5:10)*p;}
function grid(){
 ctx.fillStyle='#f6fafb';ctx.fillRect(0,0,width,height);
 const low=world({x:0,y:height}),high=world({x:width,y:0}),step=niceStep(100/camera.scale);
 ctx.font='10px system-ui';ctx.fillStyle='#91a4ae';
 for(let x=Math.ceil(low.x/step)*step;x<=high.x;x+=step){const p=screen({x,y:0});line({x:p.x,y:0},{x:p.x,y:height},'#e5eef1');ctx.textAlign='center';ctx.fillText(fmt(x/1000)+' km',p.x,height-8);}
 for(let y=Math.ceil(low.y/step)*step;y<=high.y;y+=step){const p=screen({x:0,y});line({x:0,y:p.y},{x:width,y:p.y},'#e5eef1');ctx.textAlign='left';ctx.fillText(fmt(y/1000),6,p.y-5);}
 const a=screen({x:limits.x_min_m,y:limits.y_max_m}),b=screen({x:limits.x_max_m,y:limits.y_min_m});
 ctx.strokeStyle='#b8cdd6';ctx.lineWidth=1;ctx.setLineDash([5,7]);ctx.strokeRect(a.x,a.y,b.x-a.x,b.y-a.y);ctx.setLineDash([]);
}
function zone(obj,radius,color,label){
 const p=screen(positionAt(obj)),r=radius*camera.scale;
 ctx.beginPath();ctx.ellipse(p.x,p.y,r,r*Math.sqrt(1+heightFactor()**2),0,0,Math.PI*2);ctx.fillStyle=color+'10';ctx.fill();ctx.strokeStyle=color+'b0';ctx.lineWidth=1.3;ctx.setLineDash([5,4]);ctx.stroke();ctx.setLineDash([]);
 ctx.save();ctx.translate(p.x,p.y);ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2;
 if(label==='Threat'){ctx.rotate(Math.PI/4);ctx.fillRect(-5,-5,10,10);}
 else{ctx.beginPath();ctx.arc(0,0,6,0,2*Math.PI);ctx.moveTo(-10,0);ctx.lineTo(10,0);ctx.moveTo(0,-10);ctx.lineTo(0,10);ctx.stroke();}
 ctx.restore();ctx.font='600 11px system-ui';ctx.textAlign='left';ctx.fillStyle=color;ctx.fillText(label+' · '+fmt(positionAt(obj).z)+' m',p.x+12,p.y+17);
}
function aircraft(f,current){
 const p=screen(positionAt(f)),chosen=f.flight_id===selected,partner=secondary.includes(f.flight_id),danger=current.has(f.flight_id);
 if(p.x<-30||p.x>width+30||p.y<-30||p.y>height+30)return;
 if(danger||chosen||partner){ctx.beginPath();ctx.arc(p.x,p.y,chosen?19:16,0,Math.PI*2);ctx.fillStyle=danger?'#d6536517':chosen?'#087f7810':'#646e9510';ctx.fill();ctx.strokeStyle=danger?'#d65365':chosen?'#087f78':'#6c78a1';ctx.lineWidth=chosen?1.6:1;ctx.stroke();}
 if(heightView){const state=positionAt(f),ground=screen({...state,z:0});line(ground,p,chosen?'#087f7850':'#879ba71c',chosen?1.3:.6,[3,4]);ctx.beginPath();ctx.ellipse(ground.x,ground.y,chosen?5:2,2,0,0,Math.PI*2);ctx.fillStyle='#879ba744';ctx.fill();}
 ctx.save();ctx.translate(p.x,p.y);ctx.rotate(Math.atan2(f.vx_mps,f.vy_mps));const scale=chosen?1.05:.75;ctx.scale(scale,scale);
 ctx.beginPath();ctx.moveTo(0,-11);for(const [x,y] of [[2,-3],[9,2],[9,4],[2,2],[2,8],[4,10],[-4,10],[-2,8],[-2,2],[-9,4],[-9,2],[-2,-3]])ctx.lineTo(x,y);ctx.closePath();ctx.fillStyle=danger?'#c04459':chosen?'#087f78':partner?'#68749b':'#879ba7';ctx.fill();ctx.strokeStyle='white';ctx.lineWidth=.8;ctx.stroke();ctx.restore();
 if($('labels').checked||chosen||partner||danger){ctx.font=chosen?'650 11px system-ui':'10px system-ui';ctx.textAlign='left';ctx.lineWidth=4;ctx.strokeStyle='#f6fafb';const label=f.flight_id+((chosen||partner)?' · '+fmt(positionAt(f).z)+' m':'');ctx.strokeText(label,p.x+21,p.y-7);ctx.fillStyle=danger?'#b84154':chosen?'#086e67':'#5c7481';ctx.fillText(label,p.x+21,p.y-7);}
}
function relation(events){
 if(!secondary.length)return;
 const first=positionAt(byId.get(selected)),second=positionAt(byId.get(secondary[0])),a=screen(first),b=screen(second);
 // Two aircraft may each have a zone event without violating their mutual separation.
 const danger=events.some(e=>e.type==='aircraft_aircraft'&&e.participants.includes(selected)&&e.participants.includes(secondary[0])),color=danger?'#c64d60':'#647ba0';
 if(!heightView){ctx.beginPath();ctx.arc(a.x,a.y,thresholds.horizontal_m*camera.scale,0,Math.PI*2);ctx.setLineDash([3,5]);ctx.strokeStyle=color+'55';ctx.lineWidth=1;ctx.stroke();ctx.setLineDash([]);}
 line(a,b,color,1.4,[4,4]);const x=(a.x+b.x)/2,y=(a.y+b.y)/2;
 const text=`${fmt(Math.hypot(first.x-second.x,first.y-second.y)/1000,2)} km XY · ${fmt(Math.abs(first.z-second.z))} m vertical`;
 ctx.font='600 10px system-ui';const w=ctx.measureText(text).width;ctx.fillStyle='#ffffffed';ctx.fillRect(x-w/2-7,y-19,w+14,19);ctx.fillStyle=color;ctx.textAlign='center';ctx.fillText(text,x,y-6);
}
function drawMap(events){
 updateCamera();grid();
 zone(target,thresholds.target_radius_m,'#bf8a28','Target');zone(threat,thresholds.threat_radius_m,'#d65365','Threat');
 if($('routes').checked)for(const f of flights)line(screen(originalAt(f,0)),screen(originalAt(f,T)),'#8299a327',1,[4,4]);
 const f=byId.get(selected);
 // Display samples draw the verified controls; they do not establish safety.
 function route(planned,color,dash){
  const at=t=>planned?plannedAt(f,t):originalAt(f,t);
  for(let t=0;t<T;t+=10)line(screen(at(t)),screen(at(Math.min(T,t+10))),color,1.4,dash);
 }
 route(false,'#b66b2455',[4,5]);if(heightView)route(true,'#087f7860',[]);
 const at=t=>positionAt(f,t);line(screen(at(Math.max(0,time-10))),screen(at(time)),mode==='plan'?'#087f78':'#b66b24',3);
 if(heightView){
  const other=screen(mode==='plan'?originalAt(f,time):plannedAt(f,time)),actual=screen(positionAt(f));
  line(other,actual,'#8ba4ad',1,[3,4]);ctx.beginPath();ctx.arc(other.x,other.y,7,0,2*Math.PI);ctx.strokeStyle=mode==='plan'?'#b66b24':'#087f78';ctx.lineWidth=1.5;ctx.stroke();
  ctx.font='10px system-ui';ctx.fillStyle=ctx.strokeStyle;ctx.textAlign='left';ctx.fillText(mode==='plan'?'Original altitude':'Planned altitude',other.x+11,other.y+4);
 }
 const current=new Set(events.flatMap(e=>e.participants));relation(events);
 for(const f of flights)if(f.flight_id!==selected)aircraft(f,current);aircraft(byId.get(selected),current);
 const outside=flights.filter(f=>{const p=screen(positionAt(f));return p.x<0||p.x>width||p.y<0||p.y>height;}).length;
 $('view-height').setAttribute('aria-pressed',String(heightView));$('view-top').setAttribute('aria-pressed',String(!heightView));
 $('view-title').textContent=heightView?'Height perspective':'Top view';$('view-note').textContent=heightView?'Altitude ×3 for visibility · stems reach the ground':'X / Y only: vertical maneuvers are hidden';
 $('map-caption').textContent=`${cameraMode==='all'?'All-aircraft view':cameraMode==='focus'?'Focused view':'Custom view'} · all 40 simulated${outside?' · '+outside+' beyond camera':''}`;
}
const NS='http://www.w3.org/2000/svg';
function svg(tag,attrs={},text){const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=text;return e;}
function plotPath(points,x,y){return points.map(([t,z],i)=>`${i?'L':'M'}${x(t).toFixed(3)},${y(z).toFixed(3)}`).join(' ');}
function buildProfile(){
 const root=$('profile'),W=Math.max(240,root.getBoundingClientRect().width),H=190,L=30,R=8,top=12,bottom=24;
 const x=t=>L+t/T*(W-L-R),y=z=>H-bottom-(z-limits.alt_min_m)/(limits.alt_max_m-limits.alt_min_m)*(H-top-bottom);
 root.replaceChildren();root.setAttribute('viewBox',`0 0 ${W} ${H}`);
 const defs=svg('defs'),clip=svg('clipPath',{id:'profile-clip'});clip.append(svg('rect',{x:L,y:top,width:W-L-R,height:H-top-bottom}));defs.append(clip);root.append(defs);
 const group=svg('g',{'clip-path':'url(#profile-clip)'});root.append(group);
 for(let i=0;i<=3;i++){const z=limits.alt_min_m+(limits.alt_max_m-limits.alt_min_m)*i/3;group.append(svg('line',{x1:L,x2:W-R,y1:y(z),y2:y(z),stroke:'#e5edef'}));root.append(svg('text',{x:L-7,y:y(z)+3,'text-anchor':'end','font-size':9,fill:'#7a8e99'},fmt(z/1000)));}
 const profile=DATA.profiles[selected].profile,ts=profile.time_s;
 for(const [field,color] of [['threat_band_m','#f1c3cc'],['target_band_m','#efdbb7']]){
  let indices=[];function flush(){if(indices.length>1){const pts=indices.map(i=>[ts[i],profile[field][i][1]]).concat([...indices].reverse().map(i=>[ts[i],profile[field][i][0]]));group.append(svg('path',{d:plotPath(pts,x,y)+'Z',fill:color,opacity:.65}));}indices=[];}
  for(let i=0;i<ts.length;i++){if(profile[field][i])indices.push(i);else flush();}flush();
 }
 const f=byId.get(selected);group.append(svg('path',{d:plotPath(ts.map(t=>[t,originalAt(f,t).z]),x,y),fill:'none',stroke:'#91a1aa','stroke-width':1.6,'stroke-dasharray':'4 4',class:'original-profile'}));
 group.append(svg('path',{d:plotPath(ts.map((t,i)=>[t,profile.alt_m[i]]),x,y),fill:'none',stroke:'#087f78','stroke-width':2.3,class:'safe-profile'}));
 for(const t of [0,T/2,T])root.append(svg('text',{x:x(t),y:H-6,'text-anchor':t===0?'start':t===T?'end':'middle','font-size':9,fill:'#7a8e99'},clock(t)));
 const cursor=svg('line',{x1:x(time),x2:x(time),y1:top,y2:H-bottom,stroke:'#506a77','stroke-width':1,'stroke-dasharray':'3 3',class:'time-cursor'}),dot=svg('circle',{r:4,fill:'#087f78',stroke:'white','stroke-width':1.5,class:'current-altitude'});group.append(cursor,dot);
 const originalDot=svg('circle',{r:3.5,fill:'#b66b24',stroke:'white','stroke-width':1.5,class:'original-altitude-dot'});group.append(originalDot);
 root.dataset.flightId=selected;profilePlot={x,y,cursor,dot,originalDot,L,R,W};
}
function updateProfile(){
 const key=selected+'|'+$('profile').getBoundingClientRect().width;
 if(profileKey!==key){profileKey=key;buildProfile();}
 const plot=profilePlot;
 plot.cursor.setAttribute('x1',plot.x(time));plot.cursor.setAttribute('x2',plot.x(time));plot.cursor.dataset.time=String(time);
 plot.dot.setAttribute('cx',plot.x(time));plot.dot.setAttribute('cy',plot.y(plannedAt(byId.get(selected),time).z));plot.dot.setAttribute('fill','#087f78');
 plot.dot.setAttribute('r',mode==='plan'?5:3.5);plot.originalDot.setAttribute('r',mode==='original'?5:3.5);
 plot.originalDot.setAttribute('cx',plot.x(time));plot.originalDot.setAttribute('cy',plot.y(originalAt(byId.get(selected),time).z));
}
function updateInsight(){
 const pairIds=[selected,...secondary].join(' / '),q=qualities.get(selected);
 const texts={
  explore:['Explore / Aircraft detail',`${selected}: compare the two altitude histories.`,`${q.changed?'This aircraft changes altitude to avoid conflicts.':'This aircraft keeps its original altitude.'} The two readings show the same instant. Its planned end-position error is ${fmt(q.endpoint_deviation_m)} m; its largest altitude change is ${fmt(q.max_altitude_excursion_m)} m over the full 20 minutes.`],
  conflict:['01 / The problem','The original routes contain conflicts.',secondary.length?`${pairIds}: too close horizontally and vertically. Compare the same moment in Safe plan: the aircraft keep their horizontal routes and separate in altitude.`:'This original route enters protected space. Compare the same moment in Safe plan and watch the altitude chart: the horizontal route stays unchanged.'],
  avoidance:['02 / The maneuver','Go above the threat, then return.',`F031 starts at 3,000 m. Sphere geometry requires at least ${fmt(witness.required_altitude_lower_m,2)} m at ${clock(witness.time_s)}; the plan reaches ${fmt(plannedAt(byId.get(witness.flight_id),witness.time_s).z)} m. Pink shading marks forbidden altitudes. Compare both routes at the same instant.`],
  endpoints:['03 / The result','150 m each. The smallest possible worst error.','At 20:00, two disjoint pairs still need 300 m vertical separation. Opposing −150 m / +150 m offsets attain both proven bounds: 150 m largest error and 600 m total. This proof assumes unchanged horizontal routes.']
 };
 const text=texts[story];$('insight-label').textContent=text[0];$('insight-title').textContent=text[1];$('insight-copy').textContent=text[2];
 $('compare-story').textContent=mode==='plan'?'Compare with original →':'See the safe plan →';
 for(const id of ['conflict','avoidance','endpoints'])$('story-'+id).setAttribute('aria-pressed',String(id===story));
}
function render(){
 const events=activeEvents();drawMap(events);updateProfile();
 $('mode-plan').setAttribute('aria-pressed',String(mode==='plan'));$('mode-original').setAttribute('aria-pressed',String(mode==='original'));
 $('current-state').className='state'+(mode==='original'?' original':'')+(events.length?' danger':'');
 $('current-state').textContent=mode==='plan'?'Verified nominal plan · 0 violations over 20 minutes':`Original routes · ${events.length?events.length+' active violation event'+(events.length===1?'':'s'):'no active event at this instant'} · 12 over the horizon`;
 const f=byId.get(selected),p=positionAt(f),q=qualities.get(selected),planned=mode==='plan';
 $('flight-select').value=selected;$('phase').textContent=p.vz>1e-8?'Climbing':p.vz<-1e-8?'Descending':Math.abs(p.z-f.alt_m)>1e-6?'Level hold':'Level flight';
 $('altitude').textContent=fmt(p.z)+' m';
 $('original-altitude').innerHTML=`${fmt(originalAt(f,time).z)} <small>m</small>`;
 $('planned-altitude').innerHTML=`${fmt(plannedAt(f,time).z)} <small>m</small>`;
 $('original-reading').classList.toggle('selected-reading',!planned);$('planned-reading').classList.toggle('selected-reading',planned);
 $('reading-time').textContent=clock(time);
 $('vertical-speed').innerHTML=`${p.vz>0?'+':''}${fmt(p.vz,1)} <small>m/s</small>`;
 $('endpoint').innerHTML=`${fmt(planned?q.endpoint_deviation_m:0)} <small>m</small>`;
 $('excursion').innerHTML=`${fmt((planned?q.max_altitude_excursion_m:0)/1000,2)} <small>km</small>`;
 // Distances below are display diagnostics; event status uses Python intervals only.
 if(secondary.length){
  const other=positionAt(byId.get(secondary[0]));
  $('flight-detail').textContent=`Pair ${selected} / ${secondary[0]} now: ${fmt(Math.hypot(p.x-other.x,p.y-other.y)/1000,2)} km horizontal · ${fmt(Math.abs(p.z-other.z))} m vertical.`;
 }else{
  const zones=[{obj:threat,name:'Drone',radius:thresholds.threat_radius_m},{obj:target,name:'Target',radius:thresholds.target_radius_m}];
  const nearest=zones.map(z=>({...z,distance:Math.hypot(p.x-positionAt(z.obj).x,p.y-positionAt(z.obj).y,p.z-positionAt(z.obj).z)})).sort((a,b)=>a.distance-b.distance)[0];
  $('flight-detail').textContent=`${nearest.name} distance now: ${fmt(nearest.distance)} m · minimum ${fmt(nearest.radius)} m (3D).`;
 }

 $('clock').textContent=clock(time);$('time-slider').value=String(time);$('time-slider').setAttribute('aria-valuetext',clock(time)+' of 20 minutes');
 $('play').textContent=playing?'Ⅱ Pause':'▶ Play';updateInsight();
}
function updateClock(now){if(playing){time=Math.min(T,anchorTime+(now-anchorWall)/1000*speed);if(time>=T)playing=false;}}
function seek(t){playing=false;time=Math.max(0,Math.min(T,Number(t)));anchorTime=time;render();}
function setMode(value){updateClock(performance.now());mode=value;anchorTime=time;anchorWall=performance.now();render();}
function inspectEvent(e){
 playing=false;mode='original';time=e.witness_s;story='conflict';
 const ids=e.participants.filter(id=>byId.has(id));selected=ids.find(id=>qualities.get(id).changed)||ids[0];secondary=ids.filter(id=>id!==selected);
 cameraMode='focus';profileKey='';render();
}
function showStory(value){
 playing=false;story=value;mode='plan';cameraMode='focus';secondary=[];
 if(value==='conflict'){inspectEvent(DATA.baseline.events[0]);return;}
 if(value==='avoidance'){selected=witness.flight_id;time=witness.time_s;}
 else{const pair=DATA.endpoint_bounds.disjoint_pairs[0].aircraft;selected=pair[0];secondary=[pair[1]];time=T;}
 profileKey='';render();
}
function zoom(factor,point={x:width/2,y:height/2}){
 const before=world(point);camera.scale=Math.max(.0001,Math.min(.15,camera.scale*factor));const after=world(point);camera.x+=before.x-after.x;camera.y+=before.y-after.y;cameraMode='custom';render();
}
function resize(){
 const rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
 width=Math.max(1,rect.width);height=Math.max(1,rect.height);canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);profileKey='';render();
}
$('flight-select').replaceChildren(...flights.map(f=>{const o=document.createElement('option');o.value=f.flight_id;o.textContent=f.flight_id;return o;}));
$('flight-select').onchange=e=>{selected=e.target.value;story='explore';secondary=[];cameraMode='focus';profileKey='';render();};
$('mode-plan').onclick=()=>setMode('plan');$('mode-original').onclick=()=>setMode('original');
$('compare-story').onclick=()=>setMode(mode==='plan'?'original':'plan');
$('play').onclick=()=>{const now=performance.now();updateClock(now);if(!playing&&time>=T)time=0;playing=!playing;anchorTime=time;anchorWall=now;render();};
$('speed').onchange=e=>{const now=performance.now();updateClock(now);speed=Number(e.target.value);anchorTime=time;anchorWall=now;render();};
$('time-slider').oninput=e=>seek(e.target.value);
$('view-height').onclick=()=>{heightView=true;cameraMode='focus';render();};$('view-top').onclick=()=>{heightView=false;cameraMode='focus';render();};
$('fit-all').onclick=()=>{cameraMode='all';render();};$('focus-flight').onclick=()=>{cameraMode='focus';render();};
$('zoom-in').onclick=()=>zoom(1.4);$('zoom-out').onclick=()=>zoom(1/1.4);
for(const id of ['labels','routes'])$(id).onchange=render;
for(const id of ['conflict','avoidance','endpoints'])$('story-'+id).onclick=()=>showStory(id);
$('event-track').replaceChildren(...DATA.baseline.events.map((e,i)=>{
 const b=document.createElement('button');b.style.left=e.start_s/T*100+'%';b.style.width=Math.max(.5,(e.end_s-e.start_s)/T*100)+'%';b.style.top=String(3+i%3*6)+'px';b.title=`Original ${e.participants.join(' / ')} · ${clock(e.start_s)}–${clock(e.end_s)}`;b.setAttribute('aria-label',b.title);b.onclick=()=>inspectEvent(e);return b;
}));
const q=DATA.quality;
$('maneuver-cost').textContent=`${q.changed_aircraft_count} aircraft maneuver · ${fmt(q.max_altitude_excursion_m)} m largest altitude change · ${fmt(q.vertical_travel_m/1000,1)} km fleet vertical travel. Endpoint optimality does not make these costs optimal.`;
$('quality-detail').textContent=`Selected plan: ${q.changed_aircraft_count} aircraft change altitude; ${q.reversal_count} climb/descent reversals; ${fmt(q.vertical_travel_m/1000,1)} km total vertical travel. Every aircraft finishes with zero vertical speed. The maximum temporary excursion is ${fmt(q.max_altitude_excursion_m/1000,2)} km. Full controls and numerical evidence are included below.`;
if(DATA.github_url){$('github-link').hidden=false;$('github-link').href=DATA.github_url;$('source-note').hidden=true;}
const local=e=>{const r=canvas.getBoundingClientRect();return {x:e.clientX-r.left,y:e.clientY-r.top};};
canvas.addEventListener('wheel',e=>{e.preventDefault();zoom(Math.exp(-e.deltaY*.0015),local(e));},{passive:false});
canvas.addEventListener('pointerdown',e=>{canvas.setPointerCapture(e.pointerId);drag={...local(e),x0:camera.x,y0:camera.y,moved:false};});
canvas.addEventListener('pointermove',e=>{if(!drag)return;const p=local(e),dx=p.x-drag.x,dy=p.y-drag.y;if(Math.hypot(dx,dy)>3)drag.moved=true;if(drag.moved){cameraMode='custom';camera.x=drag.x0-dx/camera.scale;camera.y=drag.y0+dy/camera.scale;render();}});
canvas.addEventListener('pointerup',e=>{
 if(drag&&!drag.moved){const p=local(e);let nearest=null,distance=21;for(const f of flights){const s=screen(positionAt(f)),d=Math.hypot(s.x-p.x,s.y-p.y);if(d<distance){nearest=f;distance=d;}}if(nearest){selected=nearest.flight_id;story='explore';secondary=[];profileKey='';render();}}
 drag=null;
});canvas.addEventListener('pointercancel',()=>drag=null);
canvas.onkeydown=e=>{if(['+','=','-','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();if(e.key==='+'||e.key==='=')zoom(1.3);else if(e.key==='-')zoom(1/1.3);else{cameraMode='custom';camera.x+=(e.key==='ArrowRight'?35:e.key==='ArrowLeft'?-35:0)/camera.scale;camera.y+=(e.key==='ArrowUp'?35:e.key==='ArrowDown'?-35:0)/camera.scale;render();}}};
$('profile').onclick=e=>{const r=$('profile').getBoundingClientRect();if(profilePlot)seek((e.clientX-r.left-profilePlot.L)/(profilePlot.W-profilePlot.L-profilePlot.R)*T);};
$('profile').onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();seek(e.key==='Home'?0:e.key==='End'?T:time+(e.key==='ArrowLeft'?-10:10));}};
new ResizeObserver(resize).observe(canvas.parentElement);
new ResizeObserver(()=>{profileKey='';render();}).observe($('profile'));
function frame(now){if(playing){updateClock(now);render();}requestAnimationFrame(frame);}
resize();requestAnimationFrame(frame);
