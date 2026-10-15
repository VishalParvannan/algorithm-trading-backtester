// Verify account entry and per-account request/storage binding without a browser.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map();function node(id){if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',hidden:false});return nodes.get(id);}
const payloads=[],redirects=[];
const context={document:{getElementById:node},location:{replace:url=>redirects.push(url)},fetch:async(url,options)=>{payloads.push([url,JSON.parse(options.body)]);return {ok:true,json:async()=>({id:'alice'})};}};
vm.runInNewContext(fs.readFileSync('web/auth.js','utf8'),context);
(async()=>{
  node('auth-username').value='alice';node('auth-password').value='a-valid-long-password';
  node('auth-toggle').onclick();assert.equal(node('auth-submit').textContent,'Create account');
  assert.equal(node('invitation-label').hidden,false);
  await node('auth-form').onsubmit({preventDefault(){}});
  assert.equal(payloads[0][0],'/api/auth/register');assert.equal(payloads[0][1].username,'alice');
  assert.equal(redirects[0],'/');
  let status=200;const requests=[],routes=[];
  const session={Headers,URL,location:{href:'http://localhost/',origin:'http://localhost',replace:url=>routes.push(url)},document:{getElementById:()=>({textContent:'{"id":"alice"}'})},window:{fetch:async(input,options)=>{requests.push(options);return {status};}}};
  vm.runInNewContext(fs.readFileSync('web/account-session.js','utf8'),session);
  assert.equal(session.window.accountStorageKey('draft'),'draft:alice');
  await session.window.fetch('/api/draft',{method:'POST',headers:{'Content-Type':'application/json'}});
  assert.equal(requests[0].headers.get('X-Backtest-Account'),'alice');
  assert.equal(requests[0].headers.get('Content-Type'),'application/json');
  status=409;await session.window.fetch('/api/draft');assert.equal(routes.at(-1),'/');
  status=401;await session.window.fetch('/api/paper');assert.equal(routes.at(-1),'/login');
  console.log('Passed: registration form, account-scoped storage, request identity, expiry and account-switch redirects.');
})().catch(error=>{console.error(error);process.exitCode=1;});
