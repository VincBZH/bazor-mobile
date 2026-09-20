const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.resolve(__dirname,'../work/studio/app/static/app.js'),'utf8');
const ui=fs.readFileSync(path.resolve(__dirname,'payload/session_ui.js'),'utf8');
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{value:'24',checked:false,innerHTML:'',textContent:'',disabled:false,className:'',classList:{values:new Set(),add(k){this.values.add(k)},remove(k){this.values.delete(k)},toggle(k,v){if(v)this.add(k);else this.remove(k)}},replaceChildren(){this.innerHTML=''}});return elements.get(id)}
const ctx={$:element,mode:'t2i',isImage:()=>true,asset:{id:'old-ref'},stylePresets:['realistic'],token:'x',health:{ollama:true},jobs:[],selectedResult:'',resultSignature:'',correctionBusy:false,uploading:false,submitting:false,optimizing:false,uploadSeq:0,previewUrl:null,sessionJobsS2:new Set(),autoAnalyzedJobs:new Set(),lastAnalysis:null,terminal:j=>j.status==='done',labels:{t2i:'Texte Image'},esc:x=>String(x??''),setTimeout:fn=>{},URL:{revokeObjectURL(){}},showAsset(){},updateMode(m){ctx.mode=m},applyPreset(){},syncStylePrompt(){},updateSpecs(){},changeView(){},error(){}};
vm.createContext(ctx);vm.runInContext(ui,ctx);
for(const name of ['payload','selectedDone','buttons','renderResult']){const fn=source.match(new RegExp('^function '+name+'\\([^\\n]*$','m'));assert(fn,name);vm.runInContext(fn[0],ctx)}
let n=0;function check(fn){fn();n++}
const old={id:'old',status:'done',params:{mode:'t2i'},outputs:[{media:'image',url:'/old.png'}]};ctx.jobs=[old];
check(()=>assert.equal(ctx.selectedDone(),undefined));
check(()=>{ctx.renderResult();assert(!element('result').innerHTML.includes('/old.png'))});
check(()=>{ctx.buttons();assert.equal(element('analyzeResult').disabled,true)});
check(()=>assert.equal(ctx.payload().asset_id,null));
check(()=>{ctx.mode='t2v';assert.equal(ctx.payload().asset_id,null)});
check(()=>{ctx.mode='i2v';assert.equal(ctx.payload().asset_id,'old-ref')});
check(()=>{ctx.selectedResult='old';ctx.renderResult();assert(element('result').innerHTML.includes('/old.png'))});
check(()=>{ctx.newCreationS2();assert.equal(ctx.selectedResult,'');assert.equal(ctx.asset,null);assert.equal(element('prompt').value,'')});
check(()=>assert.equal(ctx.generalCheckpointS2(['noob.safetensors','sd_xl_base_1.0.safetensors']),'sd_xl_base_1.0.safetensors'));
check(()=>assert.equal(ctx.generalCheckpointS2(['unknown.safetensors','pony.safetensors']),null));
(async()=>{
 ctx.jobs=[old,{...old,id:'new'}];ctx.selectedResult='old';
 ctx.api=async()=>{ctx.selectedResult='new';return{job_id:'old',output_index:0,analysis_valid:true}};
 check(()=>assert.equal(ctx.lastAnalysis,null));
 const a=await ctx.analyzeResult();assert.equal(a,null);assert.equal(ctx.lastAnalysis,null);n++;
 const f=source.match(/^function renderActivity\([^\n]*$/m)[0];assert(f.includes('visibleJobs'));assert(f.includes('sessionStartedS2'));n++;
 console.log(`PASS ${n} frontend unit scenarios; no browser rendering claimed.`);
})().catch(e=>{console.error(e);process.exitCode=1});
