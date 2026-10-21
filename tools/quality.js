// Raw quality, deltas, Pareto membership and verification are prepared by Python.
const qualityData=DATA.quality_alternatives||null;
const qualityEntries=new Map((qualityData?.entries||[]).map(e=>[e.id,e]));
const qualityLabels={max_endpoint_deviation_m:['Max endpoint deviation','m','Dmax'],total_endpoint_deviation_m:['Total endpoint deviation','m','Dtotal'],accumulated_altitude_deviation_m_s:['Accumulated altitude deviation','m·s','A'],vertical_travel_m:['Total vertical travel','m','L'],changed_aircraft_count:['Changed aircraft','aircraft','N'],reversal_count:['Vertical-direction reversals','reversals','R'],max_altitude_excursion_m:['Maximum altitude excursion','m','Excursion']};
let qualityCache='';
function selectedQualityEntry(){return qualityEntries.get(selectedAlternative)||null;}
function selectedPlanRun(){return selectedQualityEntry()?.run||planning.steps[planning.steps.length-1].run;}
function selectAlternative(id){if(!qualityEntries.has(id))return;selectedAlternative=id;profileCache='';qualityCache='';setViewMode('final');}
function renderQuality(){
 if(!qualityData)return;
 const entry=selectedQualityEntry(),reference=qualityEntries.get('reference'),key=[selectedAlternative,viewMode,$('quality-x').value,$('quality-y').value,$('quality-scatter').getBoundingClientRect().width].join('|');
 if(qualityCache===key)return;qualityCache=key;
 $('alternative-select').value=selectedAlternative;
 if(qualityData.endpoint_bounds){const b=qualityData.endpoint_bounds,g=entry.endpoint_gaps_m;$('endpoint-gaps').textContent=`Scenario endpoint bounds: Dmax ≥ ${fmt(b.max_endpoint_deviation_lower_bound_m,0)} m; Dtotal ≥ ${fmt(b.total_endpoint_deviation_lower_bound_m,0)} m. Selected gaps: ${fmt(g.max_endpoint_deviation_m,0)} m / ${fmt(g.total_endpoint_deviation_m,0)} m. ${g.max_endpoint_deviation_m===0&&g.total_endpoint_deviation_m===0?'Both valid endpoint bounds attained by this verified plan.':'A lower bound alone does not establish attainability.'} Changed aircraft vs reference: ${entry.quality.changed_aircraft_count-reference.quality.changed_aircraft_count}; vs immediate search parent: ${entry.changed_aircraft_delta_from_parent??'earlier plan'}.`;
 if(entry.first_endpoint_comparison){const c=entry.first_endpoint_comparison;$('endpoint-gaps').textContent+=` Compared with first-pass endpoint plan: ${c.changed_aircraft_delta>=0?'+':''}${c.changed_aircraft_delta} changed aircraft; added ${c.additional_aircraft.join(', ')||'none'}; restored ${c.restored_aircraft.join(', ')||'none'}.`;}
 $('target-excursions').textContent=['F004','F018','F031','F034'].map(fid=>{const q=entry.quality.per_aircraft.find(r=>r.flight_id===fid),r=reference.quality.per_aircraft.find(r=>r.flight_id===fid);return `${fid} excursion ${fmt(r.max_altitude_excursion_m,0)} → ${fmt(q.max_altitude_excursion_m,0)} m`;}).join(' · ');}
 $('quality-status').textContent=`Selected: ${entry.group||'first_pass'} / ${entry.label} · independently verified · ${entry.verification.violation_count} violations / ${entry.verification.unresolved_count} unresolved · terminal vz = 0 · ${entry.pareto_member?'retained Pareto member':`dominated under seven objectives by ${(entry.dominated_by||[]).join(', ')}`}. ${viewMode==='replay'?'Map/profiles currently show the unchanged reference search replay. Select a solution to return to its verified final view.':viewMode==='baseline'?'Map shows the original baseline; profiles overlay the selected verified solution.':'Map and profiles show the selected verified solution.'}`;
 $('quality-metrics').replaceChildren(...qualityData.objectives.map(field=>{const [label,unit]=qualityLabels[field];
  const tr=document.createElement('tr');tr.dataset.metric=field;
  for(const value of [label+' ('+unit+')',fmt(reference.quality[field],field.endsWith('_count')?0:3),fmt(entry.quality[field],field.endsWith('_count')?0:3),fmt(entry.differences_from_reference[field],field.endsWith('_count')?0:3)]){const td=document.createElement('td');td.textContent=value;tr.append(td);}return tr;
 }));
 const experiment=qualityData.experiment,scales=['max_endpoint_deviation_m','total_endpoint_deviation_m','accumulated_altitude_deviation_m_s','vertical_travel_m'].map(k=>fmt(experiment.reference_scales[k],0)+' '+qualityLabels[k][1]).join(', '),weights=['max_endpoint_deviation_m','total_endpoint_deviation_m','accumulated_altitude_deviation_m_s','vertical_travel_m'].map(k=>fmt(experiment.weights[k],2)).join(' / ');
 $('experimental-score').textContent=`Experimental J: ${fmt(entry.experimental_J.value,6)} (reference ${fmt(reference.experimental_J.value,6)}). Frozen scales: ${scales}; weights ${weights}. Comparison only; it is not the search objective or archive filter.`;
 const s=qualityData.search;
 $('quality-limits').textContent=`Bounded search: ${s.candidate_evaluations}/${s.limits.max_candidate_evaluations} candidate evaluations; ${s.independent_verifications}/${s.limits.max_independent_verifications} independent verifications; runtime guard ${s.limits.max_seconds} s. Retained archive ${s.archive_size}/${s.limits.max_archive_size}; capacity-pruning operations ${s.archive_pruning.length}. Stop: ${s.stop_reason}. No global optimality claim beyond attained scenario endpoint bounds.`;
 for(const row of $('quality-solutions').children)row.classList.toggle('quality-selected',row.dataset.solution===selectedAlternative);
 const svg=$('quality-scatter'),W=Math.max(260,svg.getBoundingClientRect().width),H=230,L=64,R=20,T=25,B=44;
 svg.replaceChildren();svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
 const xfield=$('quality-x').value,yfield=$('quality-y').value,entries=qualityData.entries;
 let xmin=Math.min(...entries.map(e=>e.quality[xfield])),xmax=Math.max(...entries.map(e=>e.quality[xfield])),ymin=Math.min(...entries.map(e=>e.quality[yfield])),ymax=Math.max(...entries.map(e=>e.quality[yfield]));
 const xp=Math.max(1,(xmax-xmin)*.08),yp=Math.max(1,(ymax-ymin)*.08);xmin-=xp;xmax+=xp;ymin-=yp;ymax+=yp;
 const x=v=>L+(v-xmin)/(xmax-xmin)*(W-L-R),y=v=>H-B-(v-ymin)/(ymax-ymin)*(H-T-B);
 const short=v=>Math.abs(v)>=1e6?fmt(v/1e6,2)+'M':fmt(v,0);
 for(let i=0;i<=4;i++){
  const v=ymin+(ymax-ymin)*i/4;svg.append(svgNode('line',{x1:L,x2:W-R,y1:y(v),y2:y(v),stroke:'#34445a'}));svgText(svg,L-8,y(v)+4,short(v),{'text-anchor':'end'});
 }
 for(const fraction of [0,.5,1]){const v=xmin+(xmax-xmin)*fraction;svgText(svg,x(v),H-B+17,short(v),{'text-anchor':'middle'});}
 svgText(svg,L,T-10,qualityLabels[yfield][2]+' ('+qualityLabels[yfield][1]+')');svgText(svg,(L+W-R)/2,H-6,qualityLabels[xfield][2]+' ('+qualityLabels[xfield][1]+') · lower is better',{'text-anchor':'middle'});
 for(const e of entries){const point=svgNode('circle',{cx:x(e.quality[xfield]),cy:y(e.quality[yfield]),r:e.id===selectedAlternative?7:5,fill:e.is_reference?'#131f30':'#87dfef',stroke:e.is_reference?'#fbbf24':e.id===selectedAlternative?'#fff':'#87dfef','stroke-width':2,role:'button',tabindex:0,'aria-label':`${e.label}: ${qualityLabels[xfield][2]} ${e.quality[xfield]}, ${qualityLabels[yfield][2]} ${e.quality[yfield]}`,'data-solution':e.id});point.append(svgNode('title',{},`${e.label} · ${e.pareto_member?'Pareto':'reference comparison'}`));point.onclick=()=>selectAlternative(e.id);point.onkeydown=event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();selectAlternative(e.id);}};svg.append(point);}
}
function initQuality(){
 if(!qualityData)return;
 $('quality-panel').hidden=false;
 $('alternative-select').replaceChildren(...qualityData.entries.map(e=>{const o=document.createElement('option');o.value=e.id;o.textContent=e.is_reference?'Unchanged verified reference':`${e.group==='second_pass'?'Second pass':'First pass'} / ${e.id} · Dmax ${fmt(e.quality.max_endpoint_deviation_m,0)} m · N ${e.quality.changed_aircraft_count}`;return o;}));
 $('alternative-select').onchange=e=>selectAlternative(e.target.value);
 for(const id of ['quality-x','quality-y']){fillSelect(id,qualityData.objectives.map(key=>({id:key,label:qualityLabels[key][0]})));$(id).onchange=()=>{qualityCache='';renderQuality();};}
 $('quality-x').value='max_endpoint_deviation_m';$('quality-y').value='vertical_travel_m';
 $('quality-solutions').replaceChildren(...qualityData.entries.map(e=>{
  const row=document.createElement('tr');row.dataset.solution=e.id;const td=document.createElement('td'),b=document.createElement('button');b.textContent=e.is_reference?'Reference':`${e.group==='second_pass'?'Second pass':'First pass'} / ${e.id}`;b.onclick=()=>selectAlternative(e.id);td.append(b);row.append(td);
  for(const value of [e.pareto_member?'Yes':'No',...qualityData.objectives.map(key=>fmt(e.quality[key],key.endsWith('_count')?0:3))]){const td=document.createElement('td');td.textContent=value;row.append(td);}return row;
 }));
 new ResizeObserver(()=>{qualityCache='';renderQuality();}).observe($('quality-panel'));
}
