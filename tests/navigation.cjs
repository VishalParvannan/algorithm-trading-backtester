// Verify page grouping, browser navigation, form ownership, and chart redraws.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),events={},storage=new Map();let redraws=0;
function element(){return {id:'',hidden:false,textContent:'',dataset:{},children:[],attributes:{},classList:{toggle(name,value){this[name]=value;}},append(child){if(child.parent)child.parent.children=child.parent.children.filter(c=>c!==child);this.children.push(child);child.parent=this;},setAttribute(name,value){this.attributes[name]=value;},removeAttribute(name){delete this.attributes[name];}};}
function node(id){if(!nodes.has(id)){const el=element();el.id=id;nodes.set(id,el);}return nodes.get(id);}
const grid=node('page-backtest'),main=node('overview');main.append(grid);
const settings=element(),control=element(),summary=element(),comparison=element();
settings.classList.add=name=>{settings.classList[name]=true;};
settings.querySelector=selector=>selector==='summary'?summary:comparison;
settings.querySelectorAll=()=>[control];settings.addEventListener=()=>{};grid.append(settings);
const panelIds=['robustness-panel','comparison-panel','holdout-panel','saved-runs-panel','saved-comparison-panel','trade-analysis','trades','market-monitor-panel','paper-trading-panel'];
for(const id of panelIds)grid.append(node(id));
node('robustness-panel').hidden=true;
const links=['backtest','research','saved','trades','monitor','paper'].flatMap(key=>[0,1].map(()=>{const el=element();el.dataset.navPage=key;return el;}));
const location={hash:'#research'};
const document={getElementById:id=>nodes.get(id)||node(id),querySelector:selector=>selector==='.studio-grid'?grid:selector==='.setup-advanced'?settings:null,querySelectorAll:()=>links,createElement:()=>{const el=element();Object.defineProperty(el,'id',{get(){return this.identity;},set(id){this.identity=id;nodes.set(id,this);}});return el;}};
const context={document,location,localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)},window:{addEventListener:(name,fn)=>events[name]=fn,scrollTo(){}},requestAnimationFrame:fn=>fn(),chart(){redraws++;}};
vm.runInNewContext(fs.readFileSync('web/navigation.js','utf8'),context);
assert.equal(node('page-research').hidden,false);
assert.equal(settings.parent,node('page-research'));
assert.equal(control.attributes.form,'config','Research controls still belong to the backtest form after moving');
assert.equal(grid.hidden,true);
assert.equal(node('page-title').textContent,'Research');
assert.equal(node('robustness-panel').parent,node('page-research'));
assert.equal(node('robustness-panel').hidden,true,'Navigation preserves conditional result visibility');
assert.equal(node('trades').parent,node('page-trades'));
assert.equal(node('paper-trading-panel').parent,node('page-paper'));
location.hash='#saved';events.hashchange();
assert.equal(node('page-saved').hidden,false);assert.equal(node('page-research').hidden,true);
assert.equal(storage.get('backtestLab.page'),'saved');
assert.equal(links.filter(link=>link.attributes['aria-current']==='page').length,2,'Desktop and mobile nav both update');
location.hash='#backtest';events.hashchange();assert.equal(grid.hidden,false);assert.equal(redraws,1);
location.hash='#configuration';events.hashchange();assert.equal(node('page-title').textContent,'Backtest');
location.hash='#unknown';events.hashchange();assert.equal(node('page-title').textContent,'Backtest');
console.log('Passed: page grouping, conditional visibility, URL navigation, saved selection, mobile nav, chart redraw, legacy links.');
