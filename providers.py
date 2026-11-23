"""Official HTTPS endpoints only. No request bodies or credentials in errors."""
import base64
import io
import json
import os
import re
import time
import httpx
import gateway
import tasks
from PIL import Image

DEFAULTS={"planner":("openai","gpt-4.1"),"auditor":("google","gemini-2.5-flash"),
          "critic":("openai","gpt-4.1"),"compiler":("openai","gpt-4.1"),"art_openai":("openai","gpt-image-1"),
          "art_google":("google","gemini-2.5-flash-image")}
KEY_NAMES={"openai":"OPENAI_API_KEY","google":"GEMINI_API_KEY","anthropic":"ANTHROPIC_API_KEY"}


def role(name):
    p,m=DEFAULTS[name]
    configured=gateway.profile().get("models",{}).get(name)
    if configured:p,m="viru",configured
    override=os.getenv("STUDIO_"+name.upper(),p+"/"+m)
    if override.startswith("viru/") and not gateway.enabled():
        return DEFAULTS[name]
    p,_,m=override.partition("/")
    if p not in ("openai","google","anthropic","viru") or not re.fullmatch(r"[a-zA-Z0-9._-]+",m):
        raise ValueError("无效的模型配置："+name)
    return p,m


def configured(name):
    from pathlib import Path
    if name.startswith("art_") and os.getenv("STUDIO_DISABLE_"+name.upper())=="1":
        return False
    p,_=role(name)
    if p=="viru":
        cfg=gateway.profile()
        return bool(cfg.get("base") and cfg.get("source") and Path(cfg["source"]).is_file())
    return bool(os.getenv(KEY_NAMES[p]))


def post(p,path,body):
    if p=="viru":return gateway.call("POST",path,body)
    base,key={"openai":("https://api.openai.com/v1/","OPENAI_API_KEY"),
              "google":("https://generativelanguage.googleapis.com/v1beta/","GEMINI_API_KEY"),
              "anthropic":("https://api.anthropic.com/v1/","ANTHROPIC_API_KEY")}[p]
    token=os.getenv(key)
    if not token: raise ValueError("缺少 "+key+"，请在「模型设置」填写后重试，无需重启")
    headers={"openai":{"Authorization":"Bearer "+token},"google":{"x-goog-api-key":token},
             "anthropic":{"x-api-key":token,"anthropic-version":"2023-06-01"}}[p]
    r=httpx.post(base+path,headers=headers,json=body,timeout=180)
    if not r.is_success: raise ValueError(f"{p} API 返回 HTTP {r.status_code}，请检查模型权限或配额。")
    return r.json()


def vision(path):
    with Image.open(path) as im:
        im.thumbnail((1100,800))
        b=io.BytesIO()
        im.convert("RGB").save(b,"JPEG",quality=83)
    return base64.b64encode(b.getvalue()).decode()


@tasks.remote
def ask(name,instruction,data,images=(),ledger=None):
    p,m=role(name)
    user=json.dumps(data,ensure_ascii=False)
    imgs=[vision(path) for path in images]
    start=time.monotonic()
    if p in ("openai","viru"):
        content=[{"type":"text","text":user}]+[{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+i}} for i in imgs]
        r=post(p,"chat/completions",dict(model=m,response_format={"type":"json_object"},messages=[
            {"role":"system","content":instruction},{"role":"user","content":content}]))
        raw=r["choices"][0]["message"]["content"]
    elif p=="google":
        parts=[{"text":user}]+[{"inlineData":{"mimeType":"image/jpeg","data":i}} for i in imgs]
        r=post(p,"models/"+m+":generateContent",{"systemInstruction":{"parts":[{"text":instruction}]},
            "contents":[{"parts":parts}],"generationConfig":{"responseMimeType":"application/json"}})
        raw="".join(x.get("text","") for x in r["candidates"][0]["content"]["parts"])
    else:
        content=[{"type":"text","text":user}]+[{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":i}} for i in imgs]
        r=post(p,"messages",dict(model=m,system=instruction,max_tokens=12000,messages=[dict(role="user",content=content)]))
        raw="".join(x.get("text","") for x in r["content"])
    if ledger is not None: ledger.append(dict(role=name,model=p+"/"+m,seconds=round(time.monotonic()-start,1),usage=r.get("usage",r.get("usageMetadata",{}))))
    return json.loads(re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$","",raw))


GEMINI_ASPECTS={"16:9":"16:9","4:3":"4:3","16:10":"16:9"}
OPENAI_SIZES={"16:9":"1536x1024","4:3":"1536x1024","16:10":"1536x1024"}


@tasks.remote
def draw(provider,prompt,path,ledger,refs=(),aspect="16:9"):
    p,m=role("art_"+provider)
    start=time.monotonic()
    size=OPENAI_SIZES.get(aspect,"1536x1024")
    if p!=provider and p!="viru": raise ValueError("图像模型与供应商不匹配")
    if p in ("openai","viru"):
        if refs and p=="openai":
            key=os.getenv("OPENAI_API_KEY")
            if not key:raise ValueError("请设置 OPENAI_API_KEY")
            files=[("image[]",("reference.jpg",base64.b64decode(vision(i)),"image/jpeg")) for i in refs]
            resp=httpx.post("https://api.openai.com/v1/images/edits",headers={"Authorization":"Bearer "+key},files=files,
                            data=dict(model=m,prompt=prompt,size=size,quality="high"),timeout=300)
            if not resp.is_success:raise ValueError(f"OpenAI 参考图请求返回 HTTP {resp.status_code}")
            r=resp.json()
        else:r=post(p,"images/generations",dict(model=m,prompt=prompt,size=size,quality="high",n=1))
        encoded=r["data"][0]["b64_json"]
    else:
        parts=[{"text":prompt}]+[{"inlineData":{"mimeType":"image/jpeg","data":vision(i)}} for i in refs]
        r=post(p,"models/"+m+":generateContent",{"contents":[{"parts":parts}],
            "generationConfig":{"responseModalities":["TEXT","IMAGE"],"imageConfig":{"aspectRatio":GEMINI_ASPECTS.get(aspect,"16:9")}}})
        encoded=next((x["inlineData"]["data"] for x in r["candidates"][0]["content"]["parts"] if "inlineData" in x),None)
        if not encoded: raise ValueError("Gemini 未返回图片")
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as im:
        im.convert("RGB").save(path,"PNG")
    ledger.append(dict(role="image",model=p+"/"+m,seconds=round(time.monotonic()-start,1),usage=r.get("usage",r.get("usageMetadata",{}))))
