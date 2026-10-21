// Evidence and certificates are prepared by Python; these controls only present them.
function initSubmission(){
  const e=DATA.submission;if(!e)return;
  $('submission-panel').hidden=false;
  const q=e.quality,w=e.excursion_bounds.strongest;
  $('submission-metrics').replaceChildren(...[
    ['Nominal conflicts',`${e.original_baseline_event_count} → ${e.verification.violation_count}`],
    ['Worst endpoint deviation',`${fmt(q.max_endpoint_deviation_m,0)} m · optimal*`],
    ['Total endpoint deviation',`${fmt(q.total_endpoint_deviation_m,0)} m · optimal*`],
    ['Aircraft retained',`${e.verification.aircraft_count} / ${e.verification.aircraft_count}`]
  ].map(([label,value])=>{const div=document.createElement('div');div.className='summary-cell';div.append(document.createTextNode(label));const strong=document.createElement('strong');strong.textContent=value;div.append(strong);return div;}));
  $('submission-excursion').textContent=`Why the large climbs? At ${fmt(w.time_s,2)} s, ${w.flight_id}'s fixed horizontal route passes close to the drone. The lower side of the sphere is below the allowed altitude floor, so it must reach at least ${fmt(w.required_altitude_lower_m,2)} m altitude: an excursion of at least ${fmt(w.excursion_lower_m,2)} m. The selected plan's fleet maximum is ${fmt(q.max_altitude_excursion_m,0)} m. This geometric bound does not include all maneuver and traffic constraints.`;
  const probe=e.endpoint_error_probe.witnesses;
  $('submission-sensitivity').textContent=`Where the guarantee ends: ${probe.length} terminal pairs have a counterexample under opposing ${fmt(e.selection.endpoint_altitude_error_probe_m,0)} m altitude errors (${probe.length?fmt(probe[0].nominal_separation_m,0)+' → '+fmt(probe[0].possible_separation_m,0)+' m separation':'no witness found'}). Rechecking these unchanged controls with the alternative ${fmt(e.vertical_reference_sensitivity.vertical_m,1)} m vertical threshold produces ${e.vertical_reference_sensitivity.violation_count} events and ${e.vertical_reference_sensitivity.unresolved_count} unresolved checks. These are separate diagnostics, not the bounded-stress trajectory model.`;
  $('submission-export').textContent=`Selected ${e.selected_id} · ${fmt(e.sampled_csv.rows,0)} trajectory rows, all 40 aircraft at every output time, including every segment join. Safety comes from ${e.verification.pair_checks} continuous pair checks and ${e.verification.aircraft_checks} aircraft/zone/motion checks, not from these samples.`;
  function inspect(fid,t){
    playing=false;updatePlay();selectAlternative(e.selected_id);
    selected=fid;$('flight-select').value=fid;profileCache='';setTime(t);fit('all');
    $('map').scrollIntoView({behavior:'smooth',block:'center'});
  }
  $('show-recommended').onclick=()=>{selectAlternative(e.selected_id);$('map').scrollIntoView({behavior:'smooth',block:'center'});};
  $('show-endpoint-proof').onclick=()=>inspect(e.endpoint_bounds.disjoint_pairs[0].aircraft[0],DURATION);
  $('show-climb-proof').onclick=()=>inspect(w.flight_id,w.time_s);
  $('show-original-conflict').onclick=()=>{
    playing=false;updatePlay();setViewMode('baseline');
    ['profile-select','mode-select','variant-select'].forEach((id,i)=>$(id).value=['metric','nominal','base'][i]);chooseRun();
    jumpToEvent(activeRun.events[0]);$('map').scrollIntoView({behavior:'smooth',block:'center'});
  };
}
initSubmission();
