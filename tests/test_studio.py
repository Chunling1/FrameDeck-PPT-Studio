import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from pptx import Presentation
import engine as e

class StudioTests(unittest.TestCase):
    def setUp(self):
        profile=patch("gateway.profile",return_value={});profile.start();self.addCleanup(profile.stop)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        m=patch.object(e,"HOME",Path(self.tmp.name));m.start();self.addCleanup(m.stop)
        self.s=e.create("test","audience","brief",True)

    def approve(self,checkpoint,choice=None):
        review=e.approvals.review(self.s,checkpoint,choice)
        e.action(self.s,"approve",dict(checkpoint=checkpoint,choice=choice,code=review["review_code"],user_reply="确认当前版本。"))

    def run_to(self,stage):
        for op in ("outline","confirm_outline","audit","samples","select","gallery","lock","export"):
            if not self.s["demo"]:
                checkpoint={"outline":"brief","confirm_outline":"outline","select":"samples","lock":"gallery"}.get(op)
                if checkpoint:self.approve(checkpoint,"A" if checkpoint=="samples" else None)
            e.action(self.s,op,{"choice":"A"})
            if self.s["stage"]==stage:break

    def test_full(self):
        self.run_to("exported");r=e.root(self.s);a=Presentation(r/"output/editable.pptx");b=Presentation(r/"output/image.pptx")
        self.assertEqual(len(a.slides),4);self.assertTrue(all(len(sl.shapes)==1 for sl in b.slides))
        self.assertTrue(any(sh.has_chart for sh in a.slides[1].shapes));self.assertIn("a:fld",a.slides[0]._element.xml)
        self.assertIn("stCxn",a.slides[3]._element.xml)
        with zipfile.ZipFile(r/"output/project.zip") as z:
            self.assertIn("rebuild.py",z.namelist());self.assertNotIn("projects.db",z.namelist())
        self.assertEqual(e.get(self.s["id"])["stage"],"exported")
        e.action(self.s,"back",{"target":"prompts"})
        with self.assertRaises(ValueError):e.action(self.s,"export",{})

    def test_audit_stops(self):
        self.run_to("prompts");self.s["plan"]["slides"][1]["chart"]["values"][0]=900
        e.action(self.s,"audit",{});self.assertEqual(self.s["stage"],"prompts")
        finding=self.s["reports"]["audit"]["findings"][0]
        self.assertIn("900",finding["problem"])
        self.assertIn("按原文改图表",finding["suggestion"])
        with self.assertRaises(ValueError):e.action(self.s,"samples",{})

    def test_audit_runs_after_regeneration(self):
        from copy import deepcopy
        self.run_to("prompts")
        self.s.pop("directions")
        e.action(self.s,"audit",{})
        self.assertTrue(self.s["reports"]["audit"]["pass"])
        e.action(self.s,"back",{"target":"prompts"})
        plan=deepcopy(self.s["plan"]);plan["slides"][0]["title"]+=" · 修订"
        e.action(self.s,"audit",{"plan":plan})
        self.assertEqual(self.s["stage"],"audited")
        self.assertEqual(self.s["reports"]["audit"]["checked_pages"],[1,2,3,4])

    def test_return_every_stage(self):
        self.run_to("exported")
        for target in reversed(e.STAGES[:-1]):
            e.action(self.s,"back",{"target":target})
            self.assertEqual(self.s["stage"],target)
            pos=e.STAGES.index(target)
            self.assertEqual(bool(self.s["samples"]),pos>=4)
            self.assertEqual(bool(self.s["selected"]),pos>=5)
            self.assertEqual(bool(self.s.get("pages")),pos>=6)
            self.assertEqual("audit" in self.s["reports"],pos>=3)
            with self.assertRaises(ValueError):e.action(self.s,"back",{"target":"exported"})

    def test_return_during_inflight_pause(self):
        import tasks,threading
        self.run_to("prompts")
        entered,release=threading.Event(),threading.Event()
        job=tasks.Task("audit")
        @tasks.remote
        def slow():
            entered.set();release.wait(4)
        writes=[]
        def worker():
            slow();writes.append("obsolete")
        t=threading.Thread(target=job.execute,args=(worker,));t.start()
        try:
            self.assertTrue(entered.wait(3))
            job.control(True)
            job.return_to("outline",lambda:e.action(e.get(self.s["id"]),"back",{"target":"outline"}))
            self.assertEqual(job.snapshot()["status"],"returning")
        finally:release.set();t.join(5)
        self.assertFalse(t.is_alive());self.assertEqual(writes,[])
        self.assertEqual(job.snapshot()["status"],"done")
        self.assertEqual(e.get(self.s["id"])["stage"],"outline")

    def test_confirm_required(self):
        with self.assertRaises(ValueError):e.action(self.s,"gallery",{})
        with self.assertRaises(ValueError):e.validate_review({"pass":"yes","issues":[]})
        self.assertFalse(e.validate_review({"pass":True,"issues":["错引"]})["pass"])

    def test_assets(self):
        buf=io.BytesIO();Image.new("RGB",(40,80),"red").save(buf,"PNG")
        e.ingest(self.s,"photo.png",buf.getvalue(),"exact");self.run_to("outline")
        self.s["plan"]["slides"][0]["asset"]="A1"
        for op in ["confirm_outline","audit","samples","select","gallery"]:e.action(self.s,op,{"choice":"A"})
        self.assertIn("assets/A1.png",json.dumps(self.s["pages"][0]))

    def test_live_does_not_fallback(self):
        self.s["demo"]=False
        self.approve("brief")
        with patch.dict("os.environ",{"OPENAI_API_KEY":""}):
            with self.assertRaisesRegex(ValueError,"OPENAI_API_KEY"):e.action(self.s,"outline",{})
        self.assertEqual(self.s["stage"],"brief")

    def test_same_model_for_planning_and_audit(self):
        self.s["demo"]=False
        model="viru/gpt-6.2-sol"
        def reply(provider,path,payload):
            self.assertEqual((provider,path,payload["model"]),("viru","chat/completions","gpt-6.2-sol"))
            instruction=payload["messages"][0]["content"]
            if instruction==e.art_direction.AUDITOR:
                value=dict(checked_pages=[1,2,3,4],findings=[])
            elif instruction==e.art_direction.DIRECTOR:
                value={k:"画面设计 "+k for k in e.art_direction.FIELDS}
            else:value=e.example()
            return {"choices":[{"message":{"content":json.dumps(value)}}]}
        with patch.dict("os.environ",{"STUDIO_PLANNER":model,"STUDIO_AUDITOR":model}),patch("providers.post",side_effect=reply),patch("gateway.enabled",return_value=True):
            self.run_to("audited")
        self.assertEqual(self.s["stage"],"audited")
        self.assertTrue(self.s["reports"]["audit"]["pass"])
        self.assertEqual([(x["role"],x["model"]) for x in self.s["usage"]],[("planner",model)]*5+[("auditor",model)])

    def test_director(self):
        self.run_to("outline");self.s["demo"]=False
        fake={k:"画面机制："+k for k in e.art_direction.FIELDS}
        self.approve("outline")
        with patch("providers.ask",return_value=fake) as api:
            e.action(self.s,"confirm_outline",{})
            self.assertEqual(api.call_count,4)
            self.assertIn("构图候选二",e.prompts(self.s)[0])
            e.art_direction.generate(self.s,e.root(self.s))
            self.assertEqual(api.call_count,4)

    def test_structured_revision_auto_applies_and_subjective_can_confirm(self):
        self.run_to("prompts");s=self.s
        row=dict(page=1,field="art",severity="blocker",problem="暗示错误因果",suggestion="移除因果箭头",replacement="画两个平行候选机制，不画连通箭头。")
        result=dict(checked_pages=list(range(1,len(s["directions"])+1)),findings=[row])
        s["demo"]=False
        with patch("providers.ask",return_value=result):e.action(s,"audit",{})
        self.assertEqual(s["directions"][0]["art"],row["replacement"])
        self.assertTrue(s["reports"]["audit"]["pass"])
        self.assertEqual(s["stage"],"audited")
        expected=e.image_prompt(s,0,1);self.assertIn(row["replacement"],expected)
        e.action(s,"back",{"target":"prompts"})
        hard=dict(page=1,field="boundary",severity="blocker",problem="主观表达边界",suggestion="可人工微调",replacement="")
        with patch("providers.ask",return_value=dict(checked_pages=list(range(1,len(s["directions"])+1)),findings=[hard])):e.action(s,"audit",{})
        self.assertEqual(s["stage"],"prompts");self.assertFalse(s["reports"]["audit"]["pass"])
        with self.assertRaisesRegex(ValueError,"未解决"):
            e.action(s,"accept_audit",{})
        self.assertEqual(s["stage"],"prompts");self.assertFalse(e.current_prompt_audit(s))

    def test_bad_audit_contract(self):
        self.run_to("prompts");pages=list(range(1,5))
        with self.assertRaises(ValueError):e.art_direction.parse_audit(dict(checked_pages=[2],findings=[]),self.s)
        with self.assertRaises(ValueError):e.art_direction.parse_audit(dict(checked_pages=pages,findings=[dict(page=1,field="claims",severity="blocker",problem="缺来源",suggestion="补证",replacement="伪造出处")]),self.s)

    def test_single_image_provider_can_finish_samples(self):
        self.run_to("prompts")
        self.s["demo"]=False
        with patch("providers.configured",side_effect=lambda role:role!="art_google"),patch("providers.ask",return_value=dict(checked_pages=[1,2,3,4],findings=[])):
            self.assertEqual(e.preflight(self.s,"samples"),{"missing":[],"sample_count":1})
            e.action(self.s,"audit",{})
            def draw(provider,prompt,path,*_):
                self.assertEqual(provider,"openai");Image.new("RGB",(20,20)).save(path)
            with patch("providers.draw",side_effect=draw),patch.object(e,"critique",return_value={"pass":True}),patch.object(e,"reconstruct",side_effect=lambda _,item:item["scene"]):
                e.action(self.s,"samples",{})
            self.assertEqual(list(self.s["samples"]),["A"])
            sample=self.s["samples"]["A"]
            self.assertEqual(len(sample["native_previews"]),len(sample["previews"]))
            deck=Presentation(e.root(self.s)/sample["pptx"])
            self.assertEqual(len(deck.slides),len(sample["previews"]))
            self.assertTrue(any(shape.has_chart for slide in deck.slides for shape in slide.shapes))
            self.approve("samples","A")
            e.action(self.s,"select",{"choice":"A"})

    def test_single_page_repair_preserves_others_and_rejects_bad_data(self):
        from copy import deepcopy
        self.run_to("gallery")
        s=self.s;before=deepcopy(s["pages"])
        draft=deepcopy(s["plan"]["slides"][1]);draft["chart"]["values"][0]=900
        with self.assertRaisesRegex(ValueError,"900"):
            e.action(deepcopy(s),"repair_page",{"index":1,"page":draft})
        self.assertEqual(e.get(s["id"])["pages"],before)
        draft["chart"]["values"][0]=18;draft["chart"]["unit"]="次/季"
        e.action(s,"repair_page",{"index":1,"page":draft})
        after=e.get(s["id"])["pages"]
        self.assertEqual([i for i,(a,b) in enumerate(zip(before,after)) if a!=b],[1])
        self.assertTrue(e.current_prompt_audit(s));self.assertEqual(s["stage"],"gallery")

    def test_delivery_versions_survive_new_export_and_rewind(self):
        from fastapi.testclient import TestClient
        import app
        self.run_to("exported")
        s=self.s;version=e.deliveries(s)[0];old=e.delivery_dir(s,version["id"])/"editable.pptx"
        content=old.read_bytes();url=f'/files/{s["id"]}/delivery/{version["id"]}/editable.pptx'
        e.action(s,"back",{"target":"gallery"})
        with TestClient(app.app) as c:
            self.assertEqual(c.get(url).content,content)
        e.action(s,"lock",{});e.action(s,"export",{})
        self.assertEqual(len(e.deliveries(s)),2)
        self.assertEqual(old.read_bytes(),content)
        with TestClient(app.app) as c:
            self.assertEqual(c.get(url).content,content)
            self.assertEqual(c.get(f'/files/{s["id"]}/output/project.zip').status_code,200)

    def test_manual_direction_edits_are_used_for_audit_and_art(self):
        from copy import deepcopy
        self.run_to("audited")
        s=self.s;i=0
        other=deepcopy(s["directions"][1:]);plan=deepcopy(s["plan"])
        art="画一条连续岸线，只用轮廓和相对位置对比。"
        boundary="示意图，不代表历史测量。"
        e.action(s,"save_direction",{"index":i,"changes":{"art":art,"boundary":boundary}})
        s=e.get(s["id"])
        self.assertEqual(s["stage"],"prompts")
        self.assertFalse(s["reports"]["audit"]["pass"])
        self.assertTrue(s["reports"]["audit"]["stale"])
        self.assertEqual(s["directions"][1:],other)
        self.assertEqual(s["plan"],plan)
        for invalid in ({"index":True,"changes":{"art":art}},{"index":i,"changes":{"art":" "}},{"index":i,"changes":{"claims":"禁止直改"}}):
            with self.assertRaises(ValueError):e.action(s,"save_direction",invalid)
        with self.assertRaises(ValueError):e.action(s,"samples",{})
        e.art_direction.generate(s,e.root(s))
        preview=e.image_prompt(s,i)
        self.assertIn(art,preview)
        self.assertNotIn(boundary,preview)
        self.assertEqual(s["directions"][i]["boundary"],boundary)
        s["demo"]=False
        with patch("providers.ask",return_value=dict(checked_pages=[1,2,3,4],findings=[])) as audit:
            e.action(s,"audit",{})
            self.assertEqual(audit.call_args.args[2]["compiled_prompts"][i],preview)
        def draw(provider,prompt,path,*args):
            self.assertEqual(prompt,preview);Image.new("RGB",(20,20)).save(path)
        with patch("providers.draw",side_effect=draw) as model:
            e.visual(s,i,0,"openai")
            model.assert_called_once()

    def test_shared_prompt_uses_native_palette_and_requires_final_audit(self):
        from copy import deepcopy
        self.run_to("audited")
        s=self.s
        s["plan"]["style"]="旧的冲突色板：#AA22BB。"
        s["reports"]["audit"].pop("prompt_signature")
        with self.assertRaises(ValueError):e.action(s,"samples",{})
        directions=deepcopy(s["directions"])
        shared="主线只表达相邻对象之间的关系。"
        e.action(s,"save_prompt_settings",dict(shared=shared,palette=1))
        self.assertEqual(s["stage"],"prompts")
        self.assertEqual(s["directions"],directions)
        self.assertTrue(s["reports"]["audit"]["stale"])
        self.assertFalse(e.current_prompt_audit(s))
        prompts=e.compiled_prompts(s)
        self.assertEqual([bool(p) for p in prompts],[True,False,True,False])
        for prompt in filter(None,prompts):
            self.assertIn(shared,prompt)
            self.assertNotIn("#AA22BB",prompt)
            for color in e.render.PALETTES[1]:self.assertIn("#"+color,prompt)
            self.assertNotIn("#F8F7F1",prompt)
        s["demo"]=False
        with patch("providers.ask",return_value=dict(checked_pages=[1,2,3,4],findings=[])) as audit:
            e.action(s,"audit",{})
            self.assertEqual(audit.call_args.args[2]["compiled_prompts"],prompts)
        self.assertTrue(e.current_prompt_audit(s))
        def draw(provider,prompt,path,*args):
            self.assertIn(prompt,prompts);Image.new("RGB",(20,20)).save(path)
        with patch("providers.draw",side_effect=draw), patch.object(e,"critique",return_value={"pass":True}),patch("providers.configured",return_value=True):
            e.action(s,"samples",{"palette":0,"feedback":"不得混入这个未经审查的补充指令"})
        for sample in s["samples"].values():
            self.assertEqual(sample["variant"],1)
            graph=json.loads((e.root(s)/sample["previews"][0]).with_suffix(".json").read_text(encoding="utf8"))["scene"]
            self.assertEqual(graph["bg"],e.render.PALETTES[1][0])
            self.assertTrue(all(n["color"]==e.render.PALETTES[1][1] for n in graph["nodes"] if n["type"]=="rule"))
        e.action(s,"save_prompt_settings",dict(shared=shared,palette=0))
        self.assertEqual(s["stage"],"prompts")
        self.assertFalse(s["samples"])

    def test_single_page_cache(self):
        self.run_to("gallery");before=[p["preview"] for p in self.s["pages"]]
        chosen=self.s["selected"]["provider"];e.action(self.s,"back",{"target":"prompts"})
        self.s["plan"]["slides"][2]["visual"]+=" 保持视觉重心偏左"
        for op in ("audit","samples"):e.action(self.s,op,{})
        label=next(k for k,v in self.s["samples"].items() if v["provider"]==chosen)
        e.action(self.s,"select",{"choice":label});e.action(self.s,"gallery",{})
        self.assertEqual([i for i,p in enumerate(self.s["pages"]) if p["preview"]!=before[i]],[2])

    def test_blocked_critic(self):
        self.run_to("gallery");self.s["reports"]["deck"]["pass"]=False
        with self.assertRaises(ValueError):e.action(self.s,"lock",{})

    def test_api_boundary(self):
        from fastapi.testclient import TestClient
        from app import app
        with TestClient(app) as c:
            self.assertEqual(c.post("/api/projects",json={}).status_code,403)
            self.run_to("samples")
            s=c.get("/api/projects/"+self.s["id"]).json()
            self.assertIsInstance(s["samples"]["A"],list)
            self.assertEqual(c.get("/files/"+s["id"]+"/output/editable.pptx").status_code,404)

    def test_live_protocols_with_fixtures(self):
        import providers as prv
        fake={"openai":{"choices":[{"message":{"content":'{"pass":true,"issues":[]}'}}]},
              "google":{"candidates":[{"content":{"parts":[{"text":'{"pass":true,"issues":[]}'}]}}]},
              "anthropic":{"content":[{"text":'{"pass":true,"issues":[]}'}]}}
        for provider,response in fake.items():
            with patch.object(prv,"post",return_value=response),patch.object(prv,"role",return_value=(provider,"test")):
                self.assertTrue(prv.ask("auditor","JSON",{})["pass"])

    def test_repair_preflight_checks_art_provider_and_direction_survives_adjacent_edit(self):
        from copy import deepcopy
        self.run_to("gallery")
        self.s["demo"]=False
        self.s["selected"]["provider"]="openai"
        with patch("providers.configured",side_effect=lambda r:r in ("planner","auditor","critic","compiler")):
            self.assertIn("OpenAI 生图",e.preflight(self.s,"repair_page",{"index":0})["missing"])
            self.assertEqual(e.preflight(self.s,"repair_page",{"index":1})["missing"],[])
        self.s["demo"]=True
        e.action(self.s,"back",{"target":"prompts"})
        custom="手工精修第1页构图指令。"
        e.action(self.s,"save_direction",{"index":0,"changes":{"art":custom}})
        plan=deepcopy(self.s["plan"]);plan["slides"][1]["title"]+=" · 修订"
        e.action(self.s,"edit",{"plan":plan})
        self.assertEqual(self.s["stage"],"outline")
        e.action(self.s,"confirm_outline",{})
        self.assertEqual(self.s["directions"][0]["art"],custom)

    def test_decimal_chart_scales_to_full_height_and_api_model_toggles(self):
        from fastapi.testclient import TestClient
        import app,render
        sc=render.scene({"kind":"chart","title":"误差率","conclusion":"B最低","copy":["同口径"],"layout":"left","visual":"柱图","asset":"","claims":[{"source":"S1","quote":"0.05"}],"chart":{"categories":["A","B"],"values":[0.05,0.02],"unit":""},"steps":[]},1,1,1,"")
        out=Path(self.tmp.name)/"dec.png"
        render.proof(sc,Path(self.tmp.name),out)
        self.assertTrue(out.is_file())
        with TestClient(app.app,headers={"X-Studio-Token":app.token}) as c:
            with patch.dict("os.environ",{"OPENAI_API_KEY":"sk-test"},clear=False):
                r=c.post("/api/models",json={"art_enabled":{"openai":False},"clear_keys":["OPENAI_API_KEY"]}).json()
                self.assertFalse(r["keys"]["OPENAI_API_KEY"])
                self.assertFalse(r["art_enabled"]["openai"])
                self.assertFalse(e.providers.configured("art_openai"))
                c.post("/api/models",json={"art_enabled":{"openai":True}})

    def test_style_preset_and_full_image_crop_compile(self):
        self.s["style_preset"]="business"
        self.run_to("prompts")
        prompt=e.image_prompt(self.s,0)
        self.assertIn("商业与产品路演",prompt)
        self.assertIn("16:9",prompt)
        # Simulate a full-slide GPT image and Plan-A crop-and-compile reconstruction
        full_rel="cache/fake-full.png"
        Image.new("RGB",(1280,720),"#F8F7F1").save(e.root(self.s)/full_rel)
        sc=e.render.scene(self.s["plan"]["slides"][0],1,4,0,full_rel)
        item={"scene":sc,"preview":full_rel,"full_image":True}
        self.s["demo"]=False
        objects=[{**{k:n[k] for k in ("x","y","w","h")}, "index":j}
                 for j,n in enumerate(n for n in sc["nodes"] if n["type"]!="image")]
        title_idx=2
        original_x=objects[title_idx]["x"]
        objects[title_idx].update(x=110,y=127,w=460,h=135)
        reply={"crops":[{"x":680,"y":135,"w":500,"h":440,"name":"核心机制图"}],"objects":objects}
        with patch("providers.ask",return_value=reply):
            paired=e.pair_page(self.s,item)
        compiled=paired["native_scene"]
        img_nodes=[n for n in compiled["nodes"] if n["type"]=="image"]
        self.assertEqual(len(img_nodes),1)
        self.assertEqual(img_nodes[0]["x"],680)
        self.assertNotEqual(img_nodes[0]["file"],full_rel)
        self.assertTrue((e.root(self.s)/img_nodes[0]["file"]).is_file())
        self.assertTrue((e.root(self.s)/paired["native_preview"]).is_file())
        self.assertGreater(abs(compiled["nodes"][title_idx+1]["x"]-original_x),6)
        reply["crops"][0].update(x=100,y=120)
        with patch("providers.ask",return_value=reply),self.assertRaisesRegex(ValueError,"压住"):
            e.reconstruct(self.s,{**item,"revision":"overlap"})


    def test_picture_prompt_is_plain_visual_language_with_quoted_copy(self):
        self.run_to("prompts")
        s=self.s
        self.assertEqual(s["prompt_format"],4)
        s["plan"]["slides"][2]["art_mode"]="diagram"
        s["plan"]["slides"][2]["diagram"]={"labels":["读取状态","已完成","未完成"],"links":[[0,1],[0,2]]}
        cover=e.image_prompt(s,0);diagram=e.image_prompt(s,2)
        for prompt in (cover,diagram):
            for word in ("【","可编辑","原生","裁切","PowerPoint","出图自检","提示词"):
                self.assertNotIn(word,prompt)
            self.assertIn("画法与质感",prompt)
            self.assertIn("你可以自由选择",prompt)
            self.assertIn("画面中只出现上述引号内的文字",prompt)
        self.assertIn("“"+s["plan"]["slides"][0]["title"]+"”",cover)
        self.assertIn("“读取状态”指向“已完成”",diagram)
        self.assertNotIn("[[0, 1]",diagram)
        long_copy="现场先记录机组运行状态和环境温度，再核对时间与缺测记录。"
        s["plan"]["slides"][2]["copy"]=[long_copy]
        self.assertIn(f"“{long_copy}”",e.image_prompt(s,2))
        self.assertNotIn("不在里面写字",e.image_prompt(s,2))
        s["prompt_format"]=3
        self.assertNotIn(long_copy,e.image_prompt(s,2))

    def test_picture_prompt_falls_back_for_older_direction_cards(self):
        self.run_to("prompts")
        s=self.s
        for d in s["directions"]:
            d.pop("medium",None);d.pop("layout",None)
        prompt=e.image_prompt(s,0)
        self.assertIn(s["directions"][0]["sequence"],prompt)

    def test_style_reference_and_aspect_reach_image_model(self):
        self.run_to("gallery")
        s=self.s;s["aspect_ratio"]="4:3"
        s["plan"]["slides"][2]["visual"]+=" 视角更低。"
        e.art_direction.generate(s,e.root(s));s["demo"]=False
        sent={}
        def draw(provider,prompt,path,ledger,refs=(),aspect="16:9"):
            sent.update(prompt=prompt,refs=list(refs),aspect=aspect);Image.new("RGB",(30,20)).save(path)
        with patch("providers.draw",side_effect=draw):
            e.visual(s,2,0,s["selected"]["provider"],replace=True)
        self.assertTrue(sent["refs"])
        self.assertIn(e.REFERENCE_NOTE,sent["prompt"])
        self.assertTrue(sent["prompt"].startswith(e.image_prompt(s,2,0)))
        self.assertEqual(sent["aspect"],"4:3")

    def test_drawable_pages_drop_stray_no_image_prefix(self):
        card={"art":"无需生图。三联分镜以平视角度呈现同一个抽象主体。"}
        self.assertEqual(e.art_direction.drawable(card,"illustration")["art"],"三联分镜以平视角度呈现同一个抽象主体。")
        self.assertTrue(e.art_direction.no_art(e.art_direction.drawable(card,"native")["art"]))
        self.run_to("prompts")
        self.assertEqual(e.art_direction.spec(self.s,1)["page_mode"],"native")
        self.assertEqual(e.art_direction.spec(self.s,0)["page_mode"],"illustration")
