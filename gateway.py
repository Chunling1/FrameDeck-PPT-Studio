"""Personal OpenAI-compatible gateway; the key stays in the user's original vault."""
import argparse
import ipaddress
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
import httpx

PROFILE=Path(os.getenv("LOCALAPPDATA",Path.home()))/"PptGptStudio"/"gateway-profile.json"
CONFIRMATION="确认启用私有网关"
_active_profile=None
ROLES={"planner":"gpt-6.2-sol","auditor":"claude-opus-5-5","critic":"claude-opus-5-5","compiler":"gpt-6.2-sol"}


def read_vault(path):
    text=Path(path).read_text(encoding="utf-8-sig")
    section=re.search(r"(?ims)^## [^\n]*Vultr[^\n]*CLIProxyAPI[^\n]*\n(.*?)(?=^## |\Z)",text)
    if not section:raise ValueError("找不到指定的 Vultr 连接信息节")
    def field(label):
        m=re.search(r"(?im)^\|\s*"+label+r"[^|\n]*\|\s*`([^`\r\n]+)`\s*\|",section[1])
        if not m:raise ValueError("缺少网关连接字段")
        return m[1]
    base=field("API Base URL").rstrip("/")
    u=urlsplit(base)
    if u.username or u.password or u.query or u.fragment or u.path!="/v1":raise ValueError("非法网关地址")
    if u.scheme!="https":
        if u.scheme!="http" or ipaddress.ip_address(u.hostname) not in ipaddress.ip_network("100.64.0.0/10"):raise ValueError("明文连接仅允许私网 Tailscale 节点")
    return base,field("API Key")


def enabled():
    return _active_profile is not None


def profile():
    # Startup and model discovery use only in-memory state.
    return _active_profile or {}


def enable(confirmation,profile_path=None):
    global _active_profile
    if confirmation!=CONFIRMATION:
        raise ValueError("请先选择并确认启用私有网关")
    path=Path(profile_path) if profile_path is not None else PROFILE
    try:
        config=json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise ValueError("没有保存的私有网关配置，请先自行配置") from None
    except (OSError, ValueError):
        raise ValueError("无法读取所选私有网关配置，请检查文件") from None
    if (not isinstance(config,dict) or any(not isinstance(config.get(k),str) or not config[k].strip() for k in ("base","source"))
        or not isinstance(config.get("models"),dict) or any(
            not isinstance(v,str) or not re.fullmatch(r"[A-Za-z0-9._-]+",v) for v in config["models"].values())):
        raise ValueError("所选私有网关配置格式不正确")
    _active_profile=config


def disable():
    global _active_profile
    _active_profile=None


def call(method,path,body=None):
    if not enabled():
        raise ValueError("私有网关默认关闭，请先主动选择并确认启用")
    return _request(method,path,body,profile())


def _request(method,path,body,cfg):
    base,key=read_vault(cfg["source"])
    if base!=cfg["base"]:raise ValueError("密钥文件中网关地址已变化，请重新确认")
    with httpx.Client(trust_env=False,follow_redirects=False,timeout=httpx.Timeout(180,connect=8)) as client:
        try:r=client.request(method,base+"/"+path,headers={"Authorization":"Bearer "+key},json=body)
        except httpx.RequestError:raise ValueError("Vultr 网关连接失败，请检查私网连接") from None
    if not r.is_success:raise ValueError(f"Vultr {path} 返回 HTTP {r.status_code}；未切换模型")
    return r.json()


def configure(source,install=False,confirmation=""):
    if confirmation!=CONFIRMATION:raise ValueError("先选择凭证文件，并确认允许私有网关目录查询")
    base,_=read_vault(source);cfg=dict(base=base,source=str(Path(source).resolve()),models=ROLES.copy())
    ids={x.get("id","") for x in _request("GET","models",None,cfg)["data"]}
    for nid in set(ROLES.values()):
        if nid not in ids:
            matches=sorted(i for i in ids if re.sub(r"[^a-z0-9]","",i.lower())==re.sub(r"[^a-z0-9]","",nid))
            if len(matches)!=1:
                hints=sorted(i for i in ids if re.fullmatch(r"(gpt-6[.\w-]*sol|claude-opus-[\d.-]+)",i))
                raise ValueError("未发现 "+nid+"；目录候选："+", ".join(hints))
            for k,v in ROLES.items():
                if v==nid:cfg["models"][k]=matches[0]
    print("Gateway catalog verified:",cfg["models"])
    if install:
        PROFILE.parent.mkdir(parents=True,exist_ok=True)
        PROFILE.write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf8")


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--install",action="store_true")
    ap.add_argument("--confirm-private-gateway",action="store_true",help="确认查询所选凭证文件指向的私有网关")
    args=ap.parse_args()
    try:configure(args.source,args.install,CONFIRMATION if args.confirm_private_gateway else "")
    except ValueError as error:raise SystemExit(str(error)) from None
