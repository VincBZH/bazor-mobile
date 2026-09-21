import asyncio,base64,io,json,sys,tempfile,unittest,uuid,shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'work/studio/app'),str(ROOT/'work/studio/tests'),str(ROOT/'fix')]
from PIL import Image
from aiohttp import web
from aiohttp.test_utils import TestServer,TestClient
from studio import create_app
from workflows import parameters,build,patch_h3_graph
from fake_comfy import FakeComfy,object_info
from studio_session_guard import normalize_analysis_image,read_media_limited,select_vision_model,engine_error_summary
from studio_h3_inventory import resolve_h3_inventory
from apply_fix import install,transform_js,transform_workflows,transform_studio,preserve_converter,transform_controls
from rollback import rollback
from studio_route_s23 import native_h3, graph_for_local, recipe_for, remote_nodes
from workflows import generation_prompt, generation_negative

def native_registry():
    """Contract fixture from ComfyUI native H3 + ClipProj, not a GPU simulator."""
    info=object_info()
    def fields(**kw):return {k:[v] for k,v in kw.items()}
    def node(**kw):return {'input':{'required':fields(**kw)}}
    info.update({
        'UNETLoader':node(unet_name=['minimax_h3_fl2va_pruned_w4a8_mixed.safetensors'],weight_dtype=['default']),
        'CLIPLoader':node(clip_name=['qwen3vl_4b_int8_convrot.safetensors'],type=['minimax','krea2'],device=['default','cpu']),
        'VAELoader':node(vae_name=['minimax_h3_video_vae_int8_convrot.safetensors']),
        'ClipProjApply':node(clip='CLIP',projection=['mmh3-4b-ClipProj-v3-mlp.safetensors']),
        'MiniMaxH3ImageToVideo':node(clip='CLIP',vae='VAE',prompt='STRING',width='INT',height='INT',length='INT'),
        'RandomNoise':node(noise_seed='INT'),
        'BasicGuider':node(model='MODEL',conditioning='CONDITIONING'),
        'KSamplerSelect':node(sampler_name=['res_multistep']),
        'BasicScheduler':node(model='MODEL',scheduler=['simple'],steps='INT',denoise='FLOAT'),
        'SamplerCustomAdvanced':node(noise='NOISE',guider='GUIDER',sampler='SAMPLER',sigmas='SIGMAS',latent_image='LATENT'),
    })
    info['MiniMaxH3ImageToVideo']['input']['optional']=fields(first_frame='IMAGE',last_frame='IMAGE')
    info['LoadImage']=node(image=['old.png'])
    return info

class Routes(unittest.TestCase):
    def test_engine_error_names_node_and_setting(self):
        result=engine_error_summary({'node_errors':{'105:6':{'class_type':'UNETLoader','errors':[{'details':'unet_name: missing.safetensors'}]}}})
        self.assertIn('UNETLoader (105:6)',result);self.assertIn('unet_name',result)
    def test_text_modes_drop_stale_reference(self):
        for mode in ('t2i','t2v'):
            p=parameters({'mode':mode,'engine':'sd' if mode=='t2i' else 'wan','checkpoint':'sdxl_test.safetensors','prompt':'bear','asset_id':'old'})
            self.assertIsNone(p['asset_id']);g=build(p,object_info(),'stale.png')
            self.assertNotIn('LoadImage',[n['class_type'] for n in g.values()])
    def test_reference_modes_require_source(self):
        for mode in ('i2i','i2v','v2v'):
            with self.assertRaises(ValueError):parameters({'mode':mode,'engine':'sd' if mode=='i2i' else 'wan','prompt':'bear'})
    def test_reference_modes_keep_intended_source(self):
        for mode in ('i2i','i2v','v2v'):
            p=parameters({'mode':mode,'engine':'sd' if mode=='i2i' else 'wan','checkpoint':'sdxl_test.safetensors','asset_id':'new','prompt':'bear'})
            g=build(p,object_info(),'new.png');self.assertEqual(g['56']['inputs']['image'],'new.png')
    def test_h3_text_cannot_reuse_template_avatar(self):
        graph={'1':{'class_type':'LoadImage','inputs':{'image':'old.png'}}}
        with self.assertRaisesRegex(ValueError,'source image'):patch_h3_graph(graph,parameters({'mode':'t2v','prompt':'bear'}))
    def test_decode_and_normalize_rgba(self):
        stream=io.BytesIO();Image.new('RGBA',(1600,800),(12,13,14,0)).save(stream,'PNG')
        with Image.open(io.BytesIO(normalize_analysis_image(stream.getvalue()))) as im:
            self.assertEqual(im.format,'JPEG');self.assertEqual(im.mode,'RGB');self.assertEqual(im.size,(1024,512))
    def test_invalid_media_fails_before_vision(self):
        with self.assertRaisesRegex(ValueError,'décodable'):normalize_analysis_image(b'<html>missing image</html>')

class Stream:
    def __init__(self,chunks):self.chunks=chunks
    async def iter_chunked(self,size):
        for chunk in self.chunks:await asyncio.sleep(0);yield chunk

class Vision(unittest.IsolatedAsyncioTestCase):
    async def test_chunked_media_is_complete(self):
        raw=await read_media_limited(Stream([b'abc',b'de',b'f']))
        self.assertEqual(raw,b'abcdef')
    async def test_chunked_limit_and_empty(self):
        for chunks,limit in [([b'ab',b'cd'],3),([],30)]:
            with self.assertRaises(ValueError):await read_media_limited(Stream(chunks),limit)
    async def test_text_model_rejected_vision_selected(self):
        s=type('S',(),{'ollama':'http://127.0.0.1:11434'})()
        s.request=AsyncMock(side_effect=[{'capabilities':['completion']},{'capabilities':['completion','vision']}])
        self.assertEqual(await select_vision_model(s,'coder',['coder','vision']),'vision')
    async def test_no_vision_no_fake_analysis(self):
        s=type('S',(),{'ollama':''})();s.request=AsyncMock(return_value={'capabilities':['completion']})
        with self.assertRaisesRegex(ValueError,'capacité vision'):await select_vision_model(s,'text',['text'])

class Integration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.fake=FakeComfy();engine=self.fake.app()
        async def show(r):return web.json_response({'capabilities':['completion','vision']})
        engine.router.add_post('/api/show',show)
        self.engine=TestServer(engine);await self.engine.start_server();base=str(self.engine.make_url('')).rstrip('/')
        app=create_app(self.temp.name,base,base);self.s=app['studio'];self.client=TestClient(TestServer(app));await self.client.start_server()
        self.token=(await (await self.client.get('/api/config')).json())['token']
    async def asyncTearDown(self):
        await self.client.close();await self.engine.close();self.temp.cleanup()
    async def post(self,url,data,key=None):
        headers={'X-Studio-Token':self.token}
        if key:headers['Idempotency-Key']=key
        r=await self.client.post(url,json=data,headers=headers);return r.status,await r.json()
    async def test_job_to_media_to_vision_keeps_job_and_prompt(self):
        status,j=await self.post('/api/jobs',{'mode':'t2i','engine':'sd','checkpoint':'sdxl_test.safetensors','prompt':'bear with blanket and straw','asset_id':'unknown-old-reference'},uuid.uuid4().hex)
        self.assertEqual(status,200);self.assertEqual(self.fake.upload_count,0)
        self.fake.complete(j['prompt_id']);await self.s.reconcile()
        self.fake.chat_response=json.dumps({'score':75,'needs_correction':True,'detected':['paille absente'],'correction':'montrer la paille','preserved':['ourson','couverture']})
        status,a=await self.post('/api/jobs/'+j['id']+'/analyze',{'model':'wrong-text-model'})
        self.assertEqual(status,200,a);self.assertEqual(a['job_id'],j['id']);self.assertEqual(a['output_index'],0)
        chat=self.fake.last_chat;self.assertIn('bear with blanket and straw',chat['messages'][1]['content'])
        with Image.open(io.BytesIO(base64.b64decode(chat['messages'][1]['images'][0]))) as im:self.assertEqual(im.format,'JPEG')
    async def test_busy_gpu_blocks_analysis(self):
        self.fake.queued.append([1,'other',{}, {},[]])
        status,a=await self.post('/api/jobs/old/analyze',{})
        self.assertEqual(status,400);self.assertIn('générations',a['error']);self.assertIsNone(self.fake.last_chat)
    async def test_recipe_matches_submitted_graph_and_retry(self):
        raw={'mode':'t2i','engine':'sd','checkpoint':'sdxl_test.safetensors','prompt':'Deux adultes sur un banc','prepared_prompt':'Two adults on a bench.','prepared_source':'Deux adultes sur un banc','prepared_mode':'t2i','seed':42}
        key=uuid.uuid4().hex;status,j=await self.post('/api/jobs',raw,key)
        self.assertEqual(status,200,j)
        result=await self.client.get('/api/recipe/'+key);recipe=await result.json()
        self.assertEqual(recipe['request'],raw['prompt']);self.assertEqual(recipe['seed'],42)
        self.assertTrue(any('Two adults on a bench.' in x['text'] for x in recipe['effective_texts']))
        expected=recipe_for(j['params'],self.fake.last_payload['prompt'],recipe['route'])
        self.assertEqual(recipe,expected)
        await self.post('/api/jobs',{**raw,'prompt':'different scene'},key)
        self.assertEqual(self.fake.post_count,1)
        self.assertEqual(await (await self.client.get('/api/recipe/'+key)).json(),recipe)
    async def test_native_h3_submits_without_converting_cloud_template(self):
        self.fake.info=native_registry()
        status,j=await self.post('/api/jobs',{'mode':'t2v','prompt':'a boat crossing a lake','seed':3},uuid.uuid4().hex)
        self.assertEqual(status,200,j);self.assertEqual(self.fake.post_count,1)
        self.assertEqual(j['recipe']['route']['workflow'],'native-h3-s23')
        self.assertEqual(j['recipe']['route']['frames_effective'],56)
        self.assertFalse(remote_nodes(self.fake.last_payload['prompt']))
    async def test_missing_local_model_does_not_submit(self):
        self.fake.info=native_registry();del self.fake.info['ClipProjApply']
        status,j=await self.post('/api/jobs',{'mode':'t2v','prompt':'a boat'},uuid.uuid4().hex)
        self.assertEqual(status,400);self.assertIn('ClipProjApply',j['error']);self.assertEqual(self.fake.post_count,0)
    async def test_missing_recipe_has_no_invented_history(self):
        r=await self.client.get('/api/recipe/unknown');self.assertEqual(r.status,400)

class SceneRouting(unittest.IsolatedAsyncioTestCase):
    def params(self,**kw):return parameters({'mode':'t2v','prompt':'a boat on the lake','seed':7,**kw})
    def test_native_graph_matches_local_contract(self):
        g,route=native_h3(self.params(),native_registry(),None,'test')
        self.assertEqual(g['h3_condition']['inputs']['length'],56)
        self.assertNotIn('LoadImage',[n['class_type'] for n in g.values()])
        self.assertEqual(g['h3_sample']['inputs']['latent_image'],['h3_condition',1])
        link=g['h3_condition']['inputs']['clip'];self.assertEqual(g[link[0]]['class_type'],'ClipProjApply')
        self.assertIn('format.codec',g['h3_save']['inputs']);self.assertNotIn('codec',g['h3_save']['inputs'])
        self.assertFalse(route['audio'])
    def test_reference_uses_only_new_upload_despite_cached_list(self):
        g,_=native_h3(self.params(mode='i2v',asset_id='new'),native_registry(),'fresh.png','test')
        self.assertEqual(g['h3_image']['inputs']['image'],'fresh.png')
        self.assertEqual(g['h3_condition']['inputs']['first_frame'],['h3_image',0])
    def test_missing_reference_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'référence'):native_h3(self.params(mode='i2v',asset_id='new'),native_registry(),None,'test')
    def test_duration_converted_to_24_fps(self):
        g,_=native_h3(self.params(fps=12),native_registry(),None,'test')
        self.assertEqual(g['h3_condition']['inputs']['length'],107)
    def test_missing_sampler_is_not_silently_replaced(self):
        info=native_registry();info['KSamplerSelect']['input']['required']['sampler_name']=[['euler']]
        with self.assertRaisesRegex(ValueError,'res_multistep'):native_h3(self.params(),info,None,'test')
    def test_unrecognized_required_field_fails_before_submit(self):
        info=native_registry();info['MiniMaxH3ImageToVideo']['input']['required']['future_required']=['STRING']
        with self.assertRaisesRegex(ValueError,'future_required'):native_h3(self.params(),info,None,'test')
    def test_old_savevideo_contract(self):
        info=native_registry();info['SaveVideo']=object_info(dynamic=False)['SaveVideo']
        g,_=native_h3(self.params(),info,None,'test');self.assertIn('codec',g['h3_save']['inputs'])
    async def test_logged_hailuo_rejected_before_conversion(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'minimax_t2v.json'
            path.write_text(json.dumps({'nodes':[{'id':23,'type':'MinimaxHailuo03TextToVideoNode','inputs':{'model.prompt':'test'}}]}))
            s=type('S',(),{})();s.h3_workflow_candidates=lambda mode:[path];s.request=AsyncMock()
            with self.assertRaisesRegex(ValueError,'en ligne exclu'):await graph_for_local(s,self.params(),{'ModelSamplingMiniMaxH3':{}},None,'test')
            s.request.assert_not_awaited()
    async def test_cloud_rejected_after_conversion_too(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'local_t2v.json';path.write_text('{"nodes": []}')
            s=type('S',(),{})();s.h3_workflow_candidates=lambda mode:[path]
            s.request=AsyncMock(return_value={'23':{'class_type':'MinimaxHailuo03TextToVideoNode','inputs':{}}})
            with self.assertRaisesRegex(ValueError,'en ligne exclu'):await graph_for_local(s,self.params(),{'ModelSamplingMiniMaxH3':{}},None,'test')
    async def test_image_route_stays_sd_when_h3_is_installed(self):
        p=self.params(mode='t2i',engine='sd',checkpoint='sdxl_test.safetensors')
        g,route=await graph_for_local(None,p,native_registry(),None,'test')
        self.assertEqual(route['family'],'sd');self.assertIn('CheckpointLoaderSimple',[n['class_type'] for n in g.values()])
    def test_prepared_prompt_rejected_when_source_or_mode_changes(self):
        raw={'prepared_prompt':'An English boat.','prepared_source':'a boat on the lake','prepared_mode':'t2v'}
        self.assertTrue(self.params(**raw)['prepared_prompt'])
        self.assertEqual(self.params(**{**raw,'prepared_source':'old'})['prepared_prompt'],'')
        self.assertEqual(self.params(**{**raw,'prepared_mode':'t2i'})['prepared_prompt'],'')
    def test_keywords_are_optional_and_do_not_route_to_remote(self):
        p=self.params(prompt='portrait corps entier debout sans noir et blanc',auto_style=True,style_presets=['portrait'])
        self.assertEqual(p['style_presets'],['fullbody','standing'])
        self.assertEqual(p['engine'],'wan');self.assertEqual(p['mode'],'t2v')
        p=self.params(prompt='corps entier debout',auto_style=False)
        self.assertNotIn('fullbody',p['style_presets'])
    def test_styles_do_not_collapse_many_actors_into_one(self):
        p=self.params(prompt='Two adults seated and a third standing.',style_presets=['fullbody','standing','natural'])
        prompt=generation_prompt(p);self.assertNotIn('one adult subject',prompt);self.assertNotIn('one clear action',prompt)
        self.assertIn('Keep other subjects',prompt);self.assertNotIn('seated, sitting',generation_negative(p))
    def test_recipe_is_immutable_snapshot_with_exact_texts(self):
        p=self.params();g,route=native_h3(p,native_registry(),None,'test');r=recipe_for(p,g,route)
        text=g['h3_condition']['inputs']['prompt'];g['h3_condition']['inputs']['prompt']='changed';route['audio']=True;p['style_presets'].append('bw')
        self.assertEqual(r['effective_texts'][0]['text'],text);self.assertFalse(r['route']['audio']);self.assertEqual(r['settings']['style_presets'],['realistic'])
    def test_remote_metadata_does_not_reject_local_saveoutput(self):
        g={'1':{'class_type':'SaveOutput','inputs':{}}};self.assertEqual(remote_nodes(g),[])
        g['2']={'class_type':'UnknownAPI','inputs':{}};self.assertEqual(remote_nodes(g,{'UnknownAPI':{'is_api_node':True}}),['UnknownAPI'])
    def test_visual_correction_survives_browser_style_block(self):
        p=self.params(prompt='Two people on a boat.\n\n[Style visuel] browser style preview\n\n[Correction visuelle BAZOR] Show the missing red hat.')
        text=generation_prompt(p);self.assertIn('Show the missing red hat.',text);self.assertNotIn('browser style preview',text)

class Installation(unittest.TestCase):
    def test_transaction_idempotence_and_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'studio';shutil.copytree(next((ROOT/'inspect').glob('AI_Simple*305*'),None) or ROOT/'inspect/AI_Simple_Studio_BAZOR_V3_3.0.5_PLAYWRIGHT_INSTALL_FIX_20260917',root)
            before=(root/'app/static/app.js').read_bytes()
            install(root);self.assertEqual(install(root)['status'],'already_installed')
            rollback(root);self.assertEqual((root/'app/static/app.js').read_bytes(),before)
            self.assertFalse((root/'app/studio_session_guard.py').exists())
    def test_unknown_source_has_no_partial_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'studio';shutil.copytree(ROOT/'inspect/AI_Simple_Studio_BAZOR_V3_3.0.5_PLAYWRIGHT_INSTALL_FIX_20260917',root)
            path=root/'app/studio.py';path.write_text('unknown local version')
            old=(root/'app/static/app.js').read_bytes()
            with self.assertRaises(ValueError):install(root)
            self.assertEqual((root/'app/static/app.js').read_bytes(),old)

class Recovery(unittest.TestCase):
    def test_partial_write_failure_restores_all_originals(self):
        import apply_fix
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'studio';shutil.copytree(ROOT/'inspect/AI_Simple_Studio_BAZOR_V3_3.0.5_PLAYWRIGHT_INSTALL_FIX_20260917',root)
            originals={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            write=apply_fix.atomic_write;triggered=False
            def fail_once(path,data):
                nonlocal triggered
                if path==root/'app/studio.py' and not triggered:
                    triggered=True;raise OSError('simulated locked file')
                return write(path,data)
            with patch.object(apply_fix,'atomic_write',side_effect=fail_once):
                with self.assertRaises(OSError):install(root)
            for name,data in originals.items():self.assertEqual((root/name).read_bytes(),data,name)
            self.assertFalse((root/'app/studio_h3_controls.py').exists())
    def test_prior_ui_converter_is_retained(self):
        source="def _api_graph(graph):\n    return graph['converted']\n"
        updated="def _api_graph(graph):\n    return unwrap_graph(graph)\n"
        from studio_h3_controls import unwrap_graph
        namespace={'unwrap_graph':unwrap_graph};exec(preserve_converter(source,updated),namespace)
        graph={'1':{'class_type':'Test','inputs':{}}}
        self.assertIs(namespace['_api_graph']({'converted':graph}),graph)
        self.assertIs(namespace['_api_graph'](graph),graph)

class Inventory(unittest.TestCase):
    def fixture(self):
        graph={'105:6':{'class_type':'UNETLoader','inputs':{'unet_name':'minimax_h3_fl2va_pruned_int8_convrot.safetensors'}},
               '105:11':{'class_type':'VAELoader','inputs':{'vae_name':'minimax_h3_video_vae_fp16.safetensors'}},
               '105:13':{'class_type':'CLIPLoader','inputs':{'clip_name':'qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors','type':'minimax','device':'default'}},
               '105:14':{'class_type':'MiniMaxH3ImageToVideo','inputs':{'clip':['105:13',0]}}}
        def node(**fields):return {'input':{'required':{k:[v] for k,v in fields.items()}}}
        info={'UNETLoader':node(unet_name=['minimax_h3_fl2va_pruned_w4a8_mixed.safetensors','wan2.2_ti2v_5B_fp16.safetensors']),
              'VAELoader':node(vae_name=['minimax_h3_video_vae_int8_convrot.safetensors','minimax_h3_audio_vae_fp32.safetensors']),
              'CLIPLoader':node(clip_name=['qwen3vl_4b_int8_convrot.safetensors'],type=['minimax','krea2'],device=['default','cpu']),
              'ClipProjApply':node(clip='CLIP',projection=['mmh3-4b-ClipProj-v3-mlp.safetensors'])}
        return graph,info
    def test_exact_logged_three_mismatches_and_projection_wiring(self):
        g,info=self.fixture();resolved,changes=resolve_h3_inventory(g,info)
        self.assertEqual(resolved['105:6']['inputs']['unet_name'],'minimax_h3_fl2va_pruned_w4a8_mixed.safetensors')
        self.assertEqual(resolved['105:11']['inputs']['vae_name'],'minimax_h3_video_vae_int8_convrot.safetensors')
        self.assertEqual(resolved['105:13']['inputs']['type'],'krea2')
        self.assertEqual(resolved['105:13']['inputs']['device'],'cpu')
        link=resolved['105:14']['inputs']['clip'];self.assertEqual(resolved[link[0]]['class_type'],'ClipProjApply')
        self.assertEqual(resolved[link[0]]['inputs']['clip'],['105:13',0])
        self.assertEqual(g['105:13']['inputs']['type'],'minimax','Original template remains intact')
    def test_no_cross_family_fallback(self):
        g,info=self.fixture();info['UNETLoader']['input']['required']['unet_name']=[['wan2.2_ti2v_5B_fp16.safetensors']]
        with self.assertRaisesRegex(ValueError,'absent'):resolve_h3_inventory(g,info)
    def test_4b_without_projection_is_rejected(self):
        g,info=self.fixture();del info['ClipProjApply']
        with self.assertRaisesRegex(ValueError,'ClipProjApply'):resolve_h3_inventory(g,info)
    def test_projection_is_idempotent(self):
        g,info=self.fixture();r,_=resolve_h3_inventory(g,info);again,_=resolve_h3_inventory(r,info)
        self.assertEqual(r,again)
    def test_unknown_projection_is_rejected(self):
        g,info=self.fixture();info['ClipProjApply']['input']['required']['projection']=[['mmh3-8b-ClipProj-v3-mlp.safetensors']]
        with self.assertRaisesRegex(ValueError,'absent'):resolve_h3_inventory(g,info)
    def test_original_model_in_subfolder_precedes_variant(self):
        g,info=self.fixture();name='H3/minimax_h3_fl2va_pruned_int8_convrot.safetensors'
        info['UNETLoader']['input']['required']['unet_name'][0].append(name)
        result,_=resolve_h3_inventory(g,info);self.assertEqual(result['105:6']['inputs']['unet_name'],name)

class H3Geometry(unittest.TestCase):
    def params(self):
        return parameters({'mode':'t2v','prompt':'a boat on a lake','width':832,'height':480,'frames':49,'seed':7})
    def graph(self):
        return {'1':{'class_type':'MiniMaxH3ImageToVideo','inputs':{'prompt':'old','clip':['2',0]}},
                '3':{'class_type':'KSampler','inputs':{'steps':20,'seed':1}}}
    def info(self):
        return {'MiniMaxH3ImageToVideo':{'input':{'required':{'width':['INT',{}],'height':['INT',{}]}}}}
    def test_missing_export_fields_use_live_schema(self):
        g=self.graph();r=patch_h3_graph(g,self.params(),info=self.info())
        self.assertEqual((g['1']['inputs']['width'],g['1']['inputs']['height']),(832,480))
        self.assertEqual(g['1']['inputs']['length'],56)
        self.assertEqual(r['dimension_nodes'],['1'])
    def test_nested_converter_response(self):
        g={'data':{'output':{'prompt':self.graph()}}}
        r=patch_h3_graph(g,self.params(),info=self.info())
        self.assertEqual(r['graph']['1']['inputs']['width'],832)
    def test_alias_fields(self):
        from studio_h3_controls import patch_controls
        g={'1':{'class_type':'CustomVideo','inputs':{'video_width':640,'video_height':352}}}
        patch_controls(g,self.params(),'test')
        self.assertEqual(g['1']['inputs']['video_height'],480)
        self.assertNotIn('width',g['1']['inputs'])
    def test_unknown_dimensions_fail_without_controls_mutation(self):
        import copy
        from studio_h3_controls import patch_controls
        g=self.graph();before=copy.deepcopy(g)
        with self.assertRaisesRegex(ValueError,'MiniMaxH3ImageToVideo'):patch_controls(g,self.params(),'test')
        self.assertEqual(g,before)
    def test_geometry_link_does_not_change_shared_primitive(self):
        g=self.graph();g['1']['inputs'].update(width=['4',0],height=['4',0])
        g['4']={'class_type':'PrimitiveInt','inputs':{'value':1024}}
        patch_h3_graph(g,self.params())
        self.assertEqual(g['1']['inputs']['width'],832)
        self.assertEqual(g['4']['inputs']['value'],1024)
    def test_all_native_geometry_nodes_agree_preview_unchanged(self):
        g=self.graph();g['1']['inputs'].update(width=1344,height=768)
        g['4']={'class_type':'EmptyMiniMaxH3LatentAV','inputs':{'width':1344,'height':768,'length':124}}
        g['5']={'class_type':'PreviewResize','inputs':{'width':200,'height':200}}
        patch_h3_graph(g,self.params())
        self.assertEqual(g['1']['inputs']['length'],g['4']['inputs']['length'])
        self.assertEqual(g['4']['inputs']['width'],832)
        self.assertEqual(g['5']['inputs']['width'],200)
    def test_wrong_live_type_not_used_as_dimensions(self):
        from studio_h3_controls import patch_controls
        info=self.info();info['MiniMaxH3ImageToVideo']['input']['required']['width']=['IMAGE',{}]
        with self.assertRaises(ValueError):patch_controls(self.graph(),self.params(),'test',info)
    def test_unconverted_ui_workflow_rejected(self):
        with self.assertRaisesRegex(ValueError,'format API'):patch_h3_graph({'nodes':[{'type':'H3'}]},self.params())

if __name__=='__main__':unittest.main(verbosity=2)
