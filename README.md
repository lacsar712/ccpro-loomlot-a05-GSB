# LoomLot-01 · 染坊缸染与色牢度抽检

靛蓝染坊台：按 **染坊 → 染缸 → 染程 → 色牢度** 工序推进，聚焦缸染调度与抽检，不是库存出入库系统。

## 技术栈

| 层 | 技术 |
| --- | --- |
| Backend | FastAPI + SQLAlchemy 2 + Pydantic v2 + Postgres + JWT |
| Frontend | Svelte 4 + Vite + svelte-spa-router |
| 部署 | docker-compose（db + backend + frontend/nginx） |

## 端口

| 服务 | 端口 |
| --- | --- |
| 前端 | **3600** |
| 后端 API | **8600** |
| PostgreSQL | **5439** |

数据库账号：`loomlot` / `loomlot` / 库名 `loomlot`。

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 染坊主管 |
| `dyer` | `123456` | 染程操作员 |

容器启动时 entrypoint 自动建表并 seed。

## 快速启动

```bash
cd D:\work\document\bytecode\claudeCodePro\LoomLot\LoomLot-01
docker compose up -d --build
```

浏览器：http://localhost:3600  
API：http://localhost:8600/api/health

停止：

```bash
docker compose down
```

## 业务实体

1. **DyeHouse** — `name`, `waterNote`, `notes`
2. **Vat** — `dyeHouseId`, `vatCode`, `fiberType`, `capacityL`, `status` ∈ `ready|dyeing|drain`
3. **DyeLot** — `vatId`, `recipeName`, `fabricKg`, `startedAt`, `operatorName`
4. **FastnessCheck** — `dyeLotId`, `checkedAt`, `washFastness`(1–5), `rubFastness`(>0), `tempC`, `notes`
5. **CombineBatch**（拼缸合染）— `dyeHouseId`, `batchCode`, `fabricLimitKg`, `status` ∈ `grouping|locked`
6. **CombineBatchVat**（合批成员行）— `batchId`, `vatId`

### 规则

- 仅当染缸状态为 `ready` 或 `dyeing` 时可新建染程，否则 409
- 新建染程后，染缸状态自动设为 `dyeing`
- 可选接口：`POST /api/vats/{id}/drain` 将染缸置为 `drain`

### 拼缸合染（布重上限规则）

- 合批字段：所属染坊、合批号、布重上限（千克）、状态（`grouping` 组批中 / `locked` 已锁定）。**同坊合批号唯一**。
- 成员行为「合批编号 + 染缸编号」。成员缸必须**属同一染坊且状态为就绪（ready）**；一口缸同时只能挂在**一个**合批上（无论组批中还是已锁定），重复占用返回 409。
- 组批中允许随时加减成员（整表替换）；**已锁定后禁止改成员、改合批字段或删除**，非法改动一律 409。
- **锁定校验（不满足任一即 409，杜绝无校验的空成员表锁定）：**
  1. 成员至少 **两口缸**；
  2. 各缸**最新染程**（按 `startedAt` 取最近，无染程按 0）布重之和 **≤ 布重上限**。
- 锁定后成员缸冻结，禁止单独改挂到其他合批。
- 种子数据含一批两口就绪缸（`HB-DEMO-01`，合计 55kg / 上限 120kg），可直接锁定演示。

## 主要 API

- `POST /api/auth/login`（OAuth2 表单）
- `GET /api/auth/me`
- `GET/POST/PUT/DELETE /api/dye-houses`
- `GET/POST/PUT/DELETE /api/vats` · `POST /api/vats/{id}/drain`
- `GET/POST/PUT/DELETE /api/dye-lots`
- `GET/POST/PUT/DELETE /api/fastness-checks`
- `GET/POST/PUT/DELETE /api/combine-batches` · `PUT /api/combine-batches/{id}/members`（加减成员）· `POST /api/combine-batches/{id}/lock`（锁定）
- `GET /api/dashboard/stats`（含 `combineGroupingCount` 组批中批次数）

除登录外需 `Authorization: Bearer <token>`。字段对外为 camelCase。

## 目录

```
LoomLot-01/
├── docker-compose.yml
├── backend/          # FastAPI
├── frontend/         # Svelte 4 + Vite + nginx
└── README.md
```

## 本地开发

### 数据库

```bash
docker compose up -d db
```

### 后端

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
$env:DATABASE_URL="postgresql+psycopg2://loomlot:loomlot@127.0.0.1:5439/loomlot"
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)"
python -c "from app.seed import seed; seed()"
uvicorn app.main:app --reload --port 8600
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

开发态 Vite 将 `/api` 代理到 `http://127.0.0.1:8600`。
