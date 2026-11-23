"""Optional real-browser acceptance test. Uses a fresh synthetic project library."""
import os
import json
import sqlite3
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]

def check_modal_layers(page,qa):
    audit=page.get_by_role("button",name="确认提示词并核查",exact=True)
    audit.wait_for()
    for width in (1348,390):
        page.set_viewport_size({"width":width,"height":800})
        page.get_by_role("button",name="返回上一步").click()
        modal=page.get_by_role("dialog",name="回退修改")
        expect(modal).to_be_visible()
        assert modal.evaluate("""el => {
            const button = document.querySelector('.reviewhead .primary');
            const r = button.getBoundingClientRect();
            const x = r.left + r.width / 2, y = r.top + r.height / 2;
            return el.matches(':modal') && y > 0 && y < innerHeight &&
              el.contains(document.elementFromPoint(x, y)) &&
              getComputedStyle(el, '::backdrop').backgroundColor !== 'rgba(0, 0, 0, 0)';
        }""")
        for _ in range(5):
            page.keyboard.press("Tab")
            assert modal.evaluate("el => el.contains(document.activeElement) || document.activeElement === document.body")
        page.screenshot(path=str(qa/f"modal-{width}.png"))
        page.keyboard.press("Escape")
        expect(modal).to_have_count(0)
        expect(page.get_by_role("button",name="返回上一步")).to_be_focused()
    page.set_viewport_size({"width":1440,"height":960})
    for button,title in (("编辑第 1 页","第 1 页"),("编辑整套逐页稿","编辑逐页策划"),("模型设置","模型设置"),("新建项目","新建演示项目")):
        page.get_by_title(button,exact=True).click()
        modal=page.get_by_role("dialog",name=title)
        expect(modal).to_be_visible()
        assert modal.evaluate("el => el.matches(':modal')")
        modal.get_by_title("关闭").click()
        expect(modal).to_have_count(0)

def run():
    with tempfile.TemporaryDirectory() as temp:
        with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
        url=f"http://127.0.0.1:{port}";env={**os.environ,"PPT_STUDIO_HOME":temp}
        proc=subprocess.Popen([sys.executable,"studio.py","serve","--port",str(port)],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:urllib.request.urlopen(url,timeout=1).close();break
                except OSError:time.sleep(.2)
            with sync_playwright() as pw:
                edge=Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
                browser=pw.chromium.launch(executable_path=str(edge) if edge.exists() else None,headless=True)
                page=browser.new_page(viewport={"width":1440,"height":960});errors=[];external=[]
                page.on("pageerror",lambda e:errors.append(str(e)))
                page.on("request",lambda req:external.append(req.url) if not req.url.startswith(url+"/") else None)
                page.goto(url)
                page.get_by_role("button",name="打开离线示例",exact=True).click()
                page.get_by_label("汇报目标",exact=True).fill("比较本轮采样")
                page.get_by_label("听众",exact=True).fill("评委")
                page.get_by_label("制作要求",exact=True).fill("四页，先给结论")
                page.get_by_label("输入内容 / 参考原文").fill("这是手动录入测试。")
                page.get_by_role("button",name="保存输入").click()
                page.get_by_title("删除资料：手动输入").wait_for()
                page.reload()
                expect(page.get_by_role("textbox",name="制作要求",exact=True)).to_have_value("四页，先给结论")
                page.once("dialog",lambda d:d.accept())
                page.get_by_title("删除资料：手动输入").click()
                page.get_by_title("删除资料：手动输入").wait_for(state="detached")
                qa=ROOT/".studio/browser-qa";qa.mkdir(parents=True,exist_ok=True)
                for label in ("生成逐页策划","编辑第 1 页","保存本页","确认叙事与逐页结构","确认提示词并核查","生成对照样张","采用此组样张","生成全稿并审阅","确认并锁版","导出交付文件"):
                    if label=="确认提示词并核查":
                        check_modal_layers(page,qa)
                        page.get_by_role("button",name="编辑公共提示词",exact=True).click()
                        shared=page.get_by_role("dialog",name="编辑公共提示词")
                        shared.get_by_label("公共画面指令").fill("主体轮廓连续，保持统一取景。")
                        shared.get_by_label("原生页面配色").select_option("1")
                        expect(shared).to_contain_text("#F7F8FB")
                        page.screenshot(path=str(qa/"shared-prompt.png"))
                        shared.get_by_role("button",name="保存公共提示词").click()
                        expect(shared).to_have_count(0)
                        nav=page.get_by_role("navigation",name="校核页码").get_by_role("button")
                        for j in (0,2):
                            nav.nth(j).click()
                            expect(page.locator(".reviewbody .prompttext")).to_contain_text("主体轮廓连续，保持统一取景。")
                            expect(page.locator(".reviewbody .prompttext")).to_contain_text("#F7F8FB")
                        nav.nth(0).click()
                        # Seed one structured finding in the isolated offline project only.
                        c=sqlite3.connect(Path(temp)/"projects.db")
                        try:
                            id,raw=c.execute("SELECT id,state FROM projects").fetchone();s=json.loads(raw)
                            before=s["directions"][0]["art"];replacement="以同一条弯曲岸线比较两次观测，不生成示意数值。"
                            s["reports"]["audit"]={"version":1,"pass":False,"issues":["P1 示意边界"],"findings":[dict(index=0,page=1,field="art",severity="blocker",problem="示意边界不清",suggestion="统一观察对象",replacement=replacement,before=before,applied=False),dict(page=1,field="boundary",severity="blocker",problem="缺少用途限定",suggestion="人工补充图示用途",replacement="",before=s["directions"][0]["boundary"],applied=False)]}
                            c.execute("UPDATE projects SET state=? WHERE id=?",(json.dumps(s,ensure_ascii=False),id));c.commit()
                        finally:c.close()
                        page.reload();page.get_by_role("button",name="逐项设计稿").click()
                        page.get_by_text("构图候选二",exact=True).wait_for()
                        page.get_by_role("button",name="固定模型指令").click()
                        page.get_by_text("审查模型 · 校核输出契约",exact=True).wait_for()
                        expect(page.locator(".reviewbody")).to_contain_text("点名原句、图里的对象、连接线或数字")
                        page.get_by_role("button",name="完整生图提示词").click()
                        expect(page.locator(".finding").first).to_contain_text("哪里有问题")
                        expect(page.locator(".finding").first).to_contain_text("怎么改")
                        page.get_by_text("对照原文与建议稿",exact=True).click()
                        page.get_by_role("button",name="应用此项修订").click()
                        expect(page.locator(".reviewbody .prompttext")).to_contain_text(replacement)
                        page.locator(".finding").filter(has_text="缺少用途限定").get_by_role("button",name="手动修改此项").click()
                        editor=page.get_by_role("dialog",name="修改第 1 页提示词")
                        expect(editor.get_by_label("修改字段")).to_have_value("boundary")
                        expect(editor).to_contain_text("人工补充图示用途")
                        boundary="仅作流程概念示意，不绘制任何观测结果。"
                        editor.get_by_label("提示词内容").fill(boundary)
                        editor.get_by_label("修改字段").select_option("art")
                        expect(editor.get_by_label("提示词内容")).to_have_value(replacement)
                        revised="用垂直俯视构图展示一条连续岸线。"
                        editor.get_by_label("提示词内容").fill(revised)
                        editor.get_by_role("button",name="保存提示词").click()
                        expect(editor).to_have_count(0)
                        expect(page.get_by_text("已修改 · 待复核",exact=True)).to_be_visible()
                        expect(page.locator(".reviewbody .prompttext")).to_contain_text(revised)
                        expect(page.locator(".reviewbody .prompttext")).to_contain_text(boundary)
                        page.reload()
                        expect(page.locator(".reviewbody .prompttext")).to_contain_text(revised)
                        label="重新校核全稿"
                    if label=="采用此组样张":
                        page.get_by_label("方案 A",exact=True).check()
                    page.get_by_role("button",name=label,exact=True).click()
                page.get_by_role("link",name="可编辑 PPTX").wait_for()
                with page.expect_download() as download:page.get_by_role("link",name="可编辑 PPTX").click()
                assert download.value.suggested_filename=="editable.pptx"
                for width in (1440,390):
                    page.set_viewport_size({"width":width,"height":900})
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    assert page.locator(".gallery img").evaluate_all("imgs => imgs.every(i => i.complete && i.naturalWidth > 0)")
                    page.screenshot(path=str(qa/f"{width}.png"),full_page=True)
                page.get_by_role("button",name="返回上一步").click()
                expect(page.get_by_role("dialog").locator("select")).to_have_value("locked")
                page.get_by_role("button",name="确认回退").click()
                page.get_by_role("button",name="导出交付文件",exact=True).wait_for()
                page.set_viewport_size({"width":1440,"height":960})
                page.get_by_title("查看：样张盲选").click()
                page.get_by_role("button",name="退回此步骤修改").click()
                page.get_by_role("button",name="确认回退").click()
                page.get_by_label("方案 A",exact=True).check()
                page.get_by_role("button",name="采用此组样张").click()
                page.get_by_role("button",name="生成全稿并审阅").wait_for()
                assert not errors,(errors,external)
                assert not external,external
                browser.close()
        finally:proc.terminate();proc.wait(10)
    print("Browser: workflow, modal stacking and keyboard focus, PPTX download, no JS errors or external requests")

if __name__=="__main__":run()
