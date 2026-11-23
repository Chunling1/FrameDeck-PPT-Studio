import base64
import json
import secrets
import threading
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
import engine as e
import gateway
import tasks

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=["127.0.0.1","localhost","testserver"])
token=secrets.token_urlsafe(24)
mutex=threading.Lock()
jobs={}
ACTIVE={"running","pausing","paused","returning"}


def active(id):
    return id in jobs and jobs[id].snapshot()["status"] in ACTIVE


@app.middleware("http")
async def protect(req:Request,next):
    if req.method!="GET" and not secrets.compare_digest(req.headers.get("X-Studio-Token",""),token):
        return JSONResponse({"detail":"本地会话无效，请刷新页面"},403)
    if int(req.headers.get("content-length","0"))>29_000_000:return JSONResponse({"detail":"文件过大"},413)
    resp=await next(req);resp.headers["X-Content-Type-Options"]="nosniff";resp.headers["Cache-Control"]="no-store"
    resp.headers["Content-Security-Policy"]="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; object-src 'none'"
    return resp


@app.exception_handler(ValueError)
async def invalid(req,err):return JSONResponse({"detail":str(err)[:1500]},422)


def public(s):
    s={**s,"sample_native":{label:{k:a[k] for k in ("native_previews","pptx","page_indices") if k in a} for label,a in s["samples"].items()},"deliveries":e.deliveries(s),"samples":{label:a["previews"] for label,a in s["samples"].items()}}
    if s["stage"]=="samples":s["usage"]=[]
    if s["plan"]:
        s["prompts"]=e.prompts(s)
        s["prompt_settings"]=e.prompt_settings(s)
        s["prompt_audit_current"]=e.current_prompt_audit(s)
        s["native_palettes"]=[dict(name=name,colors=["#"+c for c in colors]) for name,colors in zip(e.render.PALETTE_NAMES,e.render.PALETTES)]
    s["style_presets"]=[dict(id=k,name=v[0],desc=v[1]) for k,v in e.render.STYLE_PRESETS.items()]
    s["aspect_ratios"]=[dict(id=k,name=v[0]) for k,v in e.render.ASPECT_RATIOS.items()]
    return s


@app.get("/api/session")
def session():
    keys=("id","name","stage","demo","updated")
    with e.db() as c:rows=c.execute("SELECT id,json_extract(state,'$.name'),json_extract(state,'$.stage'),json_extract(state,'$.demo'),json_extract(state,'$.updated') FROM projects ORDER BY 5 DESC").fetchall()
    return {"token":token,"projects":[dict(zip(keys,r)) for r in rows]}


@app.get("/api/models")
def model_status():
    return {"roles":{k:"/".join(e.providers.role(k)) for k in e.providers.DEFAULTS},
        "private_gateway_enabled":gateway.enabled(),
        "keys":{k:bool(e.os.getenv(k)) for k in ("OPENAI_API_KEY","GEMINI_API_KEY","ANTHROPIC_API_KEY")},
        "art_enabled":{k:e.os.getenv("STUDIO_DISABLE_ART_"+k.upper())!="1" for k in ("openai","google")}}


@app.post("/api/models/private-gateway")
def toggle_private_gateway(b:dict):
    chosen=b.get("enabled")
    if type(chosen)!=bool:
        raise ValueError("请明确选择是否使用私有网关")
    with mutex:
        if any(active(id) for id in jobs):raise HTTPException(409,"任务进行中，暂不能更换模型")
        if chosen:gateway.enable(b.get("confirmation"))
        else:gateway.disable()
    return model_status()


@app.post("/api/models")
def configure(b:dict):
    import re
    roles=b.get("roles",{});keys=b.get("keys",{});clear_keys=b.get("clear_keys",[]);art_enabled=b.get("art_enabled",{})
    if not isinstance(roles,dict) or not isinstance(keys,dict) or not isinstance(clear_keys,list) or not isinstance(art_enabled,dict):raise ValueError("配置格式错误")
    for k,v in roles.items():
        if k not in e.providers.DEFAULTS or not isinstance(v,str) or not re.fullmatch(r"(openai|google|anthropic|viru)/[A-Za-z0-9._-]+",v):raise ValueError("模型角色无效")
        if k.startswith("art_") and not (v.startswith(k[4:]+"/") or v.startswith("viru/")):raise ValueError("生图角色需绑定对应的供应商或 viru 网关")
    if any(k not in model_status()["keys"] or not isinstance(v,str) or len(v)>512 or not v.isascii() or v.strip()!=v for k,v in keys.items()):raise ValueError("凭证格式错误")
    if any(k not in model_status()["keys"] for k in clear_keys):raise ValueError("凭证名称无效")
    if any(k not in ("openai","google") or type(v)!=bool for k,v in art_enabled.items()):raise ValueError("生图开关格式错误")
    with mutex:
        if any(active(id) for id in jobs):raise HTTPException(409,"任务进行中，暂不能更换模型")
        if not gateway.enabled() and any(v.startswith("viru/") for v in roles.values()):
            raise ValueError("请先在模型设置主动选择并确认启用私有网关")
        for k,v in roles.items():e.os.environ["STUDIO_"+k.upper()]=v
        for k in clear_keys:e.os.environ.pop(k,None)
        for k,v in keys.items():
            if v:e.os.environ[k]=v
        for k,v in art_enabled.items():
            e.os.environ["STUDIO_DISABLE_ART_"+k.upper()]="0" if v else "1"
    return model_status()


@app.post("/api/projects")
def create(b:dict):
    with mutex:return public(e.create(str(b["name"]),str(b.get("audience","")),str(b.get("brief","")),b.get("demo",False),str(b.get("style_preset","academic")),str(b.get("aspect_ratio","16:9"))))


@app.get("/api/projects/{id}")
def read(id:str):return public(e.get(id))


@app.get("/api/projects/{id}/review")
def review(id:str,checkpoint:str,choice:str|None=None):return e.approvals.review(e.get(id),checkpoint,choice)


@app.get("/api/projects/{id}/preflight")
def preflight(id:str,op:str,index:int|None=None):return e.preflight(e.get(id),op,{"index":index} if index is not None else None)


@app.get("/api/prompt-contract")
def prompt_contract():
    return dict(fields=e.art_direction.FIELDS,director=e.art_direction.DIRECTOR,auditor=e.art_direction.AUDITOR)


@app.post("/api/projects/{id}/prompt-preview")
def prompt_preview(id:str,b:dict):
    s=e.get(id);i=b.get("index")
    if not s["plan"] or type(i)!=int or not 0<=i<len(s["plan"]["slides"]):raise ValueError("预览参数不正确")
    return dict(prompt=e.image_prompt(s,i),updated=s["updated"])


@app.get("/api/projects/{id}/task")
def status(id:str):
    with mutex:return jobs[id].snapshot() if id in jobs else {"status":"idle"}


@app.post("/api/projects/{id}/task/{cmd}")
def manage(id:str,cmd:str,b:dict):
    with mutex:
        if cmd=="back":
            job=jobs.get(id)
            if not job or job.id!=b.get("id"):raise HTTPException(409,"任务已变更")
            target=b.get("target");s=e.get(id)
            if target not in e.STAGES[:e.STAGES.index(s["stage"])]:raise ValueError("只能返回已完成的步骤")
            return job.return_to(target,lambda:e.action(e.get(id),"back",{"target":target}))
        if cmd in ("pause","resume"):
            job=jobs.get(id)
            if not job or job.id!=b.get("id"):raise HTTPException(409,"任务已变更")
            return job.control(cmd=="pause")
        if cmd!="start":raise HTTPException(404)
        if active(id):raise HTTPException(409,"本项目已有任务")
        op=b.get("op")
        if op not in {"outline","confirm_outline","edit","audit","samples","gallery","repair_page","export"}:raise ValueError("不支持的任务")
        s=e.get(id)
        if s["updated"]!=b.get("updated"):raise HTTPException(409,"项目已变更，请刷新")
        if e.agent_backend.in_agent(s) and op in {"outline","confirm_outline","audit","samples","gallery","repair_page"}:
            raise ValueError("此项目由对话 Agent 驱动，请在对话中继续；工作台仍可查看各阶段结果")
        missing=e.preflight(s,op,b)["missing"]
        if missing:raise ValueError("请先配置："+ "、".join(missing))
        if op=="outline" and s["stage"]=="brief" and "draft" in b:e.update_brief(s,b["draft"])
        job=tasks.Task(op);jobs[id]=job
        threading.Thread(target=job.execute,args=(lambda:e.action(s,op,b),),daemon=True).start()
        return job.snapshot()


@app.post("/api/projects/{id}/{op}")
def change(id:str,op:str,b:dict):
    if not mutex.acquire(blocking=False):raise HTTPException(409,"工作台正在执行任务，请稍后重试")
    try:
        if active(id):raise HTTPException(409,"本项目有未完成任务")
        s=e.get(id)
        if b.get("updated",s["updated"])!=s["updated"]:raise HTTPException(409,"项目已变更，请刷新")
        if op=="upload":
            e.ingest(s,b["name"],base64.b64decode(b["data"],validate=True),b.get("policy","exact"))
        elif op=="save_brief":e.update_brief(s,b)
        elif op=="remove_material":e.remove_material(s,b.get("id"))
        else:e.action(s,op,b)
        return public(s)
    finally:mutex.release()


@app.get("/files/{id}/{folder}/{file}")
def file(id:str,folder:str,file:str):
    s=e.get(id);root=e.root(s)
    if folder=="output":
        versions=e.deliveries(s)
        if not versions:raise HTTPException(404)
        return delivery_file(s,versions[-1]["id"],file)
    elif folder in ("cache","assets"):
        if not e.re.fullmatch(r"(?:[0-9a-f]{20}|A[0-9]+)\.(?:png|jpg|jpeg|webp|pptx)",file):raise HTTPException(404)
    else:raise HTTPException(404)
    if file.endswith(".pptx") and (folder!="cache" or not (s.get("gallery_draft")==f"cache/{file}" or any(a.get("pptx")==f"cache/{file}" for a in s["samples"].values()))):
        raise HTTPException(404)
    path=root/folder/file
    if not path.is_file():raise HTTPException(404)
    return FileResponse(path,filename="editable-sample.pptx" if file.endswith(".pptx") else None)


def delivery_file(s,version,file):
    if file not in e.OUTPUTS or not any(v["id"]==version for v in e.deliveries(s)):raise HTTPException(404)
    path=e.delivery_dir(s,version)/file
    if not path.is_file():raise HTTPException(404)
    return FileResponse(path,filename=file)


@app.get("/files/{id}/delivery/{version}/{file}")
def download(id:str,version:str,file:str):
    return delivery_file(e.get(id),version,file)


@app.get("/")
def index():return FileResponse(e.BASE/"static/index.html")


app.mount("/static",StaticFiles(directory=e.BASE/"static"),name="static")
