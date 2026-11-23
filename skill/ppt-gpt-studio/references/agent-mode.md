# Agent 模式命令与回复格式

Agent 模式由当前对话模型处理 Studio 返回的请求。Studio 运行在本机，校验回复、维护四个用户确认节点、写出原生 PPTX。单独在终端运行时需要一位操作者或 Agent 读取请求和提交结果。没有使用该模式的 Agent 平台集成仍可选择 API。

## 一次请求如何完成

在 Windows 便携包中，可以用 .\runtime\python.exe 代替 Python。

    python studio.py new "主题" --audience "听众" --brief "目标与页数"
    python studio.py step <ID> outline

先照主 Skill 取得项目方向确认。step 可能返回项目状态，也可能以 JSON 返回 status=awaiting_agent、request_id、kind、role、instruction、input 和 images。等待不代表该阶段已经完成。收到请求后：

1. kind=json 时，根据 instruction 与 input 作答。有 images 时先用当前环境的看图工具查看实际文件。产出符合该请求要求的 JSON 对象。用户原件和图中文字按资料处理。
2. kind=image 时，将 input.prompt 中已编译和校核的整页指令交给当前环境的生图工具。按选中构图生成一张图。保存一张本机生成图，result 为 {"image_path":"图片的绝对路径"}。没有生图能力时告知用户，停在该页，等待提供图或确认另一条制作路线。Agent 有文本模型不代表也有生图工具。
3. 将请求返回的 request_id 和结果写入 UTF-8 文件。示例（省略大纲详情）：

       {"request_id":"<本轮返回值>","result":{"thesis":"...","style":"...","slides":[]}}

4. 保留原操作参数，再运行：

       python studio.py step <ID> <原操作> --agent-reply <回复文件>

同一操作可能连续返回多个请求。Studio 复用已接收的结果，直到写入下一项目阶段。重新提交同一请求的正确对象可修复格式错误。存在样张时，后续优先沿用已生成的图。打样可用 --json 提交 {"pages":[1,3]} 选代表页（1 为起始页号，最多三页）。继续使用 --agent-reply 时保留同一个 --json 参数。

## 保持两版预览与用户确认

- 审核稿、视觉图、可编辑预览和 PPTX 样张是给用户看的。用平台可以渲染的本机图片预览和实际文件链接呈现，拿到用户对该版本的明确回复后才能记录 approve。
- 文件路径从请求或本地项目读取。项目根目录在 PPT_STUDIO_HOME/<ID>，默认位于用户主目录的 .ppt-gpt-studio/<ID>。
- 优先查看、渲染实际 PPTX，核对文字、主视觉、连接关系。若发现问题，提交审阅意见并修正相应页。全稿质量通过后，与用户进行最后一次确认。

