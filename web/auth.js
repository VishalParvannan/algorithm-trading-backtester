// Handle account entry, session expiry, logout, and explicit legacy-data import.
(() => {
  const node=id=>document.getElementById(id);
  if(node('auth-form')){
    let register=false;
    const password=node('auth-password'),confirmation=node('auth-confirm');
    const checks=[['password-length',value=>[...value].length>=12&&[...value].length<=128],['password-letter',value=>/[A-Za-z]/.test(value)],['password-variety',value=>/[^A-Za-z]/.test(value)]];
    function validate(){
      const valid=checks.every(([,test])=>test(password.value));
      for(const [id,test] of checks){const met=test(password.value);node(id).textContent=`${met?'✓':'○'} ${node(id).dataset.label}`;node(id).dataset.valid=String(met);}
      const matches=!!confirmation.value&&confirmation.value===password.value;
      confirmation.setCustomValidity(register&&confirmation.value&&!matches?'Passwords do not match.':'');
      node('password-match').textContent=confirmation.value?(matches?'Passwords match.':'Passwords do not match.'):'Re-enter your password to confirm it.';
      node('password-match').dataset.valid=String(matches);
      node('password-status').textContent=!password.value?'Create a password using the requirements below.':valid?'Password meets all requirements.':'Password is missing a requirement below.';
      node('password-status').dataset.valid=String(valid);
      return valid&&matches;
    }
    const invitation=node('auth-invitation');
    const eyes=[[password,'password-eye','password'],[confirmation,'confirm-eye','password'],[invitation,'invitation-eye','hosting code']];
    for(const [input,id,label] of eyes){
      const button=node(id);
      button.onclick=()=>{input.type=input.type==='password'?'text':'password';const visible=input.type==='text';button.setAttribute('aria-pressed',String(visible));button.setAttribute('aria-label',`${visible?'Hide':'Show'} ${label}`);button.title=`${visible?'Hide':'Show'} ${label}`;};
      input.oninput=validate;
    }
    // Clear server validation when the user edits the code so they can retry.
    invitation.oninput=()=>invitation.setCustomValidity('');
    node('auth-toggle').onclick=()=>{
      register=!register;node('auth-submit').textContent=register?'Create account':'Sign in';
      node('auth-toggle').textContent=register?'Already registered? Sign in':'New here? Create an account';
      node('invitation-label').hidden=!register;
      invitation.required=register;invitation.disabled=!register;
      invitation.setCustomValidity('');
      node('auth-password').autocomplete=register?'new-password':'current-password';
      node('auth-password').minLength=register?12:1;node('auth-message').textContent='';
      node('confirmation-field').hidden=!register;confirmation.disabled=!register;confirmation.required=register;
      node('password-guidance').hidden=!register;
      confirmation.value='';password.type='password';confirmation.type='password';
      for(const [input,id,label] of eyes){input.type='password';node(id).setAttribute('aria-pressed','false');node(id).setAttribute('aria-label',`Show ${label}`);node(id).title=`Show ${label}`;}
      validate();
    };
    node('auth-form').onsubmit=async event=>{
      event.preventDefault();node('auth-submit').disabled=true;node('auth-message').textContent='';
      try{
        if(register&&!validate())throw Error('Meet the password requirements and make sure both passwords match.');
        const response=await fetch(`/api/auth/${register?'register':'login'}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:node('auth-username').value,password:password.value,...(register?{password_confirmation:confirmation.value}:{}),invitation:node('auth-invitation').value})});
        const data=await response.json();
        if(!response.ok){
          const message=data.error||data.detail||'Sign-in failed.';
          if(register&&typeof message==='string'&&message.includes('invitation code')){
            invitation.setCustomValidity('Invalid hosting code. Please check the code and try again.');
            invitation.reportValidity();
            return;
          }
          throw Error(message);
        }
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
