---
name: academic-ppt-doctor
description: 通过对话确认逐页内容、整页生图、原生可编辑样张和完整演示稿，并用本地 Studio 导出两种 PPTX。用于希望保留主视觉、同时编辑文字、数据或图解的项目。
---

使用解压目录的 studio.py 和本地项目库。Windows 便携包可用 .\runtime\python.exe studio.py；CLI 和工作台使用同一 PPT_STUDIO_HOME。需要真实模型时使用用户配置并授权的服务。选择页型和纠正重建结果时，参阅 [构图保真与可编辑交付](references/visual-to-editable.md)。

## 先选择模型来源

调用 Skill 时，默认由当前对话 Agent 完成策划、校核和看图重建，Studio 只负责流程和导出。告诉用户已有 API Key 时也可以选择 API 后端；用户没选 API 就用默认方式继续，缺少 API Key 不构成阻塞，也不据此启动私有网关。

- 默认建项使用 studio.py new。已有项目在生成逐页稿等早期阶段卡在 API Key 时，用 studio.py backend <ID> agent 切换，保留已确认的内容。
- 每次 step 返回 awaiting_agent 时，读取本轮的 instruction、input 和 images。用当前模型完成 JSON 请求，用 Agent 可用的生图工具完成 image 请求。将结果以 --agent-reply 提交。细节见 [Agent 模式命令与回复格式](references/agent-mode.md)。
- 用户选择 API 时用 new --backend api，或在打样前用 backend <ID> api。凭证用安全配置入口，避免贴进聊天或项目资料。
- 私有网关另行选择和确认。只有用户明确授权后，才在当前 API 后端 step 命令前加 --use-private-gateway --confirm-private-gateway。网关授权与「全自动执行」独立。

## 先问用户，再继续

默认逐节点交互。每到下表的节点，用 Studio 的 review 获取**当前版本**，展示用户需判断的内容，问一个具体问题，然后结束本轮或等待用户输入。**启动制作、模型点评、工具输出、用户沉默，以及上一个节点的同意，都不算当前节点的确认。** 用户给出修改意见时先改稿，再展示改过的版本。只在收到明确同意后用 approve 记录用户回复的简短原话。禁止替用户填写确认或以批量循环直接跑完。每次只记录与本节点相关的一句。

| 节点 | 给用户看什么 | 确认后执行 |
|---|---|---|
| brief | 主题、受众、页数、风格和画幅，沿用用户已明确的选择 | outline |
| outline | 逐页标题、上屏文案、来源、主视觉、制作方式及可编辑范围 | confirm_outline，再 audit |
| samples | 同页成图、可编辑预览和实际导出的样张 PPTX。方案有多组时可盲选 | select，再 gallery |
| gallery | 两版全稿预览、可下载的原生全稿检查稿，以及修订后的结果 | lock，再 export |

CLI 检查和记录方式（把 <...> 替换为实际值）：

    studio.py review <ID> <节点>
    studio.py approve <ID> <节点> --review-code <当前确认码> --user-reply "<用户明确回复原话>"

样张节点两个命令都带 --choice A（或用户实际选的组）。对话客户端可使用能取得用户真实输入的交互工具，也可以发问后结束当前回合。工作台通过对应操作让用户点击确认。只有用户明确要求「全自动执行」才在建项时用 --auto-user-reply 记录授权，全自动仍需完成内容、样张和成品质检。

## 逐页制作与交付

- 用 new 建项（--style、--aspect-ratio 可设置风格和画幅），用 import 导入材料。随后按上表逐步推进。
- 学术汇报先按 [科研汇报构图参考](references/research-composition.md) 给每页明确评审问题、判断、主证据和阅读顺序。选择适合本页论证关系的构图，案例如需迁移，只使用空间组织与视觉层级。Studio 的学术风格会把该参考传给逐页视觉策划。
- 先比较两种构图。用实际选中的版式填写阅读路径、图文占比、视觉焦点、证据与原生可编辑范围。这些字段供策划、校核和可编辑重建使用，不发给画图模型。
- Studio 将 medium（画法与质感）、layout（整页构图、层级、对齐与阅读顺序）、art（主视觉叙述）和确认稿文案编译成五段画面语言。首图应完整呈现确认文案与关系。逐项核查漏字、空标签框和额外箭头，明显问题先修本页。写法见 [生图提示词写法](references/image-prompting.md)。样张确认后，后续页自动附带样张作为风格参考图。
- 逐页选择 illustration（保留插画）、diagram（保留插画并原生重建关系，或纯关系图）、native（原生排版）。关系图用 diagram.labels 和 diagram.links 确认文字与连接方向。含插画的关系图保留独立主图，纯关系图允许裁剪区为空。
- 首图选定后，以它作为整页视觉参考。先定主图边界、对齐线和阅读顺序，再逐个放置标题、标签与说明。用 parts 拆开混在同一段里的部件名与说明，用 callouts 把标签指到插画中的对应位置。按 [构图保真与可编辑交付](references/visual-to-editable.md) 检查连接与实际渲染。
- 校核冲突先修当前页。制作方式变化需要回到逐页方案重新取得用户确认，不能靠提示词中的「无需生图」切换。可复用的已审页和生成素材保留。
- 比较整页生图与可编辑样张时，核对标题与正文的比例、主动换行和图形强调。关系图额外核对编号、节点对齐和描边、箭头颜色与线宽。关键样式丢失时，修正本页布局，重出 PPTX 样页再确认。
- 样张和锁版都使用实际 PPTX 检查。Agent 模式也必须把样张显示在对话中，生成文件后仍需等待用户确认。通过并获得用户确认后，交付 editable.pptx、从同一套已确认场景渲染的 image.pptx 和 project.zip。首图留在项目中供构图对照。工程包可能含用户原件，按用户授权分享。
