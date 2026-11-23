"""Versioned user approval receipts. A client records, rather than authenticates, user consent."""
import hashlib
import json
import re
import time

GATES={"brief":"项目方向","outline":"逐页文案","samples":"双版样张","gallery":"全稿锁版"}
STAGES={"brief":"brief","outline":"outline","samples":"samples","gallery":"gallery"}


def automatic_request(reply):
    if not reply:return ""
    if reply.strip().rstrip("。！!") not in {"全自动","全自动执行","可以全自动执行","同意全自动执行"}:
        raise ValueError("只有用户明确回复「全自动执行」时才可以启用自动确认")
    return reply.strip()


def gallery_passed(project):
    pages=project.get("pages",[])
    reports=project["reports"]
    visual=reports.get("visual",{})
    return bool(pages and project.get("gallery_draft") and
                all(page.get("native_scene") and page.get("native_preview") for page in pages) and
                all(visual.get(str(i+1),{}).get("pass") is True for i in range(len(pages))) and
                reports.get("deck",{}).get("pass") is True)


def review(project,checkpoint,choice=None):
    if checkpoint not in GATES:
        raise ValueError("未知确认节点")
    payload={}
    if checkpoint=="brief":
        payload={k:project.get(k,"") for k in ("name","audience","brief","requirements","style_preset","aspect_ratio")}
        payload["materials"]=[{k:v for k,v in item.items() if k in ("id","name","locator","policy")}
                              for item in project["sources"]+project["assets"]]
        fingerprint=[payload,project["sources"],project["assets"]]
    elif checkpoint=="outline":
        if not project.get("plan"):raise ValueError("请先生成逐页文案")
        payload={"outline":project["plan"]}
        fingerprint=payload
    elif checkpoint=="samples":
        sample=project.get("samples",{}).get(choice)
        if not sample or not sample.get("pptx") or not project["reports"].get("sample"+str(choice),{}).get("pass"):
            raise ValueError("只可确认通过检查并有可下载 PPTX 的样张")
        payload={"choice":choice,"previews":sample["previews"],"native_previews":sample["native_previews"],"pptx":sample["pptx"]}
        fingerprint=[payload,project["reports"]["sample"+choice]]
    else:
        if not gallery_passed(project):raise ValueError("全稿有未通过的页面，请先逐页修正")
        payload={"montage":project["montage"],"native_montage":project["native_montage"],"pptx":project["gallery_draft"]}
        fingerprint=[payload,project["pages"],project["reports"]["visual"],project["reports"]["deck"]]
    code=hashlib.sha256(json.dumps([project["id"],checkpoint,fingerprint],ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:18]
    return {"checkpoint":checkpoint,"label":GATES[checkpoint],"review_code":code,**payload}


def record(project,request):
    gate=request.get("checkpoint")
    if project["stage"]!=STAGES.get(gate):
        raise ValueError("确认节点与当前项目阶段不符")
    item=review(project,gate,request.get("choice"))
    reply=request.get("user_reply","")
    if not isinstance(reply,str) or not 1<=len(reply.strip())<=240:
        raise ValueError("请先在对话或工作台取得用户明确回复")
    normalized=reply.strip().rstrip("。！!.")
    if re.match(r"^(?:不确认|不同意|不行|先别|暂不|还没|等一下|等等|取消|拒绝|待确认|待用户确认|no\b|reject\b)",normalized,re.I):
        raise ValueError("用户尚未明确同意当前版本")
    if request.get("code")!=item["review_code"]:
        raise ValueError("确认码已过期，请重新展示当前版本")
    project.setdefault("approvals",{})[gate]={"code":item["review_code"],"reply":reply.strip(),"at":time.time()}


def require(project,checkpoint,choice=None):
    if project.get("demo"):return
    item=review(project,checkpoint,choice)
    approvals=project.setdefault("approvals",{})
    approval=approvals.get(checkpoint,{})
    if approval.get("code")==item["review_code"]:return
    if project.get("auto_approval"):
        approvals[checkpoint]={"code":item["review_code"],"reply":project["auto_approval"],"at":time.time(),"mode":"auto"}
        return
    raise ValueError(f"正在等待用户确认「{item['label']}」。用 review 查看这一版，展示后等待用户回复，再用 approve 记录。")


def reset_after(project,target):
    keys=list(GATES)
    first={"brief":0,"outline":1,"prompts":2,"audited":2,"samples":2,"selected":3,"gallery":3}.get(target,0)
    for key in keys[first:]:
        project.get("approvals",{}).pop(key,None)

