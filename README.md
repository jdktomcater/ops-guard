# Ops Guard — 运维安全分析 MVP

FastAPI + LangChain + LangGraph，实现操作上报、即时规则告警、异步会话分析、Web 告警查看和人工反馈。默认 Mock 模式，无需 API Key。Mock 是确定性演示，不是真实大模型推理。

## Docker 启动

```bash
cp .env.example .env
docker compose up --build -d
```

打开 http://localhost:8000 ，默认令牌 `local-demo-token`。点击「导入演示日志」，立即看到关闭审计规则告警；Worker 随后识别下载并执行的组合行为。命令仅作为字符串处理，绝不会执行。

```bash
docker compose logs -f api worker
docker compose down
# 如确需清空演示数据库：docker compose down -v
```

数据库通过命名卷持久化；数据库不映射宿主端口，Web 仅绑定 127.0.0.1。

## 本地 Python 启动

建议 Python 3.12+：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

另开终端，从同一项目目录启动 Worker（先启动 API，创建表）：

```bash
source .venv/bin/activate
python -m app.worker
```

默认使用本地 SQLite。Docker Compose 使用 PostgreSQL。不要将本地 SQLite 用于多 Worker 生产部署。

## 接入真实大模型

编辑 `.env`：

```dotenv
LLM_MODE=openai
LLM_MODEL=你的模型名称
LLM_API_KEY=你的密钥
LLM_BASE_URL=https://api.openai.com/v1
```

Docker 配置修改后运行 `docker compose up -d --force-recreate api worker`。使用 OpenAI 兼容服务时，其模型须支持 tool/function calling 结构化输出；未经真实密钥联调的服务可能不兼容。日志会发送到你配置的模型服务，应先确认允许发送的数据范围。内置脱敏只覆盖常见 key=value 和 Bearer 格式，并非完整 DLP。

## 数据上报

```bash
curl http://localhost:8000/api/v1/events/batch \
  -H 'Authorization: Bearer local-demo-token' \
  -H 'Content-Type: application/json' \
  -d '{"events":[{"source_id":"bastion-01","event_id":"evt-001","session_id":"sess-01","actor_id":"alice","asset_id":"prod-01","event_time":"2026-10-19T08:00:00Z","command":"systemctl stop auditd","exit_code":0}]}'
```

API 文档：http://localhost:8000/docs 。Swagger 调用可通过 curl 或自定义 Authorization 请求头完成；Web 输入令牌即可。上报批次上限 100 条，每条命令上限 10000 字符；事件按 source_id + event_id 去重。返回 202 表示事件和任务已持久化。

## 实现边界

- API 事务中创建事件、任务和规则告警；模型不可用不影响规则告警。
- 独立 Worker 通过数据库任务租约抢占，最多尝试 3 次；租约过期可重新领取。分析与结果持久化分离，告警按触发事件唯一去重。
- LangGraph 执行「脱敏 → 分析 → 证据校验」。LangChain 提供提示词及真实模型结构化输出；Mock 模式不调用外部服务。
- 每次只读取同数据源、同会话、同人员、同主机截至触发事件的最近 30 条接收记录；按接收顺序分析。迟到日志的事件时间排序、跨窗口长链关联尚未实现。
- 图不配置 checkpoint；进程中断后按任务重新执行整次分析，不支持节点级恢复。任务结果保存在数据库。
- 规则为演示正则，会有误报和漏报；模拟下载执行识别为启发式，未校验下载路径和执行路径一致。
- Web 使用 3 秒轮询；计数和列表只覆盖最近 200 条。反馈覆盖当前值，无历史审计。
- MVP 未实现堡垒机采集 Agent、资产/工单关联、RBAC、多租户、外部通知、自动阻断、告警聚合和迁移管理。预警通过 Web 展示。
- 默认令牌和数据库密码仅用于本地演示；令牌不写入浏览器持久化存储。对外部署前需独立鉴权、TLS、凭据管理、完整审计及数据库迁移。
- 不执行日志中的任何指令，不提供 Shell 工具。模型引用的证据必须存在于分析窗口，模型不能降低规则告警等级。

## 目录

```text
app/
  main.py       API / 上报事务 / Web
  db.py         SQLAlchemy 数据模型
  config.py     环境变量配置
  schemas.py    Pydantic 输入与模型输出
  rules.py      五类规则 / 基础脱敏
  analysis.py   LangChain + LangGraph
  worker.py     租约任务处理 / 重试
  static/       原生 HTML、CSS、JS 控制台
 tests/         完整流程与失败降级测试
Dockerfile
compose.yaml
requirements.txt        依赖范围
依赖安装成功后建议生成固定版本 lock 文件；当前未生成。
```

## 测试

```bash
pytest -q
```

测试覆盖未授权访问、输入校验、去重、即时告警、会话隔离、AI 组合分析、证据校验、反馈、脱敏及模型失败后规则告警保留。容器验证结果见 VALIDATION.md。
