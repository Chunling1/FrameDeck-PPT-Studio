import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
from pptx import Presentation

import engine as e


class AgentModeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory=Path(tmp.name)
        home=patch.object(e,"HOME",self.directory/"projects")
        home.start()
        self.addCleanup(home.stop)

    def approval(self,id,checkpoint,choice=None):
        s=e.get(id)
        r=e.approvals.review(s,checkpoint,choice)
        e.action(s,"approve",{"checkpoint":checkpoint,"choice":choice,"code":r["review_code"],"user_reply":"确认。"})
        return r

    def test_agent_models_and_local_image_complete_a_real_project(self):
        model=self.directory/"synthetic.jpg"
        im=Image.new("RGB",(1280,720),"#F8F7F1")
        d=ImageDraw.Draw(im);d.rounded_rectangle((745,285,1130,530),radius=28,fill="#163E37")
        im.save(model)
        project=e.create("Agent 后端回归","小组","离线模型回归")
        e.ingest(project,"fixture.txt",e.example.__globals__["DEMO_SOURCE"].encode())
        id=project["id"]
        accepted=self.approval(id,"brief")
        e.action(e.get(id),"set_backend",{"backend":"agent"})
        self.assertEqual(accepted["review_code"],self.approval(id,"brief")["review_code"])
        roles=set()
        reviewed_prompts=[]
        def reply_for(request):
            role=request["role"]
            roles.add(role)
            if role=="image":
                sent=request["input"]["prompt"]
                prompt=sent.split("\n\n"+e.REFERENCE_NOTE)[0]
                self.assertEqual(e.REFERENCE_NOTE in sent,bool(request["images"]))
                self.assertIn(prompt,reviewed_prompts)
                self.assertIn("标题和导语在上方，右侧大部分是主图。",prompt)
                self.assertNotIn("右侧主图占60%",prompt)
                self.assertNotIn("左下保留原生可编辑图注位置。",prompt)
                self.assertNotIn("另一种候选构图",prompt)
                self.assertNotIn("研究现象、假设、已验证结论",prompt)
                return {"image_path":str(model)}
            info=request["input"]
            if role=="planner":
                if "schema" in info:return e.example()
                guide=info["design_input"]["research_composition"]
                self.assertIn("已核实范围",guide)
                business=e.get(id)
                business["plan"]["style_preset"]="business"
                self.assertNotIn("research_composition",e.art_direction.spec(business,0))
                direction={field:f"演示设计 {field}" for field in e.art_direction.FIELDS}
                direction.update(candidate_b="另一种候选构图",sequence="标题和导语在上，右侧主图占60%。",layout="标题和导语在上方，右侧大部分是主图。",
                                 handoff="左下保留原生可编辑图注位置。")
                return direction
            if role=="auditor":
                reviewed_prompts[:]=info["compiled_prompts"]
                self.assertIsNone(reviewed_prompts[1])
                return {"checked_pages":list(range(1,len(info["plan"]["slides"])+1)),"findings":[]}
            if role=="compiler":
                objects=[]
                for n in info["objects"]:
                    objects.append({k:n[k] for k in ("index","x","y","w","h")})
                return {"objects":objects,"crops":[{"x":670,"y":160,"w":530,"h":460,"name":"合成插画"}]}
            self.assertTrue(request["images"])
            return {"pass":True,"issues":[],"basis":"合成测试数据"}
        def step(operation,params=None):
            reply=None
            for _ in range(30):
                s=e.get(id)
                try:
                    with e.agent_backend.exchange(e.root(s),reply):
                        e.action(s,operation,params or {})
                    return s
                except e.agent_backend.Pending as wait:
                    request=wait.request
                    self.assertEqual(request["status"],"awaiting_agent")
                    self.assertEqual(e.get(id)["stage"],s["stage"])
                    reply={"request_id":request["request_id"],"result":reply_for(request)}
            self.fail("Agent 请求未能完成")
        with patch("providers.ask",side_effect=AssertionError("不得访问 API")),patch(
                "providers.draw",side_effect=AssertionError("不得访问生图 API")),patch(
                "gateway.profile",side_effect=AssertionError("不得读取私有网关配置")):
            self.assertEqual(e.preflight(e.get(id),"outline")["missing"],[])
            step("outline")
            self.approval(id,"outline")
            step("confirm_outline")
            step("audit")
            sample=step("samples",{"pages":[1,2]})
            self.assertEqual(sample["samples"]["A"]["page_indices"],[0,1])
            self.approval(id,"samples","A")
            step("select",{"choice":"A"})
            step("gallery")
            self.approval(id,"gallery")
            step("lock")
            saved=step("export")
        self.assertEqual(roles,{"planner","auditor","image","compiler","critic"})
        self.assertEqual(saved["stage"],"exported")
        file=e.root(saved)/"output"/"editable.pptx"
        deck=Presentation(file)
        self.assertEqual(len(deck.slides),4)
        self.assertTrue(any(shape.has_chart for shape in deck.slides[1].shapes))
        self.assertTrue(any(shape.shape_type==13 for shape in deck.slides[0].shapes))

