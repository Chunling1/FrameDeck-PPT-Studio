import React,{useEffect,useLayoutEffect,useId,useState,useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {FindingExplanation,PromptReview} from './PromptReview';
import {Layers3,Plus,FileText,Images,FolderOpen,ArrowRight,Check,ChevronDown,Download,RotateCcw,Pencil,Upload,BookOpen,GitBranch,LayoutTemplate,ShieldCheck,ScanEye,PackageCheck,SlidersHorizontal,X,LoaderCircle,Pause,Play,Trash2,Save} from 'lucide-react';

const stages=['brief','outline','prompts','audited','samples','selected','gallery','locked','exported'];
const names=['资料与目标','逐页策划','提示词校核','风格打样','样张盲选','全稿生成','全稿审阅','锁版交付','已交付'];
const icons=[FolderOpen,FileText,ShieldCheck,LayoutTemplate,ScanEye,Images,BookOpen,PackageCheck,Check];
const ops=['outline','confirm_outline','audit','samples','select','gallery','lock','export',''];
const labels=['生成逐页策划','确认叙事与逐页结构','确认提示词并核查','生成对照样张','采用此组样张','生成全稿并审阅','确认并锁版','导出交付文件',''];
let token='';
async function request(url:string,body?:any,retry=true){let r=await fetch(url,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Studio-Token':token},body:JSON.stringify(body)});if(!r.ok){let t=await r.text();try{t=JSON.parse(t).detail}catch{}if(retry&&r.status===403&&t==='本地会话无效，请刷新页面'){token=(await request('/api/session')).token;return request(url,body,false)}throw Error(t)}return r.json()}
function Modal({title,onClose,children}:{title:string,onClose:()=>void,children:React.ReactNode}){
 const ref=useRef<HTMLDialogElement>(null);
 const titleId=useId();
 useLayoutEffect(()=>{const el=ref.current!;el.showModal();el.querySelector<HTMLElement>('[data-focus]')?.focus();return()=>{el.close()}},[]);
 return <dialog ref={ref} className="dialog" aria-labelledby={titleId} onCancel={e=>{e.preventDefault();onClose()}}>
 <div className="line"><h2 id={titleId}>{title}</h2><button title="关闭" onClick={onClose}><X size={18}/></button></div>
 {children}</dialog>
}
function PageFields({s,page,U,focus,blocked,hideVisual=false}){
 const set=(k,v)=>U(p=>({...p,[k]:v}));
 const chart=(k,v)=>U(p=>({...p,chart:{...p.chart,[k]:v}}));
 const claim=(i,k,v)=>set('claims',page.claims.map((c,j)=>i===j?{...c,[k]:v}:c));
 return <fieldset className="page-fields" disabled={blocked}>
 <label>标题<input value={page.title} maxLength={46} onChange={e=>set('title',e.target.value)}/></label>
 <label>页结论<textarea value={page.conclusion} maxLength={90} onChange={e=>set('conclusion',e.target.value)}/></label>
 <label>正文（每行一条）<textarea value={page.copy.join('\n')} onChange={e=>set('copy',e.target.value.split('\n'))}/></label>
 {page.chart&&<section className="page-field-section"><div className="line"><h3>图表数据</h3><button type="button" disabled={page.chart.categories.length>=6} onClick={()=>U(p=>({...p,chart:{...p.chart,categories:[...p.chart.categories,''],values:[...p.chart.values,'']}}))}><Plus size={15}/>添加数据项</button></div><label>单位<input data-focus={focus==='chart'&&!page.chart.values.length?'':undefined} maxLength={16} value={page.chart.unit} onChange={e=>chart('unit',e.target.value)}/></label>
 {page.chart.categories.map((cat,i)=><div className="form-row chart-row" key={i}><label>类别 {i+1}<input value={cat} onChange={e=>chart('categories',page.chart.categories.map((v,j)=>i===j?e.target.value:v))}/></label><label>数值 {i+1}<input data-focus={focus==='chart'&&!i?'':undefined} type="number" min="0" step="any" value={page.chart.values[i]} onChange={e=>chart('values',page.chart.values.map((v,j)=>i===j?e.target.value:v))}/></label><button type="button" title={page.chart.categories.length<=2?'至少保留 2 项':'删除此数据项'} disabled={page.chart.categories.length<=2} onClick={()=>U(p=>({...p,chart:{...p.chart,categories:p.chart.categories.filter((_,j)=>j!==i),values:p.chart.values.filter((_,j)=>j!==i)}}))}><Trash2 size={15}/></button></div>)}</section>}
 {['cover','content','divider'].includes(page.kind)&&!page.asset&&s.stage==='outline'&&<label>制作方式<select value={page.art_mode||'auto'} onChange={e=>{const mode=e.target.value;U({...page,art_mode:mode,diagram:mode==='diagram'?page.diagram||{labels:['起点','分支一','分支二'],links:[[0,1],[0,2]]}:null})}}><option value="auto">自动（插画）</option><option value="illustration">整页参考并保留插画</option><option value="diagram">整页参考并重建关系图</option><option value="native">原生排版</option></select></label>}
 {page.art_mode==='diagram'&&page.diagram&&s.stage==='outline'&&<><label>节点文字（从 0 开始，每行一个）<textarea value={page.diagram.labels.join('\n')} onChange={e=>set('diagram',{...page.diagram,labels:e.target.value.split('\n')})}/></label><label>连线（每行一条，例如 0,1）<textarea defaultValue={page.diagram.links.map(x=>x.join(',')).join('\n')} onBlur={e=>set('diagram',{...page.diagram,links:e.target.value.split('\n').filter(Boolean).map(x=>x.split(',').map(v=>Number(v.trim())))})}/></label></>}
 {page.kind==='flow'&&<label>流程步骤（每行一条）<textarea value={page.steps.join('\n')} onChange={e=>set('steps',e.target.value.split('\n'))}/></label>}
 {!page.chart&&page.kind!=='flow'&&<div className="form-row"><label>版式<select value={page.layout} onChange={e=>set('layout',e.target.value)}>{[['left','左文右图'],['right','右文左图'],['wide','上文下图']].map(([k,label])=><option key={k} value={k}>{label}</option>)}</select></label><label>原件<select value={page.asset} onChange={e=>set('asset',e.target.value)}><option value="">不使用独立原件</option>{s.assets.filter(a=>['exact','crop'].includes(a.policy)).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label></div>}
 {!hideVisual&&<label>画面说明<textarea value={page.visual} maxLength={2400} onChange={e=>set('visual',e.target.value)}/></label>}
 <section className="page-field-section"><div className="line"><h3>引用原文</h3><button type="button" data-focus={focus==='claims'&&!page.claims.length?'':undefined} disabled={!s.sources.length} onClick={()=>set('claims',[...page.claims,{source:s.sources[0].id,quote:''}])}><Plus size={15}/>添加引用</button></div>
 {page.claims.map((c,i)=><div className="claim-field" key={i}><label>引用 {i+1} 的来源<select value={c.source} onChange={e=>claim(i,'source',e.target.value)}>{!s.sources.some(x=>x.id===c.source)&&<option>{c.source}</option>}{s.sources.map(x=><option key={x.id} value={x.id}>{x.id} · {x.name}</option>)}</select></label>
 <label>引用 {i+1} 的原句<textarea data-focus={focus==='claims'&&!i?'':undefined} value={c.quote} maxLength={600} onChange={e=>claim(i,'quote',e.target.value)}/></label>
 <details><summary>查看资料原文</summary><p>{s.sources.find(x=>x.id===c.source)?.text||'未找到这条资料'}</p></details>
 <button type="button" onClick={()=>set('claims',page.claims.filter((_,j)=>j!==i))}><Trash2 size={15}/>移除引用 {i+1}</button></div>)}</section>
 </fieldset>
}

function StepPreview({s,which,request}){
 const [i,I]=useState(0),[prompt,P]=useState('');
 const slides=s.plan?.slides||[],p=slides[i],url=f=>'/files/'+s.id+'/'+f;
 useEffect(()=>{if(which!==2&&which!==3)return;let current=true;P('');request('/api/projects/'+s.id+'/prompt-preview',{index:i}).then(r=>{if(current)P(r.prompt||'本页不发送生图请求。')}).catch(e=>{if(current)P(e.message)});return()=>{current=false}},[s.id,which,i]);
 if(which===0)return <dl className="step-preview">{[['汇报目标',s.brief],['听众',s.audience],['制作要求',s.requirements],['资料',Array.from(new Set(s.sources.map(x=>x.name))).join('、')]].map(([k,v])=><React.Fragment key={k}><dt>{k}</dt><dd>{v||'未填写'}</dd></React.Fragment>)}</dl>;
 if(which<=3)return <><label className="direction-field">页码<select value={i} onChange={e=>I(+e.target.value)}>{slides.map((x,n)=><option key={n} value={n}>{n+1} · {x.title}</option>)}</select></label>{which===1?<div className="step-preview"><strong>{p?.conclusion}</strong>{p?.copy.map((x,n)=><p key={n}>{x}</p>)}</div>:<pre className="step-preview">{prompt}</pre>}</>;
 const groups=which===4?Object.entries(s.samples):which===5?[['已选样张',s.selected?.previews||[]]]:[['全稿',s.pages?.map(x=>x.preview)||[]]];
 return <>{groups.map(([title,files]:any)=><section key={title}><h3>{title.length===1?'方案 '+title:title}</h3><div className="strip">{files.map((f,n)=><a href={url(f)} target="_blank" rel="noreferrer" key={n}><img src={url(f)} alt={'第 '+(n+1)+' 张预览'}/></a>)}</div></section>)}</>
}

function App(){
 const [s,S]=useState<any>(null),[projects,P]=useState<any[]>([]),[busy,B]=useState(false),[err,E]=useState(''),[modal,M]=useState(''),[idx,I]=useState(0),[choice,C]=useState('A'),[text,T]=useState(''),[mode,D]=useState('live'),[title,N]=useState(''),[aud,A]=useState(''),[brief,F]=useState(''),[feedback,G]=useState(''),[policy,Q]=useState('exact'),[returnTo,R]=useState('outline');
 async function session(){let x=await request('/api/session');token=x.token;P(x.projects);return x.projects}
 async function load(id:string){try{sessionStorage.setItem('ppt-studio-active',id)}catch{}S(await request('/api/projects/'+id));I(0);C('A');G('');E('')}
 useEffect(()=>{session().then(p=>{if(p.length){let saved='';try{saved=sessionStorage.getItem('ppt-studio-active')||''}catch{};load(p.find(x=>x.id===saved)?.id||p[0].id)}}).catch(e=>E(e.message))},[]);
 async function work(fn){B(true);E('');try{await fn();await session()}catch(e){E(e.message)}finally{B(false)}}
 const stage=s?stages.indexOf(s.stage):-1,slides=s?.plan?.slides||[],p=slides[idx]||slides[0],url=(f)=>'/files/'+s.id+'/'+f;
 const [draft,Z]=useState({brief:'',audience:'',requirements:'',content:'',style_preset:'academic',aspect_ratio:'16:9'}),[job,J]=useState<any>(null);
 const [draftStatus,DS]=useState(''),[modelHint,MH]=useState<any>(null),[modelVersion,MV]=useState(0),[viewed,VW]=useState(0);
 const last=useRef(''),starting=useRef(false),epoch=useRef(0);
 const [submitting,submit]=useState('');
 const doing=job&&['running','paused','pausing','returning'].includes(job.status);
 const blocked=!!(busy||doing);
 const draftKey=s?'ppt-studio-draft:'+s.id:'';
 useEffect(()=>{
   if(s?.stage!=='brief')return;
   const saved={brief:s.brief||'',audience:s.audience||'',requirements:s.requirements||'',content:s.sources.find(x=>x.manual)?.text||'',style_preset:s.style_preset||'academic',aspect_ratio:s.aspect_ratio||'16:9'};
   let local=null;try{local=JSON.parse(localStorage.getItem(draftKey)||'null')}catch{}
   const valid=local&&['brief','audience','requirements','content'].every(k=>typeof local[k]==='string');
   Z(valid?{...saved,...local}:saved);DS(valid?'已恢复浏览器草稿':'')
 },[s?.id,s?.stage]);
 function setDraft(next){
   Z(next);try{localStorage.setItem(draftKey,JSON.stringify(next));DS('已自动保存到此浏览器')}catch{DS('草稿未能自动保存，请点「保存输入」')}
 }
 function clearDraft(){try{localStorage.removeItem(draftKey)}catch{}DS('已保存到项目')}
 const checkOp=stage===3&&!s.prompt_audit_current?'audit':stage===4?'samples':stage===6?'repair_page':ops[stage];
 const checkIdx=stage===6?idx:null;
 useEffect(()=>{
   MH(null);if(!s||s.demo||!checkOp)return;
   let alive=true;request('/api/projects/'+s.id+'/preflight?op='+checkOp+(checkIdx!==null?'&index='+checkIdx:'')).then(r=>{if(alive)MH(r)}).catch(()=>{if(alive)MH(null)});
   return()=>{alive=false}
 },[s?.id,s?.updated,checkOp,checkIdx,modelVersion]);
 const missingModels=!!modelHint?.missing?.length;
 useEffect(()=>{if(s?.stage==='samples'){const opts=Object.entries(s.samples||{});C(opts.length===1&&s.reports['sample'+opts[0][0]]?.pass?opts[0][0]:'')}},[s?.id,s?.stage,s?.samples?.A?.[0],s?.samples?.B?.[0]]);
 useEffect(()=>{if(!s)return;let stop=false,timer;const id=s.id;last.current='';J(null);
   async function tick(){let delay=1800;try{const version=epoch.current;let j=await request('/api/projects/'+id+'/task');if(stop||version!==epoch.current)return;
     if(!starting.current){if(j.id&&['done','failed'].includes(j.status)&&last.current!==j.id){
       const updated=await request('/api/projects/'+id);if(stop||version!==epoch.current)return;S(updated);if(j.op==='audit'&&!j.target&&j.status==='done'){const f=updated.reports.audit?.findings?.find(r=>r.severity==='blocker'&&!r.applied);if(f)I(f.page-1)}if(j.op==='repair_page'&&!j.target&&j.status==='done')M(x=>x==='page'?'':x);last.current=j.id;if(j.status==='failed')E(j.error);await session()
     }if(!stop)J(j)}
     if(['running','paused','pausing','returning'].includes(j.status))delay=550;
   }catch(e){if(!stop)E(e.message)}finally{if(!stop)timer=setTimeout(tick,delay)}}
   tick();return()=>{stop=true;clearTimeout(timer)}
 },[s?.id]);
 async function step(op,b:any={}){if(starting.current)return;epoch.current++;starting.current=true;submit(op);try{await work(async()=>{
   let current=s;
   const endpoint='/api/projects/'+s.id;
   if(op==='outline'&&stage===0&&!s.demo){
     current=await request(endpoint+'/save_brief',{updated:current.updated,...draft});S(current);clearDraft();
   }
   const gate=op==='outline'&&stage===0?'brief':op==='confirm_outline'?'outline':op==='select'?'samples':op==='lock'?'gallery':'';
   if(gate&&!s.demo&&!s.auto_approval){
     const query=new URLSearchParams({checkpoint:gate,...(gate==='samples'?{choice:b.choice}:{})});
     const item=await request(endpoint+'/review?'+query);
     const details=gate==='brief'?'\n受众：'+item.audience+'\n风格：'+item.style_preset+' · '+item.aspect_ratio:'';
     if(!window.confirm('确认当前版本的「'+item.label+'」？'+details))return;
     current=await request(endpoint+'/approve',{updated:current.updated,checkpoint:gate,code:item.review_code,choice:b.choice,user_reply:'用户在工作台确认'+item.label});S(current);
   }
   if(['outline','confirm_outline','edit','audit','samples','gallery','repair_page','export'].includes(op)){
     const j=await request('/api/projects/'+s.id+'/task/start',{...b,op,updated:current.updated,...(op==='outline'&&stage===0&&s.demo?{draft}:{})});
       J(j.status==='done'||j.status==='failed'?{...j,status:'running'}:j);if(op!=='repair_page')M('');if(op==='samples')C('');if(op==='outline'&&stage===0)clearDraft()
     return
   }
   let x=await request('/api/projects/'+s.id+'/'+op,{updated:current.updated,...b});S(x);I(Math.min(idx,Math.max((x.plan?.slides?.length||1)-1,0)));M('');if(op==='save_brief')clearDraft()
 })}finally{starting.current=false;submit('')}}
 function openBack(target){R(target);E('');M('back')}
 function openView(target){VW(target);M('view')}
 async function confirmBack(){if(!doing)return step('back',{target:returnTo});await work(async()=>{epoch.current++;J(await request('/api/projects/'+s.id+'/task/back',{id:job.id,target:returnTo}));M('')})}
 async function toggleJob(){try{J(await request('/api/projects/'+s.id+'/task/'+(job.status==='running'?'pause':'resume'),{id:job.id}))}catch(e){E(e.message)}}
 async function remove(x,count){if(!window.confirm('从本项目移除“'+x.name+'”'+(count>1?'的全部 '+count+' 条记录':'')+'？不会删除原始文件。'))return;
   await work(async()=>{S(await request('/api/projects/'+s.id+'/remove_material',{id:x.id,updated:s.updated}));if(x.manual)setDraft({...draft,content:''})})}
 function edit(){T(JSON.stringify(s.plan,null,2));M('edit')}
 const [sharedDraft,SD]=useState({shared:'',palette:0});
 function editShared(){E('');SD({...s.prompt_settings});M('shared')}
 const [directionDraft,WD]=useState<{index:number,field:string,fields:Record<string,string>,changes:Record<string,string>,notes:any[]} | null>(null);
 function editDirection(field,fields,notes){
   E('');WD({index:idx,field,fields,changes:{},notes});M('direction');
 }
 const [pageDraft,U]=useState<any>(null),[settings,H]=useState<any>(null),[keys,K]=useState<any>({}),[clearedKeys,CK]=useState<string[]>([]);
 const [fieldFocus,FF]=useState(''),[pageArt,PA]=useState(''),[redraw,RD]=useState(false);
 function editPage(field=''){E('');U(structuredClone(p));FF(field);PA(s.directions?.[idx]?.art||p.visual);RD(false);M('page')}
 function submitPage(){
   const page={...pageDraft,copy:pageDraft.copy.map(x=>x.trim()).filter(Boolean),steps:pageDraft.steps.map(x=>x.trim()).filter(Boolean)};
   if(!page.title.trim()||!page.conclusion.trim()){E('请填写标题和页结论。');return}
   if(page.copy.length>4||page.copy.some(x=>x.length>80)){E('正文最多 4 条，每条不超过 80 字。');return}
   if(page.kind==='flow'&&(page.steps.length<2||page.steps.length>5||page.steps.some(x=>x.length>16))){E('流程步骤需填写 2 至 5 步，每步不超过 16 字。');return}
   if(page.claims.some(c=>c.quote.trim().length<2)){E('请补齐引用原句，或移除还没填好的引用。');return}
   if(page.chart){
     const values=page.chart.values.map(v=>String(v).trim()?Number(v):NaN);
     if(page.chart.categories.length<2||page.chart.categories.length>6||values.some(v=>!Number.isFinite(v)||v<0)||page.chart.categories.some(c=>!c.trim())){E('请给 2 至 6 个图表类别填写名称和有效的非负数值。');return}
     page.chart={...page.chart,values}
   }
   return step(stage===6?'repair_page':'save_page',{index:idx,page,...(stage===6?{art:pageArt,redraw}:{})})
 }
 function showModels(){return work(async()=>{H(await request('/api/models'));K({});CK([]);M('models')})}
 function togglePrivateGateway(enabled:boolean){
   const confirmation='确认启用私有网关';
   if(enabled&&!window.confirm('读取本机已保存的私有网关设置，并允许本次工作台通过它调用模型？关闭工作台后自动恢复关闭。'))return;
   return work(async()=>{
     H(await request('/api/models/private-gateway',{enabled,...(enabled?{confirmation}:{})}));
     MV(v=>v+1);
   });
 }
 const failedPages=stage===6?Object.entries(s.reports.visual||{}).filter(([,r]:any)=>!r.pass).map(([num])=>+num):[];
 const failedDeck=stage===6&&!s.reports.deck?.pass;
 const options=s?Object.entries(s.samples):[];
 const selectedReady=stage===4&&!!choice&&!!s.reports['sample'+choice]?.pass;
 const repIds:number[]=[];
 if(slides.length){
   for(const wanted of [['cover'],['content'],['chart','flow']]){
     const found=slides.findIndex((sl,k)=>!repIds.includes(k)&&wanted.includes(sl.kind));
     if(found>=0)repIds.push(found);
   }
   for(let k=0;k<slides.length&&repIds.length<3;k++)if(!repIds.includes(k))repIds.push(k);
 }
 async function moveSlide(delta:number){
   const nextIdx=idx+delta;if(nextIdx<0||nextIdx>=slides.length)return;
   const nextSlides=[...slides];const [item]=nextSlides.splice(idx,1);nextSlides.splice(nextIdx,0,item);
   await step('edit',{plan:{...s.plan,slides:nextSlides}});I(nextIdx);
 }
 async function addSlide(){
   const blank={kind:'content',title:'新增页面',conclusion:'一句话核心结论',copy:['要点一','要点二'],layout:'left',visual:'居中或分栏结构图解，保持充足留白。',asset:'',claims:[],chart:null,steps:[]};
   const nextSlides=[...slides];nextSlides.splice(idx+1,0,blank);
   await step('edit',{plan:{...s.plan,slides:nextSlides}});I(idx+1);
 }
 async function removeSlide(){
   if(slides.length<=3){E('演示稿至少保留 3 页。');return}
   const nextSlides=slides.filter((_,j)=>j!==idx);
   await step('edit',{plan:{...s.plan,slides:nextSlides}});I(Math.max(0,idx-1));
 }
 async function create(demo){await work(async()=>{let x=await request('/api/projects',{name:demo?'春季岸线观测':title,demo,audience:aud,brief});load(x.id);M('');G('')})}
 async function upload(file){await work(async()=>{let data=await new Promise<string>((res,rej)=>{let reader=new FileReader();reader.onload=()=>res(String(reader.result).split(',')[1]);reader.onerror=rej;reader.readAsDataURL(file)});S(await request('/api/projects/'+s.id+'/upload',{updated:s.updated,name:file.name,data,policy}))})}
 const pageImage=s?.pages?.[idx]?.preview;const busyText=blocked?'处理中…':'';
 const materials=new Map<string,any>();for(const x of [...(s?.sources||[]),...(s?.assets||[])]){const k=x.group||(x.file||x.manual?x.id:'legacy:'+x.name);materials.set(k,{x,count:1+(materials.get(k)?.count||0)})}
 const sourceCount=Array.from(materials.values()).filter(({x})=>!x.file).length;
 const bottomDisabledReason=blocked?'正在处理任务':missingModels&&[0,1,3,5,7].includes(stage)?'请先完成模型配置':stage>=3&&stage<=5&&!s?.prompt_audit_current?'请先完成最终提示词校核':stage===4&&!selectedReady?'请先选择一组通过检查的样张':stage===6&&failedPages.length>0?`请先修改并复核第 ${failedPages.join('、')} 页`:stage===6&&failedDeck?'全稿尚有审阅意见未通过':'';
 const pageFindings=s?.reports?.audit?.findings?.filter(r=>r.page===idx+1)||[];
 return <><header><div className="brand"><span className="mark"><Layers3 size={21}/></span>制稿台 <small>FrameDeck PPT Studio</small></div><div className="headright"><i/> 本地工作台 <span className="version">v0.1</span><button title="模型设置" disabled={blocked} onClick={showModels}><SlidersHorizontal size={16}/></button></div></header>
 <div className="shell"><aside><div className="sidehead">项目空间 <button title="新建项目" onClick={()=>M('new')}><Plus size={16}/></button></div>
 {projects.map(pr=><button key={pr.id} disabled={blocked} onClick={()=>load(pr.id)} className={'project '+(s?.id===pr.id?'active':'')}><FolderOpen size={16}/><span>{pr.name}</span></button>)}
 <div className="sidehead pipeline">制作流程</div>{names.slice(0,8).map((x,j)=>{let Icon=icons[j];return <button type="button" disabled={j>=stage||busy||job?.status==='returning'} aria-current={stage===j?'step':undefined} title={j<stage?'查看：'+x:x} onClick={()=>openView(j)} className={'rail '+(stage===j?'current':'')} key={x}><Icon size={16}/>{x}{stage>j&&<Check className="done" size={14}/>}</button>})}
 <div className="footbrand"><GitBranch size={16}/> Studio / local</div></aside>
 <main>{!s?<div className="start"><div><div className="eyebrow">WORKSPACE / 01</div><h1>演示项目</h1><p>从项目资料开始，或打开岸线观测示例。</p><button className="primary" disabled={blocked} onClick={()=>M('new')}><Plus size={16}/>新建项目</button> <button onClick={()=>create(true)}>打开离线示例</button></div><img src="/static/cover.png" alt="岸线观测示例封面"/></div>:<>
 <div className="crumb">工作空间 <span>/</span> {s.name}</div><div className="titlebar"><div><div className="eyebrow">PRESENTATION PROJECT</div><h1>{s.name}</h1></div><span className="tag">{s.demo?'离线演示':'真实模型'} · {names[stage]}</span></div>
 <div className="meta"><span><FileText size={15}/>{slides.length||'—'} 页</span><span><BookOpen size={15}/>{sourceCount} 份资料</span><span><Images size={15}/>{s.assets.length} 个素材</span></div>
 <section className="work"><div className="sectionbar"><h2><b>{String(stage+1).padStart(2,'0')}</b>{names[stage]}</h2><div className="actions">{stage>0&&<button onClick={()=>openView(stage-1)}><BookOpen size={15}/>查看前面步骤</button>}{stage>0&&<button title="回退并修改" disabled={busy||job?.status==='returning'} onClick={()=>openBack(stages[stage-1])}><RotateCcw size={16}/>返回上一步</button>}{(stage===1||stage===2)&&<button title="编辑整套逐页稿" disabled={blocked} onClick={edit}><Pencil size={16}/></button>}</div></div>
 {doing&&<div className="taskbox" role="status"><strong>{job.status==='returning'?'正在返回，等待在途请求结束':job.status==='paused'?'已暂停':job.status==='pausing'?'正在暂停，等待已发送的请求返回':'正在处理'}{job.total>0?' · '+job.done+' / '+job.total+' 页':''}</strong><small>运行中的模型请求：{job.inflight}</small><button disabled={job.status==='returning'} onClick={toggleJob}>{job.status==='running'?<Pause size={15}/>:<Play size={15}/ >}{job.status==='running'?'暂停任务':'继续任务'}</button></div>}
 {missingModels&&<div className="notice" role="status"><span>{stage===6?'要重新审阅，请先配置：':'开始前请配置：'}{modelHint.missing.join('、')}</span><button disabled={blocked} onClick={showModels}>去模型设置</button></div>}
 {err&&!modal&&<div className="warn stage-error" role="alert">{err}</div>}
 {stage===0?<><div className="brief-fields"><label>汇报目标<input disabled={blocked} value={draft.brief} placeholder="希望听众理解什么、作出什么决定？" onChange={e=>setDraft({...draft,brief:e.target.value})}/></label><label>听众<input disabled={blocked} value={draft.audience} placeholder="例如：博士考评评委、产品投资人、团队负责人" onChange={e=>setDraft({...draft,audience:e.target.value})}/></label><label>演示风格<select disabled={blocked} value={draft.style_preset||'academic'} onChange={e=>setDraft({...draft,style_preset:e.target.value})}>{(s.style_presets||[{id:'academic',name:'学术科研汇报'},{id:'business',name:'商业与产品路演'},{id:'briefing',name:'工作总结与管理简报'},{id:'tutorial',name:'技术分享与方法教程'},{id:'custom',name:'自定义风格'}]).map((sp:any)=><option key={sp.id} value={sp.id}>{sp.name}</option>)}</select></label><label>画幅比例<select disabled={blocked} value={draft.aspect_ratio||'16:9'} onChange={e=>setDraft({...draft,aspect_ratio:e.target.value})}>{(s.aspect_ratios||[{id:'16:9',name:'16:9 宽屏 (1280×720)'},{id:'4:3',name:'4:3 标准 (1024×768)'},{id:'16:10',name:'16:10 宽屏 (1280×800)'}]).map((ar:any)=><option key={ar.id} value={ar.id}>{ar.name}</option>)}</select></label><label className="full">制作要求<textarea disabled={blocked} value={draft.requirements} placeholder="页数、时长、叙事重点、自定义风格描述，以及需要避免的内容" onChange={e=>setDraft({...draft,requirements:e.target.value})}/></label><label className="full">输入内容 / 参考原文<textarea disabled={blocked} value={draft.content} placeholder="粘贴研究思路、工作进展或可引用的原始材料" onChange={e=>setDraft({...draft,content:e.target.value})}/></label></div><div className="line"><small>{draftStatus||'生成策划时，以上内容会与保留的资料一并提交。'}</small><button disabled={blocked} onClick={()=>step('save_brief',draft)}><Save size={15}/>保存输入</button></div>
 <div className="line"><h3>来源与素材</h3><select aria-label="图片用途" value={policy} onChange={e=>Q(e.target.value)}>{[['exact','原样使用'],['crop','允许裁剪'],['reference','风格参考（最多三张）'],['exclude','不采用']].map(([v,k])=><option key={v} value={v}>{k}</option>)}</select><label className="button"><Upload size={15}/>导入文件<input type="file" hidden disabled={blocked} accept=".txt,.md,.csv,.pdf,.docx,.pptx,.xlsx,.png,.jpg,.jpeg,.webp" onChange={e=>{let f=e.target.files?.[0];e.target.value='';if(f)upload(f)}}/></label></div>
 <div className="records">{Array.from(materials.entries()).map(([k,{x,count}])=><div className="material" key={k}><span><b>{x.id}</b> {x.name} <small>{count>1?count+' 条记录':x.locator||x.policy}</small></span><button title={'删除资料：'+x.name} disabled={blocked} onClick={()=>remove(x,count)}><Trash2 size={15}/></button></div>)}</div></>:null}
 {stage===1&&p&&<><h3>{s.plan.thesis}</h3><p className="muted">{s.plan.style}</p><div className="slidegrid"><nav>{slides.map((sl,j)=><button className={j===idx?'on':''} key={j} onClick={()=>I(j)}><b>{String(j+1).padStart(2,'0')}</b>{sl.title}</button>)}</nav><article><div className="eyebrow">SLIDE {String(idx+1).padStart(2,'0')} / {p.kind.toUpperCase()}</div><h2>{p.title}</h2><p>{p.conclusion}</p>{p.copy.map((v,j)=><p key={j}>{v}</p>)}<h4>构图与素材</h4><p>{p.visual}</p>{p.claims.map((c,j)=><blockquote key={j}>{c.source} · {c.quote}</blockquote>)}</article></div></>}
 {(stage===2||stage===3)&&p&&<PromptReview {...{s,idx,I,stage,blocked,step,request,job,submitting,err,editDirection,editShared,editPage}} auditDisabled={missingModels}/>}
 {stage===1&&<div className="line"><button disabled={blocked} onClick={()=>editPage()}><Pencil size={15}/>编辑第 {idx+1} 页</button><button disabled={blocked||idx===0} onClick={()=>moveSlide(-1)}>上移</button><button disabled={blocked||idx>=slides.length-1} onClick={()=>moveSlide(1)}>下移</button><button disabled={blocked||slides.length>=40} onClick={addSlide}><Plus size={15}/>加一页</button><button disabled={blocked||slides.length<=3} onClick={removeSlide}><Trash2 size={15}/>删本页</button>{stage===1&&<><input value={feedback} placeholder="给策划模型的修改意见" onChange={e=>G(e.target.value)}/><button disabled={blocked||!feedback||s.demo} onClick={()=>step('outline',{feedback})}>重新策划</button></>}</div>}
 {stage===4&&<div className="line"><button disabled={blocked} onClick={editShared}><Pencil size={16}/>编辑公共提示词</button><button disabled={blocked||missingModels||!s.prompt_audit_current} onClick={()=>step('samples')}>重新打样</button></div>}
 {(stage===4||stage===5)&&!s.prompt_audit_current&&<p className="warn">这是旧版样张。请返回提示词校核，复核最终指令后重新打样。</p>}
 {stage===4&&options.length>0&&<div className="sample-compare" style={{gridTemplateColumns:`repeat(${options.length}, minmax(0,1fr))`}}>
 {options.map(([label]:any)=>{const r=s.reports['sample'+label];return <div className={'sample-option '+(choice===label?'picked':'')} key={label}><label><input type="radio" name="variant" aria-label={'方案 '+label} checked={choice===label} disabled={blocked||!r?.pass} onChange={()=>C(label)}/>方案 {label}</label><strong className={r?.pass?'muted':'sample-failed'}>{r?.pass?'可采用':'不能采用'}</strong>{s.sample_native?.[label]?.pptx&&<p><a href={url(s.sample_native[label].pptx)}>下载可编辑样张 PPTX</a></p>}<p>{r?.issues?.join('；')||r?.advice||r?.basis}</p></div>})}
 {(options[0][1] as string[]).flatMap((_,i)=>options.map(([label,files]:any)=>{const pageIndex=s.sample_native?.[label]?.page_indices?.[i]??repIds[i];return <figure key={label+i} className="sample-cell"><a href={url(files[i])} target="_blank" rel="noreferrer"><img src={url(files[i])} alt={'方案 '+label+' · 样张 '+(i+1)}/></a>{s.sample_native?.[label]?.native_previews?.[i]&&<a href={url(s.sample_native[label].native_previews[i])} target="_blank" rel="noreferrer"><img src={url(s.sample_native[label].native_previews[i])} alt={'方案 '+label+' · 可编辑排版预览'}/></a>}<figcaption>{pageIndex!==undefined?`P${String(pageIndex+1).padStart(2,'0')} ${slides[pageIndex].title}`:`样张 ${i+1}`} · 方案 {label}<br/>上为视觉稿，下为可编辑排版预览</figcaption></figure>}))}
 </div>}
 {stage===3&&!s.demo&&modelHint?.sample_count===1&&!missingModels&&<p className="muted">本次只生成一组样张，可先审阅再继续。</p>}
 {stage===5&&<><h3>已选样张</h3><div className="strip">{s.selected.previews.map((x,j)=><img key={j} src={url(x)} alt={'锁定样张 '+(j+1)}/>)}</div></>}
 {stage>=6&&<><div className="gallery">{s.pages.map((x,j)=><button key={j} className={idx===j?'on':''} onClick={()=>I(j)}><img src={url(x.preview)}/><small>{String(j+1).padStart(2,'0')}　{slides[j].title}{stage===6&&failedPages.includes(j+1)&&<strong className="page-failed">需修改</strong>}</small></button>)}</div><div className="line"><a href={url(pageImage)} target="_blank">查看第 {idx+1} 页原图</a>{s.pages[idx]?.native_preview&&<a href={url(s.pages[idx].native_preview)} target="_blank" rel="noreferrer">查看可编辑排版预览</a>}<span>{s.reports.visual?.[idx+1]?.advice||''}</span>{stage===6&&<button disabled={blocked} onClick={()=>editPage(slides[idx]?.chart?'chart':'')}><Pencil size={15}/>修改第 {idx+1} 页</button>}</div></>}
 {s.montage&&stage>=6&&<a href={url(s.montage)} target="_blank">查看全稿拼图</a>}{s.gallery_draft&&stage>=6&&<a href={url(s.gallery_draft)} download>下载可编辑全稿检查稿</a>}{s.native_montage&&stage>=6&&<a href={url(s.native_montage)} target="_blank" rel="noreferrer">查看可编辑全稿拼图</a>}{s.reports.deck?.issues?.length>0&&<div className="warn">{s.reports.deck.issues.join('；')}</div>}
 {stage!==2&&stage!==3&&s.reports.audit?.issues?.length>0&&<div className="warn">{s.reports.audit.issues.join('；')}</div>}{Object.entries(s.reports.visual||{}).filter(([k,x]:any)=>!x.pass).map(([k,x]:any)=><p className="warn" key={k}>P{k} · {x.issues.join('；')}</p>)}
 {stage===6&&(failedPages.length>0||failedDeck)&&<p className="warn">{failedPages.length?`第 ${failedPages.join('、')} 页需要修改。`:''}{failedDeck?'全稿还有审阅意见。':''}修改后可重新审阅，不用生成其他页。</p>}
 {stage!==8&&stage!==2&&<div className="bottom"><small>{s.demo?'离线演示不调用模型，不计费。':'模型步骤将向所选服务商发送本项目相关资料，费用由自有 API 账户承担。'}</small><div className="actions"><button className="primary" title={bottomDisabledReason||undefined} disabled={!!bottomDisabledReason} onClick={()=>step(ops[stage],{choice})}>{blocked?<LoaderCircle className="spin" size={16}/>:null}{busyText||labels[stage]} <ArrowRight size={15}/></button></div></div>}{stage===8&&<h3>交付完成</h3>}</section>
 {!s.demo&&s.usage?.length>0&&stage!==4&&<details><summary>实际 API 调用记录 · {s.usage.length}</summary>{s.usage.map((u,j)=><div key={j}>{u.role} · {u.model} · {u.seconds} 秒</div>)}</details>}
 {stage===3&&s.reports.audit?.advice&&<p>审查意见：{s.reports.audit.advice}</p>}
 
 {s.deliveries.length>0&&<details className="delivery-list" open={stage===8}><summary>交付版本 · {s.deliveries.length}</summary>{[...s.deliveries].reverse().map((v,i)=><div className="delivery-version" key={v.id}><strong>第 {s.deliveries.length-i} 版</strong><time dateTime={new Date(v.at*1000).toISOString()}>{new Date(v.at*1000).toLocaleString('zh-CN')}</time><div className="exports">{[['editable.pptx','可编辑 PPTX'],['image.pptx','图片 PPTX'],['project.zip','可重建工程']].map(([f,t])=><a className="button" href={url('delivery/'+v.id+'/'+f)} key={f}><Download size={16}/>{t}</a>)}</div></div>)}</details>}
 </>}{!s&&err&&<div className="warn" role="alert">{err}</div>}</main></div>
 {modal==='page'&&<Modal title={`第 ${idx+1} 页`} onClose={()=>M('')}>
 {(stage===2||stage===3)&&pageFindings.length>0&&<div className="notice">{pageFindings.map((r,n)=><FindingExplanation key={n} problem={r.problem} suggestion={r.suggestion}/>)}</div>}
 {stage===6&&<div className="notice">{(s.reports.visual?.[idx+1]?.issues||[]).join('；')||'修改和重新审阅当前页，其他页保持原样。'}</div>}
 <PageFields s={s} page={pageDraft} U={U} focus={fieldFocus} blocked={blocked} hideVisual={stage===6&&!pageDraft.asset&&['cover','content','divider'].includes(pageDraft.kind)}/>
 {stage===6&&!pageDraft.asset&&['cover','content','divider'].includes(pageDraft.kind)&&<><label className="direction-field">实际生图指令<textarea disabled={blocked} maxLength={12000} value={pageArt} onChange={e=>PA(e.target.value)}/></label><label><input disabled={blocked} type="checkbox" checked={redraw} onChange={e=>RD(e.target.checked)}/>即使指令不变，也重新生成本页插画</label></>}
 <div className="page-editor-footer">
 {err&&<p className="warn" role="alert">{err}</p>}
 {stage===6&&missingModels&&<p className="warn">改页审阅需要：{modelHint.missing.join('、')}。请先关闭这里并打开模型设置。</p>}
 <button className="primary" disabled={blocked||(stage===6&&missingModels)} onClick={submitPage}>{blocked&&stage===6?'正在核查并审阅本页…':stage===6?'保存并重新审阅本页':'保存本页'}</button>
 </div>
 </Modal>}
 {modal==='models'&&settings&&<Modal title="模型设置" onClose={()=>{K({});CK([]);M('')}}><small>密钥只在当前服务进程中使用，关闭服务后不保存。</small><div className="line"><span>私有网关：{settings.private_gateway_enabled?'本次工作台已启用':'已关闭'}</span><button type="button" disabled={blocked} onClick={()=>togglePrivateGateway(!settings.private_gateway_enabled)}>{settings.private_gateway_enabled?'关闭私有网关':'使用本机已保存的私有网关'}</button></div>{Object.keys(settings.keys).map(k=><div className="key-field" key={k}><label>{k}<input style={{width:'100%'}} type="password" autoComplete="off" placeholder={clearedKeys.includes(k)?'已标记清除（应用后生效）':settings.keys[k]?'已配置，留空保持':'未配置'} value={keys[k]||''} onChange={ev=>{K({...keys,[k]:ev.target.value});if(ev.target.value)CK(clearedKeys.filter(x=>x!==k))}}/></label>{settings.keys[k]&&<button type="button" onClick={()=>CK(clearedKeys.includes(k)?clearedKeys.filter(x=>x!==k):[...clearedKeys,k])}>{clearedKeys.includes(k)?'撤销清除':'清除'}</button>}</div>)}{settings.art_enabled&&<div className="art-toggles"><span>参与打样的生图服务：</span>{[['openai','OpenAI 生图'],['google','Gemini 生图']].map(([k,label])=><label key={k}><input type="checkbox" checked={settings.art_enabled[k]} onChange={ev=>H({...settings,art_enabled:{...settings.art_enabled,[k]:ev.target.checked}})}/>{label}</label>)}</div>}{Object.keys(settings.roles).map(k=><label key={k}>{({planner:'策划',auditor:'事实校核',critic:'视觉审核',compiler:'可编辑重建',art_openai:'OpenAI 生图',art_google:'Gemini 生图'})[k]}<input style={{width:'100%'}} value={settings.roles[k]} onChange={ev=>H({...settings,roles:{...settings.roles,[k]:ev.target.value}})}/></label>)}<button className="primary" disabled={blocked} onClick={()=>work(async()=>{await request('/api/models',{roles:settings.roles,keys,clear_keys:clearedKeys,art_enabled:settings.art_enabled});K({});CK([]);M('');MV(v=>v+1)})}>应用到本次运行</button>{err&&<p className="warn">{err}</p>}</Modal>}
 {modal==='direction'&&directionDraft&&<Modal title={'修改第 '+(directionDraft.index+1)+' 页提示词'} onClose={()=>M('')}>
 <label className="direction-field">修改字段<select value={directionDraft.field} onChange={e=>WD({...directionDraft,field:e.target.value})}>{Object.entries(directionDraft.fields).map(([k,label])=><option key={k} value={k}>{label}</option>)}</select></label>
 {directionDraft.notes.filter(r=>!r.field||r.field===directionDraft.field).map(r=><div key={r.index} className="finding"><FindingExplanation problem={r.problem} suggestion={r.suggestion}/></div>)}
 <label className="direction-field">提示词内容<textarea maxLength={12000} value={directionDraft.changes[directionDraft.field]??s.directions[directionDraft.index][directionDraft.field]??''} onChange={e=>{
   const k=directionDraft.field,changes={...directionDraft.changes};
   if(e.target.value===s.directions[directionDraft.index][k])delete changes[k];
   else changes[k]=e.target.value;
   WD({...directionDraft,changes})
 }}/></label>
 <small>{p.asset||['chart','flow'].includes(p.kind)?'本页使用原件或原生图形，不会发送生图请求。':''}保存后须重新校核；不会自动调用模型。</small>
 <button className="primary" disabled={blocked||!Object.keys(directionDraft.changes).length||Object.values(directionDraft.changes).some(v=>!v.trim())} onClick={()=>step('save_direction',{index:directionDraft.index,changes:directionDraft.changes})}><Save size={16}/>{submitting==='save_direction'?'保存中…':'保存提示词'}</button>
 {err&&<p className="warn" role="alert">{err}</p>}
 </Modal>}
 {modal==='shared'&&<Modal title="编辑公共提示词" onClose={()=>M('')}>
 <label className="direction-field">公共画面指令<textarea maxLength={12000} value={sharedDraft.shared} onChange={e=>SD({...sharedDraft,shared:e.target.value})}/></label>
 <label className="direction-field">原生页面配色<select value={sharedDraft.palette} onChange={e=>SD({...sharedDraft,palette:+e.target.value})}>{s.native_palettes.map((theme,i)=><option value={i} key={i}>{theme.name}</option>)}</select></label>
 <ul className="palette-row">{s.native_palettes[sharedDraft.palette].colors.map((color,i)=><li key={i}><i style={{backgroundColor:color}}/><span>{['底色','线色','待决色','辅助底色'][i]} <code>{color}</code></span></li>)}</ul>
 <small>公共指令作用于所有生图页，原件和原生图形不发给图像模型。改动后需复核各页最终指令{stage===4?'，并重新打样':''}。</small>
 <button className="primary" disabled={blocked||(sharedDraft.shared.trim()===s.prompt_settings.shared&&sharedDraft.palette===s.prompt_settings.palette)} onClick={()=>step('save_prompt_settings',sharedDraft)}><Save size={16}/>{submitting==='save_prompt_settings'?'保存中…':'保存公共提示词'}</button>
 {err&&<p className="warn" role="alert">{err}</p>}
 </Modal>}
 {modal==='view'&&<Modal title="查看前面步骤" onClose={()=>M('')}>
 <label className="direction-field">查看步骤<select value={viewed} onChange={e=>VW(+e.target.value)}>{names.slice(0,stage).map((name,i)=><option value={i} key={name}>{name}</option>)}</select></label>
 <StepPreview key={viewed} s={s} which={viewed} request={request}/>
 <button disabled={blocked} onClick={()=>openBack(stages[viewed])}><RotateCcw size={16}/>退回此步骤修改</button>
 </Modal>}
 {modal&&modal!=='page'&&modal!=='models'&&modal!=='direction'&&modal!=='shared'&&modal!=='view'&&<Modal title={modal==='new'?'新建演示项目':modal==='edit'?'编辑逐页策划':'回退修改'} onClose={()=>M('')}>
 {modal==='new'?<><select value={mode} onChange={e=>D(e.target.value)}><option value="demo">离线示例</option><option value="live">真实模型 · BYOK</option></select>{mode==='live'&&<><input placeholder="项目名称" value={title} onChange={e=>N(e.target.value)}/><input placeholder="汇报对象" value={aud} onChange={e=>A(e.target.value)}/><textarea placeholder="目标、页数、讲述时间与视觉偏好" value={brief} onChange={e=>F(e.target.value)}/></>}<button className="primary" disabled={blocked||(mode==='live'&&!title.trim())} onClick={()=>create(mode==='demo')}>建立项目</button></>:modal==='edit'?<><textarea className="code" value={text} onChange={e=>T(e.target.value)}/><button className="primary" disabled={blocked} onClick={()=>{try{step('edit',{plan:JSON.parse(text)})}catch{E('JSON 格式无效')}}}>{'保存方案'}</button></>:<><select value={returnTo} onChange={e=>R(e.target.value)}>{stages.slice(0,stage).map(v=><option key={v} value={v}>{names[stages.indexOf(v)]}</option>)}</select><p>{doing?'将停止本任务的后续请求；已发送的请求返回后再回退。':''}返回后须重新确认后续步骤；资料与图片缓存保留。</p><button className="primary" disabled={busy||job?.status==='returning'} onClick={confirmBack}>确认回退</button></>}{err&&<p className="warn">{err}</p>}</Modal>}</>
}
createRoot(document.getElementById('root')!).render(<App/>);
