// Verify searchable asset selection, keyboard controls, and source filtering.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('web/index.html', 'utf8');
const catalog = html.match(/<script id="dashboard-catalog" type="application\/json">(.*?)<\/script>/s)[1];
const main = fs.readFileSync('web/app.js', 'utf8');
const code = main.split('// Asset picker: loaded with the main dashboard so older local servers can serve it.')[1];
assert.ok(code, 'Picker must load through the existing app.js route');
assert.ok(!html.includes('src="/assets.js"'), 'No dependency on a newly added static route');
function node() {
  return {value:'', hidden:true, children:[], attributes:{}, handlers:{},
    addEventListener(name, callback){this.handlers[name] = callback;},
    setAttribute(name,value){this.attributes[name]=value;}, removeAttribute(name){delete this.attributes[name];},
    setCustomValidity(value){this.validity=value;}, replaceChildren(){this.children=[];},
    append(...children){this.children.push(...children);}, dispatchEvent(event){this.lastEvent=event;},
    focus(){this.handlers.focus?.();},select(){}, contains(target){return target===this;},
  };
}
const nodes = Object.fromEntries(['asset-search','ticker-input','source','asset-suggestions','asset-options','asset-search-note','asset-selection','asset-picker','asset-toggle','dashboard-catalog'].map(id => [id,node()]));
nodes['dashboard-catalog'].textContent=catalog;
nodes.source.value='market'; nodes['ticker-input'].value='SPY';
const context = {document:{getElementById:id=>nodes[id], createElement:node, addEventListener(){}},window:{}, Event:class{constructor(type,options){this.type=type;this.bubbles=options.bubbles;}},setTimeout:()=>1,clearTimeout(){}};
vm.runInNewContext(code,context);
const input=nodes['asset-search'],list=nodes['asset-options'];
input.focus();
assert.equal(nodes['asset-suggestions'].hidden,false);
assert.ok(list.children.length>1);
input.value='500'; input.handlers.input();
assert.ok(list.children.some(option=>option.children[0].textContent==='SPY'));
assert.ok(list.children.some(option=>option.children[0].textContent==='VOO'));
assert.ok(!list.children.some(option=>option.children[0].textContent==='500'));
assert.equal(nodes['ticker-input'].value,'SPY', 'Searching does not erase the saved selection');
input.value='apple'; input.handlers.input();
list.children[0].handlers.click();
assert.equal(nodes['ticker-input'].value,'AAPL');
assert.equal(input.validity,'');
assert.equal(nodes['ticker-input'].lastEvent.bubbles,true);
assert.equal(nodes['asset-suggestions'].hidden,true);
input.handlers.click(); assert.equal(nodes['asset-suggestions'].hidden,false);
input.value='microsoft'; input.handlers.input();
input.handlers.keydown({key:'ArrowDown',preventDefault(){}});
input.handlers.keydown({key:'Enter',preventDefault(){}});
assert.equal(nodes['ticker-input'].value,'MSFT');
nodes.source.value='coinbase';context.window.updateAssetPicker(); input.focus();
assert.ok(list.children.every(option=>option.children[2].textContent==='Crypto'));
console.log('Passed: browse, numeric/name search, click and keyboard selection, persistence event, source filtering.');
