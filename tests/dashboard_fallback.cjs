// Dashboard regressions without a browser or network dependency.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'web/index.html'), 'utf8');
const snapshot = html.match(/<script id="dashboard-catalog" type="application\/json">(.*?)<\/script>/s)[1];
const catalog = JSON.parse(snapshot);
const code = fs.readFileSync(path.join(root, 'web/app.js'), 'utf8');
const storage = new Map();
function workspace(blockedStorage = false, catalogAvailable = false) {
  const nodes = new Map();
  let parameterInputs = [];
  const aliases = {source:'#source',strategy:'#strategy',periods_per_year:'#calendar',outputsize:'#outputsize'};
  function element() {
    return {value:'',textContent:'',hidden:false,disabled:false,style:{},children:[],addEventListener(){},append(child){this.children.push(child);},replaceChildren(...children){this.children=children;}, innerHTML:''};
  }
  function node(selector) {
    const field = selector.match(/^\[name=(.+)\]$/)?.[1];
    if (aliases[field]) selector = aliases[field];
    if (!nodes.has(selector)) {
      const el = element(); nodes.set(selector, el);
      if (selector === '#parameters') Object.defineProperty(el, 'innerHTML', {
        get() {return this.markup || '';},
        set(value) {
          this.markup = value;
          parameterInputs = [...value.matchAll(/<input name="([^"]+)"[^>]*value="([^"]*)"/g)].map(match => ({...element(),name:match[1],value:match[2]}));
        },
      });
    }
    return nodes.get(selector);
  }
  node('#dashboard-catalog').textContent = snapshot;
  for (const [id, items] of [['#source',catalog.sources],['#strategy',catalog.strategies]]) {
    node(id).tagName='SELECT'; node(id).options=items.map(item=>({value:item.id}));
  }
  node('#source').value='market'; node('#strategy').value='ma';
  node('#trade-filter').value='all';
  for (const [name,value] of Object.entries({ticker:'SPY',start:'2022-01-01',end:'2025-12-31',capital:'10000',commission:'0.1',slippage:'0.05',periods_per_year:'252',outputsize:'compact'})) node(`[name=${name}]`).value=value;
  const calls=[];
  const context = vm.createContext({
    document:{getElementById:()=>null,querySelector:node,querySelectorAll:selector=>selector==='#parameters input[name]'?parameterInputs:[],createElement:element},
    localStorage:{getItem:key=>{if(blockedStorage)throw Error('blocked');return storage.get(key)||null;},setItem:(key,value)=>{if(blockedStorage)throw Error('blocked');storage.set(key,value);}},
    fetch:async url=>{calls.push(url);return {ok:catalogAvailable,json:async()=>url==='/api/catalog'?catalog:url==='/api/experiments'?[]:null};},
    Option:class{constructor(text,value){this.textContent=text;this.value=value;}},
    ResizeObserver:class{observe(){}}, window:{}, Intl,Date,console,setTimeout,clearTimeout,
  });
  vm.runInContext(code,context);
  return {context,node,calls,inputs:()=>parameterInputs};
}
const first=workspace();
setImmediate(()=>{
  assert.ok(!first.calls.includes('/api/backtest'));
  assert.match(first.node('#error').textContent,/Restart the Python server/);
  assert.match(first.node('#trade-body').innerHTML,/No trade history yet/);
  assert.equal(first.node('#run').disabled,false);
  for(const [strategy,expected] of [['ma','Fast window'],['momentum','Lookback'],['rsi','Oversold'],['ema','Fast window']]){
    first.node('#strategy').value=strategy;
    vm.runInContext('parameters()',first.context);
    assert.match(first.node('#parameters').innerHTML,new RegExp(expected));
  }
  first.node('[name=ticker]').value='AAPL';first.node('[name=capital]').value='25000';
  first.node('#source').value='csv';first.node('#calendar').value='365';
  first.node('[name=api_key]').value='secret-do-not-save';
  first.inputs()[0].value='8';first.inputs()[1].value='35';
  vm.runInContext("csvText='Date,Close\\n2025-01-02,100';csvName='prices.csv';saveDraft();",first.context);
  const saved=storage.get('quantlab.workspace.v1');
  assert.ok(!saved.includes('secret-do-not-save'));
  const reopened=workspace(false,true);
  setImmediate(()=>{
    assert.equal(reopened.node('[name=ticker]').value,'AAPL');
    assert.equal(reopened.node('[name=capital]').value,'25000');
    assert.equal(reopened.node('#strategy').value,'ema');
    assert.equal(reopened.node('#source').value,'csv');
    assert.equal(reopened.node('#calendar').value,'365');
    assert.equal(reopened.inputs()[0].value,'8');assert.equal(reopened.inputs()[1].value,'35');
    assert.match(reopened.node('#csv-status').textContent,/prices.csv restored/);
    assert.ok(!reopened.calls.includes('/api/backtest'));
    reopened.node('#strategy').value='rsi';vm.runInContext('parameters()',reopened.context);
    reopened.inputs()[0].value='10';vm.runInContext('saveDraft()',reopened.context);
    reopened.node('#strategy').value='ema';vm.runInContext('parameters()',reopened.context);
    assert.equal(reopened.inputs()[0].value,'8');
    reopened.node('#strategy').value='rsi';vm.runInContext('parameters()',reopened.context);
    assert.equal(reopened.inputs()[0].value,'10');
    vm.runInContext(`chart=()=>{};
      result={demo:true,ticker:'SPY',strategy:'ma',dates:['2025-01-02','2025-01-03'],metrics:{total_return:0.1,cagr:0.1,sharpe_ratio:1,max_drawdown:-0.02},equity:[10000,11000],trades:[{date:'2025-01-03',side:'Buy',quantity:1,price:100,commission:0.1}]};
      render();`,reopened.context);
    assert.match(reopened.node('#trade-body').innerHTML,/No trade history yet/);
    assert.equal(reopened.node('#trade-count').textContent,'0');
    vm.runInContext("result.demo=false;result.ticker='AAPL';trades();",reopened.context);
    assert.equal(reopened.node('#trade-body').children[0].children[1].textContent,'AAPL');
    const blocked=workspace(true);vm.runInContext('saveDraft()',blocked.context);
    assert.match(blocked.node('#save-status').textContent,/Could not save/);
    storage.set('quantlab.workspace.v1','invalid JSON');
    workspace();
    console.log('Passed: empty history, real trades, catalog fallback, reopen persistence, per-strategy parameters, CSV restoration, key exclusion, storage failures.');
  });
});
