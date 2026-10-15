// Display research results, compare saved experiments, and manage paper sessions.
(() => {
  const node=id=>document.getElementById(id);
  const percent=value=>value==null?'—':`${(value*100).toFixed(2)}%`;
  const number=value=>value==null?'—':Number(value).toFixed(2);
  try{const saved=localStorage.getItem(window.accountStorageKey?.('backtestLab.paperInterval')||'backtestLab.paperInterval');if(['1m','5m','1d'].includes(saved))node('paper-interval').value=saved;}catch{}
  node('paper-interval').onchange=()=>{try{localStorage.setItem(window.accountStorageKey?.('backtestLab.paperInterval')||'backtestLab.paperInterval',node('paper-interval').value);}catch{}};
  const researchActions=node('research-actions');researchActions.hidden=false;
  function researchContext(){
    const form=node('config');
    const field=name=>form.elements?.namedItem(name)?.value||'—';
    node('research-context').textContent=`Current setup: ${field('ticker')} · ${field('strategy')} · ${field('start')} to ${field('end')}. Results below belong to the last completed experiment.`;
  }
  window.updateResearchContext=researchContext;
  researchContext();
  node('research-run').onclick=async()=>{
    const get=name=>document.querySelector(`[name=${name}]`)?.value;
    if(get('robustness_mode')!=='enabled'&&get('compare_mode')!=='all'&&get('holdout_mode')!=='holdout'){
      node('research-status').textContent='Choose sensitivity + walk-forward, compare all strategies, or chronological holdout before running.';return;
    }
    if(!node('config').checkValidity()){
      window.navigateWorkspace?.('backtest');requestAnimationFrame(()=>node('config').reportValidity());return;
    }
    await run({preventDefault(){}});
  };
  window.updateResearchParameters=parameters=>{
    const select=node('sensitivity-parameter'),previous=select.value;
    select.replaceChildren(...(parameters.length?parameters.map(p=>new Option(p.label,p.name)):[new Option('No adjustable parameters','')]));
    const saved=typeof draft!=='undefined'?draft.fields.sensitivity_parameter:null;
    const preferred=parameters.some(p=>p.name===previous)?previous:saved;
    select.value=parameters.some(p=>p.name===preferred)?preferred:parameters[0]?.name||'';
    select.disabled=!parameters.length;
    const hint=node('sensitivity-hint');
    if(hint)hint.textContent=parameters.length?'Choose which strategy setting to vary; the other settings stay fixed.':'This strategy has no adjustable settings. Walk-forward tests can still evaluate its performance over time.';
  };
  const catalog=JSON.parse(node('dashboard-catalog').textContent);
  window.updateResearchParameters(catalog.strategies.find(s=>s.id===node('strategy').value)?.parameters||[]);
  function table(id,rows){
    const body=node(id);body.replaceChildren();
    for(const values of rows){const tr=document.createElement('tr');for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);}
  }
  window.renderRobustness=report=>{
    node('robustness-panel').hidden=!report;if(!report)return;
    node('robustness-description').textContent=report.method;
    node('sensitivity-title').textContent=report.parameter?`Sensitivity: ${report.parameter}`:'This strategy has no adjustable parameters';
    table('sensitivity-body',report.sensitivity.map(r=>[r.value??'Fixed',percent(r.metrics.total_return),number(r.metrics.sharpe_ratio),percent(r.metrics.max_drawdown)]));
    table('walk-body',report.folds.map(r=>[r.fold,`${r.train_start} – ${r.train_end}`,`${r.test_start} – ${r.test_end}`,r.selected_value??'Fixed',percent(r.training_return),percent(r.metrics.total_return),percent(r.metrics.max_drawdown)]));
    const chart=node('sensitivity-chart');chart.replaceChildren();
    const scale=Math.max(...report.sensitivity.map(r=>Math.abs(r.metrics.total_return||0)),.01);
    for(const row of report.sensitivity){
      const line=document.createElement('div');line.className='sensitivity-row';
      const label=document.createElement('span');label.textContent=row.value??'Fixed';
      const bar=document.createElement('i');bar.style.width=`${Math.abs(row.metrics.total_return||0)/scale*70}%`;bar.style.background=(row.metrics.total_return||0)>=0?'#168b73':'#c8866f';
      const value=document.createElement('span');value.textContent=percent(row.metrics.total_return);line.append(label,bar,value);chart.append(line);
    }
  };
  window.refreshComparisonChoices=items=>{
    const selected=new Set([...node('compare-saved').selectedOptions].map(o=>o.value));
    node('compare-saved').replaceChildren();
    for(const item of items){const option=new Option(`${item.ticker} · ${item.strategy} · ${item.start} – ${item.end}`,item.id);option.selected=selected.has(item.id);node('compare-saved').append(option);}
  };
  if(typeof refreshHistory==='function')refreshHistory();
  node('compare-saved-run').onclick=async()=>{
    const button=node('compare-saved-run');button.disabled=true;
    try{
      const ids=[...node('compare-saved').selectedOptions].map(o=>o.value);
      const response=await fetch('/api/experiments/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids,harmonize:node('compare-harmonize').checked})});
      const report=await response.json();if(!response.ok)throw Error(report.error||'Comparison failed.');
      node('saved-comparison-note').textContent=`${report.method} ${report.mismatches.length?`${report.harmonized?'Original differences corrected':'Differences to consider'}: ${report.mismatches.join(', ')}.`:'Matching prices and assumptions.'}`;
      table('saved-comparison-body',report.rows.map(({result:r})=>[r.ticker,r.strategy_name,percent(r.metrics.total_return),number(r.metrics.sharpe_ratio),percent(r.metrics.max_drawdown),number(r.equity.at(-1)),r.trades.length]));
    }catch(error){node('saved-comparison-note').textContent=error.message;}finally{button.disabled=false;}
  };
  let polling=false;
  async function refreshPaper(){
    if(polling)return;polling=true;
    try{
      const response=await fetch('/api/paper');if(!response.ok)throw Error('Paper trading needs the updated server.');
      const sessions=await response.json();
      const selected=node('paper-session').value;
      node('paper-session').replaceChildren(...sessions.map(s=>new Option(`${s.config.ticker} · ${s.config.strategy} · ${s.active?'Running':'Stopped'} · ${s.created}`,s.id)));
      if(sessions.some(s=>s.id===selected))node('paper-session').value=selected;
      const session=sessions.find(s=>s.id===node('paper-session').value)||sessions[0];
      node('paper-stop').disabled=!session?.active;
      if(!session){node('paper-note').textContent='No paper sessions yet. Configure an asset and strategy, then start.';table('paper-trades',[]);return;}
      node('paper-note').textContent=`${session.method} Sampling approximately every ${session.sample_interval||60} seconds. ${(session.candles||[]).length} completed candles; warm-up needs approximately ${session.warmup_observations||1} candles. ${session.error||''}`;
      node('paper-value').textContent=`Equity ${number(session.equity)} · Cash ${number(session.cash)} · Shares ${number(session.shares)} · ${session.currency||'Quote currency'} · ${session.active?'Running while server is open':'Stopped'}`;
      table('paper-trades',session.trades.slice(-50).reverse().map(t=>[t.timestamp,t.quantity>0?'Buy':'Sell',number(Math.abs(t.quantity)),number(t.price),number(t.commission)]));
      table('paper-actions-body',(session.corporate_actions||[]).slice(-50).reverse().map(event=>[event.effective,event.kind,number(event.value),number(event.shares_before),number(event.shares_after),number(event.cash_credit),event.model]));
    }catch(error){node('paper-note').textContent=error.message;}finally{polling=false;}
  }
  node('paper-start').onclick=async()=>{
    node('paper-start').disabled=true;
    try{
      const config=Object.fromEntries(new FormData(node('config')));
      config.paper_interval=node('paper-interval').value||'1m';
      const response=await fetch('/api/paper',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
      const session=await response.json();if(!response.ok)throw Error(session.error||'Could not start paper trading.');
      node('paper-session').value='';await refreshPaper();node('paper-session').value=session.id;await refreshPaper();
    }catch(error){node('paper-note').textContent=error.message;}finally{node('paper-start').disabled=false;}
  };
  node('paper-stop').onclick=async()=>{
    const id=node('paper-session').value;if(!id)return;
    try{const response=await fetch(`/api/paper/${id}/stop`,{method:'POST'});if(!response.ok)throw Error('Could not stop this paper session.');await refreshPaper();}
    catch(error){node('paper-note').textContent=error.message;}
  };
  node('paper-session').onchange=refreshPaper;node('paper-refresh').onclick=refreshPaper;
  const timer=setInterval(()=>{if(!document.hidden)refreshPaper();},5000);
  window.addEventListener('beforeunload',()=>clearInterval(timer));
  refreshPaper();
})();
