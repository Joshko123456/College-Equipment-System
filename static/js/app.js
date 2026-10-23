function openModal(id){document.getElementById(id)?.classList.add('show');document.body.classList.add('modal-open')}
function closeModal(id){document.getElementById(id)?.classList.remove('show');document.body.classList.remove('modal-open')}
function openBorrow(action,name,max){document.getElementById('borrowTitle').textContent='Request: '+name;document.getElementById('borrowForm').action=action;document.getElementById('bqty').max=max;openModal('borrowModal')}
function openEdit(action,e){document.getElementById('editForm').action=action;ea.value=e.asset_code;document.getElementById('editForm').elements.add_quantity.value='0';en.value=e.name;document.getElementById('em').value=(e.model&&e.model!=='Update required')?e.model:'';ec.value=e.category_id||'';eq.value=e.total_qty;el.value=e.location||'';es.value=e.condition_status;document.getElementById('efc').value=e.fair_cost??'250.00';document.getElementById('edc').value=e.damage_cost??'1000.00';ed.value=e.description||'';openModal('editModal')}
function filterTable(){let q=document.getElementById('search').value.toLowerCase();document.querySelectorAll('.searchable').forEach(x=>x.style.display=x.innerText.toLowerCase().includes(q)?'flex':'none')}
function togglePassword(id,btn){const input=document.getElementById(id);if(!input)return;const show=input.type==='password';input.type=show?'text':'password';if(btn)btn.textContent=show?'Hide':'Show'}
function toggleSidebar(force){const sidebar=document.getElementById('sidebar');if(!sidebar)return;const open=typeof force==='boolean'?force:!document.body.classList.contains('sidebar-open');document.body.classList.toggle('sidebar-open',open);const launcher=document.getElementById('homeMenuLauncher');if(launcher){launcher.setAttribute('aria-expanded',open?'true':'false');launcher.setAttribute('title',open?'Close main menu':'Open main menu');launcher.setAttribute('aria-label',open?'Close main menu':'Open main menu')}}

function updateReturnCost(form){
  const condition=form.elements.return_condition.value;
  const input=form.elements.condition_cost;
  const good=condition==='Good';
  input.disabled=good; input.required=!good;
  if(good) input.value='0';
  else if(form.dataset.lastCondition!==condition) input.value='';
  form.dataset.lastCondition=condition;
  const preview=form.querySelector('[data-auto-cost-preview]');
  if(preview)preview.textContent=good?'Good: condition note and PHP 0.00.':'Enter the total '+condition.toLowerCase()+' cost for this borrowing. The borrower must review and accept the amount.';
}
document.addEventListener('DOMContentLoaded',()=>document.querySelectorAll('.inspection-form').forEach(updateReturnCost));

window.addEventListener('click',e=>{if(e.target.classList?.contains('modal')&&!e.target.classList.contains('modal-lock'))closeModal(e.target.id)});
window.addEventListener('keydown',e=>{if(e.key==='Escape'){document.querySelectorAll('.modal.show:not(.modal-lock)').forEach(m=>closeModal(m.id));toggleSidebar(false)}});


// LIGHT / DARK THEME
function currentTheme(){
  return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}
function syncThemeControls(){
  const dark=currentTheme()==='dark';
  document.querySelectorAll('.theme-toggle').forEach(btn=>{
    const icon=btn.querySelector('.theme-icon');
    const label=btn.querySelector('.theme-label');
    if(icon) icon.textContent=dark?'☀':'☾';
    if(label) label.textContent=dark?'Light mode':'Dark mode';
    btn.setAttribute('aria-pressed', dark?'true':'false');
    btn.setAttribute('title', dark?'Switch to light mode':'Switch to dark mode');
  });
  const meta=document.getElementById('themeColor');
  if(meta) meta.setAttribute('content',dark?'#101a14':'#075b35');
}
function applyTheme(theme,save=true){
  const next=theme==='dark'?'dark':'light';
  document.documentElement.setAttribute('data-theme',next);
  if(save){try{localStorage.setItem('bcc-theme',next)}catch(e){}}
  syncThemeControls();
}
function toggleTheme(){
  applyTheme(currentTheme()==='dark'?'light':'dark');
}
document.addEventListener('DOMContentLoaded',()=>syncThemeControls());

// PEOPLE & ACCOUNT MANAGEMENT
function filterStudentRows(value){
  const q=(value||'').trim().toLowerCase();
  const sections=[...document.querySelectorAll('.student-course-section')];
  sections.forEach(section=>{
    const rows=[...section.querySelectorAll('.student-row')];
    const defaultEmpty=section.querySelector('.course-empty-default');
    const noResults=section.querySelector('.student-no-results');
    let visible=0;
    rows.forEach(row=>{
      const match=!q || (row.dataset.search||row.innerText.toLowerCase()).includes(q);
      row.style.display=match?'':'none';
      if(match) visible++;
    });
    if(defaultEmpty){
      defaultEmpty.style.display=(!q && rows.length===0)?'':'none';
    }
    if(noResults){
      noResults.style.display=(q && rows.length>0 && visible===0)?'':'none';
    }
  });
}
function openBorrowerDelete(action,name,schoolId,borrowerType){
  const type=borrowerType || 'Borrower';
  const form=document.getElementById('deleteBorrowerForm');
  const text=document.getElementById('deleteBorrowerText');
  const title=document.getElementById('deleteBorrowerTitle');
  const kicker=document.getElementById('deleteBorrowerKicker');
  const cancel=document.getElementById('deleteBorrowerCancel');
  const submit=document.getElementById('deleteBorrowerSubmit');
  if(form) form.action=action;
  if(kicker) kicker.textContent=`REMOVE ${type.toUpperCase()}`;
  if(title) title.textContent=`Delete this ${type.toLowerCase()}?`;
  if(text) text.textContent=`Remove ${name} (${schoolId}) from the active ${type} directory?`;
  if(cancel) cancel.textContent=`Keep ${type}`;
  if(submit) submit.textContent=`Yes, Remove ${type}`;
  openModal('deleteBorrowerModal');
}
function updatePasswordStrength(inputId,meterId){
  const input=document.getElementById(inputId), meter=document.getElementById(meterId);
  if(!input||!meter)return;
  const value=input.value||'';
  let score=0;
  if(value.length>=6)score++;
  if(value.length>=10)score++;
  if(/[A-Z]/.test(value)&&/[a-z]/.test(value))score++;
  if(/\d/.test(value)&&/[^A-Za-z0-9]/.test(value))score++;
  meter.dataset.score=String(score);
  const labels=['Use 6 or more characters','Basic password','Good password','Strong password','Very strong password'];
  const label=meter.querySelector('span');
  if(label) label.textContent=labels[score];
}

// LIVE NOTIFICATIONS
let bccNotificationTimer=null;
let bccAudioContext=null;
let bccPendingNotificationSound=false;

function getNotificationAudioContext(){
  const AudioContextClass=window.AudioContext||window.webkitAudioContext;
  if(!AudioContextClass)return null;
  if(!bccAudioContext)bccAudioContext=new AudioContextClass();
  return bccAudioContext;
}
function playNotificationTone(){
  const context=getNotificationAudioContext();
  if(!context)return;
  if(context.state!=='running'){
    bccPendingNotificationSound=true;
    context.resume().then(()=>{
      if(context.state==='running'&&bccPendingNotificationSound){
        bccPendingNotificationSound=false;
        playNotificationTone();
      }
    }).catch(error=>console.warn('Notification sound could not be enabled by the browser.',error));
    return;
  }
  const now=context.currentTime;
  [[0,880],[0.16,1175]].forEach(([offset,frequency])=>{
    const oscillator=context.createOscillator();
    const gain=context.createGain();
    oscillator.type='sine';
    oscillator.frequency.setValueAtTime(frequency,now+offset);
    gain.gain.setValueAtTime(0.0001,now+offset);
    gain.gain.exponentialRampToValueAtTime(0.12,now+offset+0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001,now+offset+0.14);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(now+offset);
    oscillator.stop(now+offset+0.15);
  });
}
function unlockNotificationAudio(){
  const context=getNotificationAudioContext();
  if(!context||context.state==='running')return;
  context.resume().then(()=>{
    if(context.state==='running'&&bccPendingNotificationSound){
      bccPendingNotificationSound=false;
      playNotificationTone();
    }
  }).catch(error=>console.warn('Notification sound could not be enabled by the browser.',error));
}

function notificationStorageKey(){
  const body=document.body;
  return `bcc-notification-last-id:${body.dataset.userRole||'user'}:${body.dataset.userId||'0'}`;
}
function getLastNotificationId(){
  try{return Number(localStorage.getItem(notificationStorageKey())||0)}catch(e){return 0}
}
function saveLastNotificationId(id){
  try{localStorage.setItem(notificationStorageKey(),String(id||0))}catch(e){}
}
function updateNotificationBadges(count){
  const n=Number(count||0);
  document.querySelectorAll('[data-notification-badge]').forEach(badge=>{
    badge.textContent=n>99?'99+':String(n);
    badge.hidden=n<=0;
  });
}
function showNotificationToast(message,detailUrl){
  const stack=document.getElementById('notificationToastStack');
  if(!stack||!message)return;
  const toast=document.createElement('a');
  toast.className='notification-toast';
  toast.href=detailUrl||document.body.dataset.notificationPage||'#';
  toast.innerHTML='<span class="notification-toast-icon">🔔</span><div><b>New notification</b><p></p><small>Click to view full details</small></div>';
  toast.querySelector('p').textContent=message;
  stack.prepend(toast);
  requestAnimationFrame(()=>toast.classList.add('show'));
  setTimeout(()=>{
    toast.classList.remove('show');
    setTimeout(()=>toast.remove(),260);
  },6500);
}
async function pollNotifications(){
  const url=document.body.dataset.notificationFeed;
  if(!url)return;
  try{
    const response=await fetch(url,{credentials:'same-origin',cache:'no-store',headers:{'X-Requested-With':'fetch'}});
    if(!response.ok)return;
    const data=await response.json();
    updateNotificationBadges(data.unread_count);
    const maxId=Number(data.max_id||0);
    const lastId=getLastNotificationId();
    if(maxId>lastId){
      const fresh=(data.latest||[]).filter(n=>Number(n.id)>lastId).sort((a,b)=>Number(a.id)-Number(b.id));
      if(fresh.length){
        const newest=fresh[fresh.length-1];
        showNotificationToast(newest.message,newest.url);
        playNotificationTone();
      }
      saveLastNotificationId(maxId);
    }
  }catch(e){/* Keep the UI usable while MySQL/server is temporarily unavailable. */}
}
function startLiveNotifications(){
  if(!document.body.dataset.notificationFeed)return;
  pollNotifications();
  if(bccNotificationTimer)clearInterval(bccNotificationTimer);
  bccNotificationTimer=setInterval(pollNotifications,10000);
}

document.addEventListener('DOMContentLoaded',startLiveNotifications);
document.addEventListener('pointerdown',unlockNotificationAudio,{passive:true});
document.addEventListener('keydown',unlockNotificationAudio);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)pollNotifications()});

// ACCOUNT ACTIVATION AGREEMENT POPUP
let activationAgreementApproved=false;
function openActivationAgreement(formId){
  const form=document.getElementById(formId);
  if(!form)return;
  if(!form.reportValidity())return;
  activationAgreementApproved=false;
  const accepted=document.getElementById('activationTermsAccepted');
  const check=document.getElementById('activationAgreementCheck');
  const confirm=document.getElementById('activationAgreementConfirm');
  if(accepted)accepted.value='';
  if(check)check.checked=false;
  if(confirm)confirm.disabled=true;
  openModal('activationAgreementModal');
}
function syncActivationAgreementButton(){
  const check=document.getElementById('activationAgreementCheck');
  const confirm=document.getElementById('activationAgreementConfirm');
  if(confirm)confirm.disabled=!(check&&check.checked);
}
function cancelActivationAgreement(){
  activationAgreementApproved=false;
  const accepted=document.getElementById('activationTermsAccepted');
  const check=document.getElementById('activationAgreementCheck');
  if(accepted)accepted.value='';
  if(check)check.checked=false;
  closeModal('activationAgreementModal');
}
function confirmActivationAgreement(){
  const check=document.getElementById('activationAgreementCheck');
  const form=document.getElementById('studentActivationForm');
  const accepted=document.getElementById('activationTermsAccepted');
  if(!check||!check.checked||!form||!accepted)return;
  activationAgreementApproved=true;
  accepted.value='yes';
  closeModal('activationAgreementModal');
  form.requestSubmit();
}
function activationSubmitGuard(event,formId){
  const form=document.getElementById(formId);
  const accepted=document.getElementById('activationTermsAccepted');
  if(activationAgreementApproved && accepted && accepted.value==='yes')return true;
  if(event)event.preventDefault();
  openActivationAgreement(formId);
  return false;
}

function openAccountDelete(action,name,schoolId,accountType){
  const form=document.getElementById('deleteAccountForm');
  const text=document.getElementById('deleteAccountText');
  const title=document.getElementById('deleteAccountTitle');
  if(form) form.action=action;
  if(title) title.textContent=`Delete this ${accountType || 'account'}?`;
  if(text) text.textContent=`Remove ${name} (${schoolId}) from the active ${accountType || 'account'} directory?`;
  openModal('deleteAccountModal');
}


// RESPONSIVE DATA TABLES
// On narrow screens CSS turns table rows into cards. This function copies
// column headings into data-label attributes so every value keeps its meaning.
function enhanceResponsiveTables(){
  document.querySelectorAll('.tablewrap table, .modern-tablewrap table').forEach(table=>{
    let headerRow=table.querySelector('thead tr');
    if(!headerRow){
      headerRow=[...table.querySelectorAll('tr')].find(row=>row.querySelector('th')) || null;
    }
    if(!headerRow)return;
    const headers=[...headerRow.querySelectorAll('th')].map(th=>(th.textContent||'').trim());
    table.classList.add('mobile-card-table');
    headerRow.classList.add('responsive-header-row');
    [...table.querySelectorAll('tr')].forEach(row=>{
      if(row===headerRow)return;
      [...row.children].forEach((cell,index)=>{
        if(cell.tagName!=='TD' || cell.hasAttribute('colspan'))return;
        const label=headers[index] || '';
        if(label)cell.dataset.label=label;
      });
    });
  });
}
document.addEventListener('DOMContentLoaded',enhanceResponsiveTables);
