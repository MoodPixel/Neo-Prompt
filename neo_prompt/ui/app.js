/* Neo Prompt creative-language UI. Source-faithful prompting, vision, separate batch destinations and owned profiles. */
const state = {
  page: 'overview', comfyAutoSelections:{},comfyAutoCatalog:{},comfyAuto:{prompt:{route:'llm',model:'',mmproj:'',chat_handler:'',runtime_options:{}},caption:{route:'vlm',model:'',mmproj:'',chat_handler:'',runtime_options:{}},batch:{route:'vlm',model:'',mmproj:'',chat_handler:'',runtime_options:{}}}, comfyMode:{prompt:'auto',caption:'auto',batch:'auto'},comfyWorkflows:[], comfyImportGraph:null, comfyImportName:'', comfyImportTask:'text_to_image', comfyImportMode:'generic', comfyImportProfile:'', comfyTextNode:'', comfyImageNode:'', comfyOutputNode:'', comfyTextField:'prompt', comfyImageField:'image', comfyOutputField:'text', captionWorkflow:'', batchWorkflow:'', profiles: [], profileSelections:{prompt:'',caption:'',batch:''}, csrf: '', version: '', root: '', activity: [],
  drafts: {prompt:{text:'',task:'text-image',updated_at:null},caption:{text:'',task:'describe',updated_at:null}},
  dirty: {prompt:false,caption:false}, reports: {}, editing: null, working: null,
  manifest:null, runs:[], savedPrompts:[], presets:[], categories:['General'], result:null, generating:false, promptError:'',
  images:[],captionRuns:[],savedCaptions:[],captionResult:null,captionProfile:'',captionImage:'',captionBusy:false,captionError:'',uploadBusy:false,
  batchShutdownEnabled:false,batchPowerSupported:false,batchShutdownSeconds:60,
  batchImages:[],batchJobs:[],batchProfile:'',batchMode:'dataset',batchCategory:'',batchCategoryTouched:false,batchNotes:'',batchTrigger:'',batchBusy:false, batchError:'', batchSkipDuplicates:true, batchPageOffsets:{}, uploadProgress:null, uploadCancel:false, batchPages:{}, busySince:{prompt:0,caption:0},
  captionOptions:{purpose:'general',analysis_scope:'full_image',visual_treatment:'source_accurate',grounding:'balanced',edit_intent:'general_edit',preservation_policy:'preserve_unrequested',motion_profile:'natural_balanced',camera_behavior:'preserve_auto'},
  libraryBrowse:{kind:'captions',query:'',collection:'all',category:'',categories:[],sort:'newest',offset:0,limit:20,items:[],total:0,counts:{},selectedId:'',loading:false,error:'',requestId:0},
  batchOptions:{purpose:'general',analysis_scope:'full_image',visual_treatment:'source_accurate',output_format:'descriptive_caption',grounding:'balanced'},
  promptCfg:{profile_id:'',workflow_id:'',operation:'generate',custom_instruction:'',prompt_profile:{prompt_task:'text_to_image'},params:{temperature:0.7,top_p:0.9,max_tokens:512,top_k:40}}
};
const $ = (s, root=document) => root.querySelector(s);
const escapeHTML = (input='') => String(input ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const names = {overview:'Overview',prompt:'Prompt Studio',caption:'Caption Studio',batch:'Batch & Dataset',library:'Library',activity:'Activity',connections:'Connections',settings:'Settings & Help'};
const busyView = (which,label) => `<div class="neo-inference" role="status" aria-live="polite"><div class="neo-inference-orbit" aria-hidden="true"><span></span><span></span><span></span></div><div class="neo-inference-copy"><strong>${escapeHTML(label)}</strong><p>Model request in progress · <span data-busy-elapsed="${which}">0s</span> elapsed</p><small>Waiting for backend response. Model loading, GPU warmup and token generation may take several minutes, especially for Qwen PE. No estimated percentage is shown.</small></div></div>`;
const quality = r => r?.quality_status || 'ready';
const peMeta = r => {const p=r?.pe_metadata;if(!p||!r?.comfy_auto_route?.startsWith('qwen_pe_'))return '';const vals=[];if(p.verified)vals.push(p.parse_ok?'PE parsed':'PE parse failed');else vals.push('PE parse unverified');if(p.wh_ratio)vals.push('Aspect ratio: '+p.wh_ratio);if(p.ratio_follow)vals.push('Ratio follows '+p.ratio_follow);return `<div class="meta">${vals.map(escapeHTML).join(' · ')}</div>`;};
const qualityBadge = r => badge(quality(r)==='needs_review'?'Needs Review':quality(r)==='invalid'?'Invalid':'Ready',quality(r)==='ready'?'responded':quality(r)==='invalid'?'failed':'incomplete');
const reviewed = r => quality(r)==='ready' || (quality(r)==='needs_review' && !!r?.review_approved);
const badge = (content, variant='') => `<span class="status-tag ${variant}">${escapeHTML(content)}</span>`;
const section = (title,desc,inside,extra='') => `<section class="card"><div class="card-inner"><div class="card-header"><div><h2 class="card-title">${title}</h2><p class="card-desc">${desc}</p></div>${extra}</div>${inside}</div></section>`;
const head = (tag,title,desc,action='')=>`<div class="page-head"><div><p class="eyebrow">${tag}</p><h1>${title}</h1><p>${desc}</p></div>${action?`<div class="page-actions">${action}</div>`:''}</div>`;
const button = (label,go,primary=false) => `<button type="button" class="button ${primary?'button-primary':'button-outline'}" data-go="${go}">${label}</button>`;
const notice = (message,type='') => `<div class="section-note ${type}">${message}</div>`;

async function api(path, method='GET', body=undefined){
  const response = await fetch('/api/v1'+path, {method,credentials:'same-origin',headers:{...(body===undefined?{}:{'Content-Type':'application/json'}), ...(method==='GET'?{}:{'X-Neo-CSRF':state.csrf})},body:body===undefined?undefined:JSON.stringify(body)});
  if(!response.ok){let reason=`Request failed (${response.status})`;try{const err=await response.json();reason=typeof err.detail==='string'?err.detail:reason}catch{}throw new Error(reason)}
  return response.json();
}
async function apiUpload(file, deduplicate=false){
 if(!file || !['image/png','image/jpeg','image/webp'].includes(file.type)){throw new Error('Choose a static PNG, JPEG or WebP image.')}
 if(file.size>10*1024*1024){throw new Error('Maximum image upload is 10 MB.')}
 const result=await fetch('/api/v1/caption/images',{method:'POST',credentials:'same-origin',headers:{'X-Neo-CSRF':state.csrf,'Content-Type':file.type,'X-Neo-Source-Name':encodeURIComponent(file.name).slice(0,500),'X-Neo-Relative-Path':encodeURIComponent(file.webkitRelativePath||file.name).slice(0,1000),'X-Neo-Dedupe':deduplicate?'1':'0'},body:file});
 if(!result.ok){let message='Upload failed (HTTP '+result.status+')';try{message=(await result.json()).detail||message}catch{}throw new Error(message)}
 return (await result.json()).image;
}
async function acceptImageFiles(files,target){
 if(state.uploadBusy)return;
 const selected=Array.from(files||[]).filter(f=>f instanceof File && ['image/png','image/jpeg','image/webp'].includes(f.type.toLowerCase()) || f instanceof File && /\.(png|jpe?g|webp)$/i.test(f.name));
 if(!selected.length){toast('No supported images selected (PNG, JPEG, WebP).',true);return}
 const accepted=target==='batch'?selected:selected.slice(0,1);
 if(target==='batch' && !state.batchCategoryTouched && selected[0].webkitRelativePath){
   const roots=new Set(selected.map(f=>(f.webkitRelativePath||'').split('/')[0]).filter(Boolean));
   if(roots.size===1)state.batchCategory=[...roots][0].slice(0,64);
 }
 state.uploadBusy=true;state.uploadCancel=false;
 state.uploadProgress={total:accepted.length,done:0,errors:0,duplicates:0,current:''};render();
 let ok=0;const existing=new Set(state.batchImages);
 try{
   for(const file of accepted){
     if(state.uploadCancel)break;
     state.uploadProgress.current=file.webkitRelativePath||file.name;
     try{
       const item=await apiUpload(file,target==='batch'&&state.batchSkipDuplicates);
       if(item.duplicate)state.uploadProgress.duplicates++;
       if(!state.images.some(x=>x.id===item.id))state.images.unshift(item);
       if(target==='batch'){if(!existing.has(item.id)){state.batchImages.push(item.id);existing.add(item.id)}}
       else{state.captionImage=item.id;state.captionResult=null}
       ok++;
     }catch(e){state.uploadProgress.errors++;state.batchError=e.message}
     state.uploadProgress.done++;
     // Small live counter update without recreating the current upload control.
     const status=document.querySelector('#batch-import-state');
     if(status)status.textContent=`${state.uploadProgress.done} / ${state.uploadProgress.total} scanned · ${state.uploadProgress.errors} skipped/failed · ${state.uploadProgress.duplicates} duplicates`;
     if(state.uploadProgress.done%25===0)await new Promise(resolve=>setTimeout(resolve,0));
   }
 } finally {
   const total=state.uploadProgress.done,fail=state.uploadProgress.errors;
   state.uploadBusy=false;state.uploadCancel=false;state.uploadProgress=null;
   render();toast(`Imported ${ok} of ${total} image(s)${fail?` · ${fail} skipped/failed`:''}.`);
 }
}
function categoryOptions(current='General'){
 const values=[...state.categories];
 if(current && !values.some(x=>x.toLowerCase()===current.toLowerCase()))values.push(current);
 return values.sort((a,b)=>a.localeCompare(b)).map(x=>`<option value="${escapeHTML(x)}" ${current===x?'selected':''}>${escapeHTML(x)}</option>`).join('');
}
async function refreshCategories(){
 const response=await api('/library/categories');
 state.categories=response.items||['General'];
 return state.categories;
}
let categoryCreateTarget='library';
function openCategoryCreator(target){
 categoryCreateTarget=target;
 $('#category-new-name').value='';
 $('#category-new-error').textContent='';
 $('#category-new-dialog').showModal();
 $('#category-new-name').focus();
}
async function submitNewCategory(){
 const button=$('#category-new-submit');button.disabled=true;
 try{
  const response=await api('/library/categories','POST',{name:$('#category-new-name').value.trim()});
  state.categories=response.items;
  $('#category-new-dialog').close();
  if(categoryCreateTarget==='batch'){
    state.batchCategory=response.name;state.batchCategoryTouched=true;render();
  }else{
    const select=$('#library-dialog-category');
    if(select){select.innerHTML=categoryOptions(response.name);select.value=response.name;}
  }
  toast(response.created?'Category created and available in every studio.':'Existing category selected.');
 }catch(e){$('#category-new-error').textContent=e.message;}finally{button.disabled=false;}
}
function imageSrc(id){return '/api/v1/caption/images/'+encodeURIComponent(id)+'/view'}
function imageMeta(id){return state.images.find(x=>x.id===id)}
function matchingWorkflows(profileId,task){return state.comfyWorkflows.filter(w=>w.profile_id===profileId&&w.task===task)}
function compatibleProfiles(workspace='prompt'){
 return state.profiles.filter(p=>p.kind==='koboldcpp'||p.kind==='comfyui');
}
function selectedComfy(profileId){return state.profiles.find(p=>p.id===profileId)?.kind==='comfyui'}
function autoProfileId(workspace){return workspace==='prompt'?state.promptCfg.profile_id:workspace==='caption'?state.captionProfile:state.batchProfile}
async function saveAutoChoice(workspace){
 const profile=autoProfileId(workspace);if(!selectedComfy(profile))return;
 const sel={profile_id:profile,mode:state.comfyMode[workspace],...state.comfyAuto[workspace]};
 try{await api('/comfy/auto/selections/'+workspace,'PUT',sel);state.comfyAutoSelections[workspace+':'+profile]=sel}
 catch(error){toast(error.message,true)}
}
function restoreAutoChoice(workspace,profile){
 const sel=state.comfyAutoSelections[workspace+':'+profile];
 if(sel){state.comfyMode[workspace]=sel.mode||'auto';state.comfyAuto[workspace]={route:sel.route||'llm',model:sel.model||'',mmproj:sel.mmproj||'',chat_handler:sel.chat_handler||'',runtime_options:sel.runtime_options||{}}}
 else {state.comfyMode[workspace]='auto';state.comfyAuto[workspace]={route:workspace==='prompt'?'llm':'vlm',model:'',mmproj:'',chat_handler:'',runtime_options:{}}}
}
async function loadComfyAuto(profileId){
 if(!profileId||!selectedComfy(profileId))return;
 try{const info=await api('/comfy/auto/capabilities?profile_id='+encodeURIComponent(profileId));state.comfyAutoCatalog[profileId]=info;render()}
 catch(error){state.comfyAutoCatalog[profileId]={error:error.message,routes:{}};render()}
}
// Route-owned controls. The available sockets and numeric ranges come from /object_info.
// Never show a cosmetic slider that is not wired into the selected ComfyUI node.
function runtimeControls(workspace,routeData){
 const info=routeData?.controls||{};const cfg=state.comfyAuto[workspace]?.runtime_options||{};
 const labels={n_ctx:'Context length (tokens)',vram_limit:'VRAM limit (GB; -1 = node default)',image_min_tokens:'Image minimum tokens',image_max_tokens:'Image maximum tokens',max_tokens:'Output token limit',max_new_tokens:'PE output token limit',max_output_tokens:'PE output token limit',temperature:'Temperature',top_p:'Top P',top_k:'Top K',force_offload:'Offload model after request'};
 const active=state.comfyAuto[workspace]?.route;
 const keys=Object.keys(info).filter(k=>workspace!=='prompt'||active!=='llm'||!['temperature','top_p','top_k','max_tokens'].includes(k));
 if(!keys.length)return `<p class="hint">${active?.startsWith('qwen_pe_')?'This Qwen PE node does not advertise editable token or sampling settings. Its ComfyUI defaults remain in control.':'No additional settings are exposed by the current node pack.'}</p>`;
 return `<details class="neo-runtime-panel"><summary>⚙ Runtime tuning · ${keys.length} supported controls</summary><p class="hint">Only overrides shown here are applied. Clear a value to use the node default. Values are validated against this ComfyUI installation.</p><div class="two-fields">${keys.map(k=>{const v=info[k],saved=cfg[k],hint=v.default===undefined?'Node-defined':String(v.default);return `<div class="field"><label for="runtime-${workspace}-${k}">${labels[k]||escapeHTML(k)}</label>${v.type==='boolean'?`<select class="select" id="runtime-${workspace}-${k}" data-runtime-setting="${workspace}:${k}"><option value="" ${saved===undefined?'selected':''}>Node default (${hint})</option><option value="true" ${saved===true?'selected':''}>Enabled</option><option value="false" ${saved===false?'selected':''}>Disabled</option></select>`:`<input class="input" type="number" id="runtime-${workspace}-${k}" data-runtime-setting="${workspace}:${k}" placeholder="Node default: ${escapeHTML(hint)}" value="${saved===undefined?'':escapeHTML(saved)}" ${v.min!==undefined?`min="${v.min}"`:''} ${v.max!==undefined?`max="${v.max}"`:''} step="${v.type==='int'?'1':(v.step||'any')}">`}<span class="hint">${v.node}${v.min!==undefined&&v.max!==undefined?` · ${v.min}–${v.max}`:''}</span></div>`}).join('')}</div><div class="button-row"><button type="button" class="button button-outline button-compact" data-action="reset-runtime" data-id="${workspace}">Use node defaults</button></div></details>`;
}
function workflowSelector(profileId,task,choice,workspace){
 if(!selectedComfy(profileId))return '';
 const auto=state.comfyAuto[workspace];const catalog=state.comfyAutoCatalog[profileId];const mode=state.comfyMode[workspace]||'auto';
 const allow=workspace==='prompt'?['llm',...(task==='text_to_image'?['qwen_pe_t2i']:[])]:['vlm','vlm_mtmd',...(task==='edit'&&workspace==='caption'?['qwen_pe_i2i']:[])];
 if(!allow.includes(auto.route)){auto.route=allow[0];auto.model='';auto.mmproj='';}
 const routes=(catalog?.routes||{});const route=routes[auto.route]||{available:false,models:[],mmproj:[]};
 const models=route.models||[];const projectors=route.mmproj||[];const handlers=route.handlers||[];
 const routeLabels={llm:'General LLM',vlm:'Vision LLM (llama.cpp)',vlm_mtmd:'Vision LLM (Generic MTMD)',qwen_pe_t2i:'Qwen PE · Text to Image',qwen_pe_i2i:'Qwen PE · Image Editing'};
 const selector=`<div class="field"><label>ComfyUI inference mode</label><select class="select" data-comfy-mode="${workspace}"><option value="auto" ${mode==='auto'?'selected':''}>Automatic · Neo builds the inference graph</option><option value="custom" ${mode==='custom'?'selected':''}>Advanced · Import my own workflow</option></select></div>`;
 if(mode==='custom'){
  const items=matchingWorkflows(profileId,task);
  return selector+`<div class="field"><label>Trusted custom workflow · ${escapeHTML(task)}</label><select class="select" data-select-comfy-workflow="${workspace}"><option value="">Choose workflow…</option>${listOptions(items.map(w=>[w.id,w.name]),choice)}</select><span class="hint">Advanced only. For arbitrary workflow authoring, use Neo Spaces independently; no Neo-to-Neo connection is required.</span></div>`;
 }
 const options=allow.map(r=>[r,routeLabels[r]+((catalog&&routes[r]&&!routes[r].available)?' · unavailable':'')]);
 return selector+`<div class="two-fields"><div class="field"><label>Automatic model route</label><select class="select" data-auto-setting="${workspace}:route">${listOptions(options,auto.route)}</select></div><div class="field"><label>Installed ComfyUI model</label><select class="select" data-auto-setting="${workspace}:model"><option value="">Select detected model…</option>${listOptions(models.map(m=>[m,m]),auto.model)}</select></div>${['vlm','vlm_mtmd'].includes(auto.route)?`<div class="field"><label>Vision projector (mmproj)</label><select class="select" data-auto-setting="${workspace}:mmproj"><option value="">Choose detected projector…</option>${listOptions(projectors.map(m=>[m,m]),auto.mmproj)}</select></div>`:''}${auto.route==='vlm'&&handlers.length?`<div class="field"><label>Vision chat handler</label><select class="select" data-auto-setting="${workspace}:chat_handler"><option value="">Choose the handler matching the loaded model…</option>${listOptions(handlers.map(h=>[h,h]),auto.chat_handler)}</select></div>`:''}</div>${catalog&&route.available?runtimeControls(workspace,route):''}<div class="button-row"><button type="button" class="button button-outline button-compact" data-action="refresh-comfy-auto" data-id="${escapeHTML(profileId)}">↻ Detect installed models</button></div>${catalog?.error?notice(escapeHTML(catalog.error),'warning'):(catalog&&!route.available?notice('This automatic route is unavailable: '+escapeHTML((route.missing||['Check the required nodes and output bridge.']).join(' ')),'warning'):!catalog?'<p class="hint">Click Detect installed models to read the live ComfyUI catalog. No workflow JSON is needed.</p>':'<p class="hint">Selected models stay inside your ComfyUI runtime. Neo builds a small graph internally; custom nodes and weights are not installed by Neo Prompt.</p>')}`;
}
// Shared caption/batch selector. Both pages must render independently of Prompt Studio.
// Automatic ComfyUI uses the selected runtime; imported JSON is only an advanced option.
function backendSelect(id,label){
 const workspace=id==='caption-profile'?'caption':'batch';
 const items=compatibleProfiles(workspace);
 const profileId=workspace==='caption'?state.captionProfile:state.batchProfile;
 const task=workspace==='caption'?(state.drafts.caption.task||'describe'):state.batchMode;
 const choice=workspace==='caption'?state.captionWorkflow:state.batchWorkflow;
 return `<div class="field"><label for="${id}">${escapeHTML(label)}</label>`+
  `<select id="${id}" class="select" data-vision-backend="${id}">`+
  `<option value="">Select saved profile…</option>`+
  listOptions(items.map(p=>[p.id,p.name+' · '+(p.kind==='comfyui'?'ComfyUI':'KoboldCPP')]),profileId)+
  `</select><span class="hint">Choose a saved vision backend. ComfyUI Automatic detects installed models and builds its own inference graph; advanced custom workflows are optional. KoboldCPP requires a compatible vision model.</span></div>`+
  workflowSelector(profileId,task,choice,workspace)+
  `<div class="button-row"><button type="button" class="button button-outline button-compact" data-go="connections">Manage backends and workflows →</button></div>`;
}

function autoPayload(workspace){const profile=autoProfileId(workspace);if(!selectedComfy(profile)||state.comfyMode[workspace]==='custom')return {auto_route:'',auto_model:'',auto_mmproj:'',auto_chat_handler:'',runtime_options:{}};const a=state.comfyAuto[workspace];return {auto_route:a.route,auto_model:a.model,auto_mmproj:a.mmproj,auto_chat_handler:a.chat_handler||'',runtime_options:a.runtime_options||{}};}

function dropArea(target){const batch=target==='batch';return `<div class="image-drop" id="image-drop" tabindex="0" role="button" aria-label="Upload images" data-upload-target="${target}"><span class="empty-symbol">▧</span><strong>${state.uploadBusy?'Import in progress…':'Choose images, drag & drop, or paste a screenshot'}</strong><span>PNG · JPEG · WebP · Max 10 MB/image · 20 megapixels · ${batch?'No fixed total count':'One image'}</span><div class="button-row"><button type="button" class="button button-outline button-compact" data-action="pick-image" ${state.uploadBusy?'disabled':''}>Select images</button>${batch?`<button type="button" class="button button-outline button-compact" data-action="pick-folder" ${state.uploadBusy?'disabled':''}>▱ Select folder</button>`:''}</div><input id="image-file-picker" class="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" ${batch?'multiple':''}>${batch?`<label class="batch-dedupe-option"><input type="checkbox" id="batch-skip-duplicates" ${state.batchSkipDuplicates?'checked':''}> Skip byte-identical images already imported</label><input id="batch-folder-picker" class="visually-hidden" type="file" webkitdirectory directory multiple accept="image/png,image/jpeg,image/webp">`:''}</div>${batch&&state.uploadProgress?`<div class="batch-import-status" role="status"><strong>Importing selected files</strong><p id="batch-import-state">${state.uploadProgress.done} / ${state.uploadProgress.total} scanned · ${state.uploadProgress.errors} skipped/failed</p><button class="button button-outline button-compact" data-action="stop-import">Stop after current file</button></div>`:''}`}
const captionAllowedFormats = {
  describe:['descriptive_caption','alt_text','tags_keywords','attribute_list'],
  recreate:['image_generation_prompt'],edit:['edit_instruction'],
  video:['video_generation_prompt'],dataset:['dataset_caption'],library:['descriptive_caption','alt_text','tags_keywords','attribute_list']
};
const captionTaskDefault = task => (captionAllowedFormats[task]||captionAllowedFormats.describe)[0];
function effectiveCaptionOptions(task){const opts={...state.captionOptions};
  // Task alone chooses the output contract; discard any pre-3.7 legacy format state.
  opts.output_format=captionTaskDefault(task);
  if(task==='dataset')opts.visual_treatment='source_accurate';
  if(task==='dataset')opts.grounding='strict';
  return opts;
}
function captionProfileFields(task,workspace='caption'){
 const opts=workspace==='batch'?state.batchOptions:effectiveCaptionOptions(task), dataAttr=workspace==='batch'?'data-batch-option':'data-caption-option';
 const fields=task==='dataset'?[['purpose','Primary purpose'],['analysis_scope','Analysis scope']]:[['purpose','Primary purpose'],['analysis_scope','Analysis scope'],['visual_treatment',task==='describe'?'Visual writing emphasis':'Visual treatment'],['grounding','Grounding']];
 if(task==='edit')fields.push(['edit_intent','Edit intent'],['preservation_policy','Preservation']);
 if(task==='video')fields.push(['motion_profile','Motion profile'],['camera_behavior','Camera behavior']);
  return `<div class="two-fields">${fields.map(([id,title])=>{
   const options=manifestOptions(id,opts[id]||'');
   const hint=task==='describe'&&id==='visual_treatment'?'<span class="hint">Changes descriptive emphasis, not the actual image. To create a different visual style, choose Image → Recreation.</span>':'';
   return `<div class="field"><label for="caption-opt-${id}">${title}</label><select id="caption-opt-${id}" class="select" ${dataAttr}="${id}">${options}</select>${hint}</div>`;
 }).join('')}</div>${task==='dataset'?'<div class="section-note">Dataset captions retain strict grounding, source treatment and dataset format. These are locked by the training task.</div>':''}${opts.purpose==='custom'?`<div class="field"><label for="caption-custom-purpose">Custom purpose</label><input id="caption-custom-purpose" class="input" ${dataAttr}="custom_purpose" maxlength="500" value="${escapeHTML(opts.custom_purpose||'')}"></div>`:''}${opts.visual_treatment==='custom'?`<div class="field"><label for="caption-custom-style">Custom visual treatment</label><input id="caption-custom-style" class="input" ${dataAttr}="custom_visual_treatment" maxlength="500" value="${escapeHTML(opts.custom_visual_treatment||'')}"></div>`:''}`;
}
const captionTaskGuide={describe:'Grounded description of the uploaded image. No restyling or imagined changes.',recreate:'Image-generation prompt; apply the selected target visual style.',edit:'Explicit image-edit instruction; preserve everything not requested for change.',video:'Continuous image-to-video prompt with motion, camera behavior, and continuity.',dataset:'Concise, strictly grounded training caption.'};
function captionOptions(task){return listOptions([['describe','Describe image'],['recreate','Image → Recreation prompt'],['edit','Image → Edit instruction'],['video','Image → Video prompt'],['dataset','Dataset caption']],task)}
function batchStatus(status){return badge(status,status==='completed'?'responded':status==='failed'?'failed':status==='interrupted'?'incomplete':'')}
function batchUI(job){
 const counts=job.counts||{};const finished=(counts.completed||0)+(counts.failed||0)+(counts.cancelled||0);
 const items=job.items||[];const offset=job.offset||0;
 return `<div class="batch-job"><div class="list-item"><div><strong>${job.mode==='library'?'Library':'Dataset'} job · ${escapeHTML(job.id.slice(0,10))}</strong><div class="meta">${escapeHTML(job.profile_name||'')} · ${escapeHTML(job.category||'Uncategorized')} · ${finished}/${job.total} finished · ${escapeHTML(job.updated_at)}</div></div>${batchStatus(job.status)}</div>
 <div class="batch-progress" role="progressbar" aria-label="Images processed" aria-valuenow="${finished}" aria-valuemin="0" aria-valuemax="${job.total}"><div style="width:${job.total?Math.min(100,Math.round(100*finished/job.total)):0}%"></div></div>
 <div class="meta">${counts.completed||0} complete · ${counts.failed||0} failed · ${counts.queued||0} queued · ${counts.running||0} processing</div>
 ${job.auto_route?`<div class="hint">ComfyUI ${escapeHTML(job.auto_route)} · ${escapeHTML(job.auto_model||'Selected custom graph')} · one sequential request · ComfyUI controls VRAM cache</div>`:''}
 ${job.backend_check_required?`<div class="section-note error" role="alert"><strong>ComfyUI queue check required.</strong><p>${escapeHTML(job.backend_check_message||'Remote processing may still be active. Open ComfyUI and confirm its queue/history before resuming. Shutdown is disarmed.')}</p><p>Completed items are retained. Resume only remaining queued items after confirmation; failed items can be retried after completion.</p></div>`:''}
 ${job.shutdown_state==='countdown'?`<div class="section-note warning" role="status"><strong>Windows shutdown countdown active</strong><p>PC will shut down at ${escapeHTML(new Date(job.shutdown_deadline).toLocaleTimeString())} unless cancelled. Completed captions and errors are already stored.</p><button type="button" class="button button-danger button-compact" data-action="cancel-shutdown" data-id="${escapeHTML(job.id)}">Cancel PC shutdown</button></div>`:job.shutdown_state==='armed'?`<div class="section-note warning"><strong>Windows shutdown armed.</strong> The PC will shut down after ALL images finish, including when individual images fail, following a ${state.batchShutdownSeconds}-second cancellation window. Pausing or stopping disarms this.</div>`:job.shutdown_state==='failed'?`<div class="section-note error">Windows shutdown failed: ${escapeHTML(job.shutdown_error||'Unknown OS error')}</div>`:job.shutdown_state?.startsWith('disarmed')?`<div class="hint">Unattended shutdown was disarmed; no automatic power action will occur on restart or resume.</div>`:''}

 ${items.map((item,i)=>{const meta=imageMeta(item.image_id);return `<div class="list-item batch-item"><div><strong>${offset+i+1}. ${escapeHTML(item.source_name||meta?.source_name||meta?.name||item.image_id.slice(0,12))}</strong><div class="meta">${escapeHTML((item.text||item.error||'Waiting for backend').slice(0,230))}</div>${item.quality_status==='needs_review'?`<div class="meta">Needs Review · not saved/exported until approved</div>${!item.review_approved?`<button class="button button-outline button-compact" data-action="approve-batch-item" data-id="${escapeHTML(job.id)}" data-index="${offset+i}">Approve & ${job.mode==='library'?'save':'include'}</button>`:''}`:''}${item.warnings?.length?`<div class="meta">${escapeHTML(item.warnings.join(' ').slice(0,250))}</div>`:''}${item.inference_seconds!=null?`<div class="meta">${escapeHTML(String(item.inference_seconds))}s · ${escapeHTML(item.runtime_model||'Backend model not reported')}${item.comfy_prompt_id?` · ComfyUI ID: ${escapeHTML(item.comfy_prompt_id)}`:''}</div>`:''}${item.execution_uncertain?'<div class="meta">Uncertain ComfyUI execution · inspect queue/history before retry</div>':''}</div>${batchStatus(item.status)}</div>`}).join('')}
 ${offset+items.length<job.total?`<button class="button button-outline button-compact" data-action="more-batch-items" data-id="${escapeHTML(job.id)}" data-offset="${offset+items.length}">View next items (${Math.min(30,job.total-offset-items.length)}) →</button>`:''}
 ${offset?`<button class="button button-outline button-compact" data-action="first-batch-items" data-id="${escapeHTML(job.id)}">First items</button>`:''}
 <div class="button-row" style="margin-top:12px">
 ${job.mode==='library'&&(counts.completed||0)?`<button class="button button-outline button-compact" data-go="library">View Library</button>`:''}
 <button class="button button-outline button-compact" data-action="export-batch" data-id="${job.id}" ${job.exportable?'':'disabled'}>Export ZIP</button>
 ${['running','queued','pause_requested'].includes(job.status)?`<button class="button button-outline button-compact" data-action="pause-batch" data-id="${job.id}" ${job.status==='pause_requested'?'disabled':''}>Pause after current</button>`:''}
 ${['paused','interrupted'].includes(job.status)?`<button class="button button-primary button-compact" data-action="resume-batch" data-id="${job.id}">Resume</button>`:''}
 ${['running','queued','pause_requested','paused','cancel_requested'].includes(job.status)?`<button class="button button-danger button-compact" data-action="cancel-batch" data-id="${job.id}">Stop</button>`:''}
 ${job.status==='completed_with_errors'&&(counts.failed||0)?`<button class="button button-primary button-compact" data-action="retry-failed-batch" data-id="${job.id}">Retry failed only (${counts.failed})</button>`:job.status==='cancelled'?`<button class="button button-outline button-compact" data-action="retry-batch" data-id="${job.id}">Retry incomplete</button>`:''}</div></div>`
}
function toast(message,error=false){const el=$('#toast');el.textContent=message;el.classList.toggle('error',error);el.hidden=false;clearTimeout(toast.timeout);toast.timeout=setTimeout(()=>el.hidden=true,5500)}
function navigate(page){if(!(page in names))return;state.page=page;state.editing=null;document.querySelectorAll('.nav-link').forEach(b=>{const active=b.dataset.page===page;b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});$('#top-title').textContent=names[page];$('#sidebar').classList.remove('is-open');$('#menu-toggle').setAttribute('aria-expanded','false');history.replaceState(null,'',`#${page}`);render();if(page==='library')loadLibraryBrowse();window.scrollTo({top:0,behavior:'instant'});$('#main').focus({preventScroll:true})}
function recentText(kind){const d=state.drafts[kind];return d.updated_at ? 'Last saved '+new Date(d.updated_at).toLocaleString() : 'Not saved yet'}
function draftPreview(kind){const d=state.drafts[kind];const snippet=(d.text || '').trim().slice(0,128);return `<div class="list-item"><div><strong>${kind==='prompt'?'Prompt draft':'Caption notes'}</strong><div class="meta">${escapeHTML(snippet || 'Empty draft')}</div><div class="meta">${escapeHTML(recentText(kind))}</div></div><button type="button" class="button button-quiet button-compact" data-go="${kind}">Open editor →</button></div>`}
function overview(){
  const savedCount=['prompt','caption'].filter(k=>state.drafts[k].updated_at).length;
  return `<section class="hero"><p class="eyebrow">YOUR WORDS. YOUR CREATIVE DIRECTION.</p><h2>Every idea deserves<br>room to take shape.</h2><p>A focused home for AI-powered text prompts, vision captioning, and reusable creative workflows — without bringing an entire production studio along.</p><div class="button-row">${button('✦  Open Prompt Studio','prompt',true)}${button('Explore Caption Studio →','caption')}</div></section>
   <div class="grid grid-3">
    <div class="card card-inner metric"><span class="metric-symbol">⌘</span><div><strong>${state.profiles.length}</strong><small>Configured backends</small></div></div>
    <div class="card card-inner metric"><span class="metric-symbol accent-cyan">▤</span><div><strong>${savedCount}</strong><small>Local text drafts saved</small></div></div>
    <div class="card card-inner metric"><span class="metric-symbol accent-pink">◷</span><div><strong>${state.activity.length}</strong><small>Recent connection checks</small></div></div>
   </div>
   <div class="section-heading"><div><h2>Your creative workspace</h2><p>Choose a focused tool. Each section has its own workflow.</p></div></div>
   <div class="grid grid-3">
     <article class="card feature"><span class="feature-symbol">✦</span><h3>Prompt Studio</h3><p>Create image, edit, and video prompts with KoboldCPP. Save results for reuse.</p>${button('Open editor →','prompt')}</article>
     <article class="card feature"><span class="feature-symbol accent-cyan">▧</span><h3>Caption Studio</h3><p>Prepare your reference notes and task. Generate real captions from a vision-capable KoboldCPP model.</p>${button('Explore studio →','caption')}</article>
     <article class="card feature"><span class="feature-symbol accent-pink">⌘</span><h3>Local backends</h3><p>Configure KoboldCPP and ComfyUI independently. Check each server without starting a generation.</p>${button('Manage connections →','connections')}</article>
   </div>
   <div class="section-heading"><h2>Start where you left off</h2></div>
   <section class="card card-inner">${draftPreview('prompt')}${draftPreview('caption')}</section>
   <div style="margin-top:17px">${notice('Create prompts, describe images, and prepare caption datasets using a supported KoboldCPP or ComfyUI backend. Your existing Neo Studio data is separate; automatic legacy import is not included.')}</div>`;
}
const promptTaskOptions = [['text_to_image','Text → Image'],['text_image_edit','Image edit instruction (text only)'],['text_to_video','Text → Video']];
// Refinement actions belong to individual results, never unsaved drafts.

function listOptions(options,value){return options.map(([id,label])=>`<option value="${escapeHTML(id)}" ${id===value?'selected':''}>${escapeHTML(label)}</option>`).join('')}
function manifestOptions(key,selected){let raw = state.manifest?.shared_dimensions?.[key] || state.manifest?.task_dimensions?.[key] || [];if(key==='analysis_scope')raw=raw.filter(x=>x.id!=='custom_crop');return listOptions(raw.map(x=>[x.id,x.label]),selected)}
function fieldOptions(key,label,help=''){
 const task=state.promptCfg.prompt_profile.prompt_task||'text_to_image';
 const taskEntry=(state.manifest?.task_dimensions?.prompt_task||[]).find(item=>item.id===task)||{};
 const locked=key==='output_format'&&!!taskEntry.output_format;
 const value=locked?taskEntry.output_format:(state.promptCfg.prompt_profile[key]||(key==='output_format'?'natural_prompt':''));return `<div class="field"><label for="pp-${key}">${escapeHTML(label)}</label><select id="pp-${key}" class="select" data-pprof="${key}" ${locked?'disabled title="Output format is defined by the selected edit or video task"':''}>${manifestOptions(key,value)}</select>${locked?'<span class="hint">Automatically selected for this task.</span>':''}${help?`<span class="hint">${escapeHTML(help)}</span>`:''}</div>`;
}
function promptBackend(){const items=compatibleProfiles(),cfg=state.promptCfg;
 return `<div class="field"><label for="np-backend">Saved backend profile</label><select class="select" id="np-backend" data-prompt-setting="profile_id"><option value="">Select saved profile…</option>${listOptions(items.map(p=>[p.id,p.name+' · '+(p.kind==='comfyui'?'ComfyUI':'KoboldCPP')]),cfg.profile_id)}</select><span class="hint">Choose KoboldCPP or a ComfyUI automatic model. Advanced custom workflows remain optional. Neo never silently switches between them.</span></div>${workflowSelector(cfg.profile_id,cfg.prompt_profile.prompt_task||'text_to_image',cfg.workflow_id||'','prompt')}<div class="button-row"><button class="button button-outline button-compact" data-go="connections">Manage backends and workflows →</button></div>`;
}

function lineagePanel(r){
 const parent=r?.parent_run_id?findRun(r.parent_run_id):null;
 const paired=r?.positive_run_id?findRun(r.positive_run_id):null;
 const children=state.runs.filter(x=>x.parent_run_id===r.id);
 const compare=parent?`<div class="refinement-comparison"><div class="refinement-surface"><strong>Parent · ${escapeHTML(parent.operation)}</strong><p>${escapeHTML(parent.text)}</p></div><div class="refinement-surface"><strong>Selected · ${escapeHTML(r.operation)}</strong><p>${escapeHTML(r.text)}</p></div></div><div class="button-row"><button class="button button-outline button-compact" data-action="view-run" data-id="${escapeHTML(parent.id)}">← View parent</button></div>`:'';
 const negPair=paired?`<div class="refinement-pair"><strong>Paired positive prompt</strong><div class="refinement-source">${escapeHTML(paired.text)}</div><div class="button-row"><button class="button button-outline button-compact" data-action="copy-positive" data-id="${escapeHTML(paired.id)}">Copy positive</button><button class="button button-outline button-compact" data-action="copy-pair" data-id="${escapeHTML(r.id)}">Copy positive + negative</button><button class="button button-outline button-compact" data-action="view-run" data-id="${escapeHTML(paired.id)}">View positive</button></div></div>`:'';
 const list=children.length?`<div class="refinement-children"><strong>Refinements from this result</strong>${children.map(x=>`<button class="button button-outline button-compact" data-action="view-run" data-id="${escapeHTML(x.id)}">${escapeHTML(x.operation)} · ${qualityBadge(x)}</button>`).join('')}</div>`:'';
 return compare+negPair+list;
}
function refineActions(r,busy){
 if(!r||r.operation==='negative')return '';
 const comfyAutoLLM=!!r.comfy_prompt_id&&r.comfy_auto_route==='llm'&&!r.workflow_id;
 const can=reviewed(r)&&quality(r)!=='invalid'&&!busy&&(!r.comfy_prompt_id&&!r.workflow_id||comfyAutoLLM)&&(r.lineage_depth||0)<12&&(r.text||'').length<=20000;
 return `<div class="refine-controls"><div><h3>Refine selected result</h3><p class="hint">Uses this exact saved output, not your source editor. Original stays untouched. Each result gets its own history entry.</p></div><div class="button-row refinement-chip-row">${[['enhance','✦ Enhance'],['rewrite','↻ Rewrite'],['negative','⊖ Negative']].map(([op,label])=>`<button type="button" class="refine-chip" data-action="refine-result" data-id="${escapeHTML(r.id)}" data-operation="${op}" ${can?'':'disabled'}>${label}</button>`).join('')}</div>${!reviewed(r)?'<p class="hint">Approve this Needs Review result before refining.</p>':''}</div>`;
}
function prompt(){const d=state.drafts.prompt,cfg=state.promptCfg,r=state.result;const task=cfg.prompt_profile.prompt_task||'text_to_image';const busy=state.generating;const sampleDisabled=selectedComfy(cfg.profile_id)&&!(state.comfyMode.prompt==='auto'&&state.comfyAuto.prompt.route==='llm'&&state.comfyAutoCatalog[cfg.profile_id]?.routes?.llm?.sampling);
 return `${head('LIVE PROMPT AUTHORING','Prompt Studio','Create your first prompt from an idea, then Enhance, Rewrite or generate Negatives from the selected result.',button('Connections →','connections'))}
 <div class="workspace-grid"><div class="stack">
 ${section('1 · Prompt composition','Your idea is authoritative. Source and custom instructions are never replaced by profile defaults.',`<div class="field"><label for="prompt-text">Source idea / edit request</label><textarea class="textarea" id="prompt-text" data-draft="prompt" maxlength="20000" placeholder="Describe your desired subject, scene, edits or motion…">${escapeHTML(d.text)}</textarea><span class="hint">Prompt Studio remains text-first; Caption Studio handles image understanding. Maximum 20,000 characters.</span></div><div class="field"><label for="np-instruction">Additional instructions (optional)</label><textarea class="textarea small" style="min-height:100px" id="np-instruction" data-prompt-setting="custom_instruction" maxlength="4000" placeholder="What should the model emphasize, avoid changing, or follow precisely?">${escapeHTML(cfg.custom_instruction||'')}</textarea></div><div class="button-row"><button type="button" data-action="save-prompt" class="button button-outline">Save draft & settings</button><span id="prompt-save-state" class="small-status">${escapeHTML(recentText('prompt'))}${state.dirty.prompt?' · Unsaved edits':''}</span></div>`)}
 ${section('2 · Task & prompt profile','Choose a task-specific profile for image, edit or video prompting.',`<div class="field"><label for="np-task">Target prompt</label><select id="np-task" class="select" data-pprof="prompt_task">${listOptions(promptTaskOptions,task)}</select></div><div class="two-fields">${fieldOptions('purpose','Primary purpose')}${fieldOptions('visual_treatment','Visual treatment')}${fieldOptions('output_format','Output format')}${task==='text_image_edit'?fieldOptions('edit_intent','Edit intent')+fieldOptions('preservation_policy','Preservation policy'):''}${task==='text_to_video'?fieldOptions('motion_profile','Motion profile')+fieldOptions('camera_behavior','Camera behavior'):''}</div>${cfg.prompt_profile.visual_treatment==='custom'?`<div class="field"><label for="np-custom-style">Custom visual treatment</label><input id="np-custom-style" class="input" data-pprof="custom_visual_treatment" maxlength="500" value="${escapeHTML(cfg.prompt_profile.custom_visual_treatment||'')}" placeholder="Optional custom art direction"></div>`:''}${cfg.prompt_profile.purpose==='custom'?`<div class="field"><label for="np-custom-purpose">Custom primary purpose</label><input id="np-custom-purpose" class="input" data-pprof="custom_purpose" value="${escapeHTML(cfg.prompt_profile.custom_purpose||'')}" placeholder="Which creative details should the model prioritize?" maxlength="500"></div>`:''}${cfg.prompt_profile.output_format==='custom'?`<div class="field"><label for="np-custom-format">Custom output format</label><input id="np-custom-format" class="input" data-pprof="custom_output_format" value="${escapeHTML(cfg.prompt_profile.custom_output_format||'')}" placeholder="Describe the output structure" maxlength="500"></div>`:''}${notice('Task consistency comes from the canonical profile manifest. Edit and video-specific fields do not alter unrelated tasks.')}`)}
 ${section('3 · Sampling & reusable settings','Sampling controls apply to KoboldCPP and to compatible automatic ComfyUI llama.cpp routes. Custom workflows retain their own values.',`${sampleDisabled?notice('These sliders are not applied by the current ComfyUI route. Select Automatic General LLM with llama_cpp_parameters to use them.'):''}<div class="two-fields"><div class="field"><label for="np-temp">Temperature (0–2)</label><input class="input" id="np-temp" ${sampleDisabled?'disabled title="Not supported by current inference route"':''} type="number" min="0" max="2" step="0.05" data-nparam="temperature" value="${escapeHTML(cfg.params.temperature)}"></div><div class="field"><label for="np-top-p">Top P (0–1)</label><input class="input" id="np-top-p" ${sampleDisabled?'disabled title="Not supported by current inference route"':''} type="number" min="0" max="1" step="0.05" data-nparam="top_p" value="${escapeHTML(cfg.params.top_p)}"></div><div class="field"><label for="np-max">Maximum tokens (1–8192)</label><input class="input" id="np-max" ${sampleDisabled?'disabled title="Not supported by current inference route"':''} type="number" min="1" max="8192" step="1" data-nparam="max_tokens" value="${escapeHTML(cfg.params.max_tokens)}"></div><div class="field"><label for="np-top-k">Top K (0–1000)</label><input class="input" id="np-top-k" ${sampleDisabled?'disabled title="Not supported by current inference route"':''} type="number" min="0" max="1000" step="1" data-nparam="top_k" value="${escapeHTML(cfg.params.top_k)}"></div></div>${notice('Generate uses these settings. The Negative action on a generated result applies separate safe caps automatically.')}<div class="button-row"><button class="button button-outline" data-action="save-preset">Save these settings as preset</button>${state.presets.length?`<select class="select preset-chooser" id="np-preset" aria-label="Load saved preset"><option value="">Load a preset…</option>${listOptions(state.presets.map(x=>[x.id,x.name]),'')}</select>`:''}</div>`)}
 </div><div class="stack">
 ${section('Generated output','Select a result, inspect its history and refine it without replacing your source or original output.',r?`<div class="button-row">${badge(r.operation+' · '+r.task,'responded')}${badge(r.profile_name||'KoboldCPP')}${r.workflow_id?badge('Comfy workflow: '+(r.workflow_name||'configured')):(r.runtime_model?badge('Model: '+r.runtime_model):badge('Model not reported'))}${qualityBadge(r)}${r.parent_run_id?badge('Refinement · step '+(r.lineage_depth||1)):badge('Original')}</div><div class="field" style="margin-top:12px"><label for="np-result">${r.operation==='negative'?'Negative prompt':'Generated prompt'} · read-only</label><textarea class="textarea result-textarea" id="np-result" readonly>${escapeHTML(r.text)}</textarea>${peMeta(r)}</div>${r.warnings?.length?`<div class="section-note warning" role="status"><strong>Output review notes</strong><ul>${r.warnings.map(x=>`<li>${escapeHTML(x)}</li>`).join('')}</ul></div>`:''}<div class="button-row"><button class="button button-outline" data-action="copy-result">Copy output</button><button class="button button-primary" data-action="save-result" ${reviewed(r)?'':'disabled title="Approve the review notes before saving"'}>${r.operation==='negative'&&r.positive_run_id?'Save negative pair':'Save to Library'}</button>${quality(r)==='needs_review'&&!r.review_approved?`<button class="button button-outline" data-action="approve-prompt" data-id="${escapeHTML(r.id)}">Approve after review</button>`:''}${quality(r)==='needs_review'&&!r.reformat_attempted&&(!r.comfy_prompt_id||r.comfy_auto_route==='llm'&&!r.workflow_id)?`<button class="button button-outline" data-action="reformat-prompt" data-id="${escapeHTML(r.id)}" ${busy?'disabled':''}>Reformat once · extra inference</button>`:''}<button class="button button-outline" data-action="reuse-result">Use as source (explicit)</button></div>${r.comfy_prompt_id&&r.comfy_auto_route!=='llm'?'<p class="hint">Qwen PE and Advanced custom workflows have their own output contracts. Automatic General LLM supports output-first refinement.</p>':refineActions(r,busy)}${lineagePanel(r)}`:`<div class="empty"><span class="empty-symbol">✧</span><strong>No generated prompt yet</strong><p>Select a backend, enter a source, and choose Generate. Earlier results remain in your history.</p></div>`)}
 ${section('Backend & generate','One selected backend per request. Offline or incompatible servers show explicit errors.',`${promptBackend()}<div class="button-row">${badge(cfg.profile_id?'Backend selected':'Backend required',cfg.profile_id?'responded':'incomplete')}${badge(selectedComfy(cfg.profile_id)?'ComfyUI workflow':'KoboldCPP chat')}</div><div class="card-divider"></div><button class="button button-primary generate-button" type="button" data-action="generate-prompt" ${busy?'disabled':''}>${busy?'Waiting for selected backend…':'✦ Generate prompt'}</button>${busy?busyView('prompt','Generating or refining your prompt…'):''}${state.promptError?`<div class="section-note error" role="alert">${/output contract|model mixed|second prompt|structured output|token limit|final answer/i.test(state.promptError)?qualityBadge({quality_status:'invalid'}):''} ${escapeHTML(state.promptError)}<div class="meta">You can adjust the source/profile and Generate again. No invalid result was added to history.</div></div>`:''}`)}
 ${section('Recent generated prompts','Successful requests are kept locally with source, profile and parameters for replay.',state.runs.length?state.runs.slice(0,4).map(run=>`<div class="list-item"><div><strong>${escapeHTML(run.operation+' · '+run.task)}</strong><div class="meta">${escapeHTML(run.text.slice(0,115))}</div><div class="meta">${escapeHTML(run.when)}</div></div><button class="button button-quiet button-compact" data-action="view-run" data-id="${escapeHTML(run.id)}">View</button></div>`).join(''):`<div class="empty">No recent generated prompts.</div>`)}
 </div></div>`;
}
function caption(){const d=state.drafts.caption;const meta=imageMeta(state.captionImage);const result=state.captionResult;return `${head('VISION WORKSPACE','Caption Studio','Generate visual captions and creative prompts with a chosen KoboldCPP VLM or compatible ComfyUI workflow.',button('Connections →','connections'))}
<div class="workspace-grid"><div class="stack">
${section('1 · Reference image','Upload one image. Paste a screenshot with Ctrl+V while this page is open.',`${dropArea('caption')}${meta?`<div class="image-preview"><img src="${imageSrc(meta.id)}" alt="Uploaded reference image"><div><strong>${escapeHTML(meta.name)}</strong><div class="meta">${meta.width} × ${meta.height} · ${(meta.size/1024).toFixed(0)} KB</div><button class="button button-outline button-compact" data-action="clear-caption-image">Remove selection</button></div></div>`:''}`)}
${section('2 · Instructions & task','Select a task and describe what the caption should preserve or change.',`<div class="field"><label for="caption-task">Caption task</label><select id="caption-task" class="select" data-task="caption">${captionOptions(d.task||'describe')}</select><span class="hint" id="caption-task-guide">${escapeHTML(captionTaskGuide[d.task]||captionTaskGuide.describe)}</span></div><div class="field"><label for="caption-text">User instructions / important reference notes</label><textarea id="caption-text" class="textarea small" data-draft="caption" maxlength="4000" placeholder="Optional grounded details, desired edit or motion direction…">${escapeHTML(d.text)}</textarea></div><div class="button-row"><button class="button button-outline" data-action="save-caption">Save notes</button><span id="caption-save-state" class="small-status">${escapeHTML(recentText('caption'))}${state.dirty.caption?' · Unsaved':''}</span></div>${d.task==='edit'?notice('Image editing requires a clear change request. Preserve all unrelated source details.'):d.task==='video'?notice('Image → Video needs intended action or motion. Camera and continuity controls are in Section 3.'):''}`)}
${section('3 · Analysis & task controls','Caption Task determines the output automatically. Adjust only relevant analysis, style, edit or motion settings.',captionProfileFields(d.task||'describe'))}
</div><div class="stack">
${section('Result & review','Review image accuracy and task-specific output notes before copying or saving.',result?`<div class="button-row">${badge(result.task+' · '+result.profile_name,'responded')}${qualityBadge(result)}${result.runtime_model?badge('Model: '+result.runtime_model):badge('Model not reported')}</div><div class="field" style="margin-top:12px"><label for="caption-output">Caption / prompt result</label><textarea id="caption-output" class="textarea result-textarea" readonly>${escapeHTML(result.text)}</textarea>${peMeta(result)}</div>${result.warnings?.length?`<div class="section-note warning" role="status"><strong>Caption review notes</strong><ul>${result.warnings.map(w=>`<li>${escapeHTML(w)}</li>`).join('')}</ul></div>`:''}<div class="button-row"><button class="button button-outline" data-action="copy-caption">Copy result</button><button class="button button-primary" data-action="save-caption-result" ${reviewed(result)?'':'disabled title="Approve this result after review"'}>Save to Library</button>${quality(result)==='needs_review'&&!result.review_approved?`<button class="button button-outline" data-action="approve-caption" data-id="${escapeHTML(result.id)}">Approve after review</button>`:''}<button class="button button-outline" data-action="caption-to-prompt">Use in Prompt Studio</button></div>`:`<div class="empty"><span class="empty-symbol">✧</span><strong>No caption yet</strong><p>Select an image, choose a compatible KoboldCPP backend, then generate.</p></div>`)}
${section('Backend & generation','Select your chosen KoboldCPP vision model or a trusted ComfyUI VLM/PE image workflow. No automatic backend fallback.',`${backendSelect('caption-profile','Vision backend')}${state.captionRuns.some(x=>x.profile_id===state.captionProfile)?badge('Vision previously succeeded on this backend · retest after model change','responded'):badge('Vision not tested successfully on this selected backend','incomplete')}<div class="card-divider"></div><button class="button button-primary generate-button" data-action="generate-caption" ${state.captionBusy||state.uploadBusy?'disabled':''}>${state.captionBusy?'Waiting for vision workflow…':'✦ Generate caption'}</button>${state.captionBusy?busyView('caption','Analyzing your image…'):''}${state.captionError?`<div class="section-note error" role="alert">${/caption contract|model mixed|second prompt|structured output|token limit|final answer/i.test(state.captionError)?qualityBadge({quality_status:'invalid'}):''} ${escapeHTML(state.captionError)}</div>`:''}`)}
${section('Recent captions','Previous results are saved in Neo Prompt, not Neo Studio.',state.captionRuns.length?state.captionRuns.slice(0,5).map(x=>`<div class="list-item"><div><strong>${escapeHTML(x.task)}</strong><p class="meta">${escapeHTML(x.text.slice(0,140))}</p></div><button class="button button-outline button-compact" data-action="load-caption-run" data-id="${x.id}">View</button></div>`).join(''):'<div class="empty">No caption history yet.</div>')}
</div></div>`}
function batch(){const jobs=state.batchJobs;const dataset=state.batchMode==='dataset';return `${head('BATCH WORKSPACE','Batch & Dataset','Use the same input → task → analysis → generation → results structure as the two studios. Choose where completed results go.')}
<div class="workspace-grid"><div class="stack">
${section('1 · Reference images','Choose individual files or an entire folder, including subfolders. No fixed total-image limit; each file is checked independently.',`${dropArea('batch')}<div class="batch-selected">${state.batchImages.slice(0,16).map((id,i)=>{const meta=imageMeta(id);return `<div class="batch-thumb"><img src="${imageSrc(id)}" alt="Image ${i+1}"><span>${escapeHTML(meta?.name||id.slice(0,8))}</span><button class="button button-quiet button-compact" data-action="remove-batch-image" data-id="${id}">×</button></div>`}).join('')}</div>${state.batchImages.length?`<div class="batch-selection-summary">${state.batchImages.length} image(s) selected${state.batchImages.length>16?` · showing first 16 previews`:``}</div><button class="button button-outline button-compact" data-action="clear-batch">Clear selection (${state.batchImages.length})</button>`:''}`)}
${section('2 · Instructions & destination','Choose the output workflow before running. Dataset captions and Library captions use different task rules.',`<div class="field"><label for="batch-mode">Batch workflow</label><select id="batch-mode" class="select" data-batch-setting="batchMode">${listOptions([['dataset','Prepare Dataset · image + caption pairs'],['library','Save to Library · reusable captions']],state.batchMode)}</select><span class="hint">${dataset?'Creates training-ready image/text pairs for ZIP export.':'Completed results are automatically saved into Neo Prompt’s Caption Library; original images are retained.'}</span></div><div class="field"><label for="batch-category">Library / dataset category</label><div class="category-control"><select id="batch-category" class="select" data-batch-setting="batchCategory">${categoryOptions(state.batchCategory||'General')}</select><button type="button" class="button button-outline" data-action="new-category" data-target="batch">+ New category</button></div><span class="hint">Categories are shared across Prompt, Caption and Batch. Folder import suggests the source folder; you can select or create another category.</span></div><div class="field"><label for="batch-notes">Caption instructions</label><textarea id="batch-notes" class="textarea small" maxlength="4000" data-batch-setting="batchNotes" placeholder="Describe visible attributes, pose and camera accurately…">${escapeHTML(state.batchNotes)}</textarea></div>${dataset?`<div class="field"><label for="batch-trigger">Trigger token (optional)</label><input id="batch-trigger" class="input" maxlength="90" data-batch-setting="batchTrigger" placeholder="e.g. lakmalchar" value="${escapeHTML(state.batchTrigger)}"><span class="hint">A single trigger token is prefixed to each successful training caption.</span></div>`:''}`)}
${section('3 · Analysis & output profile','Purpose, analysis and grounding settings apply to caption tasks; edit and motion settings remain separate.',captionProfileFields(dataset?'dataset':'library','batch'))}
${section('4 · Unattended completion','Optional Windows PC shutdown after the ENTIRE batch finishes. Failed items stay saved for a later failed-only retry.',`<label class="check-row"><input type="checkbox" id="batch-auto-shutdown" ${state.batchShutdownEnabled?'checked':''} ${state.batchPowerSupported?'':'disabled'}> Shut down my Windows PC after this batch finishes</label><p class="hint">Off by default. The batch continues after item errors; successful captions remain saved, and failed items stay listed for retry. The PC shuts down after all images reach a final state, even with errors. A ${state.batchShutdownSeconds}-second cancellation countdown starts afterward. Pause/Stop prevents shutdown. Restarting the app never schedules a missed shutdown.</p>${state.batchPowerSupported?'':notice('Windows PC shutdown is available only when Neo Prompt is running on Windows.','warning')}<p class="hint">Neo Prompt must remain running during the batch and countdown. No shutdown is scheduled outside the app process. Save your work in other applications first.</p>`)}
</div><div class="stack">
${section('Results & progress','Per-image outcomes are saved. Partial failures can be retried; stopping a batch waits for the active request.',jobs.length?jobs.slice(0,6).map(batchUI).join(''):'<div class="empty"><span class="empty-symbol">◷</span><strong>No batch jobs yet</strong><p>Choose a workflow, upload images, select the backend, then start the batch.</p></div>')}
${section('Backend & generation','Only the selected, compatible backend is used. ComfyUI jobs require a trusted workflow with a text-output bridge.',`${backendSelect('batch-profile','Vision backend')}<div class="card-divider"></div><button class="button button-primary generate-button" data-action="start-batch" ${state.batchBusy||!state.batchImages.length?'disabled':''}>${state.batchBusy?'Submitting batch…':dataset?'✦ Prepare dataset captions':'✦ Generate & save Library captions'}</button>${state.batchBusy?busyView('batch','Submitting batch…'):''}${state.batchError?notice(escapeHTML(state.batchError),'error'):''}`)}
${section('Output handling','Dataset and Library are separate destinations. Export remains optional in both modes.',notice('Dataset mode exports completed image + .txt pairs and a CSV manifest. Library mode automatically saves Ready captions; Needs Review items require manual approval before saving. Review AI outputs before publication or training.'))}
</div></div>`}
const libraryCollections = {
 captions:[['all','All captions'],['batch','Batch saved'],['single','Single image'],['describe','Descriptions'],['recreate','Recreations'],['edit','Edit instructions'],['video','Video prompts'],['dataset','Dataset captions']],
 prompts:[['all','All prompts'],['positive','Positive'],['negative','Negative'],['original','Original'],['refinements','Refinements']]
};
function libraryName(entry,kind){return kind==='prompts'?(entry.title||'Untitled prompt'):(entry.name||entry.title||((entry.origin==='batch_library'?'Batch · ':'')+({'describe':'Image description','recreate':'Recreation prompt','edit':'Edit instruction','video':'Video prompt','dataset':'Dataset caption'}[entry.task]||'Image caption')));}
function libraryDate(entry){if(!entry.when)return 'Date unavailable';const d=new Date(entry.when);return Number.isNaN(+d)?entry.when:d.toLocaleString()}
function librarySource(entry,kind){if(kind==='prompts')return (entry.operation||'generate')+' · '+libraryDate(entry);return (entry.origin?.startsWith('batch')?'Batch Library':'Single image')+' · '+(entry.task||'describe')+' · '+libraryDate(entry)}
function libraryTabs(kind){return `<div class="library-tabs" role="tablist" aria-label="Library content">
 <button type="button" role="tab" id="lib-tab-captions" class="library-tab ${kind==='captions'?'active':''}" aria-selected="${kind==='captions'}" data-action="library-tab" data-kind="captions">▧ Image Captions</button>
 <button type="button" role="tab" id="lib-tab-prompts" class="library-tab ${kind==='prompts'?'active':''}" aria-selected="${kind==='prompts'}" data-action="library-tab" data-kind="prompts">✧ Prompts</button>
 <button type="button" role="tab" id="lib-tab-presets" class="library-tab ${kind==='presets'?'active':''}" aria-selected="${kind==='presets'}" data-action="library-tab" data-kind="presets">⚙ Presets</button></div>`}
function libraryPresets(){
 const b=state.libraryBrowse;const q=b.query.trim().toLocaleLowerCase();
 const filtered=state.presets.filter(x=>!q||(x.name+' '+(x.settings?.prompt_profile?.prompt_task||'')).toLocaleLowerCase().includes(q));
 filtered.sort((a,c)=>b.sort==='name'?a.name.localeCompare(c.name):b.sort==='oldest'?(a.when||'').localeCompare(c.when||''):(c.when||'').localeCompare(a.when||''));
 const pages=Math.max(1,Math.ceil(filtered.length/b.limit));if(b.offset>=filtered.length)b.offset=Math.max(0,(pages-1)*b.limit);
 const items=filtered.slice(b.offset,b.offset+b.limit);const chosen=items.find(x=>x.id===b.selectedId)||items[0];
 const cards=items.map(x=>`<button type="button" class="library-record ${chosen?.id===x.id?'selected':''}" data-action="library-select" data-id="${escapeHTML(x.id)}" aria-pressed="${chosen?.id===x.id}"><span class="library-record-symbol" aria-hidden="true">⚙</span><span class="library-record-body"><strong>${escapeHTML(x.name)}</strong><small>${escapeHTML(x.settings?.prompt_profile?.prompt_task||'Default task')}</small><span>${escapeHTML(x.when||'Saved preset')}</span></span><span class="library-record-chevron" aria-hidden="true">›</span></button>`).join('');
 const params=chosen?.settings?.params||{};
 const inspector=chosen?`<div class="library-detail-heading"><div><span class="card-subtitle">SAVED SETTINGS</span><h3>${escapeHTML(chosen.name)}</h3><p class="meta">${escapeHTML(chosen.settings?.prompt_profile?.prompt_task||'Text to image')}</p></div></div><div class="library-preset-details"><div><span>Temperature</span><strong>${escapeHTML(params.temperature??'Default')}</strong></div><div><span>Top P</span><strong>${escapeHTML(params.top_p??'Default')}</strong></div><div><span>Top K</span><strong>${escapeHTML(params.top_k??'Default')}</strong></div><div><span>Maximum tokens</span><strong>${escapeHTML(params.max_tokens??'Default')}</strong></div></div><p class="hint">Presets restore task, prompt settings and backend selection; no model weights are stored.</p><div class="library-detail-actions"><button class="button button-primary" data-action="apply-preset" data-id="${escapeHTML(chosen.id)}">Use preset in Prompt Studio</button><button class="button button-danger" data-action="delete-preset" data-id="${escapeHTML(chosen.id)}">Delete preset</button></div>`:`<div class="empty">No presets match. Save settings from Prompt Studio to create one.</div>`;
 return `${head('SAVED WORK','Library','Browse captions, prompts and reusable settings in their own full-width workspaces.')}${libraryTabs('presets')}<div role="tabpanel" aria-labelledby="lib-tab-presets" class="library-browser"><section class="card"><div class="card-inner"><div class="card-header"><div><h2 class="card-title">Preset collections</h2><p class="card-desc">Find and inspect saved prompt configurations without mixing them with generated prompts.</p></div><span class="status-tag">${filtered.length} matching</span></div><div class="library-filters"><div class="field"><label for="library-search">Search presets</label><input class="input" id="library-search" type="search" maxlength="160" data-library-query="true" value="${escapeHTML(b.query)}" placeholder="Search names or tasks…"></div><div class="field"><label for="library-sort">Sort</label><select class="select" id="library-sort" data-library-sort="true">${listOptions([['newest','Newest first'],['oldest','Oldest first'],['name','Name']],b.sort)}</select></div></div><div class="library-list">${cards||'<div class="empty">No saved presets found.</div>'}</div><div class="library-pager"><span class="meta">Page ${Math.floor(b.offset/b.limit)+1} of ${pages}</span><div class="button-row"><button type="button" class="button button-outline button-compact" data-action="library-prev" ${!b.offset?'disabled':''}>← Previous</button><button type="button" class="button button-outline button-compact" data-action="library-next" ${b.offset+b.limit>=filtered.length?'disabled':''}>Next →</button></div></div></div></section><section class="card library-inspector"><div class="card-inner"><div class="card-header"><div><h2 class="card-title">Preset details</h2><p class="card-desc">Settings recorded for the selected preset.</p></div></div>${inspector}</div></section></div>`;
}
let librarySearchTimer;
async function loadLibraryBrowse(){
 const b=state.libraryBrowse,requestId=++b.requestId;
 if(b.kind==='presets'){b.loading=false;b.error='';render();return;}
 b.loading=true;b.error='';if(state.page==='library')render();
 try{
  const query=new URLSearchParams({kind:b.kind,q:b.query,collection:b.collection,sort:b.sort,offset:String(b.offset),limit:String(b.limit),category:b.category});
  const response=await api('/library/browse?'+query.toString());
  if(requestId!==b.requestId)return;
  b.items=response.items;b.total=response.total;b.counts=response.counts;b.categories=state.categories;
  if(!b.items.some(x=>x.id===b.selectedId))b.selectedId=b.items[0]?.id||'';
 }catch(err){if(requestId!==b.requestId)return;b.error=err.message;b.items=[];b.total=0;}
 finally{if(requestId===b.requestId){b.loading=false;if(state.page==='library')render()}}
}
function library(){
 if(state.libraryBrowse.kind==='presets')return libraryPresets();
 const b=state.libraryBrowse,kind=b.kind,selected=b.items.find(x=>x.id===b.selectedId),totalPages=Math.max(1,Math.ceil(b.total/b.limit)),page=Math.floor(b.offset/b.limit)+1;
 const tabs=libraryTabs(kind);
 const collectionChips=libraryCollections[kind].map(([value,label])=>`<button type="button" class="library-collection ${b.collection===value?'selected':''}" aria-pressed="${b.collection===value}" data-action="library-collection" data-collection="${value}">${escapeHTML(label)} <span>${Number(b.counts[value]||0)}</span></button>`).join('');
 const cards=b.items.map(x=>`<button type="button" class="library-record ${b.selectedId===x.id?'selected':''}" data-action="library-select" data-id="${escapeHTML(x.id)}" aria-pressed="${b.selectedId===x.id}">
  ${kind==='captions'?`<img src="${imageSrc(x.image_id)}" alt="" loading="lazy" class="library-record-thumb">`:`<span class="library-record-symbol" aria-hidden="true">${x.operation==='negative'?'⊖':'✧'}</span>`}
  <span class="library-record-body"><strong>${escapeHTML(libraryName(x,kind))}</strong><small>${escapeHTML(librarySource(x,kind))}</small><span>${escapeHTML((x.text||'').slice(0,165))}${(x.text||'').length>165?'…':''}</span></span><span class="library-record-chevron" aria-hidden="true">›</span></button>`).join('');
 const inspector=selected?`<div class="library-detail-heading"><div><span class="card-subtitle">SELECTED ${kind==='captions'?'CAPTION':'PROMPT'}</span><h3>${escapeHTML(libraryName(selected,kind))}</h3><p class="meta">${escapeHTML(librarySource(selected,kind))}</p></div></div>
 ${kind==='captions'?`<img class="library-large-preview" src="${imageSrc(selected.image_id)}" alt="Saved caption reference image" loading="lazy">`:''}
 <p class="meta">Category: ${escapeHTML(selected.category||'General')}</p>
 <div class="library-text-view" role="region" aria-label="Saved text">${escapeHTML(selected.text||'')}</div>
 ${selected.paired_positive_text?`<div class="refinement-pair"><strong>Paired positive prompt</strong><div class="library-text-view">${escapeHTML(selected.paired_positive_text)}</div><button type="button" class="button button-outline button-compact" data-action="library-copy-pair">Copy positive + negative</button></div>`:''}
 ${kind==='prompts'&&selected.source?`<details class="library-source"><summary>Original source idea</summary><p>${escapeHTML(selected.source)}</p></details>`:''}
 <div class="library-detail-actions"><button type="button" class="button button-primary" data-action="library-copy">Copy text</button><button type="button" class="button button-outline" data-action="library-reuse">${kind==='captions'?'Open in Caption Studio':'Use in Prompt Studio'}</button><button type="button" class="button button-outline" data-action="library-edit">Rename / move</button><button type="button" class="button button-danger" data-action="library-remove">Delete saved entry</button></div>`:`<div class="empty"><span class="empty-symbol">◇</span><strong>${b.loading?'Loading saved work…':'Select a saved item'}</strong><p>${b.error?escapeHTML(b.error):'Select a result from the browser to inspect its full text and image.'}</p></div>`;
 return `${head('SAVED WORK','Library','Browse saved image captions and prompts separately. Search, inspect, copy and reuse without altering generation history.')}
 ${tabs}
 <div role="tabpanel" aria-labelledby="lib-tab-${kind}" class="library-browser">
 <section class="card"><div class="card-inner"><div class="card-header"><div><h2 class="card-title">${kind==='captions'?'Image caption collections':'Prompt collections'}</h2><p class="card-desc">Filter by task, category or saved name. Rename or move an entry from its inspector.</p></div><span class="status-tag">${b.total} matching</span></div>
 <div class="library-filters"><div class="field"><label for="library-search">Search saved ${kind}</label><input id="library-search" class="input" type="search" maxlength="160" autocomplete="off" data-library-query="true" value="${escapeHTML(b.query)}" placeholder="Search names, categories, text…"></div><div class="field"><label for="library-sort">Sort</label><select id="library-sort" class="select" data-library-sort="true">${listOptions([['newest','Newest first'],['oldest','Oldest first'],['name','Name / task']],b.sort)}</select></div></div>
 <div class="field library-category-filter"><label for="library-category-filter">Category</label><select id="library-category-filter" class="select" data-library-category="true"><option value="">All categories</option>${b.categories.map(x=>`<option value="${escapeHTML(x)}" ${b.category===x?'selected':''}>${escapeHTML(x)}</option>`).join('')}</select></div>
 <div class="library-collections" aria-label="Browse collection">${collectionChips}</div><div class="library-list" role="group" aria-label="Saved entries">${b.loading?`<div class="library-loading" role="status">Loading Library…</div>`:b.error?notice(escapeHTML(b.error),'error'):cards||`<div class="empty">No matches. Try another collection or search.</div>`}</div>
 <div class="library-pager"><span class="meta">${b.total?`${b.offset+1}–${Math.min(b.offset+b.limit,b.total)} of ${b.total}`:'No results'} · page ${page} of ${totalPages}</span><div class="button-row"><button type="button" class="button button-outline button-compact" data-action="library-prev" ${page<=1||b.loading?'disabled':''}>← Previous</button><button type="button" class="button button-outline button-compact" data-action="library-next" ${page>=totalPages||b.loading?'disabled':''}>Next →</button></div></div></div></section>
 <section class="card library-inspector"><div class="card-inner"><div class="card-header"><div><h2 class="card-title">${kind==='captions'?'Caption details':'Prompt details'}</h2><p class="card-desc">Full text, reference and actions for the selected saved result.</p></div></div>${inspector}</div></section>
 </div>
 `;
}

function activity(){return `${head('RUNTIME HISTORY','Activity','Inspect recent connection tests and generated prompt history.',`<button class="button button-outline" data-action="refresh-activity">↻ Refresh</button>`)}
 ${section('Recent activity','Connection checks and prompt generation outcomes recorded by this app.',state.activity.length?state.activity.map(e=>`<div class="list-item"><div><strong>${escapeHTML(e.profile_name)}</strong><p class="meta">${escapeHTML(e.message)}</p><p class="meta">${escapeHTML(new Date(e.when).toLocaleString())}</p></div>${badge(e.status,e.status==='responded'?'responded':'failed')}</div>`).join(''):`<div class="empty"><span class="empty-symbol">◷</span><strong>Nothing to report yet</strong><p>Use Connections → Test to create a real, timestamped connection-check event.</p></div>`)}
 <div style="margin-top:16px">${notice('Connection tests are not generation jobs. Pause, resume, GPU progress and inference cancellation will only appear when backed by real execution.')}</div>`}
function profileCard(p){const r=state.reports[p.id],comfy=p.kind==='comfyui';const has=state.comfyWorkflows.filter(w=>w.profile_id===p.id);
 const destinations=(!comfy||has.length)?`<div class="profile-destinations"><span class="hint">Select for:</span><div class="button-row">${[['prompt','Prompt'],['caption','Caption'],['batch','Batch']].map(([key,label])=>`<button type="button" class="button button-outline button-compact" data-action="use-profile" data-workspace="${key}" data-id="${escapeHTML(p.id)}" ${state.profileSelections[key]===p.id?'disabled':''}>${state.profileSelections[key]===p.id?'✓ '+label+' selected':'Use for '+label}</button>`).join('')}</div></div>`:notice('Import a trusted text-output graph below before using this ComfyUI connection.');
 return `<article class="profile-item"><span class="feature-symbol ${comfy?'accent-cyan':''}">${comfy?'⌘':'✦'}</span><div class="profile-item-main"><div class="button-row"><strong>${escapeHTML(p.name)}</strong>${badge(comfy?'ComfyUI':'KoboldCPP')}${badge(r?(r.reachable?'Responded':'Unreachable'):'Not checked',r?(r.reachable?'responded':'failed'):'incomplete')}</div><small>${escapeHTML(p.endpoint)}</small><div class="button-row"><button class="button button-primary button-compact" data-action="test-profile" data-id="${p.id}">Test connection</button><button class="button button-quiet button-compact" data-action="edit-profile" data-id="${p.id}">Edit</button><button class="button button-danger button-compact" data-action="delete-profile" data-id="${p.id}">Delete</button></div>${destinations}${r?`<p class="hint">${escapeHTML(r.message)} ${r.model?'Model: '+escapeHTML(r.model):''}</p>`:''}${comfy?`<p class="hint">${has.length} trusted workflow(s) imported · Models and custom nodes are configured inside ComfyUI.</p>`:''}</div></article>`;
}
function rememberComfyImportForm(form){
 const keys={name:'comfyImportName',profile_id:'comfyImportProfile',task:'comfyImportTask',mode:'comfyImportMode',text_node:'comfyTextNode',text_field:'comfyTextField',image_node:'comfyImageNode',image_field:'comfyImageField',output_node:'comfyOutputNode',output_field:'comfyOutputField'};
 for(const [field,key] of Object.entries(keys))if(form.elements[field])state[key]=form.elements[field].value;
}
function comfyWorkflowImport(){const g=state.comfyImportGraph;
 const nodes=g?Object.entries(g).map(([id,n])=>[id,`${id} · ${n.class_type}`]):[];
 const strings=g?Object.entries(g).filter(([id,n])=>Object.values(n.inputs||{}).some(v=>typeof v==='string')).map(([id,n])=>[id,`${id} · ${n.class_type}`]):[];
 const list=state.comfyWorkflows.map(w=>`<div class="list-item"><div><strong>${escapeHTML(w.name)}</strong><div class="meta">${escapeHTML(w.task)} · ${escapeHTML(w.mode)} · ${escapeHTML(state.profiles.find(p=>p.id===w.profile_id)?.name||'Missing backend')}</div></div><button class="button button-danger button-compact" data-action="delete-comfy-workflow" data-id="${w.id}">Delete</button></div>`).join('');
 return `${section('ComfyUI text & vision workflows','Import trusted API-format JSON exported from ComfyUI; a graph must expose its final text through a history-visible output node. Neo does not install models, nodes or auto-execute imported graphs.',`${list||'<div class="empty">No ComfyUI workflows configured yet.</div>'}<div class="card-divider"></div><form id="comfy-workflow-form"><div class="two-fields"><div class="field"><label>ComfyUI connection</label><select name="profile_id" class="select" required>${listOptions(state.profiles.filter(p=>p.kind==='comfyui').map(p=>[p.id,p.name]),state.comfyImportProfile)}</select></div><div class="field"><label>Workflow name</label><input name="name" class="input" maxlength="90" required value="${escapeHTML(state.comfyImportName)}" placeholder="e.g. Qwen PE-T2I"></div><div class="field"><label>Target task</label><select name="task" class="select">${listOptions([['text_to_image','Prompt · Text → Image'],['text_image_edit','Prompt · Edit text-only'],['text_to_video','Prompt · Text → Video'],['describe','Caption · Describe'],['recreate','Caption · Recreate'],['edit','Caption · Edit with image'],['video','Caption · Image → Video'],['dataset','Batch · Dataset captions'],['library','Batch · Library captions']],state.comfyImportTask)}</select></div><div class="field"><label>Workflow mode</label><select name="mode" class="select">${listOptions([['generic','Generic ComfyUI LLM/VLM'],['qwen_pe_t2i','Qwen Image 2.1 PE-T2I'],['qwen_pe_i2i','Qwen Image 2.1 PE-I2I']],state.comfyImportMode)}</select></div></div><div class="field"><label for="comfy-file">ComfyUI API-format JSON</label><input id="comfy-file" type="file" accept=".json,application/json" class="input"><span class="hint">Import a trusted graph with a text display/output node connected to the result you want; a raw Qwen PE node output may not appear in /history until connected to a text-output bridge.</span></div>${g?`<div class="section-note"><strong>${nodes.length} nodes loaded locally</strong> — select binding IDs below. Only these two node inputs will be substituted when running.</div><div class="two-fields"><div class="field"><label>Text input node</label><select name="text_node" class="select">${listOptions(strings,state.comfyTextNode)}</select></div><div class="field"><label>Text input field</label><input name="text_field" class="input" value="${escapeHTML(state.comfyTextField)}" required></div><div class="field"><label>Image input node (vision tasks)</label><select name="image_node" class="select"><option value="">No image · text workflow</option>${listOptions(strings,state.comfyImageNode)}</select></div><div class="field"><label>Image filename field</label><input name="image_field" class="input" value="${escapeHTML(state.comfyImageField)}"></div><div class="field"><label>Text output node · /history</label><select name="output_node" class="select">${listOptions(nodes,state.comfyOutputNode)}</select></div><div class="field"><label>History output key</label><select class="select" name="output_field">${listOptions([['text','text'],['string','string'],['result','result']],state.comfyOutputField)}</select></div></div><label class="check-row"><input type="checkbox" name="trusted" required> I trust this graph and its custom nodes. It may execute local code or download models when ComfyUI runs it.</label><button class="button button-primary" type="submit">Save trusted workflow</button>`:'<p class="hint">Choose a JSON file to configure the text/image/output node bindings.</p>'}</form>`)} `;
}
function connections(){const p=state.profiles.find(x=>x.id===state.editing);return `${head('EXTERNAL BACKENDS','Connections','Keep your KoboldCPP and ComfyUI configurations in this app. Check local connectivity without triggering inference.')}
 <div class="workspace-grid"><div class="stack">
 ${section('Configured backends','Configure once, select in your workspace, and reuse on future launches. Connection checks never imply model capability.',state.profiles.length?`<div class="profile-grid">${state.profiles.map(profileCard).join('')}</div>`:`<div class="empty"><span class="empty-symbol">⌘</span><strong>No connections configured</strong><p>Add your running KoboldCPP or ComfyUI HTTP endpoint using the form.</p></div>`)}
 </div><div class="stack">
 ${section(p?'Edit connection':'Add a connection','Save a friendly name and local server URL once. Then use the profile directly in Prompt, Caption or Batch.',`<form id="connection-form"><div class="field"><label for="connection-name">Profile name</label><input id="connection-name" name="name" class="input" value="${escapeHTML(p?.name||'')}" placeholder="My local KoboldCPP" maxlength="64" minlength="2" required></div><div class="field"><label for="connection-kind">Backend type</label><select id="connection-kind" name="kind" class="select"><option value="koboldcpp" ${p?.kind==='koboldcpp'?'selected':''}>KoboldCPP</option><option value="comfyui" ${p?.kind==='comfyui'?'selected':''}>ComfyUI</option></select></div><div class="field"><label for="connection-endpoint">Local HTTP address</label><input id="connection-endpoint" name="endpoint" class="input" value="${escapeHTML(p?.endpoint||'')}" placeholder="http://127.0.0.1:5001" required><span class="hint">Neo Prompt accepts loopback only, with a port and no URL path.</span></div><div class="button-row"><button type="submit" class="button button-primary">${p?'Save changes':'Save connection'}</button>${p?'<button type="button" class="button button-outline" data-action="cancel-edit">Cancel</button>':''}</div></form>`)}
 <details class="card" style="padding:18px"><summary style="cursor:pointer;font-weight:700">Advanced · Custom ComfyUI workflows (optional)</summary>${comfyWorkflowImport()}</details>
 ${section('Readiness vs connectivity','A reachable API does not prove compatible inference nodes or models.',`${notice('Connection Test checks whether the selected server responds. For ComfyUI, use Detect installed models to inspect supported nodes and models before generation. Actual text, vision and Qwen PE readiness still require a compatible model and a successful task.')}<div class="card-divider"></div><div class="button-row">${badge('Server: test connection')}${badge('Text: task verification required')}${badge('Vision: image test required')}${badge('Qwen PE: node and model check')}</div>`)}
 </div></div>`}
function settings(){return `${head('LOCAL PREFERENCES','Settings & Help','Understand where your data lives and how to run Neo Prompt independently.')}
 <div class="grid grid-2">
 ${section('Installation & data','Every Neo app owns its own settings and saved work.',`<div class="field"><label>Local Neo Prompt data directory</label><div class="input monospace" role="note">${escapeHTML(state.root)}</div></div>${notice('This is the app\'s own folder. Neo Studio V1/V2 and Neo Spaces user data are not accessed. Legacy Studio records are not automatically imported.')}`)}
 ${section('Runtime and privacy','Local-first browser workspace, with independent external inference server configuration.',`<div class="list-item"><strong>Application</strong>${badge('Neo Prompt v'+state.version)}</div><div class="list-item"><strong>Server mode</strong>${badge('Loopback only','responded')}</div><div class="list-item"><strong>Inference</strong>${badge('KoboldCPP / supported ComfyUI','responded')}</div><div class="list-item"><strong>Legacy migration</strong>${badge('Not included','incomplete')}</div>`)}
 ${section('Starting your backends','Neo Prompt connects to the backend processes you already run.',`<p class="muted small">Start KoboldCPP or ComfyUI separately. Create an appropriate local profile under Connections. The Test button verifies a specific API response and does not load or run a model.</p>${button('Open Connections →','connections')}`)}
 ${section('Available tools','Each workflow uses the backend profile and compatible model you select.',`<div class="list-item"><strong>Prompt Studio</strong>${badge('Text prompting','responded')}</div><div class="list-item"><strong>Caption Studio</strong>${badge('Single-image vision','responded')}</div><div class="list-item"><strong>Batch & Dataset</strong>${badge('Sequential caption queue','responded')}</div><div class="list-item"><strong>ComfyUI Automatic</strong>${badge('Supported LLM, VLM and Qwen PE adapters')}</div><div class="list-item"><strong>Studio data import</strong>${badge('Not included')}</div>`)}
 </div>`}
let libraryDialogState=null;
async function openLibraryDialog({kind, mode='save', entry=null}){
 const dialog=$('#library-name-dialog');
 libraryDialogState={kind,mode,entry};
 $('#library-dialog-title').textContent=mode==='edit'?'Rename or move saved entry':'Save '+(kind==='captions'?'caption':'prompt')+' to Library';
 $('#library-dialog-hint').textContent='Managed category files are separate from source images, original prompts and generation history.';
 $('#library-dialog-category').innerHTML=categoryOptions(entry?.category||'General');
 $('#library-dialog-name').value=mode==='edit'?(entry?.name||entry?.title||''):'';
 $('#library-dialog-submit').textContent=mode==='edit'?'Update Library entry':'Save to Library';
 try{await refreshCategories();$('#library-dialog-category').innerHTML=categoryOptions(entry?.category||'General');}catch{}
 dialog.showModal();$('#library-dialog-category').focus();
}
async function confirmLibraryDialog(){
 const current=libraryDialogState;if(!current)return;
 const category=$('#library-dialog-category').value.trim()||'General';
 const name=$('#library-dialog-name').value.trim();
 if(/[<>:"/\\|?*]/.test(category+name)||category.length>64||name.length>120){toast('Please use names without path separators or reserved characters.',true);return}
 $('#library-dialog-submit').disabled=true;
 try{
   let result;
   if(current.mode==='edit'){
     result=(await api('/library/items/'+current.kind+'/'+encodeURIComponent(current.entry.id),'PATCH',{category,name})).item;
   }else if(current.kind==='prompts'){
     const r=current.entry;
     result=await api('/prompt/saved','POST',{title:name||category,name,category,text:r.text,source:r.source,operation:r.operation,origin_run_id:r.id||''});
   }else{
     const r=current.entry;
     result=await api('/caption/saved','POST',{image_id:r.image_id,text:r.text,task:r.task,origin_run_id:state.captionRuns.some(x=>x.id===r.id)?r.id:'',name,category});
   }
   const key=current.kind==='captions'?'savedCaptions':'savedPrompts';
   state[key]=[result,...state[key].filter(x=>x.id!==result.id)];
   $('#library-name-dialog').close();libraryDialogState=null;
   toast(current.mode==='edit'?'Library category/name updated.':'Saved to Library in '+category+'.');
   if(state.page==='library')loadLibraryBrowse();
 }catch(e){toast(e.message,true)}finally{$('#library-dialog-submit').disabled=false}
}
function render(){
 const routes={overview,prompt,caption,batch,library,activity,connections,settings};
 const main=$('#main');
 try{
  main.innerHTML=routes[state.page]();
 }catch(error){
  // Never leave the previous workspace visible under a new active navigation item.
  console.error('Neo Prompt could not render '+state.page,error);
  main.innerHTML=`<div class="page-head"><h1>${escapeHTML(names[state.page]||'Workspace')} unavailable</h1><p>The selected page could not be displayed. Other workspaces remain available.</p></div><div class="section-note error" role="alert">${escapeHTML(error?.message||'Unknown rendering error')}<div class="button-row"><button type="button" class="button button-outline" data-go="${escapeHTML(state.page)}">Retry page</button></div></div>`;
 }
 $('#profile-summary').textContent=state.profiles.length+' backend'+(state.profiles.length===1?'':'s');
 $('#top-status-label').textContent=state.profiles.length?'Backend profile configured':'No backend profile configured';
}
async function saveDraft(kind){try{if(kind==='prompt'){await savePromptCfg();state.drafts.prompt.task=({'text_to_image':'text-image','text_image_edit':'image-edit','text_to_video':'text-video'})[state.promptCfg.prompt_profile.prompt_task]||'text-image'}const d=state.drafts[kind];const saved=await api('/drafts/'+kind,'PUT',{text:d.text,task:d.task||''});state.drafts[kind]=saved;state.dirty[kind]=false;const label=$('#'+kind+'-save-state');if(label)label.textContent=recentText(kind);toast('Local '+(kind==='prompt'?'prompt draft':'caption notes')+' saved.')}catch(error){toast(error.message,true)}}
async function savePromptCfg(){const res=await api('/prompt/workspace','PUT',state.promptCfg);state.promptCfg=res.settings}
async function setBackendChoice(workspace,profileId){
 const res=await api('/profile-selections/'+encodeURIComponent(workspace),'PUT',{profile_id:profileId});
 state.profileSelections[workspace]=res.profile_id;
 if(workspace==='prompt'){state.promptCfg.profile_id=res.profile_id;state.promptCfg.workflow_id='';}
 if(workspace==='caption'){state.captionProfile=res.profile_id;state.captionWorkflow='';}
 if(workspace==='batch'){state.batchProfile=res.profile_id;state.batchWorkflow='';}
 if(selectedComfy(res.profile_id)){restoreAutoChoice(workspace,res.profile_id);if(!state.comfyAutoCatalog[res.profile_id])await loadComfyAuto(res.profile_id)}
 return res;
}
function findRun(id){return state.runs.find(x=>x.id===id)}
async function init(){try{const bootstrap=await api('/bootstrap');state.csrf=bootstrap.csrf;state.profiles=bootstrap.profiles;state.root=bootstrap.data_root;state.version=bootstrap.version;if(bootstrap.version!=='0.4.4'){document.querySelector('#top-status-label').textContent='Update mismatch: refresh browser';}const [pd,cd,acts,manifest,workspace,runs,saved,presets,images,captionRuns,savedCaptions,batchJobs,selections,categories,powerCapabilities,workflowData,autoSaved]=await Promise.all([api('/drafts/prompt'),api('/drafts/caption'),api('/activity'),api('/prompt/manifest'),api('/prompt/workspace'),api('/prompt/runs'),api('/prompt/saved'),api('/prompt/presets'),api('/caption/images'),api('/caption/runs'),api('/caption/saved'),api('/batch/jobs'),api('/profile-selections'),api('/library/categories'),api('/batch/power-capabilities'),api('/comfy/workflows'),api('/comfy/auto/selections')]);state.comfyWorkflows=workflowData.items||[];state.comfyAutoSelections=autoSaved.items||{};state.batchPowerSupported=!!powerCapabilities.windows_shutdown_supported;state.batchShutdownSeconds=powerCapabilities.countdown_seconds||60;state.categories=categories.items||['General'];state.images=images.items;state.captionRuns=captionRuns.items;state.savedCaptions=savedCaptions.items;state.batchJobs=batchJobs.items;state.manifest=manifest.manifest;state.runs=runs.items;state.savedPrompts=saved.items;state.presets=presets.items;state.promptCfg={...state.promptCfg,...workspace.settings,params:{...state.promptCfg.params,...(workspace.settings.params||{})},prompt_profile:{...state.promptCfg.prompt_profile,...(workspace.settings.prompt_profile||{})}};state.drafts.prompt={...state.drafts.prompt,...pd,task:pd.task||'text-image'};state.drafts.caption={...state.drafts.caption,...cd,task:cd.task||'describe'};state.activity=acts.items;const stored=selections.selections||{};state.profileSelections={prompt:stored.prompt||'',caption:stored.caption||'',batch:stored.batch||''};state.captionProfile=compatibleProfiles().some(p=>p.id===stored.caption)?stored.caption:'';state.batchProfile=compatibleProfiles().some(p=>p.id===stored.batch)?stored.batch:'';if(!compatibleProfiles().some(p=>p.id===state.promptCfg.profile_id))state.promptCfg.profile_id='';state.profileSelections.prompt=state.promptCfg.profile_id;state.promptCfg.operation='generate';state.captionWorkflow='';state.batchWorkflow='';for(const workspace of ['prompt','caption','batch']){const profile=autoProfileId(workspace);if(selectedComfy(profile))restoreAutoChoice(workspace,profile)}const start=location.hash.slice(1);navigate(start in names?start:'overview')}catch(error){$('#main').innerHTML=`<div class="page-head"><h1>Unable to load Neo Prompt</h1></div><div class="section-note error">${escapeHTML(error.message)}. Make sure the local server is still running, then reload this page.</div>`;$('#top-status-label').textContent='Startup error'}}
$('#library-dialog-cancel').addEventListener('click',()=>$('#library-name-dialog').close());
$('#library-name-dialog').addEventListener('close',()=>{libraryDialogState=null});
$('#library-name-form').addEventListener('submit',event=>{event.preventDefault();confirmLibraryDialog()});
$('#category-new-cancel').addEventListener('click',()=>$('#category-new-dialog').close());
$('#category-new-form').addEventListener('submit',event=>{event.preventDefault();submitNewCategory()});
// One event delegation path: rerenders don't leave dangling button listeners.
document.addEventListener('click',async event=>{
 const go=event.target.closest('[data-go],[data-page]');if(go){navigate(go.dataset.go||go.dataset.page);return}
 const action=event.target.closest('[data-action]');if(!action)return;
 const a=action.dataset.action,id=action.dataset.id;
 const b=state.libraryBrowse;
 if(a==='refresh-comfy-auto'){await loadComfyAuto(id);return}
 if(a==='reset-runtime'){state.comfyAuto[id].runtime_options={};render();await saveAutoChoice(id);toast('Node defaults restored for this route.');return}
 if(a==='delete-comfy-workflow'){if(!confirm('Remove this saved workflow definition? No source graph or model file will be deleted.'))return;try{await api('/comfy/workflows/'+id,'DELETE');state.comfyWorkflows=state.comfyWorkflows.filter(w=>w.id!==id);render();toast('Workflow mapping removed.')}catch(e){toast(e.message,true)}return;}
 if(a==='new-category'){openCategoryCreator(action.dataset.target||'library');return}
 if(a==='library-tab'){if(b.kind!==action.dataset.kind){b.kind=action.dataset.kind;b.category='';b.collection='all';b.query='';b.offset=0;b.selectedId='';loadLibraryBrowse()}return}
 if(a==='library-collection'){b.collection=action.dataset.collection;b.offset=0;b.selectedId='';loadLibraryBrowse();return}
 if(a==='library-select'){b.selectedId=id;render();return}
 if(a==='library-edit'){const entry=b.items.find(x=>x.id===b.selectedId);if(entry)openLibraryDialog({kind:b.kind,mode:'edit',entry});return}
 if(a==='library-prev'||a==='library-next'){b.offset=Math.max(0,b.offset+(a==='library-next'?b.limit:-b.limit));b.selectedId='';loadLibraryBrowse();return}
 if(a==='library-copy'||a==='library-copy-pair'||a==='library-reuse'||a==='library-remove'){
  const x=b.items.find(v=>v.id===b.selectedId);if(!x)return;
  if(a==='library-copy'||a==='library-copy-pair'){
   const value=a==='library-copy-pair'&&x.paired_positive_text?'Positive prompt:\n'+x.paired_positive_text+'\n\nNegative prompt:\n'+x.text:x.text;
   try{await navigator.clipboard.writeText(value);toast('Saved text copied.')}catch{toast('Clipboard blocked. Select the text manually.',true)}return;
  }
  if(a==='library-reuse'){
   if(b.kind==='captions'){state.captionResult=x;state.captionImage=x.image_id;navigate('caption')}
   else{if(state.dirty.prompt&&!confirm('Replace unsaved Prompt Studio source text?'))return;state.drafts.prompt.text=x.text;state.dirty.prompt=true;navigate('prompt');toast('Saved prompt loaded as source.')}
   return;
  }
  if(!confirm('Delete this saved '+(b.kind==='captions'?'caption':'prompt')+'? Original generation history and images are preserved.'))return;
  try{await api((b.kind==='captions'?'/caption/saved/':'/prompt/saved/')+encodeURIComponent(x.id),'DELETE');
   if(b.kind==='captions')state.savedCaptions=state.savedCaptions.filter(v=>v.id!==x.id);else state.savedPrompts=state.savedPrompts.filter(v=>v.id!==x.id);
   b.selectedId='';if(b.offset>0&&b.items.length===1)b.offset=Math.max(0,b.offset-b.limit);
   await loadLibraryBrowse();toast('Saved entry deleted.');}catch(err){toast(err.message,true)}return;
 }

 if(a==='use-profile'){
   const workspace=action.dataset.workspace;
   if(!['prompt','caption','batch'].includes(workspace))return;
   try{await setBackendChoice(workspace,id);render();toast('Profile selected for '+workspace+'. This choice will be restored next time.')}catch(e){toast(e.message,true)}return;
 }
 if(a==='pick-image'){document.querySelector('#image-file-picker')?.click();return}
 if(a==='pick-folder'){document.querySelector('#batch-folder-picker')?.click();return}
 if(a==='stop-import'){state.uploadCancel=true;toast('Stopping folder import after the current file.');return}
 if(a==='more-batch-items'||a==='first-batch-items'){try{const offset=a==='first-batch-items'?0:Number(action.dataset.offset||0);const response=await api('/batch/jobs/'+encodeURIComponent(id)+'?offset='+offset+'&limit=30');state.batchPageOffsets[id]=offset;state.batchJobs=state.batchJobs.map(x=>x.id===id?response.job:x);render()}catch(e){toast(e.message,true)}return}
 if(a==='clear-caption-image'){state.captionImage='';state.captionResult=null;render();return}
 if(a==='remove-batch-image'){state.batchImages=state.batchImages.filter(x=>x!==id);render();return}
 if(a==='clear-batch'){state.batchImages=[];render();return}
 if(a==='generate-caption'){
   if(state.captionBusy)return;
   state.captionError='';if(!state.captionImage||!state.captionProfile){state.captionError='Upload an image and select a vision backend.';render();return}
   state.captionBusy=true;state.busySince.caption=Date.now();state.captionResult=null;render();try{const out=await api('/caption/generate','POST',{profile_id:state.captionProfile,workflow_id:state.comfyMode.caption==='custom'?state.captionWorkflow:'',...autoPayload('caption'),image_id:state.captionImage,task:state.drafts.caption.task,instruction:state.drafts.caption.text,options:effectiveCaptionOptions(state.drafts.caption.task)});state.captionResult=out.result;state.captionRuns.unshift(out.result);toast('Vision caption generated. Review for accuracy.')}catch(e){state.captionError=e.message;toast(e.message,true)}finally{state.captionBusy=false;render()}return;
 }
 if(a==='copy-caption'&&state.captionResult){try{await navigator.clipboard.writeText(state.captionResult.text);toast('Caption copied.')}catch{toast('Clipboard denied; select output manually.',true)}return}
 if(a==='save-caption-result'&&state.captionResult){openLibraryDialog({kind:'captions',entry:state.captionResult});return}
 if(a==='caption-to-prompt'&&state.captionResult){if(state.dirty.prompt&&!confirm('Replace unsaved Prompt Studio text?'))return;state.drafts.prompt.text=state.captionResult.text;state.dirty.prompt=true;navigate('prompt');return}
 if(a==='load-caption-run'){const x=state.captionRuns.find(y=>y.id===id);if(x){state.captionResult=x;state.captionImage=x.image_id;navigate('caption')}return}
 if(a==='reuse-caption'){const x=state.savedCaptions.find(y=>y.id===id);if(x){state.captionResult=x;state.captionImage=x.image_id;navigate('caption')}return}
 if(a==='delete-caption'){const x=state.savedCaptions.find(y=>y.id===id);if(!x||!confirm('Delete this saved caption?'))return;try{await api('/caption/saved/'+id,'DELETE');state.savedCaptions=state.savedCaptions.filter(y=>y.id!==id);render()}catch(e){toast(e.message,true)}return}
 if(a==='start-batch'){
   if(state.batchBusy)return;state.batchError='';if(state.batchShutdownEnabled&&!confirm('SHUT DOWN WINDOWS AFTER BATCH?\n\nAll images will be processed, including after individual errors. The computer will shut down after a 60-second cancellation countdown. Unsaved work in other apps could be lost.\n\nConfirm this ONE job only.'))return;if(!state.batchProfile||!state.batchImages.length){state.batchError='Choose images and a vision backend first.';render();return}
   state.batchBusy=true;render();try{const out=await api('/batch/jobs','POST',{profile_id:state.batchProfile,workflow_id:state.comfyMode.batch==='custom'?state.batchWorkflow:'',...autoPayload('batch'),image_ids:state.batchImages,shutdown_enabled:state.batchShutdownEnabled,shutdown_confirmed:state.batchShutdownEnabled,notes:state.batchNotes,trigger:state.batchMode==='dataset'?state.batchTrigger:'',mode:state.batchMode,category:state.batchCategory,options:{...state.batchOptions,output_format:state.batchMode==='dataset'?'dataset_caption':(['descriptive_caption','alt_text','tags_keywords','attribute_list'].includes(state.batchOptions.output_format)?state.batchOptions.output_format:'descriptive_caption')}});state.batchJobs.unshift(out.job);state.batchShutdownEnabled=false;state.batchImages=[];toast(state.batchMode==='library'?'Library caption batch queued.':'Dataset caption batch queued.')}catch(e){state.batchError=e.message;toast(e.message,true)}finally{state.batchBusy=false;render()}return}
 if(a==='cancel-shutdown'){try{await api('/batch/jobs/'+encodeURIComponent(id)+'/shutdown/cancel','POST');state.batchJobs=(await api('/batch/jobs')).items;render();toast('Windows shutdown cancelled. Results remain saved.')}catch(e){toast(e.message,true)}return}
 if(['cancel-batch','retry-batch','retry-failed-batch','pause-batch','resume-batch'].includes(a)){try{let payload=undefined;if(a==='resume-batch'){const j=state.batchJobs.find(x=>x.id===id);if(j?.backend_check_required){if(!confirm('COMFYUI QUEUE CHECK REQUIRED\n\nConfirm that ComfyUI has no unfinished prompt from this Batch (check Queue and History). Neo cannot automatically verify whether a timed-out prompt is still processing.\n\nResume only remaining items? PC shutdown stays disarmed.'))return;payload={backend_queue_checked:true};}}await api('/batch/jobs/'+id+'/'+a.replace('-batch','').replace('retry-failed','retry-failed'),'POST',payload);state.batchJobs=(await api('/batch/jobs')).items;render();toast(a==='cancel-batch'?'Stop requested after current image.':a==='pause-batch'?'Pause requested after current image.':a==='resume-batch'?'Job resumed; shutdown is disarmed.':a==='retry-failed-batch'?'Only failed images are being retried; shutdown is off.':'Retry started.')}catch(e){toast(e.message,true)}return}
 if(a==='export-batch'){const url='/api/v1/batch/jobs/'+encodeURIComponent(id)+'/export';const link=document.createElement('a');link.href=url;link.download='neo_prompt_dataset_'+id.slice(0,10)+'.zip';link.click();return}
 if(a==='generate-prompt'){
   if(state.generating)return;
   if(!state.drafts.prompt.text.trim()){state.promptError='Enter a source idea first.';render();return}
   if(!state.promptCfg.profile_id){state.promptError='Choose a backend profile first.';render();return}
   state.generating=true;state.busySince.prompt=Date.now();state.promptError='';state.result=null;render();
   try{await savePromptCfg();const payload={...state.promptCfg,workflow_id:state.comfyMode.prompt==='custom'?state.promptCfg.workflow_id:'',...autoPayload('prompt'),operation:'generate',source:state.drafts.prompt.text};const out=await api('/prompt/generate','POST',payload);state.result=out.result;state.runs.unshift(out.result);state.runs=state.runs.slice(0,100);state.activity=(await api('/activity')).items;toast('Generated prompt received from selected backend.')}catch(error){state.promptError=error.message;toast(error.message,true)}finally{state.generating=false;render()}return;
 }
 if(a==='refine-result'){
   const parent=findRun(id);const op=action.dataset.operation;
   if(!parent||!['enhance','rewrite','negative'].includes(op))return;
   if(!reviewed(parent)){toast('Approve this result before refining.',true);return;}
   if(state.generating)return;
   state.generating=true;state.busySince.prompt=Date.now();state.promptError='';render();
   try{const x=await api('/prompt/runs/'+encodeURIComponent(id)+'/refine','POST',{operation:op});state.result=x.result;state.runs.unshift(x.result);state.runs=state.runs.slice(0,100);state.activity=(await api('/activity')).items;toast(op==='negative'?'Negative prompt paired with selected positive.':'New '+op+' result created. Original preserved.');}
   catch(e){state.promptError=e.message;toast(e.message,true)}finally{state.generating=false;render()}return;
 }
 if(a==='copy-positive'||a==='copy-pair'){
    const selected=findRun(id);const pos=a==='copy-positive'?selected:findRun(selected?.positive_run_id);
    if(!pos||a==='copy-pair'&&!selected){toast('The paired result is no longer available.',true);return}
    try{await navigator.clipboard.writeText(a==='copy-positive'?pos.text:'Positive prompt:\n'+pos.text+'\n\nNegative prompt:\n'+selected.text);toast(a==='copy-positive'?'Positive copied.':'Positive and negative copied together.');}catch{toast('Clipboard blocked.',true)}return;
 }
 if(a==='approve-prompt'){
   try{const x=await api('/prompt/runs/'+encodeURIComponent(id)+'/approve','POST');state.result=x.result;state.runs=state.runs.map(r=>r.id===id?x.result:r);render();toast('Review approved. Save to Library is now available.')}catch(e){toast(e.message,true)}return;
 }
 if(a==='reformat-prompt'){
   if(state.generating||!confirm('Request one additional inference on the original backend to reformat this output? This does not guarantee source fidelity.'))return;
   state.generating=true;state.busySince.prompt=Date.now();state.promptError='';render();
   try{const x=await api('/prompt/runs/'+encodeURIComponent(id)+'/reformat','POST');state.result=x.result;state.runs.unshift(x.result);state.runs=state.runs.map(r=>r.id===id?{...r,reformat_attempted:true}:r);toast('Reformat complete. Review against the source before approving.')}catch(e){state.promptError=e.message;toast(e.message,true)}finally{state.generating=false;render()}return;
 }
 if(a==='approve-caption'){
   try{const x=await api('/caption/runs/'+encodeURIComponent(id)+'/approve','POST');state.captionResult=x.result;state.captionRuns=state.captionRuns.map(r=>r.id===id?x.result:r);render();toast('Caption review approved.')}catch(e){toast(e.message,true)}return;
 }
 if(a==='approve-batch-item'){
   try{const x=await api('/batch/jobs/'+encodeURIComponent(id)+'/items/'+encodeURIComponent(action.dataset.index)+'/approve','POST');state.batchJobs=state.batchJobs.map(j=>j.id===id?x.job:j);if(x.job.mode==='library')state.savedCaptions=(await api('/caption/saved')).items;render();toast('Batch item approved.')}catch(e){toast(e.message,true)}return;
 }
 if(a==='copy-result' && state.result){try{await navigator.clipboard.writeText(state.result.text);toast('Generated output copied.')}catch{toast('Clipboard blocked. Select text and use Ctrl+C.',true)}return}
 if(a==='save-result' && state.result){openLibraryDialog({kind:'prompts',entry:state.result});return}
 if(a==='reuse-result' && state.result){if(state.dirty.prompt&&!confirm('Replace your unsaved source idea with this output?'))return;state.drafts.prompt.text=state.result.text;state.dirty.prompt=true;render();toast('Result copied into source editor. Save draft when ready.');return}
 if(a==='view-run'){const run=findRun(id);if(run){state.result=run;state.promptError='';navigate('prompt')}return}
 if(a==='save-preset'){const name=window.prompt('Name this settings preset:');if(!name)return;try{const x=await api('/prompt/presets','POST',{name,settings:state.promptCfg});state.presets.unshift(x);render();toast('Preset saved.')}catch(e){toast(e.message,true)}return}
 if(a==='apply-preset'){const x=state.presets.find(y=>y.id===id);if(x){state.promptCfg={...state.promptCfg,...structuredClone(x.settings),operation:'generate',params:{...state.promptCfg.params,...x.settings.params},prompt_profile:{...state.promptCfg.prompt_profile,...x.settings.prompt_profile}};render();toast('Preset loaded. Save settings to keep it.')}return}
 if(a==='delete-preset'||a==='delete-library'){const preset=a==='delete-preset',x=(preset?state.presets:state.savedPrompts).find(y=>y.id===id);if(!x||!confirm('Delete '+(preset?'preset':'saved prompt')+' "'+(x.name||x.title)+'"?'))return;try{await api('/prompt/'+(preset?'presets':'saved')+'/'+id,'DELETE');if(preset)state.presets=state.presets.filter(y=>y.id!==id);else state.savedPrompts=state.savedPrompts.filter(y=>y.id!==id);render();toast('Removed.')}catch(e){toast(e.message,true)}return}
 if(a==='copy-library'){const x=state.savedPrompts.find(y=>y.id===id);if(!x)return;try{await navigator.clipboard.writeText(x.text);toast('Copied.')}catch{toast('Clipboard blocked.',true)}return}
 if(a==='copy-saved-pair'){const x=state.savedPrompts.find(y=>y.id===id);if(!x?.paired_positive_text)return;try{await navigator.clipboard.writeText('Positive prompt:\n'+x.paired_positive_text+'\n\nNegative prompt:\n'+x.text);toast('Saved pair copied.')}catch{toast('Clipboard blocked.',true)}return}
 if(a==='reuse-library'){const x=state.savedPrompts.find(y=>y.id===id);if(!x)return;if(state.dirty.prompt&&!confirm('Replace unsaved prompt editor text?'))return;state.drafts.prompt.text=x.text;state.dirty.prompt=true;navigate('prompt');toast('Saved prompt loaded into editor.');return}
 if(a==='save-prompt'||a==='save-caption'){await saveDraft(a.replace('save-',''));return}
 if(a==='cancel-edit'){state.editing=null;render();return}
 if(a==='edit-profile'){state.editing=id;render();$('#connection-name')?.focus();return}
 if(a==='delete-profile'){
  const p=state.profiles.find(x=>x.id===id);if(!p||!confirm(`Delete connection "${p.name}"? This does not alter the backend.`))return;
  try{await api('/profiles/'+id,'DELETE');state.profiles=state.profiles.filter(x=>x.id!==id);delete state.reports[id];for(const k of ['prompt','caption','batch'])if(state.profileSelections[k]===id){state.profileSelections[k]='';if(k==='prompt')state.promptCfg.profile_id='';if(k==='caption')state.captionProfile='';if(k==='batch')state.batchProfile=''}if(state.editing===id)state.editing=null;render();toast('Connection profile deleted.')}catch(error){toast(error.message,true)}return;
 }
 if(a==='test-profile'){
   if(state.working)return;state.working=id;render();
   try{const report=await api('/profiles/'+id+'/test','POST');state.reports[id]=report;const activities=await api('/activity');state.activity=activities.items;toast(report.reachable?'Backend responded. KoboldCPP text generation can be tested in Prompt Studio.':report.message,!report.reachable)}catch(error){toast(error.message,true)}finally{state.working=null;render()}return;
 }
 if(a==='refresh-activity'){try{state.activity=(await api('/activity')).items;render();toast('Activity refreshed.')}catch(error){toast(error.message,true)}}
});
document.addEventListener('submit',async event=>{
 if(event.target.id==='comfy-workflow-form'){
  event.preventDefault();if(!state.comfyImportGraph){toast('Select an API-format ComfyUI workflow JSON first.',true);return}
  const f=event.target;const body={name:f.elements.name.value,profile_id:f.elements.profile_id.value,task:f.elements.task.value,mode:f.elements.mode.value,graph:state.comfyImportGraph,text_node:f.elements.text_node.value,text_field:f.elements.text_field.value,image_node:f.elements.image_node.value,image_field:f.elements.image_field.value,output_node:f.elements.output_node.value,output_field:f.elements.output_field.value,trusted:f.elements.trusted.checked};
  try{const w=await api('/comfy/workflows','POST',body);state.comfyWorkflows.push(w);state.comfyImportGraph=null;state.comfyImportName='';render();toast('Trusted ComfyUI workflow saved. Select it under the matching studio task.')}catch(e){toast(e.message,true)}return;
 }
 if(event.target.id!=='connection-form')return;event.preventDefault();const f=event.target;const body={name:f.elements.name.value,kind:f.elements.kind.value,endpoint:f.elements.endpoint.value};
 try{const editing=state.editing;const item=await api(editing?'/profiles/'+editing:'/profiles',editing?'PUT':'POST',body);if(editing){state.profiles=state.profiles.map(p=>p.id===item.id?item:p);delete state.reports[editing];if(item.kind!=='koboldcpp'&&item.kind!=='comfyui'){for(const k of ['prompt','caption','batch'])if(state.profileSelections[k]===item.id){await setBackendChoice(k,'')}}}else{state.profiles.push(item)}state.editing=null;render();toast(editing?'Connection updated. Test it again.':'Connection saved. Use Test to check the server.')}catch(error){toast(error.message,true)}
});
document.addEventListener('input',event=>{if(event.target.closest('#comfy-workflow-form')&&event.target.id!=='comfy-file'){rememberComfyImportForm(event.target.form);return}if(event.target.dataset.libraryQuery){state.libraryBrowse.query=event.target.value;state.libraryBrowse.offset=0;state.libraryBrowse.selectedId='';clearTimeout(librarySearchTimer);librarySearchTimer=setTimeout(()=>{if(state.page==='library')loadLibraryBrowse()},260);return}const captionOption=event.target.dataset.captionOption;if(captionOption){state.captionOptions[captionOption]=event.target.value;return}const batchOption=event.target.dataset.batchOption;if(batchOption){state.batchOptions[batchOption]=event.target.value;return}const batchSetting=event.target.dataset.batchSetting;if(batchSetting){state[batchSetting]=event.target.value;if(batchSetting==='batchCategory')state.batchCategoryTouched=true;return}const setting=event.target.dataset.promptSetting;if(setting){if(setting!=='profile_id')state.promptCfg[setting]=event.target.value;return}const prof=event.target.dataset.pprof;if(prof){state.promptCfg.prompt_profile[prof]=event.target.value;return}const param=event.target.dataset.nparam;if(param){const v=event.target.valueAsNumber;if(Number.isFinite(v))state.promptCfg.params[param]=v;return}const kind=event.target.dataset.draft;if(kind){state.drafts[kind].text=event.target.value;state.dirty[kind]=true;const s=$('#'+kind+'-save-state');if(s)s.textContent='Unsaved edits · '+recentText(kind)}});
document.addEventListener('change',async event=>{if(event.target.closest('#comfy-workflow-form')){rememberComfyImportForm(event.target.form);if(event.target.id!=='comfy-file')return}if(event.target.dataset.libraryCategory){state.libraryBrowse.category=event.target.value;state.libraryBrowse.offset=0;state.libraryBrowse.selectedId='';loadLibraryBrowse();return}if(event.target.dataset.librarySort){state.libraryBrowse.sort=event.target.value;state.libraryBrowse.offset=0;state.libraryBrowse.selectedId='';loadLibraryBrowse();return}const capOption=event.target.dataset.captionOption;if(capOption){state.captionOptions[capOption]=event.target.value;if(['purpose','visual_treatment'].includes(capOption))render();return}const batchOption=event.target.dataset.batchOption;if(batchOption){state.batchOptions[batchOption]=event.target.value;if(['purpose','visual_treatment'].includes(batchOption))render();return}if(event.target.dataset.batchSetting==='batchCategory'){state.batchCategory=event.target.value;state.batchCategoryTouched=true;return}if(event.target.dataset.batchSetting==='batchMode'){state.batchMode=event.target.value;state.batchWorkflow='';render();return}if(event.target.id==='comfy-file'){
  const file=event.target.files?.[0];if(!file)return;
  try{if(file.size>2*1024*1024)throw new Error('Graph exceeds 2 MB.');const graph=JSON.parse(await file.text());if(!graph||!Object.values(graph).every(n=>n&&typeof n.class_type==='string'&&n.inputs))throw new Error('Use ComfyUI Save (API Format), not normal editor JSON.');state.comfyImportGraph=graph;const entries=Object.entries(graph);state.comfyTextNode=(entries.find(([id,n])=>typeof n.inputs.prompt==='string')||entries.find(([id,n])=>Object.values(n.inputs).some(v=>typeof v==='string'))||[])[0]||'';state.comfyImageNode=(entries.find(([id,n])=>typeof n.inputs.image==='string'&&/loadimage/i.test(n.class_type))||[])[0]||'';state.comfyOutputNode=(entries.find(([id,n])=>/showtext|reporttext|displaytext|textoutput/i.test(n.class_type))||entries.at(-1)||[])[0]||'';render();toast('Graph imported locally. Verify all three binding nodes.')}catch(e){toast(e.message,true)}return;
 }
 const tune=event.target.dataset.runtimeSetting;if(tune){const [surface,key]=tune.split(':');const profile=autoProfileId(surface);const route=state.comfyAuto[surface].route;const spec=state.comfyAutoCatalog[profile]?.routes?.[route]?.controls?.[key];if(!spec){toast('This setting is not supported by the selected ComfyUI node.',true);return}const raw=event.target.value;const value=spec.type==='boolean'?(raw==='true'?true:false):Number(raw);if(raw!==''&&(spec.type!=='boolean'&&(!Number.isFinite(value)||(spec.type==='int'&&!Number.isInteger(value))||(spec.min!==undefined&&value<spec.min)||(spec.max!==undefined&&value>spec.max)))){toast('Value must be inside the installed node range.',true);render();return}const dest=state.comfyAuto[surface].runtime_options||(state.comfyAuto[surface].runtime_options={});if(raw==='')delete dest[key];else dest[key]=value;await saveAutoChoice(surface);return;}
 const autoSetting=event.target.dataset.autoSetting;if(autoSetting){const [surface,key]=autoSetting.split(':');const dest=state.comfyAuto[surface];dest[key]=event.target.value;if(key==='route'){dest.model='';dest.mmproj='';dest.chat_handler='';dest.runtime_options={};}render();await saveAutoChoice(surface);return;}const modeSurface=event.target.dataset.comfyMode;if(modeSurface){state.comfyMode[modeSurface]=event.target.value;render();await saveAutoChoice(modeSurface);return;}const comfySelection=event.target.dataset.selectComfyWorkflow;if(comfySelection){if(comfySelection==='prompt')state.promptCfg.workflow_id=event.target.value;else if(comfySelection==='caption')state.captionWorkflow=event.target.value;else state.batchWorkflow=event.target.value;return;}
 if(event.target.id==='image-file-picker'){acceptImageFiles(event.target.files,state.page==='batch'?'batch':'caption');return}if(event.target.id==='batch-folder-picker'){acceptImageFiles(event.target.files,'batch');return}if(event.target.id==='batch-auto-shutdown'){state.batchShutdownEnabled=event.target.checked;return}if(event.target.id==='batch-skip-duplicates'){state.batchSkipDuplicates=event.target.checked;return}const visionBackend=event.target.dataset.visionBackend;if(visionBackend){try{await setBackendChoice(visionBackend==='caption-profile'?'caption':'batch',event.target.value);toast('Backend selection saved.')}catch(e){toast(e.message,true);render()}return}if(event.target.id==='np-preset'&&event.target.value){const x=state.presets.find(y=>y.id===event.target.value);if(x){state.promptCfg=structuredClone(x.settings);render();toast('Preset loaded.')}return}const setting=event.target.dataset.promptSetting;if(setting){if(setting==='profile_id'){try{await setBackendChoice('prompt',event.target.value);toast('Backend selection saved.')}catch(e){toast(e.message,true);render()}}else state.promptCfg[setting]=event.target.value;return}const prof=event.target.dataset.pprof;if(prof){state.promptCfg.prompt_profile[prof]=event.target.value;if(['visual_treatment','purpose','output_format'].includes(prof)){render()}if(prof==='prompt_task'){state.promptCfg.workflow_id='';const entry=(state.manifest?.task_dimensions?.prompt_task||[]).find(x=>x.id===event.target.value)||{};if(entry.output_format){state.promptCfg.prompt_profile.output_format=entry.output_format}else if(['video_generation_prompt','edit_instruction','descriptive_caption'].includes(state.promptCfg.prompt_profile.output_format)){state.promptCfg.prompt_profile.output_format='natural_prompt'}render()}return}const kind=event.target.dataset.task;if(kind){state.drafts[kind].task=event.target.value;state.dirty[kind]=true;if(kind==='caption'){state.captionWorkflow='';render();return}const s=$('#'+kind+'-save-state');if(s)s.textContent='Unsaved edits · '+recentText(kind)}});
document.addEventListener('click',event=>{const drop=event.target.closest('#image-drop');if(drop&&!event.target.closest('button,input'))drop.querySelector('#image-file-picker')?.click()});
document.addEventListener('dragover',event=>{if(event.target.closest('#image-drop')){event.preventDefault();event.target.closest('#image-drop').classList.add('is-over')}});
document.addEventListener('dragleave',event=>{if(event.target.closest('#image-drop'))event.target.closest('#image-drop').classList.remove('is-over')});
document.addEventListener('drop',event=>{const target=event.target.closest('#image-drop');if(target){event.preventDefault();target.classList.remove('is-over');acceptImageFiles(event.dataTransfer.files,state.page==='batch'?'batch':'caption')}});
document.addEventListener('paste',event=>{if(!['caption','batch'].includes(state.page))return;const files=Array.from(event.clipboardData?.files||[]).filter(x=>x.type.startsWith('image/'));if(files.length){event.preventDefault();acceptImageFiles(files,state.page==='batch'?'batch':'caption')}});
document.addEventListener('keydown',event=>{if(event.target.id==='image-drop'&&['Enter',' '].includes(event.key)){event.preventDefault();$('#image-file-picker')?.click()}});
setInterval(async()=>{if(!state.csrf||!state.batchJobs.some(x=>['running','queued','cancel_requested','pause_requested'].includes(x.status)||x.shutdown_state==='countdown'))return;try{const jobs=await api('/batch/jobs');const paged=await Promise.all(jobs.items.map(async j=>{const off=state.batchPageOffsets[j.id]||0;if(!off)return j;try{return (await api('/batch/jobs/'+encodeURIComponent(j.id)+'?offset='+off+'&limit=30')).job}catch{return j}}));state.batchJobs=paged;if(jobs.items.some(x=>x.mode==='library'&&x.counts?.completed)){state.savedCaptions=(await api('/caption/saved')).items}if(state.page==='batch'&&!document.activeElement?.matches('textarea,input,select'))render()}catch{}},2200);
setInterval(()=>{for(const el of document.querySelectorAll('[data-busy-elapsed]')){const key=el.dataset.busyElapsed;const since=state.busySince[key];if(since)el.textContent=Math.max(0,Math.floor((Date.now()-since)/1000))+'s'}},1000);
window.addEventListener('hashchange',()=>{const target=location.hash.slice(1);if(target in names&&target!==state.page)navigate(target)});
$('#menu-toggle').addEventListener('click' ,()=>{const open=$('#sidebar').classList.toggle('is-open');$('#menu-toggle').setAttribute('aria-expanded',String(open))});
init();
