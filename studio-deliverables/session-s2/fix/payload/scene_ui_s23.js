// BAZOR_SCENE_S23: recipe belongs to the job, never to the mutable form.
let preparedS23=null;
function resetPreparedS23(){preparedS23=null;if($('preparedPromptS23'))$('preparedPromptS23').value='';if($('autoStyleS23'))$('autoStyleS23').checked=false}
function restorePreparedS23(p){resetPreparedS23();if(p.prepared_prompt){preparedS23={source:$('prompt').value.trim(),mode};$('preparedPromptS23').value=p.prepared_prompt;$('preparedPanelS23').open=true}$('autoStyleS23').checked=p.auto_style===true}
function preparedPayloadS23(){const same=preparedS23&&preparedS23.source===$('prompt').value.trim()&&preparedS23.mode===mode;return {prepared_prompt:same?($('preparedPromptS23')?.value||''):'',prepared_source:same?preparedS23.source:'',prepared_mode:same?mode:'',auto_style:$('autoStyleS23')?.checked===true}}
function mountSceneS23(){
 if($('preparedPanelS23'))return;
 const p=document.createElement('details');p.id='preparedPanelS23';p.className='advanced';
 p.innerHTML='<summary>Prompt envoyé et réglages par mots-clés</summary><p class="hint">Préparer avec Ollama conserve votre demande et propose une version anglaise modifiable. Si la demande ou le mode change, préparez-la de nouveau.</p><label for="preparedPromptS23">Version préparée pour le modèle</label><textarea id="preparedPromptS23" rows="5" placeholder="Cliquez sur Préparer pour le modèle"></textarea><label><input type="checkbox" id="autoStyleS23"> Déduire le cadrage et le style : corps entier, debout, portrait, noir et blanc, cinématique</label><p class="hint">Le mode Image/Vidéo et la référence restent ceux que vous choisissez. Aucun mot-clé ne déclenche un service en ligne.</p>';
 $('optimizeState').after(p);$('optimize').textContent='✧ Préparer pour le modèle';
 const b=document.createElement('button');b.type='button';b.className='secondary';b.id='recipeS23';b.textContent='Prompt et paramètres du résultat';b.onclick=showRecipeS23;$('sessionS2').querySelector('.toolbar').append(b);
}
async function optimize(){
 if(optimizing||submitting||correctionBusy)return;
 const request=payload(),source=$('prompt').value.trim(),selectedMode=mode;
 optimizing=true;buttons();$('optimizeState').textContent='Préparation locale : personnages, actions et objets doivent rester dans la description…';
 try{const r=await api('/api/optimize',request);if($('prompt').value.trim()!==source||mode!==selectedMode){$('optimizeState').textContent='Demande modifiée pendant la préparation : proposition écartée.';return}preparedS23={source,mode:selectedMode};$('preparedPromptS23').value=r.prompt;$('preparedPanelS23').open=true;$('optimizeState').textContent='Version préparée utilisée au prochain envoi. Vérifiez que chaque personnage et objet y figure. Votre demande initiale est conservée.'}catch(e){$('optimizeState').textContent=e.message}finally{optimizing=false;buttons()}
}
async function showRecipeS23(){
 const selected=jobs.find(j=>j.id===selectedResult);if(!selected){error('Choisissez un résultat pour consulter sa fiche.');return}
 try{
  const r=await api('/api/recipe/'+encodeURIComponent(selected.id));
  $('recipeDialogS23')?.remove();const d=document.createElement('dialog');d.id='recipeDialogS23';d.className='workflow-dialog-s2';
  const h=document.createElement('h2');h.textContent='Prompt et paramètres de cette création';d.append(h);
  const note=document.createElement('p');note.textContent=selected.id+' · '+String(r.mode).toUpperCase()+' · graine '+r.seed;d.append(note);
  for(const [label,value] of [['Votre demande',r.request],['Textes réellement envoyés',r.effective_texts?.map(x=>x.node+' · '+x.input+'\n'+x.text).join('\n\n')],['Modèles, réglages et route',JSON.stringify({models:r.models,settings:r.settings,route:r.route,graph_sha256:r.graph_sha256},null,2)]]){const title=document.createElement('h3');title.textContent=label;const pre=document.createElement('pre');pre.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px';pre.textContent=value||'Non enregistré';d.append(title,pre)}
  const a=document.createElement('a');a.href='/api/recipe/'+encodeURIComponent(selected.id);a.download='creation-'+selected.id+'.json';a.className='secondary';a.textContent='Télécharger cette fiche';const b=document.createElement('button');b.className='secondary';b.textContent='Fermer';b.onclick=()=>d.close();d.append(a,b);document.body.append(d);d.showModal();
 }catch(e){error(e.message)}
}
