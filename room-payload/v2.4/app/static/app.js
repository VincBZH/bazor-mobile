// BAZOR AI Room : aucune disponibilité supposée et aucune exécution de texte IA.
async function getJSON(url, options) {
  const resp = await fetch(url, options);
  const data = await resp.json();
  return { ...data, http_status: resp.status };
}
const byId = id => document.getElementById(id);
function availability(v) {
  if (v === true) return ['● CONFIRMÉ', 'ok'];
  if (v === false) return ['● INDISPONIBLE', 'bad'];
  return ['● NON VÉRIFIÉ', 'unknown'];
}
function setEngine(id, available, detail = '') {
  const el = byId(id + 'State');
  if (!el) return;
  const [label, css] = availability(available);
  el.textContent = label + (detail ? ' · ' + detail : '');
  el.className = css;
}
async function refresh() {
  const [s, p] = await Promise.all([getJSON('/api/status'), getJSON('/api/projects')]);
  const proj = s.state?.project || {};
  byId('globalState').textContent = (proj.delivery_state || proj.status || 'À VÉRIFIER').toUpperCase();
  const progress = Math.min(100, Math.max(0, Number(proj.progress_percent) || 0));
  byId('progressText').textContent = progress + '% (déclaré)';
  byId('progressBar').style.width = progress + '%';
  const card = byId('projectCard');
  card.textContent = [
    proj.name || proj.id || 'Projet',
    'État déclaré : ' + (proj.delivery_state || proj.status || '—'),
    'Tâche : ' + (proj.current_task || '—'),
    'Suite : ' + (proj.next_task || '—')
  ].join('\n');
  setEngine('gpt', null, 'passation manuelle');
  setEngine('mammouth', null, s.engines?.mammouth?.configured
    ? 'clé configurée ; appel réel non vérifié' : 'API non confirmée');
  setEngine('ollama', (s.engines?.core?.available && s.engines?.ollama?.available) || false,
    s.engines?.ollama?.model_count ? s.engines.ollama.model_count + ' modèles détectés' : 'pas de modèle vérifié');
  const projects = byId('projects');
  projects.replaceChildren();
  for (const project of p.projects || []) {
    const article = document.createElement('article');
    const title = document.createElement('h3');
    title.textContent = project.name || project.id || 'Projet';
    article.appendChild(title);
    for (const item of [project.status, project.next_step]) {
      const para = document.createElement('p');
      para.textContent = item || '—';
      article.appendChild(para);
    }
    projects.appendChild(article);
  }
  if (!projects.children.length) projects.textContent = 'Aucun projet déclaré.';
}
function chatText(data) {
  if (data.mode === 'manual_handoff') {
    return 'TEXTE PRÊT À COPIER pour ' + data.recipient.toUpperCase()
      + ' (aucune requête envoyée)\n\n' + data.message;
  }
  if (Array.isArray(data.results)) {
    return data.results.map(r => (
      (r.ok ? '● RÉPONSE CONFIRMÉE' : '● ÉCHEC') + ' — ' + r.provider
      + ' / modèle retourné : ' + (r.model || 'inconnu')
      + '\n' + (r.ok ? r.text : ('Erreur : ' + (r.error || 'non vérifiée')))
    )).join('\n\n') + '\n\nStatut global : ' + (data.ok ? 'confirmé par Core' : 'partiel ou bloqué');
  }
  return 'BLOQUÉ : ' + (data.error || 'réponse invalide') + ' (HTTP ' + data.http_status + ')';
}
byId('chatBtn').addEventListener('click', async () => {
  const prompt = byId('chatPrompt').value.trim();
  const target = byId('chatTarget').value;
  if (!prompt) { byId('chatResult').textContent = 'Écris d’abord ta demande.'; return; }
  if ((target === 'mammouth' || target === 'notrack' || target === 'both') && !byId('allowExternal').checked) {
    byId('chatResult').textContent = "Coche l’autorisation avant un appel externe.";
    return;
  }
  byId('chatBtn').disabled = true;
  byId('chatResult').textContent = 'Transmission locale en cours…';
  try {
    const data = await getJSON('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: prompt, target, allow_external: byId('allowExternal').checked})
    });
    byId('chatResult').textContent = chatText(data);
  } catch (error) {
    byId('chatResult').textContent = 'Erreur locale : ' + (error?.name || 'connexion impossible');
  } finally {
    byId('allowExternal').checked = false; // Consentement pour un seul envoi.
    byId('chatBtn').disabled = false;
  }
});
byId('copyGPT').addEventListener('click', async () => {
  const text = byId('chatPrompt').value.trim();
  if (!text) { byId('chatResult').textContent = 'Écris d’abord ta demande.'; return; }
  try {
    await navigator.clipboard.writeText(text);
    byId('chatResult').textContent = 'Texte copié. Colle-le dans ta conversation GPT (aucune liaison automatique).';
  } catch (_) {
    byId('chatResult').textContent = 'Copie manuellement le texte ci-dessous :\n\n' + text;
  }
});
byId('routeBtn').addEventListener('click', async () => {
  const task_class = byId('taskClass').value;
  const mode = byId('mode').value;
  try {
    const body = mode === 'auto' ? {task_class} : {task_class, manual: mode};
    const result = await getJSON('/api/route', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    byId('routeResult').textContent = result.selected
      ? 'Moteur confirmé : ' + result.selected
      : 'Aucun routage automatique confirmé. Choisis le destinataire dans « Discuter ».';
  } catch (_) {
    byId('routeResult').textContent = 'Core / Room indisponible.';
  }
});
refresh().catch(() => { byId('globalState').textContent = 'ÉTAT INCONNU'; });
setInterval(() => refresh().catch(() => {}), 10000);
