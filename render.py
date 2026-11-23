"""A locked scene is shared by the image proof and native Office writer."""
import math
import os
import uuid
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE,MSO_CONNECTOR
from pptx.enum.chart import XL_CHART_TYPE,XL_LABEL_POSITION
from pptx.enum.text import MSO_ANCHOR,MSO_AUTO_SIZE,PP_ALIGN
from pptx.chart.data import CategoryChartData
from pptx.oxml.xmlchemy import OxmlElement

W,H=1280,720
ASPECT_RATIOS={
    "16:9":("16:9 宽屏 (1280×720)",1280,720),
    "4:3":("4:3 标准 (1024×768)",1024,768),
    "16:10":("16:10 宽屏 (1280×800)",1280,800),
}
def canvas(ratio="16:9"):
    _,cw,ch=ASPECT_RATIOS.get(ratio,ASPECT_RATIOS["16:9"])
    return cw,ch
PALETTES=[("F8F7F1","163E37","BF5233","E3EBDE"),("F7F8FB","23364E","426C9C","E2E9F1")]
PALETTE_NAMES=("暖白 / 墨绿 / 朱红","冷白 / 深蓝 / 蓝色")
STYLE_PRESETS={
    "academic":("学术科研汇报","继承学术汇报视觉系统：白底或暖白底，克制专业，青蓝/墨绿为主色，绿色表示模型与适应，橙色表示事件与待验证；版面开阔，图形保持平面，保留充足留白。"),
    "business":("商业与产品路演","干净现代商务视觉，强视觉焦点与清晰层级，对比色突出核心卖点、用户痛点与转化路径，克制留白。"),
    "briefing":("工作总结与管理简报","高对比清晰版面，结论前置，重点数据与行动项一目了然，适合投影与快速决策阅读。"),
    "tutorial":("技术分享与方法教程","分步图解与架构关系清晰，概念对比直观，配色清爽易读，避免无意义装饰。"),
    "custom":("自定义风格","按用户在汇报目标、制作要求或公共提示词中指定的视觉风格执行。"),
}
FONTNAME=os.getenv("STUDIO_FONT_FAMILY","Microsoft YaHei")


@lru_cache(maxsize=128)
def font(sz,bold=False):
    for path in (os.getenv("STUDIO_FONT_"+("BOLD" if bold else "REGULAR"),""),
                 "C:/Windows/Fonts/"+("msyhbd.ttc" if bold else "msyh.ttc"),
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc","DejaVuSans.ttf"):
        if path:
            try: return ImageFont.truetype(path,sz)
            except OSError: pass
    raise ValueError("缺少渲染字体，请指定 STUDIO_FONT_REGULAR")


def wrap(txt,w,size,bold):
    f=font(size,bold); lines=[""]
    for c in txt:
        if c=="\n": lines.append("");continue
        if lines[-1] and f.getlength(lines[-1]+c)>w: lines.append("")
        lines[-1]+=c
    return lines


def scene(s,i,total,variant,image,refs=None,ratio="16:9"):
    cw,ch=canvas(ratio);sx,sy=cw/W,ch/H
    def rx(v):return round(v*sx)
    def ry(v):return round(v*sy)
    bg,ink,accent,pale=PALETTES[variant]
    nodes=[]
    def box(t,x,y,w,h,**kw):
        nodes.append(dict(type=t,x=rx(x),y=ry(y),w=rx(w),h=ry(h),**kw))
    def text(txt,x,y,w,h,size,color=ink,bold=False,kind="text"):
        sw,sh=rx(w),ry(h);sz=max(14,round(size*min(sx,sy)))
        while sz>=14:
            lines=wrap(txt,sw-4,sz,bold); step=int(sz*1.38)
            if len(lines)*step<=sh: break
            sz-=1
        else: raise ValueError(f"第 {i} 页文本超出版面，请精简："+txt[:25])
        box(kind,x,y,w,h,text="\n".join(lines),size=sz,step=step,color=color,bold=bold)
    text({"cover":"学习路线","chart":"数据","content":"要点","flow":"步骤","divider":"章节"}[s["kind"]],64,42,600,38,19,accent,True)
    box("rule",64,92,1152,2,color=ink)
    structured=s["kind"] in ("flow","chart")
    if structured:
        text(s["title"],64,118,1152,88,43,bold=True)
        if s["kind"]=="chart": box("chart",90,218,1092,245,data=s["chart"],color=accent,ink=ink)
        else: box("flow",66,234,1148,185,steps=s["steps"],color=ink,pale=pale)
        text("\n".join(s["copy"]),64,440,1152,112,21)
        text(s["conclusion"],64,556,1152,80,32,bold=True)
    else:
        wide=s["layout"]=="wide"
        right=(s["layout"]=="right")^(variant==1)
        tx,tw=(64,1152) if wide else ((678,528) if right else (64,538))
        ix,iy,iw,ih=(64,350,1152,278) if wide else ((64 if right else 638),124,568,490)
        text(s["title"],tx,112 if wide else 165,tw,80 if wide else 150,49 if s["kind"]=="cover" else 42,bold=True)
        text(s["conclusion"],tx,195 if wide else 333,tw,75 if wide else 108,27)
        if image:
            text("\n".join(s["copy"]),tx,269 if wide else 455,tw,78 if wide else 171,21)
            box("image",ix,iy,iw,ih,file=image)
        elif wide:
            text("\n".join(s["copy"]),64,300,1152,300,26)
        else:
            text("\n".join(s["copy"]),tx,455,tw,171,26)
    box("rule",64,645,1152,2,color=ink)
    refs=refs or {}
    ids=list(dict.fromkeys(c["source"] for c in s["claims"]))
    cite="  ·  ".join((k+" "+refs.get(k,"")).strip() for k in ids)
    text(cite if len(cite)<=62 else "来源："+"、".join(ids)+"（详见备注）",64,658,1020,38,17)
    text(str(i),1160,657,52,38,20,accent,True,"number")
    return dict(width=cw,height=ch,bg=bg,nodes=nodes,notes="\n".join(c["source"]+" "+refs.get(c["source"],"")+"："+c["quote"] for c in s["claims"]))


def demo_art(path,i,v):
    bg,line,pending,surface=("#"+c for c in PALETTES[v])
    im=Image.new("RGB",(900,660),bg);d=ImageDraw.Draw(im)
    for j in range(-30,65):
        pts=[(x,int(j*18+90*math.sin(x/168+i*.36)+34*math.sin(x/83+j*.18))) for x in range(-5,910,5)]
        d.line(pts,fill=surface,width=2)
    pts=[(x,int(289+113*math.sin(x/165+i*.36)+36*math.sin(x/73))) for x in range(-10,915,3)]
    d.line(pts,fill=bg,width=68);d.line(pts,fill=line,width=59)
    for x,y in pts[45::83]:
        d.ellipse((x-8,y-8,x+8,y+8),fill=pending,outline=bg,width=3)
    im.save(path)


def placement(n,path):
    with Image.open(path) as im: w,h=im.size
    k=min(n["w"]/w,n["h"]/h)
    a,b=max(1,round(w*k)),max(1,round(h*k))
    return round(n["x"]+(n["w"]-a)/2),round(n["y"]+(n["h"]-b)/2),a,b


def geometry(n):
    x,y,w,h=(n[k] for k in ("x","y","w","h"))
    gap=40; count=len(n["steps"]); width=(w-gap*(count-1))/count
    return [(round(x+j*(width+gap)),y+35,round(width),h-70,t) for j,t in enumerate(n["steps"])]


def graph_ports(first,second):
    def point(n,side):
        x,y,w,h=(n[k] for k in ("x","y","w","h"))
        return [(x+w/2,y),(x,y+h/2),(x+w/2,y+h),(x+w,y+h/2)][side]
    first_center=(first["x"]+first["w"]/2,first["y"]+first["h"]/2)
    second_center=(second["x"]+second["w"]/2,second["y"]+second["h"]/2)
    dx=second_center[0]-first_center[0]
    dy=second_center[1]-first_center[1]
    a,b=((3,1) if dx>=0 else (1,3)) if abs(dx)>=abs(dy) else ((2,0) if dy>=0 else (0,2))
    return a,b,point(first,a),point(second,b)


def text_area(n):
    diagram=n["type"]=="diagram_box"
    px=n.get("pad_x",8 if diagram else 0)
    py=n.get("pad_y",2 if diagram else 0)
    height=len(n["text"].split("\n"))*n["step"]
    extra=n["h"]-2*py-height
    valign=n.get("valign","middle" if diagram else "top")
    offset={"top":0,"middle":extra/2,"bottom":extra}[valign]
    return dict(x=n["x"]+px,y=n["y"]+py+offset,w=n["w"]-2*px,h=height)


def draw_text(d,n):
    area=text_area(n)
    align=n.get("align","center" if n["type"]=="diagram_box" else "left")
    offset,anchor={"left":(0,"lt"),"center":(.5,"mt"),"right":(1,"rt")}[align]
    x=area["x"]+offset*area["w"]
    for j,line in enumerate(n["text"].split("\n")):
        d.text((x,area["y"]+j*n["step"]),line,font=font(n["size"],n["bold"]),fill="#"+n["color"],anchor=anchor)


def graph_edges(sc):
    links=sc.get("diagram_links",[])
    styles=sc.get("diagram_edge_styles") or [{"color":"32659B","width":3}]*len(links)
    for (a,b),style in zip(links,styles,strict=True):
        yield a,b,style


def proof(sc,root,out):
    cw,ch=sc.get("width",W),sc.get("height",H)
    im=Image.new("RGB",(cw,ch),"#"+sc["bg"]); d=ImageDraw.Draw(im)
    boxes=[n for n in sc["nodes"] if n["type"]=="diagram_box"]
    for a,b,style in graph_edges(sc):
        _,_,start,end=graph_ports(boxes[a],boxes[b])
        ink="#"+style["color"]
        d.line((start,end),fill=ink,width=style["width"])
        angle=math.atan2(end[1]-start[1],end[0]-start[0])
        arrow=max(7,style["width"]*3.5)
        d.polygon([end,*[(end[0]-arrow*math.cos(angle+v),end[1]-arrow*math.sin(angle+v)) for v in (-.5,.5)]],fill=ink)
    for n in sc["nodes"]:
        x,y,w,h=(n[k] for k in ("x","y","w","h")); t=n["type"]; color="#"+n.get("color","000000")
        if t in ("text","number","diagram_number"):
            draw_text(d,n)
        elif t=="diagram_box":
            stroke=n.get("stroke")
            d.rounded_rectangle((x,y,x+w,y+h),radius=n.get("corner_radius",min(12,h//5)),fill="#"+n["fill"],
                                outline="#"+stroke if stroke else None,width=n.get("stroke_width",1))
            draw_text(d,n)
        elif t=="rule": d.rectangle((x,y,x+w,y+h),fill=color)
        elif t=="image":
            a,b,c,e=placement(n,root/n["file"])
            with Image.open(root/n["file"]) as pic:
                pic=pic.convert("RGBA").resize((c,e),Image.Resampling.LANCZOS);im.paste(pic,(a,b),pic)
        elif t=="flow":
            boxes=geometry(n)
            for j,(a,b,c,e,txt) in enumerate(boxes):
                if j: d.line((a-40,b+e/2,a,b+e/2),fill=color,width=3)
                d.rectangle((a,b,a+c,b+e),fill="#"+n["pale"],outline=color,width=2)
                d.text((a+c/2,b+e/2),txt,font=font(min(23,int((c-8)/max(1,len(txt)))),True),fill=color,anchor="mm")
        elif t=="chart":
            data=n["data"]; vals=data["values"];peak=max(vals) or 1;cell=w/len(vals);ink="#"+n.get("ink","243632")
            for j,(cat,val) in enumerate(zip(data["categories"],vals)):
                cx=x+(j+.5)*cell; base=y+h-39; height=(h-87)*val/peak
                d.rectangle((cx-cell*.24,base-height,cx+cell*.24,base),fill=color)
                label=f"{val:g} {data['unit']}".strip()
                d.text((cx,base-height-8),label,font=font(19),fill=ink,anchor="mb")
                d.text((cx,base+8),cat,font=font(19),fill=ink,anchor="mt")
    im.save(out)


def crop_region(src,box,dest,cw=W,ch=H):
    with Image.open(src) as im:
        im=im.convert("RGB").resize((cw,ch),Image.Resampling.LANCZOS)
        x,y,w,h=int(box["x"]),int(box["y"]),int(box["w"]),int(box["h"])
        x=max(0,min(cw-2,x));y=max(0,min(ch-2,y))
        w=max(2,min(cw-x,w));h=max(2,min(ch-y,h))
        im.crop((x,y,x+w,y+h)).save(dest,"PNG")


def write_text(frame,n,u,rgb):
    diagram=n["type"]=="diagram_box"
    frame.clear()
    frame.vertical_anchor={"top":MSO_ANCHOR.TOP,"middle":MSO_ANCHOR.MIDDLE,"bottom":MSO_ANCHOR.BOTTOM}[
        n.get("valign","middle" if diagram else "top")]
    frame.margin_left=frame.margin_right=u(n.get("pad_x",8 if diagram else 0))
    frame.margin_top=frame.margin_bottom=u(n.get("pad_y",2 if diagram else 0))
    frame.word_wrap=not n.get("keep_line_breaks",False)
    if n.get("keep_line_breaks"):
        frame.auto_size=MSO_AUTO_SIZE.NONE
    align={"left":PP_ALIGN.LEFT,"center":PP_ALIGN.CENTER,"right":PP_ALIGN.RIGHT}[
        n.get("align","center" if diagram else "left")]
    for j,line in enumerate(n["text"].split("\n")):
        p=frame.add_paragraph() if j else frame.paragraphs[0]
        p.alignment=align
        p.space_before=p.space_after=Pt(0)
        p.line_spacing=Pt(n["step"]*.75)
        r=p.add_run();r.text=line
        f=r.font;f.name=FONTNAME;f.size=Pt(n["size"]*.75);f.bold=n["bold"];f.color.rgb=rgb(n["color"])
        if n["type"]=="number":
            el=OxmlElement("a:fld");el.set("id","{"+str(uuid.uuid4())+"}");el.set("type","slidenum")
            for child in list(r._r):el.append(child)
            r._r.getparent().replace(r._r,el)


def flat_shape(shape):
    for effect in shape._element.xpath("./p:style/a:effectRef"):
        effect.set("idx","0")


def decks(scenes,root,dest,*,editable_name=None):
    def u(px):return Inches(px/96)
    def rgb(c):return RGBColor.from_string(c)
    cw,ch=(scenes[0].get("width",W),scenes[0].get("height",H)) if scenes else (W,H)
    modes=[(False,editable_name)] if editable_name else [(True,"image.pptx"),(False,"editable.pptx")]
    for raster,name in modes:
        prs=Presentation();prs.slide_width=u(cw);prs.slide_height=u(ch)
        for i,sc in enumerate(scenes,1):
            sl=prs.slides.add_slide(prs.slide_layouts[6])
            sl.notes_slide.notes_text_frame.text=sc.get("notes","")
            if raster:
                sl.shapes.add_picture(str(root/f"pages/{i:02}.png"),0,0,u(cw),u(ch)); continue
            sl.background.fill.solid();sl.background.fill.fore_color.rgb=rgb(sc["bg"])
            diagram_shapes=[]
            for n in sc["nodes"]:
                xy=[u(n[k]) for k in ("x","y","w","h")];t=n["type"]
                if t=="image":
                    sh=sl.shapes.add_picture(str(root/n["file"]),*[u(i) for i in placement(n,root/n["file"])]);sh.name=n.get("name") or "原始图片";continue
                if t=="diagram_box":
                    radius=n.get("corner_radius")
                    shape=MSO_SHAPE.RECTANGLE if radius==0 else MSO_SHAPE.ROUNDED_RECTANGLE
                    sh=sl.shapes.add_shape(shape,*xy)
                    flat_shape(sh)
                    sh.name="关系节点："+n["text"].replace("\n","")
                    if radius!=0:
                        sh.adjustments[0]=.24 if radius is None else radius/min(n["w"],n["h"])
                    sh.fill.solid();sh.fill.fore_color.rgb=rgb(n["fill"])
                    if n.get("stroke"):
                        sh.line.color.rgb=rgb(n["stroke"])
                        sh.line.width=Pt(n["stroke_width"]*.75)
                    else:
                        sh.line.fill.background()
                    write_text(sh.text_frame,n,u,rgb)
                    diagram_shapes.append((n,sh))
                    continue
                if t=="chart":
                    cd=CategoryChartData();cd.categories=n["data"]["categories"];cd.add_series(n["data"]["unit"] or "数值",n["data"]["values"])
                    obj=sl.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,*xy,cd);obj.name=n.get("name") or "数据图";ch=obj.chart
                    ch.has_legend=False;ch.has_title=False
                    deleted=OxmlElement("c:autoTitleDeleted");deleted.set("val","1");ch._chartSpace.chart.insert(0,deleted)
                    ch.value_axis.minimum_scale=0;ch.value_axis.visible=False
                    ch.value_axis.has_major_gridlines=False
                    plot=ch.plots[0];plot.has_data_labels=True;plot.data_labels.position=XL_LABEL_POSITION.OUTSIDE_END
                    unit=n["data"]["unit"].replace('"','')
                    plot.data_labels.number_format=f'0.##" {unit}"' if unit else '0.##'
                    fill=ch.series[0].format.fill;fill.solid();fill.fore_color.rgb=rgb(n["color"]);continue
                if t=="flow":
                    prev=None
                    for a,b,c,e,txt in geometry(n):
                        sh=sl.shapes.add_shape(MSO_SHAPE.RECTANGLE,u(a),u(b),u(c),u(e))
                        sh.fill.solid();sh.fill.fore_color.rgb=rgb(n["pale"]);sh.line.color.rgb=rgb(n["color"])
                        sh.text=txt;p=sh.text_frame.paragraphs[0];p.alignment=PP_ALIGN.CENTER;p.font.name=FONTNAME;p.font.size=Pt(min(17,c*.7/max(1,len(txt))));p.font.bold=True;p.font.color.rgb=rgb(n["color"])
                        if prev is not None:
                            co=sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,u(a-40),u(b+e/2),u(a),u(b+e/2))
                            co.begin_connect(prev,3);co.end_connect(sh,1);co.line.color.rgb=rgb(n["color"])
                        prev=sh
                    continue
                if t=="rule":
                    sh=sl.shapes.add_shape(MSO_SHAPE.RECTANGLE,*xy);sh.line.fill.background()
                    sh.fill.solid();sh.fill.fore_color.rgb=rgb(n["color"]);continue
                obj=sl.shapes.add_textbox(*xy)
                obj.name=n.get("name") or n["text"][:40]
                write_text(obj.text_frame,n,u,rgb)
            for a,b,style in graph_edges(sc):
                first,src=diagram_shapes[a];second,dst=diagram_shapes[b]
                p1,p2,start,end=graph_ports(first,second)
                co=sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,*(u(v) for v in (*start,*end)))
                flat_shape(co)
                co.name="关系连线"
                co.begin_connect(src,p1);co.end_connect(dst,p2)
                co.line.color.rgb=rgb(style["color"]);co.line.width=Pt(style["width"]*.75 if "diagram_edge_styles" in sc else 2)
                arrow=OxmlElement("a:tailEnd");arrow.set("type","triangle")
                co.line._get_or_add_ln().append(arrow)
        prs.save(dest/name)


def verify_editable(file,scenes):
    deck=Presentation(file)
    if len(deck.slides)!=len(scenes):
        raise ValueError("实际导出的 PPTX 与预览页数不符")
    for i,(page,scene) in enumerate(zip(deck.slides,scenes),1):
        shapes=page.shapes
        nodes=scene["nodes"]
        texts={s.text.replace("\n","") for s in shapes if s.has_text_frame}
        required={n["text"].replace("\n","") for n in nodes if n["type"] in ("text","diagram_box","diagram_number") and n["text"]}
        chart_count=sum(s.has_chart for s in shapes)
        diagram_edges=[s for s in shapes if s.name=="关系连线"]
        if (not required.issubset(texts) or chart_count!=sum(n["type"]=="chart" for n in nodes) or
            len(diagram_edges)!=len(scene.get("diagram_links",[])) or
            any(not (s._element.xpath(".//a:stCxn") and s._element.xpath(".//a:endCxn")) for s in diagram_edges)):
            raise ValueError(f"实际导出的 PPTX 第 {i} 页缺少原生文字、图表或节点连接")
