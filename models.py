from typing import Annotated, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class Checked(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    def model_dump(self,**kwargs):
        kwargs.setdefault("by_alias",True)
        return super().model_dump(**kwargs)


class Claim(Checked):
    source: str
    quote: str = Field(min_length=2, max_length=600)


class Chart(Checked):
    categories: list[str] = Field(min_length=2, max_length=6)
    values: list[float]
    unit: str = Field(max_length=16)

    @model_validator(mode="after")
    def consistent(self):
        import math
        if len(self.values) != len(self.categories) or not all(math.isfinite(x) and x >= 0 for x in self.values):
            raise ValueError("柱图需要对应的非负有限数值")
        return self


class Diagram(Checked):
    labels: list[Annotated[str, Field(min_length=1,max_length=30)]] = Field(min_length=2,max_length=12)
    links: list[tuple[int,int]] = Field(min_length=1,max_length=20)

    @model_validator(mode="after")
    def valid_links(self):
        if len(set(self.links))!=len(self.links) or any(
            a==b or not 0<=a<len(self.labels) or not 0<=b<len(self.labels) for a,b in self.links
        ):raise ValueError("关系图连线必须连接两个不同的已确认节点")
        return self


class Slide(Checked):
    kind: Literal["cover", "content", "divider", "chart", "flow"]
    title: str = Field(min_length=1, max_length=46)
    conclusion: str = Field(min_length=1, max_length=90)
    body_lines: list[Annotated[str, Field(max_length=80)]] = Field(alias="copy",max_length=4)
    layout: Literal["left", "right", "wide"]
    visual: str = Field(min_length=3, max_length=2400)
    asset: str = ""
    claims: list[Claim]
    art_mode: Literal["auto","illustration","diagram","native"] = "auto"
    diagram: Diagram | None = None
    chart: Chart | None = None
    steps: list[Annotated[str, Field(max_length=16)]] = Field(default_factory=list,max_length=5)

    @model_validator(mode="after")
    def coherent(self):
        if any(len(x)>80 for x in self.body_lines) or any(len(x)>16 for x in self.steps):
            raise ValueError("正文或流程节点过长，请压缩文案")
        if self.kind == "chart" and not self.chart or self.kind == "flow" and len(self.steps)<2:
            raise ValueError("缺少可编辑的图表数据或流程节点")
        if self.kind in ("chart","flow") and self.asset:
            raise ValueError("数据图与流程图使用原生对象，原件请放在内容页")
        if self.art_mode in ("diagram","illustration") and (self.asset or self.kind in ("chart","flow")):
            raise ValueError("原件、图表和线性流程页使用原有原生画法")
        if (self.art_mode=="diagram") != (self.diagram is not None):
            raise ValueError("关系图重建需要确认节点文字和连线")
        return self


class Plan(Checked):
    thesis: str = Field(min_length=3,max_length=500)
    style: str = Field(min_length=3,max_length=800)
    style_preset: str = "academic"
    slides: list[Slide] = Field(min_length=3,max_length=40)


DEMO_SOURCE = """演示资料，全部为虚构数据，不代表实际工程。岸线观测小组拟比较三段岸线的春季记录，并确定下一轮复测顺序。
东岸记录18次，中段记录32次，西湾记录24次。记录次数反映采样投入，不能推断生态质量。
复测分为现场记录、交叉复核、归档发布三个步骤。"""


def example():
    def page(kind,title,conclusion,body,visual,quote,**kw):
        return dict(kind=kind,title=title,conclusion=conclusion,copy=body,visual=visual,
                    layout="left",asset="",claims=[dict(source="S1",quote=quote)],chart=None,steps=[],**kw)
    slides=[
        page("cover","春季岸线观测","从三段岸线的记录，确定下一轮复测顺序。",["岸线观测小组  /  演示项目"],"航测地图构图，以河湾和等高线呈现岸线，不画文字、比例尺或图例。","岸线观测小组拟比较三段岸线的春季记录"),
        page("chart","中段记录次数最多","记录次数衡量采样投入，不能据此判断生态质量。",["东岸、中段、西湾按同一口径统计。"],"三组柱图，零起点，统一单位，不添加图标。","东岸记录18次，中段记录32次，西湾记录24次。"),
        page("divider","从记录到复测","下一阶段关注记录如何复核。",[],"近景观察同一条河湾的几何剖面，保留大片留白。","复测分为现场记录、交叉复核、归档发布三个步骤。"),
        page("flow","复测的三个步骤","现场记录经过交叉复核后再归档发布。",[],"三个横向节点，以直线相连。","复测分为现场记录、交叉复核、归档发布三个步骤。")]
    slides[1]["chart"]=dict(categories=["东岸","中段","西湾"],values=[18,32,24],unit="次")
    slides[3]["steps"]=["现场记录","交叉复核","归档发布"]
    return Plan(thesis="以采样投入说明下一轮复测的依据",style="暖白底，墨绿标题，朱红用于标记重点；自然地理图册的线条和留白。",slides=slides).model_dump()
