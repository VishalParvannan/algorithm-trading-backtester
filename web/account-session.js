// Bind API requests and browser drafts to the account rendered into this page.
(() => {
  const account=JSON.parse(document.getElementById('account-context').textContent);
  window.accountStorageKey=key=>`${key}:${account.id}`;
  const original=window.fetch.bind(window);
  window.fetch=async(input,options={})=>{
    const url=new URL(typeof input==='string'?input:input.url,location.href);
    if(url.origin===location.origin&&url.pathname.startsWith('/api/')){
      const headers=new Headers(options.headers||input.headers);headers.set('X-Backtest-Account',account.id);
      const response=await original(input,{...options,headers});
      if(response.status===401)location.replace('/login');
      if(response.status===409)location.replace('/');
      return response;
    }
    return original(input,options);
  };
})();
