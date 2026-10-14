// Verify research controls, sensitivity displays, comparisons, and paper-session actions.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),calls=[];let sessions=[],researchRuns=0;
function element(){return {value:'',textContent:'',hidden:false,disabled:false,checked:false,style:{},children:[],replaceChildren(...children){this.children=children;this.value=children[0]?.value||'';},append(...children){this.children.push(...children);},get selectedOptions(){return this.children.filter(o=>o.selected);}};}
function node(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);}
const html=fs.readFileSync('web/index.html','utf8');node('dashboard-catalog').textContent=html.match(/<script id="dashboard-catalog" type="application\/json">(.*?)<\/script>/s)[1];node('strategy').value='momentum';
class Option{constructor(label,value){this.textContent=label;this.value=value;this.selected=false;}}
const metrics={total_return:.1,sharpe_ratio:1,max_drawdown:-.05};
const context={document:{getElementById:node,createElement:element,querySelector:selector=>node(selector),hidden:false},window:{addEventListener(){}},run:async()=>{researchRuns++;},Option,FormData:class{constructor(){return new Map([['ticker','AAPL'],['source','demo'],['strategy','buyhold']]);}},setInterval(){return 1;},clearInterval(){},fetch:async(url,options)=>{
  calls.push([url,options]);
  let data;
  if(url==='/api/experiments/compare')data={method:'Shared snapshot',mismatches:['commission'],harmonized:true,rows:[{result:{ticker:'AAPL',strategy_name:'Momentum',metrics,equity:[100,110],trades:[]}}]};
  else if(url==='/api/paper'&&options?.method==='POST'){sessions=[{id:'paper-one',created:'today',config:{ticker:'AAPL',strategy:'buyhold'},active:true,cash:1000,shares:0,equity:1000,currency:'USD',observations:[],trades:[],method:'Simulated',warmup_observations:1}];data=sessions[0];}
  else if(url.endsWith('/stop')){sessions[0].active=false;data=sessions[0];}
  else data=sessions;
  return {ok:true,json:async()=>data};
}};
vm.runInNewContext(fs.readFileSync('web/research-ui.js','utf8'),context);
(async()=>{
  node('config').checkValidity=()=>true;
  await node('research-run').onclick();assert.equal(researchRuns,0);
  assert.match(node('research-status').textContent,/Choose/);
  node('[name=compare_mode]').value='all';
  await node('research-run').onclick();assert.equal(researchRuns,1);
  assert.equal(node('sensitivity-parameter').children[0].value,'lookback');
  assert.equal(node('sensitivity-parameter').value,'lookback');
  assert.equal(node('sensitivity-parameter').disabled,false);
  context.window.updateResearchParameters([]);
  assert.equal(node('sensitivity-parameter').children[0].textContent,'No adjustable parameters');
  assert.equal(node('sensitivity-parameter').disabled,true);
  node('sensitivity-parameter').value='invalid';
  context.window.updateResearchParameters([{name:'fast',label:'Fast window'},{name:'slow',label:'Slow window'}]);
  assert.equal(node('sensitivity-parameter').value,'fast');
  node('sensitivity-parameter').value='slow';
  context.window.updateResearchParameters([{name:'fast',label:'Fast window'},{name:'slow',label:'Slow window'}]);
  assert.equal(node('sensitivity-parameter').value,'slow');
  context.window.renderRobustness({parameter:'lookback',method:'Training only',sensitivity:[{value:5,metrics}],folds:[{fold:1,train_start:'Jan',train_end:'Feb',test_start:'Mar',test_end:'Apr',selected_value:5,training_return:.2,metrics}]});
  assert.equal(node('robustness-panel').hidden,false);
  assert.equal(node('sensitivity-body').children.length,1);
  assert.equal(node('walk-body').children.length,1);
  assert.equal(node('sensitivity-chart').children.length,1);
  context.window.refreshComparisonChoices([{id:'a',ticker:'AAPL',strategy:'Momentum'},{id:'b',ticker:'AAPL',strategy:'RSI'}]);
  for(const option of node('compare-saved').children)option.selected=true;
  node('compare-harmonize').checked=true;
  await node('compare-saved-run').onclick();
  const request=JSON.parse(calls.find(([url])=>url==='/api/experiments/compare')[1].body);
  assert.deepEqual(request.ids,['a','b']);assert.equal(request.harmonize,true);
  assert.match(node('saved-comparison-note').textContent,/corrected/);
  await node('paper-start').onclick();
  assert.equal(node('paper-stop').disabled,false);
  assert.match(node('paper-note').textContent,/warm-up/);
  await node('paper-stop').onclick();
  assert.equal(node('paper-stop').disabled,true);
  console.log('Passed: sensitivity chart, fold table, saved comparison request, paper start/status/stop.');
})().catch(error=>{console.error(error);process.exitCode=1;});
