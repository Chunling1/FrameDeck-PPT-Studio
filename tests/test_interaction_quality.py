import copy
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt
import engine as e


class InteractionQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for obj,attr,value in ((e,"HOME",Path(self.temp.name)),(e.providers.gateway,"profile",lambda:{})):
            mock=patch.object(obj,attr,value)
            mock.start()
            self.addCleanup(mock.stop)

    def approve(self,s,gate,choice=None):
        r=e.approvals.review(s,gate,choice)
        e.action(s,"approve",dict(checkpoint=gate,choice=choice,code=r["review_code"],user_reply="确认这个版本。"))

    def test_interactive_requires_four_fresh_decisions(self):
        s=e.create("互动演示","组员","面向组员的教程",demo=True)
        # Keep the demo source but exercise actual interactive gates against simulated models.
        s["demo"]=False
        verified={"pass":True,"issues":[]}
        def reply(role,*args,**kwargs):
            return e.example() if role=="planner" and args[0]!=e.art_direction.DIRECTOR else (
                {k:f"由左至右讲解 {k}" for k in e.art_direction.FIELDS} if role=="planner" else
                {"checked_pages":[1,2,3,4],"findings":[]} if role=="auditor" else verified)
        def draw(_,__,path,*args):
            Image.new("RGB",(1280,720),"white").save(path)
        with patch("providers.ask",side_effect=reply) as calls,patch("engine.providers.draw",side_effect=draw),patch(
            "engine.sample_providers",return_value=["openai"]),patch("engine.reconstruct",side_effect=lambda _,item:item["scene"]):
            review=e.approvals.review(s,"brief")
            e.update_brief(s,{"brief":"改过目标的新版本"})
            with self.assertRaisesRegex(ValueError,"过期"):
                e.action(s,"approve",dict(checkpoint="brief",code=review["review_code"],user_reply="同意"))
            with self.assertRaisesRegex(ValueError,"等待用户确认"):
                e.action(s,"outline",{})
            calls.assert_not_called()
            updated=e.approvals.review(s,"brief")
            with self.assertRaisesRegex(ValueError,"尚未明确同意"):
                e.action(s,"approve",dict(checkpoint="brief",code=updated["review_code"],user_reply="不同意，先改一下"))
            self.approve(s,"brief")
            e.action(s,"outline",{})
            with self.assertRaisesRegex(ValueError,"等待用户确认"):
                e.action(s,"confirm_outline",{})
            self.approve(s,"outline")
            e.action(s,"confirm_outline",{})
            for op in ("audit","samples"):
                e.action(s,op,{})
            with self.assertRaisesRegex(ValueError,"等待用户确认"):
                e.action(s,"select",{"choice":"A"})
            self.approve(s,"samples","A")
            e.action(s,"select",{"choice":"A"})
            e.action(s,"gallery",{})
            self.assertTrue((e.root(s)/e.approvals.review(s,"gallery")["pptx"]).is_file())
            with self.assertRaisesRegex(ValueError,"等待用户确认"):
                e.action(s,"lock",{})
            failed=copy.deepcopy(s)
            failed["reports"]["visual"]["1"]["pass"]=False
            with self.assertRaisesRegex(ValueError,"未通过"):
                e.action(failed,"lock",{"force":True})
            self.approve(s,"gallery")
            e.action(s,"lock",{})
            e.action(s,"export",{})
        self.assertEqual(e.get(s["id"])["stage"],"exported")
        self.assertEqual(set(s["approvals"]),set(e.approvals.GATES))
        root=e.root(s)
        delivery=e.delivery_dir(s,s["deliveries"][-1]["id"])
        first=s["pages"][0]
        native=(root/first["native_preview"]).read_bytes()
        self.assertNotEqual(native,(root/first["preview"]).read_bytes())
        self.assertEqual(Presentation(delivery/"image.pptx").slides[0].shapes[0].image.blob,native)
        with zipfile.ZipFile(delivery/"project.zip") as bundle:
            self.assertEqual(bundle.read("pages/01.png"),native)
            self.assertEqual(bundle.read("locked-scenes.json"),bundle.read("scenes.json"))

    def test_auditor_cannot_switch_art_route(self):
        s=e.create("校核","组员","教程",True)
        e.action(s,"outline",{})
        e.action(s,"confirm_outline",{})
        art=s["directions"][0]["art"]
        s["demo"]=False
        response={"checked_pages":[1,2,3,4],"findings":[{"page":1,"field":"art","severity":"blocker",
            "problem":"换成原生排版","suggestion":"询问用户","replacement":"无需生图。改为文字。"}]}
        with patch("providers.ask",return_value=response):e.action(s,"audit",{})
        self.assertEqual(s["directions"][0]["art"],art)
        self.assertTrue(s["reports"]["audit"]["findings"][0]["changes_mode"])
        self.assertFalse(e.current_prompt_audit(s))

    def test_diagram_reconstructs_without_cropping(self):
        s=e.create("分叉图","组员","教程")
        root=e.root(s)
        art="cache/fixture.png"
        canvas=Image.new("RGB",(1280,720),"#F6F8FC")
        draw=ImageDraw.Draw(canvas)
        for x,y in [(100,300),(480,235),(480,435)]:
            draw.rounded_rectangle((x,y,x+230,y+75),radius=12,fill="#DDEAF5")
        canvas.save(root/art)
        p=dict(kind="content",layout="left",title="任务状态",conclusion="条件判断有两条分支",copy=[],claims=[],asset="")
        scene=e.render.scene(p,1,1,0,art)
        base=[n for n in scene["nodes"] if n["type"]!="image"]
        rows=[{k:n[k] for k in ("x","y","w","h")} | {"index":i,"keep":i not in (0,1,len(base)-3)}
              for i,n in enumerate(base)]
        rows[2].update(x=75,y=40,w=1100,h=80)
        rows[3].update(x=75,y=145,w=1100,h=60)
        boxes=[{"index":i,"x":x,"y":y,"w":230,"h":75}
               for i,(x,y) in enumerate([(100,300),(480,235),(480,435)])]
        item={"scene":scene,"preview":art,"full_image":True,
              "diagram":{"labels":["读取状态","已完成","未完成"],"links":[[0,1],[0,2]]}}
        with patch("providers.ask",return_value={"background":"F6F8FC","objects":rows,"crops":[],"diagram_boxes":boxes}):
            pair=e.pair_page(s,item)
        out=root/"output"
        e.render.decks([pair["native_scene"]],root,out,editable_name="diagram.pptx")
        e.render.verify_editable(out/"diagram.pptx",[pair["native_scene"]])
        ppt=Presentation(out/"diagram.pptx")
        links=[shape for shape in ppt.slides[0].shapes if shape.name=="关系连线"]
        self.assertEqual(len(links),2)
        self.assertFalse(any(n["type"]=="image" for n in pair["native_scene"]["nodes"]))
        self.assertEqual(pair["preview"],art)

    def test_split_text_and_anchored_leaders(self):
        s=e.create("部件图","组员","讲部件位置")
        root=e.root(s)
        art="cache/fixture.png"
        Image.new("RGB",(1280,720),"#F6F8FC").save(root/art)
        page=dict(kind="content",layout="wide",title="机组部件",conclusion="沿图识别",copy=["风机 持续送风。"],claims=[])
        scene=e.render.scene(page,1,1,0,art)
        nodes=[n for n in scene["nodes"] if n["type"]!="image"]
        rows=[dict(index=i,**{k:n[k] for k in ("x","y","w","h")}) for i,n in enumerate(nodes)]
        parts=[dict(text="风机",x=60,y=290,w=220,h=38,size=24,bold=True),
               dict(text="持续送风。",x=60,y=330,w=220,h=35,size=18)]
        rows[4]=dict(index=4,parts=parts)
        leader=dict(index=4,part=0,points=[[270,300],[380,300],[520,340]])
        result=dict(objects=rows,crops=[dict(x=385,y=281,w=480,h=320)],callouts=[leader])
        item=dict(scene=scene,preview=art,full_image=True)
        with patch("providers.ask",return_value=result):
            pair=e.pair_page(s,item)
        out=root/"output"
        e.render.decks([pair["native_scene"]],root,out,editable_name="parts.pptx")
        e.render.verify_editable(out/"parts.pptx",[pair["native_scene"]])
        shapes=Presentation(out/"parts.pptx").slides[0].shapes
        self.assertTrue({"风机","持续送风。"}<={shape.text for shape in shapes if shape.has_text_frame})
        self.assertEqual(sum(shape.name=="部件引线" for shape in shapes),2)
        parts[1]["text"]="未经确认的说明"
        with patch("providers.ask",return_value=result),self.assertRaisesRegex(ValueError,"须完整保留"):
            e.reconstruct(s,{**item,"revision":"mutated"})
        parts[1]["text"]="持续送风。"
        leader["points"][-1]=[100,390]
        with patch("providers.ask",return_value=result),self.assertRaisesRegex(ValueError,"插画内"):
            e.reconstruct(s,{**item,"revision":"anchor-outside"})


    def test_diagram_preserves_visual_hierarchy_in_export(self):
        project=e.create("监测流程样张","课题组","设备监测与数据预处理")
        root=e.root(project)
        art="cache/styled-reference.png"
        Image.new("RGB",(1280,720),"#F6F4EB").save(root/art)
        labels=["现场：确认测点","监测：记录工况","整理：对齐时间","归档：保留原始记录"]
        page=dict(kind="content",layout="wide",title="热泵监测数据怎么整理",
                  conclusion="从测点与工况记录出发，追溯每一次处理。",copy=[],claims=[],asset="")
        scene=e.render.scene(page,1,1,0,art)
        base=[n for n in scene["nodes"] if n["type"]!="image"]
        rows=[{k:n[k] for k in ("x","y","w","h")} | {"index":i,"keep":i not in (0,1,len(base)-3)}
              for i,n in enumerate(base)]
        rows[2].update(x=74,y=66,w=1130,h=68,size=50)
        rows[3].update(x=74,y=145,w=1130,h=54,size=29)
        boxes=[]
        for i,(label,x) in enumerate(zip(labels,[74,370,666,962])):
            title,body=label.split("：")
            boxes.append(dict(index=i,x=x,y=272,w=230,h=256,size=28,align="left",valign="middle",
                              pad_x=28,pad_y=12,lines=[title+"：",body],fill="213E35" if i==2 else "DCE3D6",
                              color="FFFFFF" if i==2 else "233C34",number=f"{i+1:02}",
                              number_color="A35833" if i==3 else "506156",corner_radius=18))
        boxes[-1].update(stroke="A35833",stroke_width=4)
        edges=[dict(index=i,color="233C34",width=5) for i in range(3)]
        item=dict(scene=scene,preview=art,full_image=True,diagram=dict(labels=labels,links=[[0,1],[1,2],[2,3]]))
        result=dict(background="F6F4EB",objects=rows,crops=[],diagram_boxes=boxes,diagram_edges=edges)
        with patch("providers.ask",return_value=result):
            paired=e.pair_page(project,item)
        native=paired["native_scene"]
        self.assertTrue((root/paired["native_preview"]).is_file())
        dest=root/"output"/"diagram-styled.pptx"
        e.render.decks([native],root,dest.parent,editable_name=dest.name)
        e.render.verify_editable(dest,[native])
        shapes=list(Presentation(dest).slides[0].shapes)
        numbered={shape.text:shape for shape in shapes if shape.has_text_frame and shape.text in ("01","02","03","04")}
        nodes=[shape for shape in shapes if shape.name.startswith("关系节点：")]
        connections=[shape for shape in shapes if shape.name=="关系连线"]
        self.assertEqual(set(numbered),{"01","02","03","04"})
        self.assertLess(numbered["04"].top+numbered["04"].height,nodes[-1].top)
        self.assertEqual(numbered["04"].text_frame.paragraphs[0].alignment,PP_ALIGN.RIGHT)
        self.assertFalse(nodes[-1].text_frame.word_wrap)
        self.assertEqual(nodes[-1].text.splitlines(),["归档：","保留原始记录"])
        self.assertTrue(all(p.alignment==PP_ALIGN.LEFT for p in nodes[-1].text_frame.paragraphs))
        self.assertEqual(str(nodes[-1].line.color.rgb),"A35833")
        self.assertEqual(nodes[-1].line.width,Pt(3))
        self.assertEqual(str(nodes[2].fill.fore_color.rgb),"213E35")
        self.assertEqual(str(connections[0].line.color.rgb),"233C34")
        self.assertEqual(connections[0].line.width,Pt(3.75))
        self.assertEqual(connections[0]._element.xpath(".//a:stCxn")[0].get("id"),str(nodes[0].shape_id))
        self.assertEqual(connections[0]._element.xpath(".//a:endCxn")[0].get("id"),str(nodes[1].shape_id))
        boxes[-1]["lines"]=["归档：","替换确认过的文案"]
        with patch("providers.ask",return_value=result),self.assertRaisesRegex(ValueError,"须保留已确认文案"):
            e.reconstruct(project,{**item,"revision":"invalid-breaks"})

    def test_visual_anchors_rich_runs_text_banner_and_divider_rules(self):
        project=e.create("定位与复盘","个人创作者","检验零依赖锚点、行内富文本、底条与分割线")
        root=e.root(project)
        art="cache/anchored-reference.png"
        canvas=Image.new("RGB",(1280,720),"#F4F4EC")
        draw=ImageDraw.Draw(canvas)
        # Simulated dark title bar, vertical divider at x=640, and bottom light-green pill bar
        draw.rectangle((70,55,900,102),fill="#18332A")
        draw.rectangle((640,185,642,580),fill="#C6C7BF")
        draw.rounded_rectangle((60,596,1140,650),radius=10,fill="#E1E9DC")
        canvas.save(root/art)

        anchors=e.visual_anchors.extract_anchors(root/art,1280,720)
        self.assertEqual(anchors["background"],"F4F4EC")
        self.assertIn("title_box",anchors)
        self.assertIn("bottom_bar",anchors)
        self.assertEqual(anchors["bottom_bar"]["fill"],"E1E9DC")
        self.assertEqual(len(anchors.get("dividers",[])),1)
        self.assertAlmostEqual(anchors["dividers"][0]["x"],640,delta=2)

        page=dict(kind="content",layout="left",title="账号定位方法",
                  conclusion="不追大而全，先锁定一个垂直问题。",
                  copy=["目标人群：明确写给谁看"],claims=[],asset="")
        scene=e.render.scene(page,1,1,0,art)
        base=[n for n in scene["nodes"] if n["type"]!="image"]
        rows=[{k:n[k] for k in ("x","y","w","h")} | {"index":i,"keep":i not in (0,1,len(base)-3)}
              for i,n in enumerate(base)]
        rows[2].update(x=70,y=52,w=1100,h=68,size=44,bold=True)
        rows[3].update(x=60,y=596,w=1080,h=54,size=24,bold=True,align="center",valign="middle",
                       fill="E1E9DC",corner_radius=10)
        rows[4].update(x=70,y=210,w=520,h=110,size=24,runs=[
            dict(text="目标人群：",bold=True,size=26,color="18332A"),
            dict(text="\n明确写给谁看",bold=False,size=22,color="18332A"),
        ])
        result=dict(
            background="F4F4EC",
            objects=rows,
            rules=[dict(x=640,y=185,w=2,h=395,color="C6C7BF")],
            crops=[dict(name="主插画",x=690,y=170,w=500,h=410)],
        )
        item=dict(scene=scene,preview=art,full_image=True)
        captured={}
        def fake_ask(role,prompt,payload,*args,**kwargs):
            captured["payload"]=payload
            return result
        with patch("providers.ask",side_effect=fake_ask):
            paired=e.pair_page(project,item)
        self.assertEqual(captured["payload"]["visual_anchors"]["bottom_bar"]["fill"],"E1E9DC")
        native=paired["native_scene"]
        self.assertTrue((root/paired["native_preview"]).is_file())
        dest=root/"output"/"rich-native.pptx"
        e.render.decks([native],root,dest.parent,editable_name=dest.name)
        e.render.verify_editable(dest,[native])
        shapes=list(Presentation(dest).slides[0].shapes)
        bullet_shape=next(s for s in shapes if s.has_text_frame and "目标人群：" in s.text)
        self.assertTrue(bullet_shape.text_frame.paragraphs[0].runs[0].font.bold)
        self.assertFalse(bullet_shape.text_frame.paragraphs[1].runs[0].font.bold)
        banner_shape=next(s for s in shapes if s.has_text_frame and "垂直问题" in s.text)
        self.assertEqual(str(banner_shape.fill.fore_color.rgb),"E1E9DC")

        bad_result=copy.deepcopy(result)
        bad_result["objects"][4]["runs"][1]["text"]="\n篡改后的正文"
        with patch("providers.ask",return_value=bad_result),self.assertRaisesRegex(ValueError,"须完整保留已确认文案"):
            e.reconstruct(project,{**item,"revision":"mutated-runs"})
