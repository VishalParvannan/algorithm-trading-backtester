// Manage backtest configuration, saved drafts, research jobs, and result charts.
const $ = selector => document.querySelector(selector);
let result = null, view = 'equity', page = 0, definitions = JSON.parse($('#dashboard-catalog').textContent), csvText = '', csvGeneration = 0;
const storageKey = window.accountStorageKey?.('quantlab.workspace.v1') || 'quantlab.workspace.v1';
const savedFields = ['sensitivity_parameter','robustness_mode','walk_folds','source','ticker','strategy','start','end','periods_per_year','market_calendar','capital','commission','slippage','outputsize','allocation','execution_price','share_mode','compare_mode','holdout_mode','train_percent'];
let draft = {fields: {}, parameters: {}}, activeStrategy = null, csvName = '';
let draftTimer = null, edited = false;
let runningJob = null;
let backtestRunning = false;

function loadDraft() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    if (saved && typeof saved.fields === 'object' && saved.fields && typeof saved.parameters === 'object' && saved.parameters) {
      draft = saved;
      csvText = typeof saved.csvText === 'string' ? saved.csvText : '';
      csvName = typeof saved.csvName === 'string' ? saved.csvName : '';
    }
  } catch { /* A missing or damaged draft leaves the initial controls usable. */ }
}
function rememberParameters() {
  if (!activeStrategy) return;
  const values = {};
  for (const input of document.querySelectorAll('#parameters input[name]')) values[input.name] = input.value;
  draft.parameters[activeStrategy] = values;
}
function saveDraft() {
  window.updateResearchContext?.();
  edited = true;
  rememberParameters();
  for (const name of savedFields) {
    const input = $(`[name=${name}]`);
    if (input) draft.fields[name] = input.value;
  }
  draft.csvText = csvText; draft.csvName = csvName;
  draft.updatedAt = new Date().toISOString();
  try {
    localStorage.setItem(storageKey, JSON.stringify(draft));
    $('#save-status').textContent = 'Configuration saved on this browser';
  } catch {
    $('#save-status').textContent = 'Could not save locally. Browser storage may be full or unavailable.';
  }
  clearTimeout(draftTimer);
  draftTimer = setTimeout(async () => {
    try { await fetch('/api/draft', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(draft)}); } catch { /* Browser draft remains available offline. */ }
  }, 500);
}
function restoreDraft() {
  for (const name of savedFields) {
    const input = $(`[name=${name}]`), value = draft.fields[name];
    if (!input || typeof value !== 'string') continue;
    if (input.tagName === 'SELECT' && !Array.from(input.options).some(option => option.value === value)) continue;
    input.value = value;
  }
  if (!draft.fields.source) $('#source').value = 'market';
  if (csvText) $('#csv-status').textContent = `${csvName || 'Saved CSV'} restored from this browser. Ready to run.`;
}
const money = value => new Intl.NumberFormat('en-US', {style:'currency', currency:'USD', maximumFractionDigits:2}).format(value);
const pct = value => value == null ? '—' : `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`;
function parameters() {
  if (!definitions) return;
  rememberParameters();
  const strategy = definitions.strategies.find(s => s.id === $('#strategy').value);
  window.updateResearchParameters?.(strategy.parameters);
  $('#parameters').innerHTML = strategy.parameters.length ? `<div class="field-row">${strategy.parameters.map(p => `<label>${p.label}<input name="${p.name}" type="number" min="${p.min}" max="${p.max}" step="${p.step}" value="${p.default}" required></label>`).join('')}</div>` : '<p class="strategy-description">No parameters needed. Ready to test.</p>';
  $('#strategy-description').textContent = strategy.description;
  activeStrategy = strategy.id;
  for (const input of document.querySelectorAll('#parameters input[name]')) {
    const value = draft.parameters[strategy.id]?.[input.name];
    if (typeof value === 'string') input.value = value;
  }
}
$('#strategy').addEventListener('change', parameters);
function sourceSettings(changed = false) {
  const source = definitions.sources.find(s => s.id === $('#source').value);
  $('#source-note').textContent = source.note;
  for (const [id, active] of [['alpha-settings',source.id === 'alpha'], ['csv-settings',source.id === 'csv']]) {
    $(`#${id}`).hidden = !active;
    document.querySelectorAll(`#${id} input, #${id} select`).forEach(input => input.disabled = !active);
  }
  const ticker = $('[name=ticker]'); ticker.placeholder = source.example;
  if (changed) {
    const isDefault = ['SPY','BTC-USD','IBM','CUSTOM'].includes(ticker.value);
    if (isDefault) ticker.value = source.example;
    $('#calendar').value = source.id === 'coinbase' ? '365' : '252';
    if (source.id === 'alpha' && $('#outputsize').value === 'compact') recentDates();
  }

  window.updateAssetPicker?.();
}
function recentDates() {
  const end = new Date(); end.setDate(end.getDate()-1);
  const start = new Date(end); start.setDate(start.getDate()-90);
  const localDate = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  $('[name=start]').value = localDate(start); $('[name=end]').value = localDate(end);
}
$('#source').addEventListener('change', () => sourceSettings(true));
$('#outputsize').addEventListener('change', () => { if ($('#outputsize').value === 'compact') recentDates(); });
$('#csv-file').addEventListener('change', async () => {
  const generation = ++csvGeneration; csvText = '';
  csvName = ''; saveDraft();
  const file = $('#csv-file').files[0]; $('#csv-status').textContent = '';
  if (!file) return;
  if (file.size > 2000000) { $('#csv-status').textContent = 'Choose a CSV smaller than 2 MB.'; return; }
  $('#csv-status').textContent = 'Reading file…';
  try {
    const text = await file.text(); if (generation !== csvGeneration) return;
    csvText = text; csvName = file.name; $('#csv-status').textContent = `${file.name} is ready. Set the date range to match your file.`;
    // Only suggest a range for recognizable ISO date columns; the server validates the file.
    const lines = text.trim().split(/\r?\n/), headers = lines[0].replace(/^﻿/,'').split(',').map(h => h.trim().replace(/^"|"$/g,'').toLowerCase());
    const column = headers.findIndex(h => ['date','timestamp','datetime'].includes(h));
    if (column >= 0) {
      const dates = lines.slice(1).map(line => line.split(',')[column]?.trim().replace(/^"|"$/g,'')).filter(d => /^\d{4}-\d{2}-\d{2}$/.test(d)).sort();
      if (dates.length) { $('[name=start]').value = dates[0]; $('[name=end]').value = dates.at(-1); }
    }
    saveDraft();
  } catch { $('#csv-status').textContent = 'Could not read this file. Select it again.'; }
});
function download(text, filename) {
  const url = URL.createObjectURL(new Blob([text], {type:'text/csv'}));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('#csv-template').onclick = () => download('Date,Open,High,Low,Close,Volume\n2025-01-02,100,103,99,102,10000\n2025-01-03,102,105,101,104,12000\n2025-01-06,104,106,102,103,9000\n2025-01-07,103,108,102,103,14000\n2025-01-08,107,109,105,108,11000\n','quantlab-example.csv');
async function run(event) {
  event?.preventDefault();
  if(backtestRunning)return;
  backtestRunning=true;
  $('#research-run').disabled=true;
  $('#research-status').textContent='Running selected analyses…';
  saveDraft();
  const button = $('#run'); button.disabled = true; button.textContent = 'Running experiment…'; $('#error').hidden = true; $('#result-status').textContent = 'Running';
  try {
    const config = Object.fromEntries(new FormData($('#config')));
    config.compare_strategies = config.compare_mode === 'all' ? definitions.strategies.map(s => s.id) : [];
    config.holdout = config.holdout_mode === 'holdout';
    config.robustness = config.robustness_mode === 'enabled';
    if (config.source === 'csv') { if (!csvText) throw new Error('Select a CSV file and wait until it is ready.'); config.csv_text = csvText; }
    let response = await fetch('/api/jobs', {method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
    let data;
    if (response.status === 404) {
      response = await fetch('/api/backtest', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
      data = await response.json();
    } else {
      data = await response.json();
    }
    if (response.status === 202 && response.ok) {
      runningJob = data.id; $('#cancel-run').hidden = false;
      while (true) {
        await new Promise(resolve=>setTimeout(resolve,400));
        const progress = await fetch(`/api/jobs/${runningJob}`);
        if (!progress.ok) throw new Error('The run could not be found. The server may have restarted.');
        const job = await progress.json();
        $('#result-status').textContent = job.state === 'queued' ? 'Queued' : 'Running';
        $('#research-status').textContent=job.state==='queued'?'Research queued…':'Research running…';
        if (job.state === 'complete') {data=job.result;break;}
        if (job.state === 'failed') throw new Error(job.error || 'Backtest failed.');
        if (job.state === 'cancelled') throw new Error('Backtest cancelled.');
      }
    }
    if (!response.ok) throw new Error(data.error || data.detail || 'Could not run backtest.');
    result = data; page = 0; render(); $('#export').disabled = result.demo;
    $('#research-status').textContent=`Results: ${result.ticker} · ${result.strategy_name} · ${result.dates[0]} to ${result.dates.at(-1)}.`;
    if (!result.demo) refreshHistory();
  } catch(error) { $('#error').textContent = error.message; $('#error').hidden = false; $('#research-status').textContent=error.message; $('#result-status').textContent = result ? 'Previous result' : 'Run failed'; }
  finally {backtestRunning=false;$('#research-run').disabled=false;runningJob=null;$('#cancel-run').hidden=true;button.disabled = false; button.innerHTML = '<span>▶</span> Run backtest <span>↗</span>';}
}
$('#cancel-run').onclick=async()=>{
  if(!runningJob)return;
  try {await fetch(`/api/jobs/${runningJob}/cancel`,{method:'POST'});}catch{$('#error').hidden=false;$('#error').textContent='Could not cancel. Check the server connection.';}
};
$('#config').addEventListener('submit', run);
$('#config').addEventListener('input', saveDraft);
$('#config').addEventListener('change', saveDraft);
function render() {
  const m = result.metrics;
  const strategyName = result.strategy_name || definitions.strategies.find(s => s.id === result.strategy)?.name || 'Experiment';
  $('#result-title').textContent = `${result.demo ? 'Sample market' : result.ticker} · ${strategyName}`;
  $('#result-period').textContent = `${result.dates[0]} — ${result.dates.at(-1)}`;
  $('#result-status').textContent = result.demo ? 'Sample complete' : 'Backtest complete';
  const cards = [['Total return',pct(m.total_return),'Across the full period',m.total_return],['Annual return',pct(m.cagr),'Compounded annual growth',m.cagr],['Sharpe ratio',m.sharpe_ratio?.toFixed(2) ?? '—','Risk-adjusted performance',m.sharpe_ratio],['Max drawdown',pct(m.max_drawdown),'Largest peak-to-trough decline',m.max_drawdown]];
  $('#metrics').innerHTML = cards.map(([label,value,note,sign]) => `<article class="metric"><div class="metric-label">${label}<span>↗</span></div><div class="metric-value ${sign >= 0 ? 'positive' : 'negative'}">${value}</div><div class="metric-note">${note}</div></article>`).join('');
  $('#final-value').textContent = money(result.equity.at(-1)); $('#return-chip').textContent = pct(m.total_return);
  $('#data-label').textContent = `${result.source_name || (result.demo ? 'Synthetic sample' : 'Yahoo Finance')} · ${result.periods_per_year || 252} bars/year`;
  const warnings = $('#result-warnings'); warnings.replaceChildren(); warnings.hidden = !(result.warnings || []).length;
  for (const warning of result.warnings || []) { const p = document.createElement('p'); p.textContent = warning; warnings.append(p); }
  $('#trade-count').textContent = result.demo ? 0 : result.trades.length;
  chart(); trades();
  researchResults();
}
function rows(selector, records) {
  const body = $(selector); body.replaceChildren();
  for (const values of records) { const tr = document.createElement('tr'); for (const value of values) { const td = document.createElement('td'); td.textContent = value; tr.append(td); } body.append(tr); }
}
function researchResults() {
  window.renderRobustness?.(result.robustness);
  const summary = result.trade_summary;
  $('#trade-analysis').hidden = result.demo || !summary;
  if (summary && !result.demo) {
    const factor = summary.profit_factor_no_losses ? 'No losing trades' : summary.profit_factor?.toFixed(2) ?? '—';
    $('#trade-statistics').innerHTML = [['Closed trades',summary.completed_trades],['Win rate',summary.win_rate == null ? '—' : (summary.win_rate*100).toFixed(1)+'%'],['Profit factor',factor],['Realized P&L',money(summary.realized_pnl)],['Open shares',summary.open_quantity.toFixed(3)]].map(([label,value])=>`<div>${label}<strong>${value}</strong></div>`).join('');
    rows('#completed-body', (result.completed_trades || []).slice().reverse().map(t=>[t.entry_date,t.exit_date,t.quantity.toFixed(3),money(t.net_pnl),t.return_pct.toFixed(2)+'%',t.holding_days]));
  }
  $('#comparison-panel').hidden = !(result.comparison || []).length;
  rows('#comparison-body',(result.comparison || []).map(r=>[r.name,pct(r.metrics.total_return),r.metrics.sharpe_ratio?.toFixed(2)??'—',pct(r.metrics.max_drawdown),r.n_executions]));
  $('#holdout-panel').hidden = !result.holdout;
  if (result.holdout) { $('#holdout-description').textContent=result.holdout.method; rows('#holdout-body',result.holdout.periods.map(r=>[r.name,`${r.start} — ${r.end}`,r.bars,pct(r.metrics.total_return),r.metrics.sharpe_ratio?.toFixed(2)??'—'])); }
}
async function refreshHistory() {
  try {
    const response = await fetch('/api/experiments'); if (!response.ok) throw new Error('Saved history needs the updated server.');
    const items = await response.json();
    window.refreshComparisonChoices?.(items);
    $('#saved-experiment').replaceChildren(new Option(items.length ? 'Choose an experiment' : 'No saved experiments yet',''),...items.map(r=>new Option(`${r.ticker} · ${r.strategy} · ${r.start} — ${r.end}`,r.id)));
    $('#history-status').textContent = `${items.length} saved experiments`;
  } catch (error) { $('#history-status').textContent=error.message; }
}
async function openExperiment(replay=false) {
  const id=$('#saved-experiment').value;if(!id)return;
  try {
    $('#history-status').textContent=replay?'Replaying the exact data snapshot…':'Loading…';
    const response=await fetch(replay?'/api/replay':`/api/experiments/${id}`,replay?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}:{});
    const record=await response.json();if(!response.ok)throw new Error(record.error || record.detail || 'Could not open experiment.');
    result=replay?record:record.result;page=0;render();$('#export').disabled=result.demo;
    window.navigateWorkspace?.('backtest');
    $('#history-status').textContent=replay?'Replay complete; no provider download was needed.':'Saved result opened. Current input settings are unchanged.';
  } catch(error){$('#history-status').textContent=error.message;}
}
$('#refresh-history').onclick=refreshHistory;
$('#load-experiment').onclick=()=>openExperiment();
$('#replay-experiment').onclick=()=>openExperiment(true);
function chart() {
  if (!result) return;
  const wrap = $('#chart'), width = Math.max(wrap.clientWidth, 260), height = wrap.clientHeight;
  const left=58, right=12, top=18, bottom=30, values=view === 'equity' ? result.equity : result.drawdown;
  const all=view === 'equity' ? [...values,...result.benchmark] : [...values,0];
  let min=Math.min(...all), max=Math.max(...all); const pad=(max-min)*.12 || 1; min-=pad; max+=pad;
  const x=i => left+i/(values.length-1)*(width-left-right), y=v => top+(max-v)/(max-min)*(height-top-bottom);
  const path = data => data.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${view === 'equity' ? 'Strategy equity compared with buy and hold' : 'Portfolio drawdown percentage'}"><defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#159778" stop-opacity=".13"/><stop offset="1" stop-color="#159778" stop-opacity="0"/></linearGradient></defs>`;
  for(let i=0;i<5;i++){const v=min+(max-min)*i/4;svg+=`<line x1="${left}" y1="${y(v)}" x2="${width-right}" y2="${y(v)}" stroke="#edf1f4" stroke-dasharray="3 4"/><text x="${left-10}" y="${y(v)+3}" text-anchor="end" fill="#9aa7b4" font-size="9">${view==='equity'?`$${(v/1000).toFixed(1)}k`:`${v.toFixed(1)}%`}</text>`;}
  svg+=`<path d="${path(values)} L${x(values.length-1)},${view==='equity'?height-bottom:y(0)} L${left},${view==='equity'?height-bottom:y(0)} Z" fill="url(#area)"/>`;
  if(view==='equity') svg+=`<path d="${path(result.benchmark)}" fill="none" stroke="#b0bdca" stroke-width="1.6" stroke-dasharray="5 4"/>`;
  svg+=`<path d="${path(values)}" fill="none" stroke="#168b73" stroke-width="2.1" stroke-linejoin="round"/>`;
  for(let i=0;i<5;i++){const index=Math.round((values.length-1)*i/4);svg+=`<text x="${x(index)}" y="${height-7}" text-anchor="${i===0?'start':i===4?'end':'middle'}" fill="#9aa7b4" font-size="9">${new Date(result.dates[index]+'T00:00:00').toLocaleDateString('en-US',{month:'short',year:'2-digit'})}</text>`;}
  svg+='<line id="hover-line" stroke="#8eaea1" stroke-dasharray="3 3" visibility="hidden"/><circle id="hover-dot" r="4" fill="#168b73" stroke="white" stroke-width="2" visibility="hidden"/></svg>';wrap.innerHTML=svg;
  $('#benchmark-legend').hidden=view!=='equity';
  wrap.onpointermove=event=>{const box=wrap.getBoundingClientRect(), index=Math.max(0,Math.min(values.length-1,Math.round((event.clientX-box.left-left)/(width-left-right)*(values.length-1)))); const line=$('#hover-line'),dot=$('#hover-dot'); line.setAttribute('x1',x(index));line.setAttribute('x2',x(index));line.setAttribute('y1',top);line.setAttribute('y2',height-bottom);line.setAttribute('visibility','visible');dot.setAttribute('cx',x(index));dot.setAttribute('cy',y(values[index]));dot.setAttribute('visibility','visible');const tooltip=$('#chart-tooltip');tooltip.hidden=false;tooltip.textContent=`${result.dates[index]} · ${view==='equity'?money(values[index]):values[index].toFixed(2)+'%'}`;tooltip.style.left=`${Math.max(12, Math.min(x(index),width-190))}px`;tooltip.style.top='100px';};
  wrap.onpointerleave=()=>{$('#chart-tooltip').hidden=true;$('#hover-line').setAttribute('visibility','hidden');$('#hover-dot').setAttribute('visibility','hidden');};
}
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{view=button.dataset.view;document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button));});$('#chart-tooltip').hidden=true;chart();}));
function trades(){
  if(!result || result.demo){
    $('#trade-body').innerHTML = '<tr><td colspan="6" class="empty-trades">No trade history yet. Run a backtest with market data or your CSV to see executions.</td></tr>';
    $('#trade-range').textContent = 'No executions'; $('#trade-count').textContent = '0';
    $('#prev').disabled = true; $('#next').disabled = true;
    return;
  }
  const filter=$('#trade-filter').value,rows=result.trades.filter(t=>filter==='all'||t.side===filter).slice().reverse();
  page=Math.min(page,Math.max(0,Math.ceil(rows.length/5)-1)); const current=rows.slice(page*5,page*5+5),body=$('#trade-body');body.replaceChildren();
  for(const t of current){const row=document.createElement('tr');for(const value of [t.date,result.ticker,t.side,t.quantity.toFixed(3),money(t.price),money(t.commission)]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}const badge=document.createElement('span');badge.className='side'+(t.side==='Sell'?' sell':'');badge.textContent=t.side;row.children[2].replaceChildren(badge);body.append(row);}
  if(!current.length){const cell=document.createElement('td');cell.colSpan=6;cell.textContent='No trades for this selection. Try a longer period or different parameters.';const row=document.createElement('tr');row.append(cell);body.append(row);}
  $('#trade-range').textContent=rows.length?`Showing ${page*5+1}–${Math.min(page*5+5,rows.length)} of ${rows.length} executions`:'No executions';$('#prev').disabled=page===0;$('#next').disabled=(page+1)*5>=rows.length;
}
$('#trade-filter').addEventListener('change',()=>{page=0;trades();});$('#prev').onclick=()=>{page--;trades();};$('#next').onclick=()=>{page++;trades();};
$('#export').onclick=()=>{if(!result)return;const csv=['date,side,quantity,price,commission,slippage',...result.trades.map(t=>[t.date,t.side,t.quantity,t.price,t.commission,t.slippage].join(','))].join('\n');download(csv,`${result.demo?'sample':result.ticker}-trades.csv`);};
new ResizeObserver(()=>chart()).observe($('#chart'));
function emptyResults() {
  $('#metrics').innerHTML = ['Total return','Annual return','Sharpe ratio','Max drawdown'].map(label => `<article class="metric"><div class="metric-label">${label}</div><div class="metric-value">—</div><div class="metric-note">Run a backtest to view results</div></article>`).join('');
  $('#chart').innerHTML = '<div class="empty-chart"><strong>Your next experiment starts here</strong><p>Choose a data source and strategy, then run your backtest.</p></div>';
  $('#result-status').textContent = 'Ready to run'; $('#data-label').textContent = 'Awaiting your backtest';
  trades();
}
async function initialize() {
  loadDraft(); restoreDraft(); parameters(); sourceSettings(); emptyResults();
  let catalogError = '';
  try {
    const response = await fetch('/api/catalog'); if (!response.ok) throw new Error('Using the saved options. Restart the Python server to enable all new data sources and strategies.');
    const latest = await response.json();
    if (!Array.isArray(latest.sources) || !Array.isArray(latest.strategies)) throw new Error('Using the saved options because the server catalog could not be loaded. Restart the Python server.');
    definitions = latest;
    for (const [selector, items] of [['#source',definitions.sources], ['#strategy',definitions.strategies]]) {
      $(selector).replaceChildren(...items.map(item => new Option(item.name, item.id)));
    }
    restoreDraft(); parameters(); sourceSettings();
  } catch (error) { catalogError = error.message; }
  $('#run').disabled = false;
  if (catalogError) { $('#error').hidden = false; $('#error').textContent = catalogError; }
  refreshHistory();
  try {
    const response=await fetch('/api/draft');const saved=response.ok?await response.json():null;
    if(saved && !edited && (!localStorageDraftExists() || (saved.updatedAt && saved.updatedAt > (draft.updatedAt || '')))) {draft=saved;csvText=saved.csvText||'';csvName=saved.csvName||'';activeStrategy=null;restoreDraft();parameters();sourceSettings();}
  } catch { /* Local-only state still works. */ }

  window.updateAssetPicker?.();
}
function localStorageDraftExists(){try{return !!localStorage.getItem(storageKey);}catch{return false;}}
initialize();

// Asset picker: loaded with the main dashboard so older local servers can serve it.
(() => {
  const input = document.getElementById('asset-search');
  if (!input) return;
  const ticker = document.getElementById('ticker-input');
  const source = document.getElementById('source');
  const panel = document.getElementById('asset-suggestions');
  const list = document.getElementById('asset-options');
  const note = document.getElementById('asset-search-note');
  const caption = document.getElementById('asset-selection');
  const picker = document.getElementById('asset-picker');
  const toggle = document.getElementById('asset-toggle');
  const assets = JSON.parse(document.getElementById('dashboard-catalog').textContent).assets || [];
  let results = [], active = -1, generation = 0, timer;
  const valid = symbol => /[A-Z]/.test(symbol) && /^[A-Z0-9.\-^=]{1,16}$/.test(symbol) && (source.value !== 'coinbase' || /^[A-Z0-9]+-USD$/.test(symbol));
  const available = () => assets.filter(asset => source.value === 'coinbase' ? asset.type === 'Crypto' : source.value === 'alpha' ? asset.type !== 'Crypto' : source.value !== 'csv');
  function close() {
    panel.hidden = true; input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant'); active = -1;
  }
  function choose(asset) {
    generation++; clearTimeout(timer);
    ticker.value = asset.symbol; input.value = asset.symbol;
    input.setCustomValidity(''); caption.textContent = `${asset.symbol} · ${asset.name}`;
    close(); ticker.dispatchEvent(new Event('input', {bubbles: true}));
  }
  function highlight(index) {
    active = index;
    [...list.children].forEach((child, i) => child.setAttribute('aria-selected', String(i === active)));
    if (active >= 0) {
      input.setAttribute('aria-activedescendant', `asset-option-${active}`);
      list.children[active]?.scrollIntoView?.({block: 'nearest'});
    }
  }
  function render(items, message = '') {
    results = items.slice(0, 15); active = -1; list.replaceChildren();
    input.removeAttribute('aria-activedescendant');
    for (const [index, asset] of results.entries()) {
      const option = document.createElement('button');
      option.type = 'button'; option.tabIndex = -1; option.id = `asset-option-${index}`;
      option.className = 'asset-option'; option.setAttribute('role', 'option'); option.setAttribute('aria-selected', 'false');
      const symbol = document.createElement('strong'); symbol.textContent = asset.symbol;
      const name = document.createElement('span'); name.textContent = asset.name;
      const type = document.createElement('small'); type.textContent = asset.type;
      option.append(symbol, name, type);
      option.addEventListener('mousedown', event => event.preventDefault());
      option.addEventListener('click', () => choose(asset)); list.append(option);
    }
    note.textContent = message || (results.length ? 'Use ↑ ↓ and Enter to select an asset.' : 'No matches. Try another name or symbol.');
    panel.hidden = false; input.setAttribute('aria-expanded', 'true');
  }
  function local(query) {
    const needle = query.toUpperCase();
    const items = available().filter(asset => `${asset.symbol} ${asset.name}`.toUpperCase().includes(needle));
    items.sort((a, b) => Number(b.symbol === needle) - Number(a.symbol === needle) || Number(b.symbol.startsWith(needle)) - Number(a.symbol.startsWith(needle)));
    if (needle && valid(needle) && !items.some(asset => asset.symbol === needle)) items.push({symbol: needle, name: 'Use this symbol (availability checked when you run)', type: 'Custom'});
    return items;
  }
  function search(query) {
    const request = ++generation; clearTimeout(timer); render(local(query));
    if (source.value === 'csv' || source.value === 'demo') return;
    const provider = source.value;
    timer = setTimeout(async () => {
      try {
        const response = await fetch('/api/assets/search', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({source: provider, query})});
        if (!response.ok) throw Error('Search unavailable');
        const data = await response.json();
        if (request !== generation || panel.hidden) return;
        const merged = [...data.assets];
        for (const asset of local(query)) if (!merged.some(item => item.symbol === asset.symbol)) merged.push(asset);
        render(merged, data.warning || '');
      } catch {
        if (request === generation && !panel.hidden) render(local(query), 'Showing built-in matches. You can also select a custom symbol.');
      }
    }, 250);
  }
  input.addEventListener('focus', () => search(input.value === ticker.value ? '' : input.value.trim()));
  input.addEventListener('click', () => { if (panel.hidden) search(input.value === ticker.value ? '' : input.value.trim()); });
  toggle?.addEventListener('mousedown', event => event.preventDefault());
  toggle?.addEventListener('click', () => {
    if (!panel.hidden) { generation++; close(); }
    else { input.focus(); search(''); input.select(); }
  });
  input.addEventListener('input', () => {
    input.setCustomValidity('Choose an asset from the search results.');
    caption.textContent = 'Search by company name or ticker, then select a result.';
    search(input.value.trim());
  });
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') { generation++; close(); return; }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault(); if (panel.hidden) search(input.value.trim());
      if (results.length) highlight((active + (event.key === 'ArrowDown' ? 1 : -1) + results.length) % results.length);
    } else if (event.key === 'Enter' && !panel.hidden) {
      event.preventDefault(); if (results.length) choose(results[active >= 0 ? active : 0]);
    }
  });
  document.addEventListener('mousedown', event => { if (!picker.contains(event.target)) { generation++; close(); } });
  window.updateAssetPicker = () => {
    generation++; clearTimeout(timer); close();
    if (!valid(ticker.value.toUpperCase())) ticker.value = '';
    input.value = ticker.value;
    const asset = available().find(item => item.symbol === ticker.value);
    caption.textContent = asset ? `${asset.symbol} · ${asset.name}` : ticker.value ? `${ticker.value} · Custom symbol` : 'Search by company name or ticker, then select a result.';
    input.setCustomValidity(ticker.value ? '' : 'Choose an asset from the search results.');
  };
  window.updateAssetPicker();
})();
