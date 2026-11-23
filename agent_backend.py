"""Bridge the current conversational agent to Studio without an API key."""
import contextvars
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

from PIL import Image
import providers

_current = contextvars.ContextVar("studio_agent_exchange", default=None)


class Pending(Exception):
    def __init__(self, request):
        self.request=request
        super().__init__("等待当前 Agent 提交模型结果")


def in_agent(project):
    return project.get("backend")=="agent" and not project.get("demo")


def role(project,name):
    return ("agent","current") if in_agent(project) else providers.role(name)


@contextmanager
def exchange(root,reply=None):
    if reply is not None and (not isinstance(reply,dict) or set(reply)!={"request_id","result"}
        or not isinstance(reply["request_id"],str) or not isinstance(reply["result"],dict)):
        raise ValueError("Agent 回复文件须包含 request_id 与 result 对象")
    state={"root":Path(root),"reply":reply}
    token=_current.set(state)
    try:
        yield
    finally:
        _current.reset(token)


def request(project,kind,role_name,instruction,data,images=()):
    state=_current.get()
    if state is None:
        raise ValueError("当前项目使用 Agent 后端，请从 Studio CLI 执行 step。")
    payload={"kind":kind,"role":role_name,"instruction":instruction,"input":data,
             "images":[str(Path(image).resolve()) for image in images]}
    encoded=json.dumps([project["id"],payload],ensure_ascii=False,sort_keys=True).encode("utf8")
    key=hashlib.sha256(encoded).hexdigest()
    directory=state["root"]/"agent-exchange"
    directory.mkdir(exist_ok=True)
    cache=directory/(key+".json")
    supplied=state["reply"]
    if supplied is not None and supplied["request_id"]==key:
        result=supplied["result"]
    elif cache.is_file():
        result=json.loads(cache.read_text(encoding="utf8"))
    else:
        raise Pending({"status":"awaiting_agent","request_id":key,**payload})
    if kind=="image":
        source=result.get("image_path")
        if not isinstance(source,str) or not Path(source).is_absolute():
            raise ValueError("请提交本机已生成的图片绝对路径 image_path")
        path=Path(source)
        if not path.is_file() or path.stat().st_size>20_000_000:
            raise ValueError("找不到本地生成图，或图像超过 20 MB")
        with Image.open(path) as image:
            if image.format not in ("PNG","JPEG","WEBP") or image.width*image.height>32_000_000:
                raise ValueError("生成图须使用有效的 PNG、JPEG 或 WebP，不超过 3200 万像素")
            image.verify()
    if supplied is not None and supplied["request_id"]==key:
        cache.write_text(json.dumps(result,ensure_ascii=False),encoding="utf8")
    project["usage"].append({"role":role_name,"model":"agent/current","request_id":key,"local":True})
    return result


def ask(project,name,instruction,data,images=()):
    if in_agent(project):
        return request(project,"json",name,instruction,data,images)
    return providers.ask(name,instruction,data,images,project["usage"])


def draw(project,provider,prompt,path,refs=()):
    aspect=project.get("aspect_ratio","16:9")
    if not in_agent(project):
        return providers.draw(provider,prompt,path,project["usage"],refs,aspect)
    result=request(project,"image","image",
        "使用当前 Agent 可用的生图工具按提示生成一张图片，并将本地绝对路径放入 result.image_path。input.prompt 原样交给生图工具，不改写、不增删；画幅按 input.aspect_ratio 设置。"
        "images 中如有图片，是已确认样张或风格参考，作为参考图一并传给生图工具。无需配置 Studio 的 API。没有生图工具时向用户说明，保留当前流程。",
        {"prompt":prompt,"asset":path.name,"aspect_ratio":aspect},refs)
    with Image.open(result["image_path"]) as image:
        image.convert("RGB").save(path,"PNG")

