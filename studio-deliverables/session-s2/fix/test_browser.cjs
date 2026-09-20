let playwright;try{playwright=require('playwright')}catch{playwright=require('/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')}
const {chromium}=playwright;
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const staticRoot=path.resolve(__dirname,'../work/studio/app/static');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}});let errors=[],posts=[],analyses=0;
  page.on('pageerror',e=>errors.push(e.message));
  let records=[{id:'old-job',created:1,status:'done',stage:'Création terminée',params:{prompt:'OLD CONTENT MUST STAY IN GALLERY',mode:'t2i'},outputs:[{media:'image',url:'/fixture.png',_source_index:0}]}];
  await page.addInitScript(()=>{
    localStorage.setItem('studio2-draft',JSON.stringify({prompt:'OLD DRAFT',asset_id:'old-avatar',mode:'i2v',style_presets:['fullbody']}));
    window.WebSocket=class{constructor(){}close(){}};
  });
  await page.route('http://127.0.0.1:8191/**',async route=>{
   const req=route.request(),url=new URL(req.url());let data={};
   if(url.pathname==='/'||url.pathname.startsWith('/static/')){
    const file=url.pathname==='/'?'index.html':url.pathname.slice(8);
    return route.fulfill({path:path.join(staticRoot,file),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
   }
   if(url.pathname==='/fixture.png')return route.fulfill({body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jhCsAAAAASUVORK5CYII=','base64'),contentType:'image/png'});
   if(url.pathname==='/api/config')data={token:'test',version:'3.0.5'};
   if(url.pathname==='/api/health')data={ready:true,comfy:true,ollama:true,models:['gemma3:4b'],checkpoints:['sd_xl_base_1.0.safetensors'],devices:[],profile:{family:'wan',label:'Wan'},workflows:{}};
   if(url.pathname==='/api/jobs'){
    if(req.method()==='POST'){
      const params=req.postDataJSON();posts.push(params);
      const j={id:'new-job-'+posts.length,created:Date.now()/1000,status:'done',stage:'Création terminée',params,outputs:[{media:'image',url:'/fixture.png',_source_index:0}]};records.unshift(j);data=j;
    }else data={jobs:records};
   }
   if(url.pathname.endsWith('/analyze')){analyses++;data={job_id:url.pathname.split('/')[3],output_index:0,analysis_valid:true,score:90,needs_correction:false,model:'gemma3:4b',detected:[],preserved:[]}}
   if(url.pathname==='/api/estimate')data={seconds:null,samples:0};
   if(url.pathname==='/api/optimize')data={prompt:'Two adults waving by a lake.'};
   if(url.pathname.startsWith('/api/recipe/'))data={request:'Deux adultes au bord du lac',mode:'t2i',seed:42,effective_texts:[{node:'6',input:'text',text:'Two adults waving by a lake.'}],models:[],settings:{},route:{workflow:'native-sd'},graph_sha256:'test'};
   if(url.pathname==='/api/log')data={lines:[]};
   if(url.pathname==='/api/prompts')data={prompts:[]};
   if(url.pathname==='/api/projects')data={projects:[]};
   return route.fulfill({json:data});
  });
  await page.goto('http://127.0.0.1:8191/');await page.waitForSelector('#sessionS2');
  assert.equal(await page.locator('#result img').count(),0,'No historical preview on launch');
  assert.equal(await page.locator('#prompt').inputValue(),'','No draft prompt restored');
  assert.equal(await page.locator('#assetPreview:not(.hidden)').count(),0,'No draft reference restored');
  assert.equal(await page.locator('#jobList').innerText(),'','History absent from current activity');
  assert(await page.locator('#analyzeResult').isDisabled(),'No implicit analysis target');
  await page.locator('#analysisAuto').check();
  await page.locator('[data-view="gallery"]').click();
  assert.equal(await page.locator('.gallery-card').count(),1,'History retained in gallery');
  await page.locator('[data-view="create"]').click();
  await page.locator('#discoverS2').click();await page.locator('[data-example-s2="bear"]').click();
  assert((await page.locator('#prompt').inputValue()).includes('paille'));
  assert.equal(posts.length,0,'Discovery never starts computation');
  await page.locator('#generate').click();await page.waitForSelector('#result img');
  assert.equal(posts.length,1);assert.equal(posts[0].asset_id,null);assert.equal(posts[0].mode,'t2i');
  await page.locator('#analyzeResult').click();await page.waitForFunction(()=>document.querySelector('#analysisStatus').textContent.includes('Analyse terminée'));
  assert.equal(analyses,1);
  await page.locator('#newCreationS2').click();
  assert.equal(await page.locator('#result img').count(),0);assert(await page.locator('#analysisReport').evaluate(e=>e.classList.contains('hidden')));
  await page.locator('[data-mode="i2v"]').click();await page.locator('#prompt').fill('A quiet lake');
  await page.locator('#generate').click();assert.equal(posts.length,1,'Missing I2V source rejected');
  await page.locator('[data-mode="t2v"]').click();assert(await page.locator('#uploadArea').evaluate(e=>e.classList.contains('hidden')));
  await page.locator('#newCreationS2').click();
  await page.locator('#prompt').fill('Deux adultes au bord du lac');await page.locator('#optimize').click();
  await page.waitForFunction(()=>document.querySelector('#preparedPromptS23').value==='Two adults waving by a lake.');
  assert.equal(await page.locator('#prompt').inputValue(),'Deux adultes au bord du lac');
  await page.locator('#autoStyleS23').check();await page.locator('#generate').click();
  await page.waitForFunction(()=>document.querySelector('#generate').disabled===false);
  assert.equal(posts.at(-1).prepared_prompt,'Two adults waving by a lake.');assert.equal(posts.at(-1).auto_style,true);
  await page.locator('#recipeS23').click();await page.waitForSelector('#recipeDialogS23[open]');
  assert((await page.locator('#recipeDialogS23').innerText()).includes('Two adults waving by a lake.'));
  await page.locator('#recipeDialogS23 button').click();
  await page.locator('#newCreationS2').click();
  assert.equal(await page.locator('#preparedPromptS23').inputValue(),'');assert.equal(await page.locator('#autoStyleS23').isChecked(),false);
  await page.locator('#discoverS2').click();
  await page.screenshot({path:path.resolve(__dirname,'../studio-session-s2-preview.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: browser flow — clean startup, explicit history, source isolation, discovery, generation request, correct analysis target, reset, required I2V source, separate prepared prompt, result recipe and keyword preference. Mock engines; no GPU generation.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
