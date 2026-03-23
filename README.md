# PRD Agent Studio

面向专题页需求采集、知识库管理、RAG 检索、GraphRAG 查询和 PRD 交付的一体化工作台。

当前项目包含三块主界面：

1. 提需工作台：会话采集、结构化槽位、参考资料、PRD 预览、DOCX 导出。
2. 知识库管理：文档上传、版本恢复、单文档重建、批量重建、召回测试、GraphRAG 构图任务。
3. 图谱查询：GraphRAG 索引选择、关系图可视化、社区报告、索引资产查看。

## 技术栈

- 前端：Next.js 16、React 19、Ant Design 6、ahooks、TypeScript
- 后端：FastAPI、LangChain、LangGraph、Qdrant、GraphRAG、python-docx
- 模型：Qwen Chat、Qwen Embedding
- 存储：PostgreSQL 或 SQLite、MinIO

## 环境要求

至少准备以下依赖：

1. Python 3.10+
2. Node.js 20+
3. Qdrant
4. MinIO
5. DashScope / Qwen API Key
6. GraphRAG CLI（仅构图时需要）

项目从根目录 `.env` 读取配置，常用变量如下：

```env
DASHSCOPE_API_KEY=your_key
QDRANT_URL=http://localhost:6333
POSTGRES_URL=postgresql+psycopg://prd_agent:prd_agent@localhost:5432/prd_agent
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=xxx
MINIO_SECRET_KEY=xxx
MINIO_BUCKET=prd-agent
QWEN_CHAT_MODEL=qwen3.5-flash
QWEN_EMBEDDING_MODEL=text-embedding-v4
```

## Windows 稳定启动方式

Windows 下不建议直接长期使用：

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

原因是 `--reload` 在 Windows 上容易留下多进程或僵死 watcher，出现：

1. `/health` 超时
2. `/docs` 超时
3. 接口整体阻塞
4. 8000 端口被旧进程占着

### 推荐：使用脚本启动

项目已提供两个 PowerShell 脚本：

- [scripts/start-backend.ps1](/D:/application/new2/scripts/start-backend.ps1)
- [scripts/start-frontend.ps1](/D:/application/new2/scripts/start-frontend.ps1)

### 1. 启动后端，稳定模式

```powershell
cd D:\application\new2
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

这个脚本会做三件事：

1. 强制切到 UTF-8 输出。
2. 清理当前占用 `8000` 端口的旧进程。
3. 以单进程模式启动 FastAPI，不默认开 `--reload`。

这是最稳的开发方式，适合你现在这类长时间本地联调。

### 2. 启动后端，热更新模式

如果你确实需要热更新，再显式加 `-Reload`：

```powershell
cd D:\application\new2
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1 -Reload
```

注意：

1. `-Reload` 仅建议短时间开发使用。
2. 一旦发现接口整体卡住，先停掉再用稳定模式重启。

### 3. 启动前端

```powershell
cd D:\application\new2
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

默认会把：

```powershell
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
```

自动注入到前端开发环境。

如果你要换后端地址：

```powershell
cd D:\application\new2
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1 -ApiBaseUrl "http://127.0.0.1:8010/api/v1"
```

## 访问地址

- 工作台：<http://127.0.0.1:3000>
- 知识库：<http://127.0.0.1:3000/knowledge>
- 图谱页：<http://127.0.0.1:3000/graph>
- 手册页：<http://127.0.0.1:3000/manual>
- 后端健康检查：<http://127.0.0.1:8000/api/v1/health>

## 首次安装

### 后端

```powershell
cd D:\application\new2\backend
python -m pip install -r requirements.txt
```

### 前端

```powershell
cd D:\application\new2\frontend
npm install
```

## 常用验证命令

### 后端

```powershell
cd D:\application\new2\backend
python -m compileall app
```

### 前端

```powershell
cd D:\application\new2\frontend
npm run lint
npm run build
```

## 如果接口又卡住，先这样排查

### 1. 先测健康接口

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/v1/health -UseBasicParsing
```

### 2. 如果超时

不要直接怀疑业务代码，先怀疑旧 `uvicorn --reload` 进程残留。

最简单的恢复方式：

```powershell
cd D:\application\new2
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

脚本会自动清理 8000 端口占用后再启动。

## 文档

完整使用说明、操作手册和案例在这里：

- [docs/PROJECT_MANUAL.md](/D:/application/new2/docs/PROJECT_MANUAL.md)
