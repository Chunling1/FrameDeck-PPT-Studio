import React,{useState,useEffect} from 'react';
import {Check,Copy,ShieldCheck,Pencil} from 'lucide-react';

export function FindingExplanation({problem,suggestion}:{problem:string,suggestion?:string}){
 return <div className="finding-explanation">
 <p><strong>哪里有问题</strong>{problem}</p>
 {suggestion&&<p><strong>怎么改</strong>{suggestion}</p>}
 </div>
}

export function PromptReview({s,idx,I,stage,blocked,step,request,editPage,editDirection,editShared,job,submitting,err,auditDisabled}){
 const [tab,T]=useState('prompt'),[contract,K]=useState<any>(null),[prompt,P]=useState<any>(undefined),[error,E]=useState(''),[copied,C]=useState(false);
 const report=s.reports.audit,legacy=report&&!report.version;
 const auditing=job?.op==='audit'&&!job.target&&['running','paused','pausing'].includes(job.status);
 const progress=submitting==='audit'?'正在提交校核…':job?.status==='returning'?'正在返回，等待在途请求结束…':auditing?(job.status==='running'?'正在校核全稿…':job.status==='paused'?'校核已暂停':'校核正在暂停…'):'';
 const oldRows=(legacy?report.issues||[]:[]).flatMap(text=>text.split(/(?=(?:第\s*\d+\s*页|P\d+)\s*[:：])/).filter(x=>x.trim()).map(x=>({page:Number(x.match(/(?:第\s*|P)(\d+)/)?.[1]||0),severity:'blocker',problem:x})));
 const rows=report?.findings||oldRows;
 const pages=s.plan.slides,page=pages[idx],direction=s.directions?.[idx],num=idx+1;
 const selected=rows.map((r,i)=>({...r,index:i})).filter(r=>r.page===num);
 const fields=contract?.fields||{art:'画面指令',boundary:'证据边界'};
 function revise(field='art'){
   T(field==='art'||field==='boundary'?'prompt':'design');
   editDirection(field,fields,selected);
 }
 const state=!report?'待校核':report.stale?'已修改 · 待复核':report.confirmed?'已确认放行':report.pass&&!s.prompt_audit_current?'待复核最终指令':report.pass?(report.auto_applied?`已自动修订 ${report.auto_applied} 项 · 通过`:'校核通过'):'待确认';
 useEffect(()=>{let ok=true;request('/api/prompt-contract').then(x=>ok&&K(x)).catch(e=>ok&&E(e.message));return()=>{ok=false}},[]);
 useEffect(()=>{let ok=true;P(undefined);C(false);E('');
   const timer=setTimeout(()=>request('/api/projects/'+s.id+'/prompt-preview',{index:idx}).then(x=>{if(ok)P(x.prompt)}).catch(e=>ok&&E(e.message)),100);
   return()=>{ok=false;clearTimeout(timer)}
 },[s.id,s.updated,idx]);
 async function copy(){try{await navigator.clipboard.writeText(prompt);C(true)}catch{E('无法访问剪贴板，可选中文本复制')}}
 return <section className="reviewdesk"><div className="reviewhead"><div><strong>提示词校核台</strong> <span className="tag">{progress||state}</span></div>
 <div className="review-controls"><button disabled={blocked} onClick={editShared}><Pencil size={16}/>编辑公共提示词</button>{(stage===2||!s.prompt_audit_current)&&<><button className="primary" disabled={blocked||auditDisabled} onClick={()=>step('audit')}><ShieldCheck size={16}/>{progress||(report?'重新校核全稿':'确认提示词并核查')}</button><button disabled={blocked} onClick={()=>step('accept_audit')}><Check size={16}/>确认并放行</button></>}</div>
 <div aria-live="polite" style={{width:'100%'}}>{err?<strong className="warn">{err}</strong>:progress?<span>{progress}{auditing&&job.inflight>0?' 正在等待模型返回。':''}</span>:s.prompt_audit_current?(report?.confirmed?'已确认当前提示词并放行，可生成对照样张。':report?.auto_applied?`已自动应用 ${report.auto_applied} 项提示词修订并校核通过，可生成对照样张。`:'最终指令已校核，可生成对照样张。'):report?.pass?'旧版校核不包含当前编译结果，请重新校核或直接确认放行。':report&&!report.stale?<span>{report.auto_applied?`已自动应用 ${report.auto_applied} 项提示词修订；`:''}仍有 {rows.filter(r=>r.severity==='blocker'&&!r.applied).length} 项待确认（若属主观偏好或无需修改，可直接点「确认并放行」）。{rows.some(r=>r.page>0)&&<button onClick={()=>{let f=rows.find(r=>r.severity==='blocker'&&!r.applied&&r.page>0)||rows.find(r=>r.page>0);I(f.page-1);document.querySelector('.reviewresults')?.scrollIntoView({block:'center'})}}>查看校核意见</button>}</span>:null}</div></div>
 <div className="reviewgrid"><nav aria-label="校核页码">{pages.map((p,j)=>{
   let count=rows.filter(r=>r.page===j+1&&!r.applied&&r.severity==='blocker').length;
   return <button key={j} className={idx===j?'on':''} onClick={()=>{I(j);T('prompt')}}><b>{String(j+1).padStart(2,'0')}</b><span>{p.title}</span>{count>0&&<em>{count}</em>}</button>
 })}</nav><div className="reviewbody"><div className="line"><h3>P{String(num).padStart(2,'0')} · {page.title}</h3><div className="actions"><button title={'编辑第 '+num+' 页'} disabled={blocked} onClick={()=>editPage()}>{page.chart?'编辑文案与图表':'编辑文案'}</button><button disabled={blocked||!direction} onClick={()=>revise()}><Pencil size={15}/>修改本页提示词</button></div></div>
 <div className="reviewtabs">{[['prompt','完整生图提示词'],['design','逐项设计稿'],['rules','固定模型指令']].map(([id,label])=><button key={id} aria-pressed={tab===id} onClick={()=>T(id)}>{label}</button>)}</div>
 {tab==='prompt'&&<><div className="line"><small>{page.asset?'原件排版':page.kind==='chart'||page.kind==='flow'?'原生图形排版':'最终发送文本 · '+s.native_palettes[s.prompt_settings.palette].name}</small>{prompt&&<button title="复制完整提示词" onClick={copy}>{copied?<Check size={14}/>:<Copy size={14}/>}复制</button>}</div><pre className="prompttext">{prompt===undefined?'读取中…':prompt===null?(page.asset||['chart','flow'].includes(page.kind)?'本页不发送生图请求。'+(direction?.art||''):'尚无正式提示词，请先生成逐页设计稿。'):prompt}</pre></>}
 {tab==='design'&&<dl>{Object.entries(contract?.fields||{}).map(([key,name])=><React.Fragment key={key}><dt>{String(name)}</dt><dd>{direction?.[key]||'尚未生成'}</dd></React.Fragment>)}</dl>}
 {tab==='rules'&&<><h4>主力模型 · 设计稿输出契约</h4><pre className="prompttext">{contract?.director}</pre><h4>审查模型 · 校核输出契约</h4><pre className="prompttext">{contract?.auditor}</pre></>}
 </div></div>
 <div className="reviewresults"><div className="line"><h3>校核结果 · P{String(num).padStart(2,'0')}</h3>{(report||legacy)&&<button disabled={blocked||!direction} onClick={()=>revise()}><Pencil size={15}/>对照意见修改</button>}</div>
 {legacy?<><p>旧版文字意见尚未改稿。重新校核可生成逐字段修订稿。</p>{oldRows.filter(r=>!r.page||r.page===num).map((r,i)=><p key={i}>{r.problem}</p>)}</>:!selected.length?<p>{!report?'尚未执行校核。':report.stale?'稿件已修改，需重新校核。':'本页没有记录到问题。'}</p>:selected.map(r=><div className="finding" key={r.index}>
 <strong>{r.applied?'已应用 · 待复核':report.stale&&direction?.[r.field]!==undefined&&direction[r.field]!==r.before?'已编辑 · 待复核':r.severity==='blocker'?'必须修订':'可选建议'} · {fields[r.field]||({slide:'页面文案',claims:'来源与引文',style:'整稿风格',shared:'公共提示词'})[r.field]}</strong>
 <FindingExplanation problem={r.problem} suggestion={r.suggestion}/>
 {r.replacement&&<details><summary>对照原文与建议稿</summary><h4>原文</h4><pre>{r.before}</pre><h4>修改后</h4><pre>{r.replacement}</pre></details>}
 <div className="finding-actions">
 {direction?.[r.field]!==undefined?<button disabled={blocked} onClick={()=>revise(r.field)}><Pencil size={15}/>手动修改此项</button>:r.field==='shared'?<button disabled={blocked} onClick={editShared}>修改公共提示词</button>:r.field==='slide'?<><button disabled={blocked} onClick={()=>editPage()}>编辑本页文案</button>{page.chart&&<button disabled={blocked} onClick={()=>editPage('chart')}>改图表数据</button>}</>:r.field==='claims'?<><button disabled={blocked} onClick={()=>editPage('claims')}>改引用</button>{page.chart&&<button disabled={blocked} onClick={()=>editPage('chart')}>改图表数据</button>}</>:<small>这项意见涉及整稿风格，请检查公共提示词或策划内容。</small>}
 {r.replacement&&<button disabled={blocked||r.applied||direction?.[r.field]!==r.before} onClick={()=>step('apply_finding',{index:r.index})}>应用此项修订</button>}
 </div>
 </div>)}</div>{error&&<p className="warn">{error}</p>}</section>
}
