const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),timers=[];let resolveQuote,calls=0;
function node(id){if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',innerHTML:'',replaceChildren(){this.innerHTML='';}});return nodes.get(id);}
const context=vm.createContext({document:{getElementById:node,querySelector:()=>({value:'key'})},window:{addEventListener(){}},localStorage:{getItem(){return null;},setItem(){}},Intl,Date,console,csvText:'Date,Close\n2025-01-01,100',fetch:()=>{calls++;return new Promise(resolve=>{resolveQuote=resolve;});},setTimeout(fn){timers.push(fn);return timers.length;},clearTimeout(){},setInterval(){},clearInterval(){}});
vm.runInContext(fs.readFileSync('web/live.js','utf8'),context);
(async()=>{
  node('live-source').value='market';node('live-source').onchange();node('live-connect').onclick();
  assert.equal(calls,1);
  resolveQuote({ok:true,json:async()=>({price:123,currency:'USD',timestamp:'2025-01-01',mode:'Yahoo · may be delayed',interval:60})});
  await new Promise(setImmediate);
  assert.equal(node('live-price').textContent,'$123.00');
  assert.equal(node('live-status').textContent,'Polled quote');
  assert.equal(timers.length,1);
  node('live-connect').onclick();node('live-disconnect').onclick();
  resolveQuote({ok:true,json:async()=>({price:999,currency:'USD',interval:60})});
  await new Promise(setImmediate);
  assert.equal(node('live-status').textContent,'Disconnected');
  assert.notEqual(node('live-price').textContent,'$999.00');
  node('live-source').value='csv';node('live-source').onchange();node('live-connect').onclick();
  resolveQuote({ok:true,json:async()=>({price:100,currency:null,timestamp:'2025-01-01',mode:'Historical snapshot',interval:null})});
  await new Promise(setImmediate);
  assert.equal(node('live-status').textContent,'Snapshot');
  assert.equal(node('live-disconnect').disabled,true);
  console.log('Passed: polling, source switching, disconnect ignores late responses, CSV snapshot.');
})().catch(error=>{console.error(error);process.exitCode=1;});
