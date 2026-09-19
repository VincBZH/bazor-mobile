async function getJSON(url,opts){const r=await fetch(url,opts);return r.json()}
function stateClass(v){if(v===true)return'ok';if(v===false)return'bad';return'unknown'}
function engineLabel(v){if(v===true)return'● DISPONIBLE';if(v===false)return'● INDISPONIBLE';return'● À VÉRIFIER'}

async function refresh(){
  const s=await getJSON('/api/status');
  const p=s.state?.project||{};
  document.getElementById('globalState').textContent=(p.delivery_state||p.status||'BOOTSTRAP').toUpperCase();
  const pr=Number(p.progress_percent||0);
  document.getElementById('progressText').textContent=pr+'%';
  document.getElementById('progressBar').style.width=pr+'%';
  document.getElementById('projectCard').innerHTML='<strong>'+(p.name||p.id||'Projet')+'</strong><br>'+
    '<span>État: '+(p.delivery_state||p.status||'—')+'</span><br>'+
    '<span>Tâche: '+(p.current_task||'—')+'</span><br>'+
    '<span>Suite: '+(p.next_task||'—')+'</span>';

  for(const key of ['gpt','mammouth','ollama']){
    const e=s.engines?.[key]||{};
    const el=document.getElementById(key+'State');
    el.textContent=engineLabel(e.available);
    el.className=stateClass(e.available);
  }

  const projects=await getJSON('/api/projects');
  const box=document.getElementById('projects');
  box.innerHTML=(projects.projects||[]).map(x=>'<article><h3>'+x.name+'</h3><p>'+x.status+'</p><p>'+x.next_step+'</p></article>').join('')||'<article><h3>Aucun projet</h3><p>Ajoute projects.json</p></article>';
}

document.getElementById('routeBtn').addEventListener('click',async()=>{
  const task_class=document.getElementById('taskClass').value;
  const mode=document.getElementById('mode').value;
  const body={task_class};
  if(mode!=='auto')body.manual=mode;
  const r=await getJSON('/api/route',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  document.getElementById('routeResult').textContent=r.selected?'Moteur choisi : '+r.selected:'Aucun moteur disponible';
});

refresh().catch(e=>{document.getElementById('globalState').textContent='ERREUR UI';console.error(e)});
setInterval(()=>refresh().catch(()=>{}),10000);
