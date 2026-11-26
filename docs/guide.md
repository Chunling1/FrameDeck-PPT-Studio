# FrameDeck PPT Studio 使用指南

[返回项目首页](../README.md) · [Agent 操作指南](../skill/academic-ppt-doctor/references/agent-mode.md)

## 1. 导入资料

在「资料与目标」填写汇报目标、听众、页数和制作要求。可以粘贴内容，也可以导入 UTF-8 文本、CSV、DOCX、含文本的 PDF、PPTX 文本、XLSX 数值以及独立图片。单个文件上限 20 MB，文本资料累计上限十万字。扫描件先做 OCR，文档里的照片和论文图请单独导出后添加。

导入图片时选择用途。**原样使用**和**允许裁剪**当前都保留图片的完整画面。**风格参考**最多前三张发送给图像服务。**不采用**的图片不会参与排版。

「保存输入」将当前内容写入项目。「生成逐页策划」会一并提交当前输入和保留的资料。删除资料只移除项目中的记录或副本。已导出的文件和先前发送给模型的请求仍然存在。

## 2. 选择运行方式

| 方式 | 适用场景 | 如何开始 |
| --- | --- | --- |
| 离线示例 | 第一次试用或检查本地导出 | 点击「打开离线示例」，不需要账户或 API Key。 |
| 工作台 + API | 用自己的资料和模型制作 | 在「模型设置」填写所用服务的 API Key，再新建真实项目。 |
| 对话 Agent | 在能读写本地文件、运行终端命令的 Agent 中制作 | 读取 [academic-ppt-doctor](../skill/academic-ppt-doctor/SKILL.md)，默认由当前 Agent 接手模型任务。生图需要 Agent 提供图像工具。 |

工作台的密钥仅保留在当前进程。命令行也可使用 `OPENAI_API_KEY`、`GEMINI_API_KEY` 或 `ANTHROPIC_API_KEY`。策划、校核、视觉审核、可编辑重建和生图可分别配置模型，模型格式为 `供应商/模型ID`。支持的环境变量见 [providers.py](../providers.py)。使用云端 API 时，相关资料会发送给所选服务商，费用由该 API 账户承担。

私有网关默认关闭。工作台需要在「模型设置」选择使用本机保存的私有网关并确认，授权在进程退出后失效。CLI 需要将 `--use-private-gateway` 与 `--confirm-private-gateway` 一并放在 `step` 前，授权只对该命令生效。自选网关配置使用 `--gateway-profile <配置文件>`。初次配置可用 `python gateway.py <凭证文件> --confirm-private-gateway --install`，安装后仍需单独确认启用。

## 3. 审阅和交付

1. **逐页策划**。确认标题、结论、图表数据、原文引用和图片用途。科研风格会参考[科研构图知识库](../skill/academic-ppt-doctor/references/research-composition.md)。
2. **提示词校核**。逐页查看设计稿、完整生图提示词和校核意见。「编辑公共提示词」可调整通用生图指令和原生页面配色。修改后重新校核再打样。
3. **风格打样**。样张提供视觉稿、可编辑排版预览和可下载的 PPTX。启用两家生图服务时可以盲选。原生图表与保留原件从同一份定稿绘制，两套样张中的这些页可能相同。
4. **全稿审阅、锁版**。可单页修改和复审，再导出图片版、可编辑版和工程包。只读查看前面的步骤不会回退，选择回退修改会使后续确认失效。

图片版把已确认的原生版面逐页渲染成图。可编辑版在 PowerPoint 中保留文字、部件标注、流程节点、连接线、页码字段和原生柱状图数据。插画可整张替换。实际打开 PPTX 时，字体和图表细节受 PowerPoint 环境影响。需要编辑的页请打开样张 PPTX 实查。

网页模型任务支持刷新后查看进度，也可暂停并继续。暂停会阻止新的调用，已经发出的请求仍可能完成和计费。暂停期间需要保持工作台进程运行。

## 4. 项目文件

项目默认保存在用户目录的 `.ppt-gpt-studio`，可用 `PPT_STUDIO_HOME` 指定独立目录。工作台和 CLI 共用项目库，请避免同时写入同一个项目。

归档文件 `project.zip` 包含来源摘录、审阅记录、图像和锁版场景。解压后安装其中的 `requirements.txt`，再执行 `python rebuild.py` 可以离线重建。中文渲染默认使用微软雅黑。可用 `STUDIO_FONT_REGULAR`、`STUDIO_FONT_BOLD` 和 `STUDIO_FONT_FAMILY` 选择系统已有字体。分享工程前请检查其中的原始资料。

## 5. 开发与验证

以下操作在源码目录中运行。

- 安装 Python 依赖后运行 `python -m unittest discover -s tests`。修改前端后用 `npm ci` 和 `npm run build` 更新静态文件。
- [engine.py](../engine.py) 负责项目状态与执行，[render.py](../render.py) 负责场景渲染，[app.py](../app.py) 和 [studio.py](../studio.py) 分别是网页和 CLI 的入口。
- 本地装有 Playwright 和浏览器时，可执行 `python tests/browser_smoke.py` 复验从录入到下载的流程。安装 LibreOffice 后可用 `python scripts/native_qa.py <项目目录> <输出目录>` 生成锁版图与实际 PPTX 渲染的对照图。
- Windows x64 便携构建见[便携包构建脚本](https://github.com/Chunling1/FrameDeck-PPT-Studio/blob/main/scripts/portable.ps1)。脚本从 python.org 获取并验证运行时签名，使用 PyPI wheel 构建独立环境。

启动失败时，先记录终端最后几行错误。导出后的中文排版异常时，请确认打开文件的设备上装有相应字体。提交 Issue 时，附上版本号、出现问题的步骤和脱敏截图。

## 6. 提交更新与发布

1. 从最新的 `main` 建分支，在同一个 PR 里提交相关代码、测试和文档。公开样例只使用可公开发布的材料。
2. 运行回归测试。涉及出稿时，另外检查实际导出的 PPTX，确认文字和图解能编辑，并在 PR 中附上两版预览。
3. 测试和审阅通过后，将 PR 合入 `main`。合并后检查 GitHub 首页、样例链接和下载文件。
4. 需要更新便携包时，从已验证的 `main` 创建版本标签，构建并试运行安装包，再上传到 GitHub Releases，并写明本版改动。
