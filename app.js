const app=document.querySelector('#app'), panel=document.querySelector('#panel'), modal=document.querySelector('#modal');
let cfg,user,moduleKey='dashboard',rows=[],cache={},query='',descending=false,archived=false;
const esc=v=>String(v??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
async function api(path,data){
 const r=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json','X-Local-App':'fire-safety'},body:JSON.stringify(data)}:{});
 const v=await r.json();if(!r.ok)throw Error(v.error);return v;
}
function notify(s){const n=document.querySelector('#notice');n.textContent=s;n.hidden=false;clearTimeout(n.timer);n.timer=setTimeout(()=>n.hidden=true,6500)}
window.addEventListener('unhandledrejection',e=>{notify(e.reason.message);e.preventDefault()});
const btn=(label,action,primary=false)=>'<button class="'+(primary?'primary':'')+'" onclick="'+action+'">'+esc(label)+'</button>';
const opts=(items,v)=>items.map(s=>'<option '+(v===s?'selected':'')+'>'+esc(s)+'</option>').join('');
function popup(html){panel.innerHTML=html;if(!modal.open)modal.showModal()}
function brand(){return '<div class="brand"><b>LOA</b><div>Lyceum of Alabang<small>Institutional EHS&S Office</small></div></div>'}
async function boot(){
 const s=await api('/session');user=s.user;
 if(!user){app.innerHTML='<main class="login">'+brand()+'<h1>'+ (s.setup?'Set up your administrator account':'Fire Safety Management')+'</h1><form id="login">'+(s.setup?'<label>Full name<input name="name" required></label>':'')+'<label>Institutional email<input type="email" name="email" required></label><label>Password<input type="password" name="password" '+(s.setup?'minlength="12" placeholder="At least 12 characters"':'')+' required></label><button class="primary">'+(s.setup?'Create administrator account':'Sign in')+'</button></form></main>';document.querySelector('#login').onsubmit=async e=>{e.preventDefault();await api('/login',Object.fromEntries(new FormData(e.target)));await boot()};return}
 cfg=await api('/config');
 app.innerHTML='<aside>'+brand()+'<nav>'+Object.entries(cfg.names).filter(([k])=>!(k==='users'&&!cfg.admin)&&!(k==='audit'&&!cfg.admin&&!cfg.reviewer&&!user.role.startsWith('Auditor'))).map(([k,v])=>'<button data-key="'+k+'" onclick="navigate(\''+k+'\')">'+esc(v)+'</button>').join('')+'</nav><footer>'+esc(user.name)+'<small>'+esc(user.role)+'</small>'+btn('Sign out','signout()')+'</footer></aside><main class="workspace"><header><button class="menu" onclick="document.body.classList.toggle(\'open\')">Menu</button> Institutional EHS&S Office</header><section id="view"></section></main>';
 await navigate(cfg.names[location.hash.slice(1)]?location.hash.slice(1):'dashboard')
}
async function signout(){await api('/logout',{});location.reload()}
async function navigate(k){moduleKey=k;location.hash=k;query='';archived=false;descending=false;document.body.classList.remove('open');document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.key===k));await render()}
const view=()=>document.querySelector('#view');
const list=k=>api('/list?module='+k);
const heading=(title,actions='')=>'<div class="heading"><h1>'+esc(title)+'</h1><div class="actions">'+actions+'</div></div>';
const table=(cols,data)=>'<div class="scroll"><table><thead><tr>'+cols.map(k=>'<th>'+esc(k)+'</th>').join('')+'</tr></thead><tbody>'+data.map(row=>'<tr>'+row.map(v=>'<td>'+v+'</td>').join('')+'</tr>').join('')+'</tbody></table>'+(data.length?'':'<p class="empty">No records to display.</p>')+'</div>';
async function render(){
 const k=moduleKey,v=view();
 if(k==='dashboard'||k==='reports'){
 const entries=await Promise.all(Object.keys(cfg.fields).map(async key=>[key,await list(key)]));if(k!==moduleKey)return;cache=Object.fromEntries(entries);
 const metrics=[['Registered extinguishers',cache.fe.length,'fe'],['Inspections awaiting review',cache.inspections.filter(r=>r.review==='Pending Verification').length,'inspections'],['Open corrective actions',cache.capa.filter(r=>r.data.Status!=='Closed').length,'capa'],['Active work orders',cache.maintenance.filter(r=>!['Completed','Cancelled'].includes(r.data.Status)).length,'maintenance']];
 if(k==='reports'){v.innerHTML=heading(cfg.names[k])+table(['Register','Records','Report'],entries.map(([key,r])=>[esc(cfg.names[key]),r.length,btn('Open report',"navigate('"+key+"')")]));return}
 const today=new Date().toLocaleDateString('en-CA'),cutoff=new Date(Date.now()+30*86400000).toISOString().slice(0,10);
 const due=entries.flatMap(([key,rs])=>rs.filter(r=>!['Closed','Completed','Cancelled'].includes(r.data.Status)).flatMap(r=>Object.entries(r.data).filter(([f,d])=>['Next Inspection Date','Next Service Date','Target Date','Expiration Date','Next Review Date'].includes(f)&&d&&d<=cutoff).map(([f,d])=>[esc(r.ref),esc(f),esc(d),esc(d<today?'Overdue':'Upcoming')]))).sort((a,b)=>a[2].localeCompare(b[2]));
 v.innerHTML=heading('Executive Dashboard')+'<div class="metrics">'+metrics.map(([label,n,key])=>'<button onclick="navigate(\''+key+'\')"><span>'+label+'</span><strong>'+n+'</strong></button>').join('')+'</div><div class="boards"><article><h2>Equipment condition</h2>'+cfg.choices['Inspection Result'].map(s=>{const n=cache.fe.filter(r=>r.data['Equipment Status']===s).length;return '<div class="bar"><span>'+esc(s)+'</span><meter min="0" max="'+(cache.fe.length||1)+'" value="'+n+'"></meter><b>'+n+'</b></div>'}).join('')+'</article><article><h2>Due within 30 days</h2>'+table(['Reference','Activity','Due date','Status'],due)+'</article></div>';return
 }
 if(k==='users'||k==='audit'){const data=await api('/'+k),cols=k==='users'?['name','email','role']:['stamp','user','module','action','ref','old','new'];v.innerHTML=heading(cfg.names[k],k==='users'?btn('Create account','userForm()',true):'')+table(cols,data.map(r=>cols.map(c=>esc(r[c]))));return}
 rows=await api('/list?module='+k+'&archived='+(archived?1:0));if(k!==moduleKey)return;
 let actions=k==='fsmr'?(cfg.reviewer?btn('Generate annual report','annual()',true):''):(cfg.write.includes(k)?btn(k==='fe'?'Add fire extinguisher':k==='inspections'?'New inspection':'Add record','edit()',true):'');
 if(k==='fe'&&cfg.write.includes(k))actions+=btn('Import Excel','importForm()');
 if(k!=='fsmr')actions+=btn('Export Excel','excel()');
 if(k!=='fsmr')actions+=btn('Download PDF','downloadPDF()');
 v.innerHTML=heading(cfg.names[k],actions)+'<div class="tools"><input id="search" placeholder="Search records" aria-label="Search records">'+btn('Reverse sort','reverseSort()')+((cfg.admin||user.role.startsWith('Auditor'))?btn(archived?'Show active':'Show archived','toggleArchived()'):'')+'</div><div id="grid"></div>';
 document.querySelector('#search').value=query;document.querySelector('#search').oninput=e=>{query=e.target.value;grid()};grid()
}
function downloadPDF(id){location.href='/pdf?module='+moduleKey+'&q='+encodeURIComponent(query)+(id?'&id='+id:'')}
function excel(){location.href='/export?module='+moduleKey+'&q='+encodeURIComponent(query)}
function reverseSort(){descending=!descending;grid()}
async function toggleArchived(){archived=!archived;await render()}
function grid(){
 const k=moduleKey;const columns=k==='fe'?['FE #','LOCATION','TYPE OF FE','WEIGHT','Equipment Status']:k==='fsmr'?['Reporting Year','Prepared By']:cfg.fields[k].slice(0,4);
 let result=rows.filter(r=>JSON.stringify(r).toLowerCase().includes(query.toLowerCase()));if(descending)result.reverse();
 document.querySelector('#grid').innerHTML=table(['Reference',...columns,'Review',''],result.map(r=>[esc(r.ref),...columns.map(c=>esc(r.data[c])),esc(r.review),btn('View','detail('+r.id+')')]))
}
async function detail(id){
 const r=rows.find(x=>x.id===id),k=moduleKey;if(k==='fsmr'){const sections=r.data.Sections;popup('<div class="report"><small>LYCEUM OF ALABANG · EHS&S OFFICE</small><h1>Annual Fire Safety Maintenance Report</h1><p>'+esc(r.ref)+' · '+esc(r.data['Reporting Year'])+' · '+esc(r.review)+'</p>'+Object.entries(sections).map(([s,rs])=>'<h2>'+esc(cfg.names[s])+'</h2>'+(rs.length?rs.map(x=>'<p><b>'+esc(x.ref)+'</b> '+Object.entries(x.data).filter(([a,b])=>b).map(([a,b])=>esc(a)+': '+esc(b)).join(' · ')+'</p>').join(''):'<p>No verified records for the reporting year.</p>')).join('')+'<p>Prepared by '+esc(r.data['Prepared By'])+'</p>'+btn('Download PDF','downloadPDF('+id+')')+'</div>');return}
 const files=await api('/files?id='+id);let history='';
 if(k==='fe'){for(const key of ['inspections','maintenance','capa']){const linked=(await list(key)).filter(x=>x.asset===id);history+='<h3>'+cfg.names[key]+'</h3>'+table(['Reference','Date created','Review'],linked.map(x=>[esc(x.ref),esc(x.created),esc(x.review)]))}}
 let actions='';if(!r.archived&&cfg.write.includes(k)){actions+=btn('Edit','edit('+id+')');if(cfg.reviewer)actions+=btn('Review evidence','reviewForm('+id+')');if(cfg.admin)actions+=btn('Archive','archiveForm('+id+')')}
 if(k==='fe' && !r.archived && cfg.write.includes('inspections')){
   actions+=btn('Record inspection','inspectExtinguisher('+id+')');
 }
 popup('<small>'+esc(cfg.names[k])+'</small><h2>'+esc(r.ref)+'</h2><div class="actions">'+actions+'</div><dl>'+Object.entries({...r.data,Review:r.review}).filter(([k])=>!k.startsWith('_')).map(([a,b])=>'<div><dt>'+esc(a)+'</dt><dd>'+esc(b||'—')+'</dd></div>').join('')+'</dl><h3>Evidence</h3>'+ (files.length?files.map(f=>'<a target="_blank" href="/file?id='+f.id+'">'+(f.type.startsWith('image')?'<img class="thumb" src="/file?id='+f.id+'">':'')+esc(f.category)+' · '+esc(f.name)+'</a>').join(' '):'<p>No attachments.</p>')+history)
}
function form(title,html,action,label='Save'){popup('<h2>'+esc(title)+'</h2><form id="editor">'+html+'<div class="actions"><button class="primary">'+esc(label)+'</button></div></form>');document.querySelector('#editor').onsubmit=async e=>{e.preventDefault();const f=e.target;const submit=f.querySelector('button[type=submit],button.primary');submit.disabled=true;try{await action(f)}catch(error){let message=f.querySelector('[role=alert]');if(!message){message=document.createElement('p');message.setAttribute('role','alert');f.append(message)}message.textContent=error.message}finally{submit.disabled=false}}}
async function done(message){modal.close();await render();notify(message)}
async function encoded(f){return await new Promise((ok,fail)=>{const reader=new FileReader();reader.onload=()=>ok(reader.result.split(',')[1]);reader.onerror=fail;reader.readAsDataURL(f)})}
function inspectExtinguisher(id){
 const asset=rows.find(row=>row.id===id);
 if(moduleKey!=='fe' || !asset || asset.archived || !cfg.write.includes('inspections')) return;
 return edit(undefined,'inspections',{'FE #':asset.data['FE #']});
}
async function edit(id,k=moduleKey,defaults={}){
 const r=id==null?undefined:rows.find(x=>x.id===id),d=r?.data||defaults,assets=await list('fe'),locations=await list('settings');
 const input=field=>{
 const required=(cfg.required[k]||[cfg.fields[k][0]]).includes(field)?' required':'',value=d[field]||'',name=' name="'+esc(field)+'"'+required;
 let choices=cfg.choices[field]||(field==='Status'&&cfg.status[k]?cfg.status[k].split('|'):null);
 if(field==='FE #'&&k!=='fe')choices=[...new Set([...assets.map(x=>x.data['FE #']),...(value?[value]:[])])];
 if(choices&&value&&!choices.includes(value))choices=[value,...choices];
 if(choices)return '<select'+name+'><option value=""></option>'+opts(choices,value)+'</select>';
 return '<input'+name+' type="'+(/date/i.test(field)?'date':'text')+'" value="'+esc(value)+'" '+(field==='LOCATION'?'list="places"':'')+(field==='FE #'&&k==='fe'&&id?' readonly':'')+'>'
 };
 form((id?'Edit ':'New ')+cfg.names[k],'<div class="fields">'+cfg.fields[k].map(f=>'<label>'+esc(f)+input(f)+'</label>').join('')+'</div><datalist id="places">'+opts(locations.map(x=>x.data['Location Name']))+'</datalist><label>Evidence category<input name="_category" value="Overall equipment view"></label><label>Evidence (5 MB per file)<input type="file" name="_files" multiple accept="image/jpeg,image/png,image/webp'+(['inspections','fe'].includes(k)?'':',application/pdf')+'"></label><div id="preview"></div>',async f=>{
 const fd=new FormData(f),files=[];for(const file of f._files.files){if(file.size>5242880)throw Error('Maximum 5 MB per attachment');files.push({bytes:await encoded(file),name:file.name,category:fd.get('_category')})}
 await api('/save',{module:k,id,revision:r?.revision,data:Object.fromEntries(cfg.fields[k].map(a=>[a,fd.get(a)])),files});await done('Record saved')});
 document.querySelector('[name="_files"]').onchange=e=>{document.querySelector('#preview').textContent=Array.from(e.target.files,f=>f.name).join(' · ')}
}
function reviewForm(id){const r=rows.find(x=>x.id===id);form('Review '+r.ref,'<label>Decision<select name="decision">'+opts(['Verified','Returned for Correction','Rejected'])+'</select></label><label>Review remarks<textarea name="reason" required></textarea></label>',async f=>{await api('/review',{module:moduleKey,id,revision:r.revision,...Object.fromEntries(new FormData(f))});await done('Review recorded')})}
function archiveForm(id){const r=rows.find(x=>x.id===id);form('Archive '+r.ref,'<p>The record and evidence will remain in the archive.</p><label>Reason<textarea name="reason" required></textarea></label>',async f=>{await api('/archive',{module:moduleKey,id,revision:r.revision,reason:f.reason.value});await done('Record archived')},'Confirm archive')}
function userForm(){form('Create account','<label>Full name<input name="name" required></label><label>Email<input type="email" name="email" required></label><label>Password<input type="password" name="password" minlength="12" required></label><label>Role<select name="role">'+opts(cfg.roles,cfg.roles.at(-1))+'</select></label>',async f=>{await api('/users',Object.fromEntries(new FormData(f)));await done('Account created')})}
function annual(){form('Generate annual FSMR','<label>Reporting year<input name="year" type="number" min="1900" max="2100" value="'+new Date().getFullYear()+'"></label><p>Saves a dated snapshot of verified records for the selected year.</p>',async f=>{await api('/fsmr',{year:f.year.value});await done('Annual report saved')},'Generate report')}
function importForm(){form('Import extinguisher registry','<p>Use the 15-column registry workbook. Export Excel provides the template.</p><label>Workbook<input type="file" name="sheet" accept=".xlsx" required></label>',async f=>{const data=await api('/preview',{module:'fe',file:await encoded(f.sheet.files[0])});const valid=data.rows.filter(x=>!x.error).length;form('Review import','<p>'+valid+' ready · '+(data.rows.length-valid)+' skipped</p>'+table(['Row','FE #','Location','Validation'],data.rows.map(x=>[x.row,esc(x.data['FE #']),esc(x.data.LOCATION),esc(x.error||'Ready')])),async()=>{const result=await api('/import',{module:'fe',batch:data.batch});await done(result.count+' records imported')},'Import valid rows')},'Preview workbook')}
boot();


