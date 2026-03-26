# Phase 3：商品归组 — Phase Spec

> **文档优先级：** 本 phase-spec 及其下属 task-spec 的内容优先于 master-plan。若 master-plan 中有与本文档冲突的描述，以本文档为准。

## 目标

基于 Phase 2 产出的标准化商品行，实现商品归组核心链路：文本归一化 → 多因子打分 → 硬约束过滤 → 置信度分层 → 候选归组生成 → 用户确认/拆分/合并/拖拽调整。完成后用户可在工作台第三步完成商品归组操作，归组结果供 Phase 4 比价使用。

**不是** "一次做完所有归组优化"。分桶优化、语义模型、用户自定义品牌别名等后续版本功能不在本 Phase 范围内。

## 边界

### 本 Phase 包含

- CommodityGrouper 引擎（文本归一化 + 多因子打分 + 硬约束 + 候选归组生成）
- 品牌别名表 + 噪音词表（内置，不开放用户编辑）
- 归组相关 Pydantic 模型（CommodityGroup, GroupMember, MatchScore 等）
- 归组 API（生成候选 + 获取列表 + 确认 + 拆分 + 合并 + 标记不可比 + 成员移动）
- 归组数据库操作层（GroupRepo）
- 归组服务层（GroupingService）
- 前端 GroupingStage 组件（候选列表 + 拖拽交互 + 确认/拆分/合并/标记不可比）
- 归组操作触发失效传播（compliance dirty → comparison dirty）
- openapi.json 更新

### 本 Phase 不包含（明确排除）

- 分桶优化或提前终止等性能优化（→ 后续版本，MVP 500 行上限下暴力 O(n^2) 足够）
- 语义模型 / embedding 归组（→ 后续版本）
- 用户自定义品牌别名 / 噪音词编辑（→ 后续版本）
- 符合性审查相关功能（→ Phase 4）
- 比价计算相关功能（→ Phase 4）
- 归组操作的 AuditLog 记录（Phase 2 已建好 AuditLogService，本 Phase 归组确认/拆分/合并操作应调用，但不新增 AuditLog 基础设施）

---

## 本 Phase 引入的新模块/文件

### 后端

```
backend/
├── engines/
│   └── commodity_grouper.py        # CommodityGrouper 引擎（归一化 + 打分 + 硬约束 + 聚合）
├── models/
│   └── grouping.py                 # 归组相关 Pydantic 模型
├── db/
│   └── group_repo.py               # commodity_groups + group_members 表操作
├── services/
│   └── grouping_service.py         # 归组业务编排（协调 engine + repo + 失效传播）
├── api/
│   └── grouping.py                 # 归组 API 路由
└── tests/
    ├── test_commodity_grouper.py   # 引擎单元测试
    ├── test_group_repo.py          # 数据库操作测试
    └── test_grouping_api.py        # API 集成测试
```

### 前端

```
frontend/src/
├── components/stages/
│   ├── grouping-stage.tsx          # 归组阶段主容器
│   ├── group-candidate-list.tsx    # 候选归组列表（按置信度分层）
│   └── group-drag-zone.tsx         # dnd-kit 拖拽区域
├── types/
│   └── grouping.ts                 # 归组相关 TypeScript 类型
└── stores/
    └── grouping-store.ts           # 归组状态管理（独立 store）
```

---

## 任务列表与依赖关系

```
                ┌── 3.4 Pydantic 模型 ──────────────────┐
                │                                        │
Phase 2 ──── 3.1 文本归一化 ── 3.2 多因子打分+硬约束 ── 3.3 归组 API ── 3.8 openapi
                                                         │
                                                    ┌────┤
                                                    │    │
                                               3.5 候选列表
                                                    │
                                               ┌────┤
                                               │    │
                                          3.6 拖拽  3.7 确认/拆分/合并
```

| Task | 名称 | 负责人 | 依赖 |
|------|------|--------|------|
| 3.1 | CommodityGrouper — 文本归一化 + 品牌别名 + 噪音词 | backend-dev | Phase 2 |
| 3.2 | CommodityGrouper — 多因子打分 + 硬约束 + 候选归组生成 | backend-dev | 3.1 |
| 3.3 | 归组 API（生成 + 确认 + 拆分 + 合并） | backend-dev | 3.2, 3.4 |
| 3.4 | 归组相关 Pydantic 模型 | backend-dev | Phase 2 |
| 3.5 | 前端 GroupingStage — 候选归组列表（置信度分层） | frontend-dev | 3.3 |
| 3.6 | 前端 GroupingStage — dnd-kit 拖拽归组交互 | frontend-dev | 3.5 |
| 3.7 | 前端 GroupingStage — 确认/拆分/合并/标记不可比 | frontend-dev | 3.5 |
| 3.8 | 更新 openapi.json + reviewer 审查 | backend-dev | 3.3 |

**并行化：**
- 3.1（归一化）必须先行，3.2（打分）依赖 3.1
- 3.4（Pydantic 模型）可与 3.1 并行开发
- 3.3（API）依赖 3.2 和 3.4
- 3.5/3.6/3.7 前端任务等待 3.3 完成
- 3.6 和 3.7 可并行（都仅依赖 3.5）
- 3.8 依赖 3.3 完成

---

## 完成标准（机器可判定）

### 后端验收

```bash
cd backend

# 1. 工程门禁全部通过
ruff check .                          # exit 0，零警告
mypy . --ignore-missing-imports       # exit 0，零错误
pytest -x -q                          # exit 0，全部通过

# 2. 引擎单元测试
pytest tests/test_commodity_grouper.py -v  # 归一化 + 打分 + 硬约束 + 聚合 全部通过

# 3. API 集成测试
pytest tests/test_grouping_api.py -v       # 归组 API 全部通过

# 4. 启动验证
DEV_MODE=1 uvicorn main:app --host 127.0.0.1 --port 17396 &
sleep 2

# 假设已有项目 $PROJECT_ID 且已完成标准化

# 5. 生成归组候选
TASK=$(curl -sf -X POST http://127.0.0.1:17396/api/projects/$PROJECT_ID/grouping/generate \
  -H "Authorization: Bearer $TOKEN")
TASK_ID=$(echo $TASK | python -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
echo "✓ 归组任务已提交: $TASK_ID"

# 6. 获取归组列表
curl -sf http://127.0.0.1:17396/api/projects/$PROJECT_ID/groups \
  -H "Authorization: Bearer $TOKEN" | python -c "
import sys, json
data = json.load(sys.stdin)
assert isinstance(data, list), 'Expected list'
for g in data:
    assert g['confidence_level'] in ('high', 'medium', 'low')
    assert g['status'] in ('candidate', 'confirmed', 'split', 'not_comparable')
    assert 'members' in g
    assert 'match_reason' in g
print(f'✓ 归组列表: {len(data)} 个归组')
"

# 7. 确认归组
GROUP_ID=$(curl -sf http://127.0.0.1:17396/api/projects/$PROJECT_ID/groups \
  -H "Authorization: Bearer $TOKEN" | python -c "
import sys, json
data = json.load(sys.stdin)
if data: print(data[0]['id'])
")
if [ -n "$GROUP_ID" ]; then
  curl -sf -X PUT http://127.0.0.1:17396/api/groups/$GROUP_ID/confirm \
    -H "Authorization: Bearer $TOKEN" | python -c "
  import sys, json
  data = json.load(sys.stdin)
  assert data['status'] == 'confirmed'
  print('✓ 确认归组 OK')
  "
fi

kill %1
```

### 前端验收

```bash
cd frontend

# 1. 工程门禁全部通过
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0

# 2. 手动验证（需后端运行中）
# - 工作台第三步显示归组候选列表
# - 高置信组绿色标识，中置信组黄色标识，低置信组灰色标识
# - 可拖拽商品行在归组间移动
# - 可确认归组 → 状态变为 confirmed
# - 可拆分归组 → 原组拆为多个新组
# - 可合并归组 → 选中多个组合并为一个
# - 可标记不可比 → 状态变为 not_comparable
# - 操作后下游阶段状态变为 dirty
```

### 契约验收

```bash
# openapi.json 已更新
cd backend
python scripts/generate_openapi.py
python -c "
import json
with open('../docs/api/openapi.json') as f:
    spec = json.load(f)
paths = list(spec.get('paths', {}).keys())
assert '/api/projects/{id}/grouping/generate' in paths, 'Missing grouping generate'
assert '/api/projects/{id}/groups' in paths, 'Missing groups list'
assert '/api/groups/{id}/confirm' in paths, 'Missing confirm'
assert '/api/groups/{id}/split' in paths, 'Missing split'
assert '/api/projects/{id}/grouping/merge' in paths, 'Missing merge'
assert '/api/groups/{id}/not-comparable' in paths, 'Missing not-comparable'
assert '/api/groups/{id}/move-member' in paths, 'Missing move-member'
print(f'✓ openapi.json 归组 API: 7 个路径已定义')
"
```

---

## 关键技术决策

### 算法参数（写死在代码中，MVP 不做配置化）

| 参数 | 值 | 说明 |
|------|-----|------|
| 名称相似度权重 | 0.50 | `S_name` 权重 |
| 规格型号权重 | 0.35 | `S_spec` 权重 |
| 单位一致性权重 | 0.15 | `S_unit` 权重 |
| 高置信阈值 | >= 0.85 | 且未命中硬约束 |
| 中置信阈值 | >= 0.60 | 待确认候选 |
| 低置信阈值 | < 0.60 | 保持独立 |
| 数量级差异倍数 | > 10 | 触发禁止自动归组 |
| 归一化后最短名称 | >= 2 字符 | 低于此值不做噪音词移除 |

### 相似度算法

- 商品名称：`rapidfuzz.fuzz.token_sort_ratio`（对 token 顺序不敏感）
- 规格型号：Jaccard 系数（token 集合交并比）
- 单位：完全匹配（二值判定）

### MCP 强制规则

- backend-dev 首次使用 `rapidfuzz` API 时，**必须**先通过 Context7 查文档确认用法
- frontend-dev 首次使用 `dnd-kit` API 时，**必须**先通过 Context7 查文档确认用法

---

## 各 Task 的 task-spec

见同目录下的独立文件：
- `task-3.1-text-normalization.md`
- `task-3.2-scoring-and-constraints.md`
- `task-3.3-grouping-api.md`
- `task-3.4-pydantic-models.md`
- `task-3.5-candidate-list-ui.md`
- `task-3.6-dnd-kit-drag.md`
- `task-3.7-confirm-split-merge.md`
- `task-3.8-openapi-update.md`
