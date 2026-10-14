// Verify opt-in streaming, ticker filtering, reconnects, and disconnect behavior.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const nodes=new Map(),sockets=[],timers=[];
function node(id){if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',style:{},replaceChildren(){this.innerHTML='';},innerHTML:''});return nodes.get(id);}
class Socket{
  constructor(url){this.url=url;sockets.push(this);}
  send(text){this.subscription=JSON.parse(text);}
  close(){this.closed=true;this.onclose?.();}
}
const context=vm.createContext({document:{getElementById:node},window:{addEventListener(){}},localStorage:{getItem(){return null;},setItem(){}},WebSocket:Socket,Intl,Date,console,setTimeout(fn){timers.push(fn);return timers.length;},clearTimeout(){},setInterval(){return 1;},clearInterval(){}});
vm.runInContext(fs.readFileSync(path.resolve(__dirname,'../web/live.js'),'utf8'),context);
assert.equal(sockets.length,0);
node('live-pair').value='BTC-USD';node('live-connect').onclick();
assert.equal(sockets.length,1);
const socket=sockets[0];socket.onopen();
assert.deepEqual(socket.subscription.product_ids,['BTC-USD']);
assert.ok(socket.subscription.channels.includes('heartbeat'));
socket.onmessage({data:JSON.stringify({type:'ticker',product_id:'ETH-USD',price:'999'})});
assert.equal(node('live-price').textContent,'—');
for(const price of ['100','105'])socket.onmessage({data:JSON.stringify({type:'ticker',product_id:'BTC-USD',price,open_24h:'100',best_bid:'104',best_ask:'106',time:'2025-01-01T10:00:00Z'})});
assert.equal(node('live-price').textContent,'$105.00');
assert.equal(node('live-change').textContent,'5.00%');
assert.match(node('live-chart').innerHTML,/polyline/);
socket.close();assert.match(node('live-status').textContent,/retrying/);
assert.equal(timers.length,1);
node('live-disconnect').onclick();
assert.equal(node('live-status').textContent,'Disconnected');
node('live-pair').value='BAD';node('live-connect').onclick();
assert.equal(sockets.length,1);
console.log('Live monitor passed: opt-in connection, subscriptions, pair filtering, prices, chart, reconnect, disconnect, input validation.');
