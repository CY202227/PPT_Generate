# 中文使用说明

项目状态：0.4.0 alpha，未发布。当前可以作为其他 agent 的本地 PPT 工具使用，但尚不能宣称生成结果达到企业设计质量。

## 无密钥生成

安装 Python 3.10+，创建并激活虚拟环境，在项目目录运行：

```powershell
python -m pip install .
ppt-generate validate examples/quarterly_report.json
ppt-generate render examples/quarterly_report.json --output-root outputs
```

输出包括任务与版本编号、可编辑 PPTX、逐页 JSON 和结构检查报告。示例数据为模拟数据。安装后不依赖仓库位置，其他 agent 可以传入自己的逐页 JSON。

## 从资料生成

```powershell
python -m pip install ".[llm,mcp,documents]"
ppt-generate generate --topic "季度经营汇报" --report examples/quarterly_source.md --slides 8 --env-file .env --output-root outputs
```

报告支持 Markdown、TXT、可提取文本的 PDF 和 DOCX。扫描 PDF 需要外部 OCR。模型会收到提供的资料，应选择允许接收这些资料的服务。

配置使用 API_KEY、API_BASE_URL、MODEL_NAME。兼容 LLM_* 和 OPENAI_* 别名；LLM_* 优先。配置文件必须通过 --env-file 或 PPT_GENERATE_ENV_FILE 显式指定，避免安装后的包自动读取不明确的 .env。

## 其他 agent 接入

安装 mcp extra 后，使用虚拟环境中 ppt-generate-mcp 的绝对路径。Windows 文件位于 Scripts/ppt-generate-mcp.exe，Linux 位于 bin/ppt-generate-mcp。配置 PPT_GENERATE_OUTPUT_ROOT 指定任务保存位置。只用 render_deck 时无需模型密钥。

工具包含格式查询、资料读取、模型规划生成、结构化直接生成、任务查询、单页修改和实际预览。JSON Schema 为统一数据契约，单页修改可带 base_revision 防止覆盖另一 agent 的新修改。跨进程任务锁保护同一任务的写入。

失败结果包含 error.code 和 error.message。成功生成文件不代表通过视觉检查，质量报告会保留 visual_review=required。

## 实际预览

Windows 安装 PowerPoint 后：

```powershell
./tools/render_preview.ps1 -PptxPath '<输出的 PPTX 路径>'
```

可通过 ppt-generate preview JOB_ID --backend powerpoint --output-root outputs 直接生成绑定版本的预览和测量报告。PowerPoint 检查文字容量、普通文本框重叠与对象越界；LibreOffice 后端检查范围较窄。模型规划最多尝试三次，内容问题会带页码反馈修正，过程和 token 用量保存到 planning.json。已支持 PowerPoint 实测文字溢出的定向字号修复，最多两轮，只接受测量通过且没有已知质量阻碍的候选版本。使用 ppt-generate repair JOB_ID --base-revision REVISION --output-root outputs，或 MCP repair_ppt。修复保留原文和数据；标题区域字号不低于 24 pt，正文不低于 18 pt。重叠、越界、图表标签、审美判断与事实核验仍待完善，模板保留和金额费用统计未实现。详见 docs/quality.md。

## 开发与发行

完整检查参见 CONTRIBUTING.md。安装开发依赖后进行离线测试、代码规范检查、构建 wheel/sdist，并在没有源码目录和 API 密钥的干净环境中验证安装。

本地密钥、生成文件和第三方参考 PPT 不进入发行包。旧代码归档于 legacy/，不作为支持的接口。后续验收关卡见 docs/roadmap.md。

## 本轮新增

已支持指标卡与时间线，共七种可编辑版式。修复可处理实测文字溢出，以及有足够空白空间时的文本框重叠和对象越界；复杂拥挤版面及图表内部标签仍未覆盖。

bind-evidence / MCP bind_evidence 将图表值绑定到 source.txt 中的确切引用和字符位置，检查数值、指标、分类、单位、时期。上下文匹配不等于语义事实证明，推导与翻译仍需人工核对。

review / MCP record_review 可记录用户明确提供的事实或视觉审核结果。结果绑定当前版本，自动检查有问题时人工批准不能绕过。内容改动会清除旧审核，重新预览会清除视觉批准，重新绑定引用会清除事实批准。所有必需检查和人工审核通过后才能标记 ready。本地记录不认证审核者身份。

完整的无模型 PDF / DOCX 示例：python examples/document_pipeline.py --format pdf --preview powerpoint，或改为 --format docx。示例会创建模拟报告、提取文本、生成五页 PPT、绑定图表引用并实际预览，不会伪造人工审核。需要 documents 可选依赖；结果写入 outputs/document-example。

## 日常使用基础

生成默认采用弹性页数，指定页数为上限，材料少时可少生成；需要固定页数时使用 --slide-count-mode exact。Python plan_deck 的默认行为仍为固定页数，避免破坏已有调用。

MCP submit_ppt 立即返回任务号，get_task 查看状态和最终文件，cancel_task 可取消排队或规划阶段。默认最多十个活动任务、两个并发规划。同一输出目录只允许一个队列持有者。重启后恢复未开始的排队任务；被中断的规划不会自动重发模型请求，已导出文件可由保存的任务关联恢复。开始导出后不可取消；正常关闭服务会等待导出完成。任务源文会保存在本地，状态响应不回显源文，票据不保存密钥。

cleanup / MCP cleanup_history 默认只预览历史清理范围，使用 --apply 或 apply=true 才删除。保护当前版本及任务清单引用，默认保留近期版本和三版历史，拒绝路径链接或越出任务目录的目标。本次开发未删除你的实际历史文件。当前版本的预览、审核快照和任务票据暂不清理。

GitHub 已实际运行首版 Windows/Linux、Python 3.10/3.12 四组检查通过；不代表这些环境中的真实 Office/LibreOffice 已测，也不需要在本机安装 WSL。

## MCP 启动与依赖升级

当前依赖 FastMCP >=4.1,<5，已在 4.1.0 / MCP SDK 2.3.0 验证。旧版上限 <3 已移除，Authlib 弃用警告通过升级实际解决，没有过滤警告。推广/升级横幅关闭，正常启动与错误日志保留。

start_demo.py 会显示实际 FastMCP 版本并等待 agent 请求，生成 PPT 使用 CLI 或连接的 agent 工具。已运行的旧进程需 Ctrl+C 后重新启动才能载入新版。
