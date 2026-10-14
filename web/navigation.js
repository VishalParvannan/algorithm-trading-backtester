// Group dashboard panels into pages while preserving their state and event handlers.
(() => {
  const byId=id=>document.getElementById(id);
  const pages={
    backtest:{title:'Backtest',description:'Configure a strategy and inspect its historical performance.'},
    research:{title:'Research',description:'Compare strategies and evaluate sensitivity and unseen periods.',panels:['robustness-panel','comparison-panel','holdout-panel']},
    saved:{title:'Saved runs',description:'Open, replay, and compare your saved experiments.',panels:['saved-runs-panel','saved-comparison-panel']},
    trades:{title:'Trade history',description:'Review executions and completed trades from the current backtest.',panels:['trade-analysis','trades']},
    monitor:{title:'Market monitor',description:'Watch incoming prices from your chosen data source.',panels:['market-monitor-panel']},
    paper:{title:'Paper trading',description:'Run a separate simulated portfolio using incoming quote observations.',panels:['paper-trading-panel']},
  };
  const grid=document.querySelector('.studio-grid');grid.id='page-backtest';grid.dataset.page='backtest';
  const main=byId('overview');
  for(const [key,page] of Object.entries(pages)){
    if(key==='backtest')continue;
    const section=document.createElement('section');section.id=`page-${key}`;section.dataset.page=key;section.className='workspace-page';section.hidden=true;
    if(key==='research'){
      const note=document.createElement('p');note.className='page-note';note.textContent='Research checks whether a strategy holds up across different parameters and unseen dates. Choose analyses here; the asset, dates, strategy, and costs come from Backtest.';section.append(note);
      const settings=document.querySelector('.setup-advanced');
      if(settings){
        settings.open=true;settings.classList.add('research-settings');
        settings.querySelector('summary').textContent='Research settings';
        // Moved controls still belong to the original form for validation and FormData.
        for(const control of settings.querySelectorAll('input,select'))control.setAttribute('form','config');
        settings.addEventListener('input',()=>{if(typeof saveDraft==='function')saveDraft();});
        settings.addEventListener('change',()=>{if(typeof saveDraft==='function')saveDraft();});
        const comparison=settings.querySelector('.research-controls');
        if(comparison){
          comparison.open=true;
          const fields=document.createElement('div');fields.className='research-comparison-fields';
          for(const child of [...comparison.children])if(child.tagName!=='SUMMARY')fields.append(child);
          comparison.append(fields);
        }
        const fields=document.createElement('div');fields.className='research-settings-fields';
        for(const child of [...settings.children])if(child.tagName!=='SUMMARY')fields.append(child);
        settings.append(fields);
        section.append(settings);
      }
      const actions=byId('research-actions');if(actions)section.append(actions);
    }
    if(key==='trades'){
      const note=document.createElement('p');note.className='page-note';note.textContent='These are historical backtest trades. Simulated incoming-quote orders are shown on Paper trading.';section.append(note);
    }
    for(const id of page.panels){const panel=byId(id);if(panel)section.append(panel);}
    main.append(section);
  }
  const navLinks=[...document.querySelectorAll('[data-nav-page]')];
  let current='backtest';
  function show(key,remember=true){
    if(!pages[key])key='backtest';current=key;
    for(const name of Object.keys(pages))byId(`page-${name}`).hidden=name!==key;
    for(const link of navLinks){
      const selected=link.dataset.navPage===key;link.classList.toggle('active',selected);
      if(selected)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
    }
    byId('workspace-title').textContent=pages[key].title;
    byId('page-title').textContent=pages[key].title;
    byId('page-description').textContent=pages[key].description;
    if(key==='research')window.updateResearchContext?.();
    byId('export').hidden=!['backtest','trades'].includes(key);
    document.title=`Backtest Lab · ${pages[key].title}`;
    if(remember)try{localStorage.setItem('backtestLab.page',key);}catch{}
    // Charts need a new width after their previously hidden container opens.
    if(key==='backtest'&&typeof chart==='function')requestAnimationFrame(()=>chart());
  }
  function hashPage(){const key=location.hash.slice(1);return {overview:'backtest',configuration:'backtest'}[key]||key;}
  window.addEventListener('hashchange',()=>{show(hashPage());window.scrollTo({top:0,behavior:'auto'});});
  window.navigateWorkspace=key=>{if(location.hash===`#${key}`)show(key);else location.hash=key;};
  let saved;try{saved=localStorage.getItem('backtestLab.page');}catch{}
  show(location.hash?hashPage():saved||'backtest',false);
})();
