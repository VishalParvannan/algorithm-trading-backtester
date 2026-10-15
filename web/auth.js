// Handle account entry, session expiry, logout, and explicit legacy-data import.
(() => {
  const node=id=>document.getElementById(id);
  if(node('auth-form')){
    let register=false;
    node('auth-toggle').onclick=()=>{
      register=!register;node('auth-submit').textContent=register?'Create account':'Sign in';
      node('auth-toggle').textContent=register?'Already registered? Sign in':'New here? Create an account';
      node('invitation-label').hidden=!register;
      node('auth-password').autocomplete=register?'new-password':'current-password';
      node('auth-password').minLength=register?12:1;node('auth-message').textContent='';
    };
    node('auth-form').onsubmit=async event=>{
      event.preventDefault();node('auth-submit').disabled=true;
      try{
        const response=await fetch(`/api/auth/${register?'register':'login'}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:node('auth-username').value,password:node('auth-password').value,invitation:node('auth-invitation').value})});
        const data=await response.json();if(!response.ok)throw Error(data.error||data.detail||'Sign-in failed.');
        location.replace('/');
      }catch(error){node('auth-message').textContent=error.message;}finally{node('auth-submit').disabled=false;}
    };
    return;
  }
  const context=node('account-context');if(!context)return;
  const account=JSON.parse(context.textContent);
  const profile=document.createElement('div');profile.className='account-toolbar';
  const placeholder=document.querySelector('.topbar .pill');placeholder.replaceWith(profile);
  document.querySelector('.profile').textContent=account.username;
  const label=document.createElement('span');label.className='account-name';label.textContent=account.username;label.title=account.username;
  const logout=document.createElement('button');logout.type='button';logout.className='text-button';logout.textContent='Sign out';
  logout.onclick=async()=>{logout.disabled=true;try{const response=await fetch('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!response.ok)throw Error('Sign-out failed');location.replace('/login');}catch{logout.disabled=false;logout.textContent='Retry sign out';}};
  profile.append(label,logout);
  const importButton=document.createElement('button');importButton.type='button';importButton.className='text-button';importButton.textContent='Import previous local workspace';
  const message=document.createElement('p');message.className='strategy-description';
  importButton.onclick=async()=>{
    importButton.disabled=true;
    try{const response=await fetch('/api/auth/import-local',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const data=await response.json();if(!response.ok)throw Error(data.error||data.detail);location.reload();}
    catch(error){message.textContent=error.message;importButton.disabled=false;}
  };
  document.querySelector('.sidebar-bottom').append(importButton,message);
  // Re-check on focus, including tabs restored after another tab signs out.
  async function check(){try{const response=await fetch('/api/auth/me');if(response.status===401){location.replace('/login');return;}if(response.ok&&(await response.json()).id!==account.id)location.replace('/');}catch{}}
  window.addEventListener('focus',check);
  // Back/Forward can restore a page from browser memory after signing out.
  window.addEventListener('pageshow',check);
})();
