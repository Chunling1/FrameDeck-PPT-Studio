import argparse
import base64
import json
import socket
import threading
import webbrowser
from pathlib import Path
import engine as e
import gateway


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--use-private-gateway",action="store_true",help="选择私有网关")
    cli.add_argument("--confirm-private-gateway",action="store_true",help="确认仅在此次命令中使用所选私有网关")
    cli.add_argument("--gateway-profile",type=Path,help="可选：选择其他已保存的网关配置文件")
    sub=cli.add_subparsers(dest="cmd",required=True)
    srv=sub.add_parser("serve");srv.add_argument("--port",type=int,default=8740);srv.add_argument("--open",action="store_true")
    demo=sub.add_parser("demo");new=sub.add_parser("new");new.add_argument("title");new.add_argument("--brief",default="");new.add_argument("--audience",default="")
    new.add_argument("--style",choices=e.render.STYLE_PRESETS,default="academic")
    new.add_argument("--aspect-ratio",choices=e.render.ASPECT_RATIOS,default="16:9")
    new.add_argument("--auto-user-reply",default="")
    new.add_argument("--backend",choices=("agent","api"),default="agent",help="默认由调用 Skill 的 Agent 完成模型任务")
    backend=sub.add_parser("backend");backend.add_argument("id");backend.add_argument("backend",choices=("agent","api"))
    review=sub.add_parser("review");review.add_argument("id");review.add_argument("checkpoint",choices=e.approvals.GATES);review.add_argument("--choice")
    approve=sub.add_parser("approve");approve.add_argument("id");approve.add_argument("checkpoint",choices=e.approvals.GATES)
    approve.add_argument("--review-code",required=True);approve.add_argument("--user-reply",required=True);approve.add_argument("--choice")
    show=sub.add_parser("show");show.add_argument("id")
    imp=sub.add_parser("import");imp.add_argument("id");imp.add_argument("file",type=Path);imp.add_argument("--policy",default="exact")
    run=sub.add_parser("step");run.add_argument("id");run.add_argument("action");run.add_argument("--json",type=Path);run.add_argument("--agent-reply",type=Path)
    args=cli.parse_args()
    if args.use_private_gateway or args.confirm_private_gateway or args.gateway_profile is not None:
        if not (args.use_private_gateway and args.confirm_private_gateway):
            raise ValueError("私有网关需要同时选择 --use-private-gateway 并使用 --confirm-private-gateway 明确确认")
        if args.cmd!="step":
            raise ValueError("这些私有网关参数只用于 step；工作台请在模型设置中确认启用")
    if args.cmd=="serve":
        import uvicorn
        port=args.port
        with socket.socket() as sock:
            try:sock.bind(("127.0.0.1",port))
            except OSError:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
        url=f"http://127.0.0.1:{port}";print(url,flush=True)
        if args.open:threading.Timer(1.2,lambda:webbrowser.open(url)).start()
        uvicorn.run("app:app",host="127.0.0.1",port=port);return
    if args.cmd=="demo":
        s=e.create("岸线观测 · 离线示例","研究小组","春季复测",True)
        for op in ["outline","confirm_outline","audit","samples","select","gallery","lock","export"]:e.action(s,op,{"choice":"A"})
        print(e.root(s)/"output");return
    if args.cmd=="new":s=e.create(args.title,args.audience,args.brief,style_preset=args.style,aspect_ratio=args.aspect_ratio,auto_user_reply=args.auto_user_reply,backend=args.backend)
    else:
        s=e.get(args.id)
        if args.cmd=="backend":
            e.action(s,"set_backend",{"backend":args.backend})
        if args.cmd=="review":
            print(json.dumps(e.approvals.review(s,args.checkpoint,args.choice),ensure_ascii=False,indent=2));return
        if args.cmd=="approve":
            e.action(s,"approve",dict(checkpoint=args.checkpoint,code=args.review_code,user_reply=args.user_reply,choice=args.choice))
        if args.cmd=="import":e.ingest(s,args.file.name,args.file.read_bytes(),args.policy)
        elif args.cmd=="step":
            local=e.agent_backend.in_agent(s)
            if args.use_private_gateway:
                if local:raise ValueError("项目正在使用 Agent 自带模型。先选择 API 后端，才可确认启用私有网关")
                gateway.enable(gateway.CONFIRMATION,args.gateway_profile)
            if args.agent_reply and not local:
                raise ValueError("此项目使用 API 后端；Agent 回复只用于 Agent 后端")
            payload=json.loads(args.json.read_text(encoding="utf-8-sig")) if args.json else {}
            reply=json.loads(args.agent_reply.read_text(encoding="utf-8-sig")) if args.agent_reply else None
            if local:
                with e.agent_backend.exchange(e.root(s),reply):
                    e.action(s,args.action,payload)
            else:e.action(s,args.action,payload)
    print(json.dumps(s,ensure_ascii=False,indent=2))


if __name__=="__main__":
    try:main()
    except e.agent_backend.Pending as waiting:
        print(json.dumps(waiting.request,ensure_ascii=False,indent=2))
    except ValueError as error:raise SystemExit(str(error)) from None
