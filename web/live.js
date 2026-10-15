// Public read-only market monitoring. A connection starts only on user request.
let liveSocket=null, liveStopped=true, liveRetry=0, liveRetryTimer=null, liveWatchdog=null, livePrices=[], liveLastMessage=0;
let quoteTimer=null,quoteGeneration=0;
const liveNode=id=>document.getElementById(id);
const liveMoney=value=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value);
try {liveNode('live-pair').value=localStorage.getItem(window.accountStorageKey?.('quantlab.livePair')||'quantlab.livePair')||'BTC-USD';}catch{}
function stopFeed(){
  quoteGeneration++;clearTimeout(quoteTimer);
  liveStopped=true;clearTimeout(liveRetryTimer);clearInterval(liveWatchdog);
  if(liveSocket){const socket=liveSocket;liveSocket=null;socket.close();}
  liveNode('live-status').textContent='Disconnected';liveNode('live-disconnect').disabled=true;
}
function drawLive(){
  if(livePrices.length<2)return;
  const low=Math.min(...livePrices),high=Math.max(...livePrices),span=high-low||1;
  const points=livePrices.map((price,i)=>`${i/(livePrices.length-1)*600},${70-(price-low)/span*60}`).join(' ');
  liveNode('live-chart').innerHTML=`<svg viewBox="0 0 600 80" role="img" aria-label="Recent monitored prices"><polyline points="${points}" fill="none" stroke="#168b73" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`;
}
function connectFeed(reconnecting=false){
  if((liveNode('live-source').value||'coinbase') !== 'coinbase'){connectQuote();return;}
  const pair=liveNode('live-pair').value.trim().toUpperCase();
  if(!/^[A-Z0-9]+-USD$/.test(pair)){liveNode('live-status').textContent='Use a USD pair, e.g. BTC-USD';return;}
  if(!reconnecting){stopFeed();liveRetry=0;livePrices=[];liveNode('live-chart').replaceChildren();liveNode('live-price').textContent='—';liveNode('live-change').textContent='—';liveNode('live-spread').textContent='—';}
  liveStopped=false;liveNode('live-disconnect').disabled=false;
  try{localStorage.setItem(window.accountStorageKey?.('quantlab.livePair')||'quantlab.livePair',pair);}catch{}
  liveNode('live-status').textContent=reconnecting?'Reconnecting…':'Connecting…';
  let socket;
  try{socket=new WebSocket('wss://ws-feed.exchange.coinbase.com');}catch{stopFeed();liveNode('live-status').textContent='WebSocket unavailable';return;}
  liveSocket=socket;liveLastMessage=Date.now();
  socket.onopen=()=>{if(socket!==liveSocket)return;socket.send(JSON.stringify({type:'subscribe',product_ids:[pair],channels:['ticker_batch','heartbeat']}));liveNode('live-status').textContent='Waiting for prices';};
  socket.onmessage=event=>{
    if(socket!==liveSocket)return;
    let message;try{message=JSON.parse(event.data);}catch{return;}
    if(message.type==='error'){liveStopped=true;liveNode('live-status').textContent='Feed rejected this pair';liveNode('live-updated').textContent='Check that the pair is traded on Coinbase.';socket.close();return;}
    liveLastMessage=Date.now();
    if(message.type!=='ticker' || message.product_id!==pair)return;
    const price=Number(message.price);if(!Number.isFinite(price)||price<=0)return;
    liveRetry=0;livePrices.push(price);if(livePrices.length>120)livePrices.shift();
    liveNode('live-status').textContent='Live';liveNode('live-price').textContent=liveMoney(price);
    const open=Number(message.open_24h);liveNode('live-change').textContent=open>0?`${((price/open-1)*100).toFixed(2)}%`:'—';
    const bid=Number(message.best_bid),ask=Number(message.best_ask);liveNode('live-spread').textContent=bid>0&&ask>0?`${liveMoney(bid)} / ${liveMoney(ask)}`:'—';
    const timestamp=new Date(message.time);liveNode('live-updated').textContent=`${pair} · ${Number.isNaN(timestamp.getTime())?'Latest received price':timestamp.toLocaleString()} · Read-only market data`;
    drawLive();
  };
  socket.onerror=()=>{if(socket===liveSocket)liveNode('live-status').textContent='Connection interrupted';};
  socket.onclose=()=>{
    if(socket!==liveSocket)return;liveSocket=null;clearInterval(liveWatchdog);
    if(liveStopped){liveNode('live-disconnect').disabled=true;return;}
    if(liveRetry>=5){liveNode('live-status').textContent='Offline · reconnect manually';liveNode('live-disconnect').disabled=true;return;}
    liveNode('live-status').textContent='Offline · retrying';liveRetryTimer=setTimeout(()=>connectFeed(true),Math.min(30000,1000*2**liveRetry++));
  };
  clearInterval(liveWatchdog);
  liveWatchdog=setInterval(()=>{if(liveSocket===socket && Date.now()-liveLastMessage>45000){liveNode('live-status').textContent='Stale feed · reconnecting';socket.close();}},5000);
}
liveNode('live-connect').onclick=()=>connectFeed();
liveNode('live-disconnect').onclick=stopFeed;
window.addEventListener('beforeunload',stopFeed);

const sourceDescriptions={coinbase:'Coinbase · streaming crypto · USD pairs',market:'Yahoo Finance · quotes polled every minute · may be delayed',alpha:'Alpha Vantage · daily quotes · checked hourly · API key required',csv:'CSV · latest uploaded price · historical snapshot',demo:'Demo · simulated prices · refreshes every 5 seconds'};
function monitorSourceChanged(){
  stopFeed();const source=liveNode('live-source').value||'coinbase';
  liveNode('live-description').textContent=sourceDescriptions[source];
  liveNode('live-pair').value=source==='coinbase'?'BTC-USD':source==='csv'?'CUSTOM':'AAPL';
  liveNode('live-price').textContent='—';liveNode('live-change').textContent='—';liveNode('live-spread').textContent='—';
  livePrices=[];liveNode('live-chart').replaceChildren();
  liveNode('live-updated').textContent='Choose an asset and connect to see prices.';
  try{localStorage.setItem(window.accountStorageKey?.('quantlab.liveSource')||'quantlab.liveSource',source);}catch{}
}
async function connectQuote(){
  stopFeed();liveStopped=false;const generation=quoteGeneration;
  const source=liveNode('live-source').value,symbol=liveNode('live-pair').value.trim().toUpperCase();
  const key=document.querySelector('[name=api_key]')?.value||'';
  const csv=typeof csvText==='string'?csvText:'';
  liveNode('live-disconnect').disabled=false;livePrices=[];liveNode('live-chart').replaceChildren();
  liveNode('live-price').textContent='—';liveNode('live-change').textContent='—';liveNode('live-spread').textContent='—';
  try{localStorage.setItem(window.accountStorageKey?.('quantlab.livePair')||'quantlab.livePair',symbol);}catch{}
  async function poll(){
    if(liveStopped||generation!==quoteGeneration)return;
    liveNode('live-status').textContent='Fetching quote…';
    try{
      const response=await fetch('/api/quote',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source,ticker:symbol,api_key:key,csv_text:source==='csv'?csv:undefined})});
      const quote=await response.json();if(!response.ok)throw Error(quote.error||quote.detail||'Quote unavailable');
      if(liveStopped||generation!==quoteGeneration)return;
      const price=Number(quote.price);if(!Number.isFinite(price)||price<=0)throw Error('Invalid quote received');
      liveNode('live-price').textContent=quote.currency?new Intl.NumberFormat('en-US',{style:'currency',currency:quote.currency}).format(price):price.toFixed(2);
      liveNode('live-change').textContent=quote.change==null?'—':`${Number(quote.change).toFixed(2)}%`;
      liveNode('live-spread').textContent='—';
      liveNode('live-status').textContent=source==='demo'?'Simulated':source==='csv'?'Snapshot':source==='alpha'?'Daily quote':'Polled quote';
      liveNode('live-updated').textContent=`${symbol} · ${quote.timestamp} · ${quote.mode}`;
      livePrices.push(price);if(livePrices.length>120)livePrices.shift();drawLive();
      if(quote.interval)quoteTimer=setTimeout(poll,quote.interval*1000);
      else liveNode('live-disconnect').disabled=true;
    }catch(error){
      if(generation!==quoteGeneration||liveStopped)return;
      liveNode('live-status').textContent='Quote unavailable';liveNode('live-updated').textContent=error.message;
      liveStopped=true;liveNode('live-disconnect').disabled=true;
    }
  }
  await poll();
}
liveNode('live-source').onchange=monitorSourceChanged;
try{const saved=localStorage.getItem(window.accountStorageKey?.('quantlab.liveSource')||'quantlab.liveSource');if(saved&&sourceDescriptions[saved]){liveNode('live-source').value=saved;const pair=liveNode('live-pair').value;monitorSourceChanged();liveNode('live-pair').value=pair;}}catch{}
liveNode('live-pair').onchange=()=>{stopFeed();};
