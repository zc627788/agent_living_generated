# PRD Agent Studio 完整操作手册（小白版）

> 版本日期：2026-03-13  
> 适用系统：Windows（PowerShell）  
> 字符集规范：UTF-8（本项目前后端输入输出统一按 UTF-8 处理）

---

## 1. 这份文档是干什么的

这是一份“从零开始可直接照做”的操作手册，目标是让第一次接触项目的人也能独立完成：

1. 启动前后端服务。
2. 管理知识库文档（上传、编辑、版本恢复、重建索引）。
3. 在提需工作台发起需求对话并生成 PRD。
4. 导出 DOCX。
5. 构建并查询 GraphRAG 图谱。
6. 定位常见问题并排查。

文档内容严格基于当前代码实现，不引用历史旧版说明。

---

## 2. 项目是什么

PRD Agent Studio 是一个“专题需求到 PRD 交付”的后台工作台，核心由三块组成：

1. 提需工作台（`/`）  
通过会话输入需求，系统做语义路由、槽位提取、RAG 检索、风险检查，最后产出 PRD。

2. 知识库管理（`/knowledge`）  
管理知识文档、版本、重建任务、召回测试，支持 GraphRAG 构图任务创建。

3. 图谱查询（`/graph`）  
基于已构建 GraphRAG 索引做图谱问答、关系图查看、社区报告查看。

---

## 3. 技术栈（代码实装）

### 3.1 前端

- Next.js 16.1.6
- React 19.2.3
- Ant Design 6.3.2
- ahooks 3.9.6
- React Markdown + remark-gfm（用于 PRD/手册渲染）

### 3.2 后端

- FastAPI 0.116.1
- LangChain 0.3.27
- LangGraph 0.3.34
- Qdrant Client 1.15.1
- graphrag 3.0.6
- python-docx 1.2.0（DOCX 导出）
- psycopg 3.2.12（PostgreSQL）
- minio 7.2.18（对象存储）

### 3.3 模型与检索

- 大模型：Qwen（DashScope 兼容接口）
- Embedding：Qwen Embedding
- 检索：Qdrant Hybrid（向量召回 + 关键词加权 + 邻接切片补全）
- 图谱：GraphRAG CLI 构图 + 后端聚合查询

---

## 4. 目录结构你要先看懂

```text
D:\application\new2
├─ backend
│  ├─ app
│  │  ├─ api          # FastAPI 路由
│  │  ├─ core         # 配置读取（.env）
│  │  ├─ db           # 数据库访问层
│  │  ├─ models       # Pydantic 数据模型
│  │  ├─ services     # 业务服务（会话、RAG、知识库、任务、GraphRAG）
│  │  └─ storage      # 默认本地存储目录（sqlite、上传、导出、graphrag工作区）
│  └─ requirements.txt
├─ frontend
│  ├─ src
│  │  ├─ app          # 页面路由（/ /knowledge /graph /manual）
│  │  ├─ components   # 页面组件
│  │  └─ lib          # 前端 API 封装与类型
│  └─ package.json
└─ docs
   └─ PROJECT_MANUAL.md  # 当前这份手册
```

---

## 5. 启动前准备（必须）

## 5.1 安装软件

1. Python 3.10+（建议 3.11）
2. Node.js 20+（建议 LTS）
3. npm（随 Node 安装）
4. Qdrant（本地或远程）
5. MinIO（用于上传文件、导出文件、GraphRAG 产物归档）
6. GraphRAG CLI（用于构图）

### 5.2 Windows 终端 UTF-8

每次新开 PowerShell 建议先执行：

```powershell
chcp 65001
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
```

这样可以减少中文日志乱码概率。

---

## 6. `.env` 关键配置说明

项目从根目录 `.env` 读配置。你至少要保证这些值可用：

```env
# 必填：Qwen / DashScope
DASHSCOPE_API_KEY=你的key

# 必填：向量库
QDRANT_URL=http://127.0.0.1:6333

# 建议填：数据库（不填时后端会自动回退到 sqlite）
POSTGRES_URL=postgresql+psycopg://user:pass@127.0.0.1:5432/dbname

# 建议填：对象存储（上传文档、导出docx、graph归档）
MINIO_ENDPOINT=http://127.0.0.1:9000
MINIO_ACCESS_KEY=xxx
MINIO_SECRET_KEY=xxx
MINIO_BUCKET=prd-agent

# 可选：模型
QWEN_CHAT_MODEL=qwen3.5-flash
QWEN_EMBEDDING_MODEL=text-embedding-v4
GRAPHRAG_CHAT_MODEL=qwen3.5-flash
GRAPHRAG_EMBEDDING_MODEL=text-embedding-v4
```

说明：

1. 如果不配 `POSTGRES_URL`，后端默认用 `backend/app/storage/mvp.sqlite3`。
2. GraphRAG 构图要求：`DASHSCOPE_API_KEY` 可用且系统中能执行 `graphrag` 命令。

---

## 7. 后端启动（PowerShell）

```powershell
cd D:\application\new2\backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动后会做：

1. 初始化数据库表。
2. 检查/注入内置知识文档。
3. 在首次需要时初始化知识切片与向量索引。

---

## 8. 前端启动（PowerShell）

```powershell
cd D:\application\new2\frontend
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000/api/v1"
npm install
npm run dev
```

访问地址：

- 提需工作台：[http://127.0.0.1:3000](http://127.0.0.1:3000)
- 知识库管理：[http://127.0.0.1:3000/knowledge](http://127.0.0.1:3000/knowledge)
- 图谱查询：[http://127.0.0.1:3000/graph](http://127.0.0.1:3000/graph)
- 项目手册：[http://127.0.0.1:3000/manual](http://127.0.0.1:3000/manual)

---

## 9. 页面总览（先知道每页干什么）

### 9.1 左侧菜单

1. 提需工作台（Agent）
2. 知识库管理（Ops）
3. 图谱查询（Graph）
4. 项目使用说明（Doc）

### 9.2 顶部刷新按钮（按页面不同）

1. 提需页：刷新系统状态（会刷新 health + 文档列表）
2. 知识库页：刷新知识状态（执行 `/knowledge/refresh`）
3. 图谱页：刷新索引（刷新可用 GraphRAG 索引列表）

顶部标签固定显示：`UTF-8`、`SSE`、`Qwen`、`GraphRAG`。

---

## 10. 提需工作台完整操作（`/`）

该页面有 4 个 Tab：会话采集、结构化结果、PRD 预览、参考资料。

### 10.1 会话采集

你在这里输入自然语言需求，点“发送”后即触发完整流程（不需要额外“运行流程”按钮）。

流程节点（后端真实状态流）：

1. router：语义路由
2. extractor：槽位提取
3. researcher：知识检索
4. guardrails：风险检查
5. planner：决定追问还是交付
6. interviewer：生成澄清提问（信息不足时）
7. builder：生成 PRD 草稿（信息足够时）
8. reviewer：文档复核

页面右侧会显示：

1. 会话概览（标题、类型、消息数、更新时间、完成度）
2. 流程追踪（每一步在做什么）
3. 检索参数（可调）

### 10.2 检索参数含义（右侧）

1. 文档范围 `document_ids`  
为空=全库检索；选中=只在选中文档检索。

2. `candidate_multiplier`（候选放大倍数）  
先召回更多候选，再做重排；越大越耗时。

3. `limit`（最终返回条数）  
最终参考资料卡片数量上限。

4. `keyword_weight`（关键词加权）  
增强 query 词命中标题/正文时的得分。

5. `neighbor_hops`（邻接补片）  
命中切片时额外补前后切片，增强上下文连贯性。

6. `min_score`（最低分阈值）  
低于阈值的结果会被过滤。

7. `use_query_rewrite`（Query Rewrite）  
是否让 LLM 先重写问题再检索。

### 10.3 结构化结果

此页是“中间态校对层”：

1. 槽位表：系统提取出的字段和值。
2. 待补字段：还缺哪些关键字段。
3. 风险提示：哪些信息不完整或存在业务风险。
4. 使用建议：何时应该继续追问再交付。

### 10.4 PRD 预览

1. 展示 Markdown PRD。
2. 可点“导出 DOCX”下载 Word 文件。
3. 导出时后端会同时将 DOCX 上传到对象存储（MinIO）。

### 10.5 参考资料

1. 显示本轮检索命中的知识卡片（标题、来源、章节路径、分数、摘要）。
2. 缩略图来自文档元数据的 `thumbnail_url`，不是系统自动生图。
3. 点击行可打开详情抽屉。
4. 命中内容均来自知识库，不会把聊天回复自动写回知识库。

---

## 11. 知识库管理完整操作（`/knowledge`）

此页有 3 个 Tab：文档中心、任务中心、召回测试。

### 11.1 文档中心

顶部统计：

1. 知识文档总数
2. 切片总数
3. RAG Provider
4. 最近刷新时间
5. 内置文档数
6. 托管文档数

核心能力：

1. 上传文档（支持 `.md/.txt/.docx`）
2. 查看文档详情
3. 重建单文档索引
4. 编辑托管文档
5. 删除托管文档
6. 查看切片预览
7. 查看版本记录
8. 恢复历史版本

### 11.2 上传文档（重点）

上传弹窗字段：

1. 文档标题 `title`
2. 来源类型 `source_type`
3. 来源标识 `source`
4. 标签 `tags`（英文逗号分隔）
5. 外部链接 `url`（可选）
6. 缩略图链接 `thumbnail_url`（可选）
7. 文件（仅 `.md/.txt/.docx`）

上传后系统会自动：

1. 保存原始文件到对象存储。
2. 创建文档记录。
3. 创建版本快照（初始上传）。
4. 自动切片（chunk size=1000，overlap=200）。
5. 生成 embedding 并写入 Qdrant。

### 11.3 文档详情抽屉

包含 3 个页签：

1. 正文预览
2. 切片预览（含 section_path 与切片内容）
3. 版本记录（可恢复）

恢复版本后会自动重建索引。

### 11.4 任务中心

任务中心用于跑后台异步任务（线程池）：

1. 批量重建任务 `batch_reindex`
2. GraphRAG 构图任务 `graphrag_standard / graphrag_fast`

任务状态：

1. `pending`
2. `running`
3. `succeeded`
4. `failed`

点击任务可看详情：进度、开始结束时间、错误信息、产物 JSON。

### 11.5 GraphRAG 构图就在这里创建

流程：

1. 在文档中心勾选文档。
2. 切到任务中心。
3. 选择构图模式（standard/fast）。
4. 点“创建 GraphRAG 构图任务”。
5. 任务成功后去 `/graph` 页面查询。

### 11.6 召回测试

这是“检索链路调参台”，用于验证召回质量与耗时：

1. 输入测试问题。
2. 选 topic 类型（可空）。
3. 可限制文档范围。
4. 调整检索参数（limit/candidate/keyword/hops/min_score/rewrite）。
5. 执行后查看命中条数、耗时(ms)、具体命中内容。

---

## 12. 图谱查询完整操作（`/graph`）

图谱页不是独立数据源，它依赖“知识库页任务中心”创建出的 GraphRAG 索引。

### 12.1 使用前提

必须先存在至少一个成功的 GraphRAG 构图任务，否则会提示“暂无可用索引”。

### 12.2 左侧区

1. 图谱索引列表  
可选 job，对应某次构图产物（文档集合、方法、创建时间）。

2. 查询配置  
- query 文本  
- mode：`local` / `global`  
- entity_limit  
- edge_limit  
- community_limit  
- 点击“执行查询”

3. 当前索引说明  
展示构图方法、创建时间、文档数、workspace 目录等。

### 12.3 右侧结果区（4 个 Tab）

1. 查询回答  
显示 rewritten query、答案文本、产物统计。

2. 关系图  
显示节点/边可视化 + 节点表 + 边表。

3. 社区报告  
显示社区摘要与排序。

4. 索引资产  
显示 workspace_dir、graphml_path、artifact_counts。

---

## 13. 聊天输入和知识库写入的边界（非常关键）

1. 你在提需页发送的会话消息，只会写入“会话表 + 消息表”。
2. 会话生成的 PRD，不会自动写回知识文档。
3. 参考资料卡片来自当前知识库切片检索，不是临时编造。
4. 知识库内容只能通过“上传/编辑/版本恢复”变更。

---

## 14. 数据存储与产物存储

### 14.1 数据库（SQLite 或 PostgreSQL）

主要表：

1. `prd_agent_sessions`
2. `prd_agent_messages`
3. `prd_agent_knowledge_documents`
4. `prd_agent_knowledge_chunks`
5. `prd_agent_knowledge_document_versions`
6. `prd_agent_knowledge_jobs`

### 14.2 向量库（Qdrant）

1. 集合名：`QDRANT_COLLECTION`（默认 `prd_agent_chunks`）
2. 每个切片作为一个 point，payload 含 title/source/tags/section_path/content 等。

### 14.3 对象存储（MinIO）

1. 上传原文件：`knowledge/uploads/...`
2. 导出 DOCX：`exports/{session_id}/...`
3. GraphRAG 输出压缩包：`graphrag/jobs/{job_id}/output.zip`

### 14.4 本地目录（默认）

1. sqlite：`backend/app/storage/mvp.sqlite3`
2. 上传缓存：`backend/app/storage/knowledge`
3. 导出缓存：`backend/app/storage/exports`
4. graphrag 工作区：`backend/app/storage/graphrag`

---

## 15. 对外 API 总览（便于联调）

### 15.1 系统状态

- `GET /api/v1/health`

### 15.2 会话与SSE

- `POST /api/v1/sessions`
- `POST /api/v1/sessions/stream`
- `GET /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/messages`
- `POST /api/v1/sessions/{session_id}/messages/stream`
- `GET /api/v1/sessions/{session_id}/export/docx`

### 15.3 知识库

- `POST /api/v1/knowledge/refresh`
- `GET /api/v1/knowledge/documents`
- `GET /api/v1/knowledge/documents/{id}`
- `PUT /api/v1/knowledge/documents/{id}`
- `DELETE /api/v1/knowledge/documents/{id}`
- `POST /api/v1/knowledge/documents/{id}/reindex`
- `GET /api/v1/knowledge/documents/{id}/versions`
- `POST /api/v1/knowledge/documents/{id}/versions/{version_id}/restore`
- `GET /api/v1/knowledge/chunks`
- `POST /api/v1/knowledge/upload`
- `POST /api/v1/knowledge/search-test`

### 15.4 任务与图谱

- `GET /api/v1/knowledge/jobs`
- `GET /api/v1/knowledge/jobs/{job_id}`
- `POST /api/v1/knowledge/jobs/reindex`
- `POST /api/v1/knowledge/jobs/graphrag`
- `GET /api/v1/knowledge/graph/indexes`
- `POST /api/v1/knowledge/graph/query`

---

## 16. 一条完整业务链路（推荐实操）

### 16.1 第一次跑通建议按这个顺序

1. 启动后端与前端。
2. 打开 `/knowledge` 上传 1~3 篇测试文档（最好带真实业务术语）。
3. 在“召回测试”调一次参数，确认能命中文档。
4. 在“任务中心”对选中文档执行 GraphRAG 构图。
5. 去 `/graph` 选索引执行查询，确认关系图与报告可见。
6. 去 `/` 提需页发一条完整需求。
7. 看“流程追踪”是否走完，查看“结构化结果”是否有缺失字段。
8. 若缺字段，继续补充对话再发送。
9. 在“PRD预览”导出 DOCX。

### 16.2 你应当看到的结果

1. 会话页有连续对话、状态轨迹、结构化槽位、参考资料卡片。
2. PRD tab 有完整 markdown。
3. 知识库页任务中心有成功任务记录。
4. 图谱页能查到实体关系与社区摘要。
5. 导出按钮可下载 docx。

---

## 17. 常见问题与排查

### 17.1 `requests` 依赖版本 warning 会不会影响运行

如果只是：

`RequestsDependencyWarning: urllib3/chardet/charset_normalizer doesn't match supported version`

通常不会直接导致服务不可用，但建议统一依赖版本，避免边缘行为。  
如果 API 已正常返回，可以先继续开发，再做依赖收敛。

### 17.2 缩略图显示“???”或占位图

原因通常是：

1. `thumbnail_url` 未填写；
2. URL 无法访问；
3. 图片链接过期或跨域受限。

处理方式：在知识文档编辑里修正 `thumbnail_url`。

### 17.3 为什么图谱页没有可用索引

你还没有成功的 GraphRAG 构图任务。  
去 `/knowledge` → 任务中心创建构图任务并等待 `succeeded`。

### 17.4 召回测试为什么慢

主要耗时来源：

1. Query Rewrite（如果开启）
2. Embedding 请求
3. 候选放大倍数过高
4. 文档范围太大

可先降低 `candidate_multiplier` 和 `limit` 验证。

### 17.5 Hydration mismatch（前后端渲染不一致）

常见触发点：

1. 浏览器 localStorage 老值和服务端初值冲突；
2. 时间格式化在服务端/客户端不同步；
3. 非稳定值（随机数、当前时间）直接参与 SSR 文本。

先清理浏览器本地存储后刷新，再检查组件初始状态逻辑。

---

## 18. 当前系统边界（MVP 已知限制）

1. 不包含权限体系（登录、角色、审计）。
2. 不包含部署编排说明（容器化/CI/CD）。
3. 主要面向中文专题需求场景。
4. Graph 布局目前为前端轻量布局，不是专业图数据库可视化引擎。

---

## 19. 运维/验证常用命令

### 19.1 前端质量检查

```powershell
cd D:\application\new2\frontend
npm run lint
npm run build
```

### 19.2 后端基础检查

```powershell
cd D:\application\new2\backend
python -m compileall app
```

### 19.3 GraphRAG CLI 可用性

```powershell
graphrag --help
```

若提示找不到命令，需要安装 GraphRAG 并加入 PATH。

---

## 20. 你可以把这套系统怎么用在业务里

1. 产品经理：快速把模糊想法转成结构化 PRD 初稿。
2. 运营同学：将活动规则文档沉淀到知识库，召回验证后再投喂提需。
3. 设计同学：通过参考资料和槽位结果快速对齐视觉与内容结构。
4. 技术同学：用任务中心维护索引与构图，保障检索和图谱质量稳定。

---

## 21. 最后一句话版操作指引

先上传文档并验证召回，再发需求生成 PRD，最后导出文档；要做图谱分析就先在知识库任务中心创建 GraphRAG 构图任务，再去图谱页查询。

---

## 22. 完整使用例子（从 0 到可交付）

下面给一个可直接照做的完整案例：  
目标是做一个“春季招聘专题页”。

### 22.1 案例目标

我们要产出：

1. 一份可预览的 PRD Markdown。
2. 一份可下载的 PRD DOCX。
3. 一次可解释的 GraphRAG 图谱查询结果。

### 22.2 第一步：准备知识文档

先在本地准备 2 个 UTF-8 文档（可 `.md` 或 `.docx`）：

文档 A（招聘专题模板）建议包含：

1. 页面结构：KV、岗位列表、投递方式、FAQ。
2. 关键文案：主标题、副标题、按钮文案。
3. 数据埋点：page_view、click_apply。

文档 B（招聘活动规则）建议包含：

1. 招聘时间范围。
2. 投递资格限制。
3. 常见风险说明。

### 22.3 第二步：上传知识文档

进入 `/knowledge` → `文档中心` → `上传文档`，分别上传 A/B 两个文档。

推荐填写（示例）：

1. `title`：`春季招聘专题模板`
2. `source_type`：`内部招聘模板库`
3. `source`：`hr_topic_template_v1`
4. `tags`：`recruitment,spring,topic`
5. `thumbnail_url`：可选，不填会显示占位图

上传成功后，系统会自动：

1. 创建文档记录和版本快照。
2. 切片并写入向量库。
3. 在文档列表里看到 `chunk_count > 0`。

### 22.4 第三步：先做一次召回测试

进入 `/knowledge` → `召回测试`，输入：

```text
春季招聘专题页需要包含哪些模块？按钮文案和投递链路如何设计？
```

推荐参数：

1. `limit = 5`
2. `candidate_multiplier = 3`
3. `keyword_weight = 0.06`
4. `neighbor_hops = 1`
5. `min_score = 0.15`
6. `Query Rewrite = 开启`

你应看到：

1. 右侧命中结果出现刚上传文档的标题。
2. 有分数（如 0.4~0.8 区间）。
3. 摘要内容和原文一致（不是模型临时编造）。

### 22.5 第四步：去提需工作台发起需求

进入 `/`，在“对话窗口”输入：

```text
我们要做春季招聘专题页，面向应届前端和设计岗位，活动时间是2026年3月20日到2026年4月20日。
页面要突出团队氛围和成长路径，按钮写“立即投递”。投递方式是跳转招聘官网。
```

点击“发送”后，观察三处：

1. 聊天区：会出现用户消息 + Agent 回复。
2. 流程追踪：会依次出现 router/extractor/researcher/guardrails/planner 等状态。
3. 结构化结果：会自动填入槽位（活动名称、时间、岗位列表、投递方式等）。

如果“待补字段”还有缺失，例如岗位列表不全，再补一条：

```text
岗位包括前端开发工程师、交互设计师，城市是上海和杭州，支持校招和社招。
```

再次发送，直到“待补字段”明显减少。

### 22.6 第五步：查看 PRD 并导出 DOCX

切到 `PRD 预览` Tab：

1. 查看是否有“基本信息、页面结构图、模块说明、交互逻辑、埋点、风险提示”。
2. 点击“导出 DOCX”。

预期结果：

1. 浏览器下载一个 `.docx` 文件（例如 `春季招聘专题页.docx`）。
2. 后端会把导出文件同步写入对象存储（MinIO）。

### 22.7 第六步：构建 GraphRAG 索引

进入 `/knowledge` → `任务中心`：

1. 先在文档中心勾选“春季招聘专题模板”和“招聘活动规则”。
2. 回任务中心，`GraphRAG 构图`选择 `standard`。
3. 点击“创建 GraphRAG 构图任务”。

等待任务状态从 `pending/running` 变成 `succeeded`。

### 22.8 第七步：执行图谱查询

进入 `/graph`：

1. 在左侧“图谱索引列表”选中刚成功的索引。
2. 输入查询：

```text
这个招聘专题页的关键实体关系和主要风险是什么？
```

3. 参数示例：
   `mode=local`，`entity_limit=12`，`edge_limit=20`，`community_limit=3`
4. 点击“执行查询”。

你会看到：

1. `查询回答`：图谱摘要答复。
2. `关系图`：实体节点与边。
3. `社区报告`：聚类报告摘要。
4. `索引资产`：workspace 路径与 artifact 数量。

### 22.9 这个案例的最终交付物

这条链路跑完，你应该拿到 3 类成果：

1. 会话侧：可回溯的需求澄清记录 + 流程轨迹。
2. 文档侧：可审阅的 PRD Markdown + 可下载 DOCX。
3. 图谱侧：可解释的实体关系与社区报告，方便复盘与汇报。
