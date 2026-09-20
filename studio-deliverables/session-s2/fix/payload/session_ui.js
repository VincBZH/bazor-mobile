// BAZOR_SESSION_S2 — active creation is never inferred from history.
function generalCheckpointS2(names){
  // Preference only, never a content-safety certification.
  const rank=name=>{const n=name.toLowerCase();if(/noob|pony|hentai|nsfw|illustrious|animagine/.test(n))return -1;const known=['sd_xl_base','sdxl_base','realvis','juggernaut','dreamshaper'];const i=known.findIndex(k=>n.includes(k));return i<0?-1:known.length-i};
  return names.map(name=>({name,rank:rank(name)})).filter(x=>x.rank>=0).sort((a,b)=>b.rank-a.rank||a.name.localeCompare(b.name))[0]?.name||null;
}
function clearSourceS2(){
  uploadSeq++;
  asset=null;
  if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null}
  showAsset(null);
}
function clearAnalysisS2(){
  lastAnalysis=null;
  $('analysisReport').classList.add('hidden');
  $('analysisReport').replaceChildren();
  $('analysisStatus').textContent='';
}
function newCreationS2(nextMode='t2i'){
  if(submitting||uploading||optimizing||correctionBusy){error('Attends la fin de l’opération en cours, ou arrête les corrections.');return false}
  clearSourceS2(); selectedResult='';resultSignature='';pendingRequest=null;
  clearAnalysisS2();originalPrompt='';styleBasePrompt='';stylePresets=['realistic'];
  $('prompt').value='';$('negative').value='';$('seed').value='-1';
  $('artistic').checked=false;$('analysisAuto').checked=false;
  $('undoPrompt').classList.add('hidden');
  updateMode(nextMode);applyPreset('balanced');syncStylePrompt(false);
  renderResult();changeView('create');error('');return true;
}
function mountSessionS2(){
  if($('sessionS2'))return;
  const box=document.createElement('section');box.id='sessionS2';box.className='panel session-s2';
  box.innerHTML=`<div class="panel-body"><div class="toolbar"><button type="button" id="newCreationS2" class="primary">Nouvelle création</button><button type="button" id="discoverS2" class="secondary">Découverte</button><span class="chip">Session vierge · S2</span></div><p class="hint">Une ancienne création ne devient une référence que si vous la choisissez.</p><div id="discoverCardsS2" class="hidden"><div class="s2-cards"><button type="button" class="secondary" data-example-s2="bear">Ourson devant la télé</button><button type="button" class="secondary" data-example-s2="landscape">Paysage imaginaire</button><button type="button" class="secondary" data-example-s2="animation">Animer une photo</button></div><p class="hint">Ces exemples remplissent le formulaire. Ils ne lancent aucun calcul.</p></div></div>`;
  $('view-create').insertBefore(box,$('view-create').querySelector('.workspace'));
  $('newCreationS2').onclick=()=>newCreationS2();
  $('discoverS2').onclick=()=>$('discoverCardsS2').classList.toggle('hidden');
  const workflowButton=document.createElement('button');workflowButton.type='button';workflowButton.className='secondary';workflowButton.id='workflowS2';workflowButton.textContent='Voir le workflow sélectionné';box.querySelector('.toolbar').append(workflowButton);
  workflowButton.onclick=showWorkflowS2;
  box.addEventListener('click',e=>{
    const kind=e.target.closest('[data-example-s2]')?.dataset.exampleS2;if(!kind)return;
    if(!newCreationS2(kind==='animation'?'i2v':'t2i'))return;
    const examples={bear:'Un ourson brun assis sur un canapé regarde une télévision allumée. Une couverture enveloppe son corps. Il tient un verre de cola et boit avec une paille bien visible. Le verre, la paille, la couverture et la télévision sont tous visibles dans le cadre.',landscape:'Un village au bord d’un lac, des petites maisons en pierre, une forêt et des montagnes au loin. Lumière du matin, composition calme.',animation:'La caméra avance lentement vers le sujet. Préserver son identité, ses vêtements et le décor de la photo.'};
    $('prompt').value=examples[kind];styleBasePrompt=examples[kind];syncStylePrompt(false);updateSpecs();
  });
}

async function showWorkflowS2(){
  const selected=jobs.find(j=>j.id===selectedResult);
  if(!selected){error('Choisissez une création pour afficher le workflow réellement envoyé à ComfyUI.');return}
  try{
    const graph=await api('/api/workflow/'+encodeURIComponent(selected.id));
    const nodes=Object.entries(graph).filter(([,n])=>n&&typeof n.class_type==='string');
    if(!nodes.length)throw Error('Ce workflow ne contient aucun nœud affichable.');
    $('workflowDialogS2')?.remove();
    const dialog=document.createElement('dialog');dialog.id='workflowDialogS2';dialog.className='workflow-dialog-s2';
    const title=document.createElement('h2');title.textContent='Workflow de la création sélectionnée';dialog.append(title);
    const subtitle=document.createElement('p');subtitle.className='hint';subtitle.textContent=`${selected.params.mode.toUpperCase()} · ${nodes.length} nœuds · ${selected.id}`;dialog.append(subtitle);
    const close=document.createElement('button');close.className='secondary';close.textContent='Fermer';close.onclick=()=>dialog.close();dialog.append(close);
    const scroll=document.createElement('div');scroll.className='workflow-scroll-s2';
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    const ids=new Set(nodes.map(([id])=>id)),levels=new Map(),visiting=new Set();
    const parents=n=>Object.entries(n.inputs||{}).filter(([,v])=>Array.isArray(v)&&v.length===2&&ids.has(String(v[0]))&&Number.isInteger(v[1]));
    function level(id){if(levels.has(id))return levels.get(id);if(visiting.has(id))return 0;visiting.add(id);const n=graph[id];const v=Math.min(nodes.length,Math.max(0,...parents(n).map(([,p])=>1+level(String(p[0])))));visiting.delete(id);levels.set(id,v);return v}
    nodes.forEach(([id])=>level(id));
    const counts=new Map(),pos=new Map();let width=700,height=0;
    for(const [id] of nodes){const l=levels.get(id);const col=counts.get(l)||0;counts.set(l,col+1);const x=30+col*300,y=30+l*110;pos.set(id,{x,y});width=Math.max(width,x+290);height=Math.max(height,y+100)}
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.setAttribute('width',String(width));svg.setAttribute('height',String(height));svg.setAttribute('role','img');svg.setAttribute('aria-label','Nœuds et connexions du workflow exécuté');
    function el(tag,attrs={},text){const n=document.createElementNS(svg.namespaceURI,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,String(v));if(text!=null)n.textContent=text;return n}
    for(const [id,n]of nodes){for(const [input,p]of parents(n)){const a=pos.get(String(p[0])),b=pos.get(id);svg.append(el('path',{d:`M ${a.x+130} ${a.y+65} C ${a.x+130} ${a.y+95}, ${b.x+130} ${b.y-25}, ${b.x+130} ${b.y}`,class:'workflow-edge-s2'}));svg.append(el('text',{x:b.x+134,y:b.y-6,class:'workflow-port-s2'},input))}}
    for(const[id,n]of nodes){const{x,y}=pos.get(id),g=el('g');g.append(el('rect',{x,y,width:260,height:65,rx:12,class:'workflow-node-s2'}));g.append(el('text',{x:x+12,y:y+24,class:'workflow-label-s2'},n.class_type.length>30?n.class_type.slice(0,29)+'…':n.class_type));g.append(el('text',{x:x+12,y:y+48,class:'workflow-port-s2'},'Nœud '+id));g.append(el('title',{},JSON.stringify(n.inputs,null,2)));svg.append(g)}
    scroll.append(svg);dialog.append(scroll);
    const download=document.createElement('a');download.className='secondary';download.href='/api/workflow/'+encodeURIComponent(selected.id);download.download='workflow_api.json';download.textContent='Télécharger le workflow API';dialog.append(download);
    const note=document.createElement('p');note.className='hint';note.textContent='Vue des connexions réellement enregistrées. Pour modifier le graphe, ouvrez ComfyUI. Les modèles restent chargés par la seule branche exécutée.';dialog.append(note);
    document.body.append(dialog);dialog.showModal();
  }catch(e){error('Workflow indisponible : '+e.message)}
}

async function analyzeResult(auto=false,index=null,expectedId=null){
  const j=selectedDone();
  if(!j||expectedId&&j.id!==expectedId){$('analysisStatus').textContent='Choisissez le rendu terminé à analyser.';return null}
  const outputIndex=index==null?(j.outputs[0]._source_index??0):Number(index);
  if(!Number.isInteger(outputIndex)||outputIndex<0)return null;
  try{
    $('analysisStatus').textContent='Analyse du rendu sélectionné…';
    const a=await api('/api/jobs/'+j.id+'/analyze',{model:$('ollamaModel').value,index:outputIndex});
    if(selectedResult!==j.id||a.job_id!==j.id||a.output_index!==outputIndex)return null;
    lastAnalysis=a;showAnalysis(a);
    $('analysisStatus').textContent=a.analysis_valid===false?'Rapport non exploitable · aucune correction lancée':`Analyse terminée · ${a.model||'vision locale'}`;
    return a;
  }catch(e){if(selectedResult===j.id)$('analysisStatus').textContent='Analyse impossible : '+e.message;return null}
}
async function runCorrections(outputIndex=null){
  if(correctionBusy)return;
  const initial=selectedDone();if(!initial)return;
  correctionBusy=true;correctionStop=false;correctionAttempts=0;buttons();
  const base={...initial.params};let current=initial;
  try{
    let a=await analyzeResult(false,outputIndex,current.id);
    const limit=Math.min(10,Math.max(1,+$('analysisLimit').value||3));
    while(a?.analysis_valid===true&&a.needs_correction&&correctionAttempts<limit&&!correctionStop){
      if(selectedResult!==current.id||a.job_id!==current.id)break;
      const fix=String(a.correction||'').trim();if(!fix)break;
      correctionAttempts++;
      const p={...base,prompt:base.prompt+'\n\n[Correction visuelle BAZOR] '+fix,seed:'-1'};
      const next=await api('/api/jobs',p,{headers:{'Idempotency-Key':crypto.randomUUID()}});
      selectedResult=next.id;resultSignature='';autoAnalyzedJobs.add(next.id);clearAnalysisS2();
      await refreshJobs();current=await waitForJob(next.id);
      if(current.status!=='done'||correctionStop)break;
      a=await analyzeResult(true,null,current.id);
    }
    $('analysisStatus').textContent=correctionStop?'Corrections arrêtées.':a?.analysis_valid!==true?'Analyse indisponible · aucune validation du rendu.':a.needs_correction?`Corrections terminées (${correctionAttempts}/${limit}) · résultat encore à vérifier.`:`Rendu jugé cohérent par le modèle · ${correctionAttempts} correction(s).`;
  }catch(e){$('analysisStatus').textContent=e.message}
  finally{correctionBusy=false;buttons()}
}
async function applyAnalysisCorrection(){
  const j=selectedDone();
  const a=lastAnalysis?.job_id===j?.id?lastAnalysis:j?.analysis;
  if(!j||!a||a.job_id!==j.id||a.analysis_valid!==true||!a.correction||correctionBusy)return;
  correctionBusy=true;buttons();
  try{
    const next=await api('/api/jobs',{...j.params,prompt:j.params.prompt+'\n\n[Correction visuelle BAZOR] '+a.correction,seed:'-1'},{headers:{'Idempotency-Key':crypto.randomUUID()}});
    selectedResult=next.id;resultSignature='';clearAnalysisS2();await refreshJobs();
  }catch(e){$('analysisStatus').textContent=e.message}
  finally{correctionBusy=false;buttons()}
}
