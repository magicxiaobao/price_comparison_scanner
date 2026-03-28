# Phase 4 执行计划

> 基于 phase-spec.md 勘误后的版本，采用"后端先收口、4.12 作为前端硬 gate、局部并行"编排。

## 波次编排

| Wave | 任务 | 负责人 | Gate | 备注 |
|------|------|--------|------|------|
| W0 | 4.11 | backend-owner | G0: 审模型与 alias/camelCase 基线 | 必须单独收口 |
| W1 | 4.1 + 4.4 | backend-worker-A + B | — | 后端并行收益最高 |
| W2 | 4.2 | backend | G1: 审 4.1 + 4.4 | 4.2 串在 4.1 后，与 4.4 审查错峰 |
| W3 | 4.3 | backend-owner | G2: 审 4.2 + 4.3 | 符合性链路稳定点 |
| W4 | 4.5 | backend-owner | 快速检查 ComplianceRepo 依赖 | 后端第二关键集成点 |
| W5 | 4.6 + 4.7 | backend-worker-A + B | — | 写集分离，适合并行 |
| W6 | 4.12 | backend-owner | G3: 审 4.5+4.6+4.7+openapi | 4.12 依赖 4.6+4.7（非仅 4.7） |
| W7 | 4.8+4.9+4.10 | frontend-owner + workers | — | 共享文件归 owner |
| W8 | 前端整合 | frontend-owner | G4: Phase 4 整体验收 | |

## 依赖关系

```
4.11 ─┬─ 4.1 ─── 4.2 ─── 4.3 ──┬─ 4.5 ──┬─ 4.6 ──┬─ 4.12 ── [前端开工]
      │                          │        │        │
      └─ 4.4 ───────────────────┘        └─ 4.7 ──┘
```

## 角色与共享文件归属

| 角色 | 负责任务 | 共享文件 |
|------|----------|----------|
| backend-owner | 4.11, 4.3, 4.5, 4.12 | — |
| backend-worker-A | 4.1, 4.6 | — |
| backend-worker-B | 4.4, 4.7 | — |
| frontend-owner | 4.10 + api.ts + workbench 整合 | api.ts, project-workbench.tsx |
| frontend-worker-A | 4.8 本地文件 | — |
| frontend-worker-B | 4.9 本地文件 | — |
| reviewer | G0-G4 共 5 个 gate | — |

## Gate 审查要求

- **G0**: 模型与 alias 基线（_CAMEL_CONFIG 落地、字段与 schema 对齐）
- **G1**: 4.1 + 4.4 方向正确（CRUD 完整性、异常检测覆盖度）
- **G2**: 符合性链路稳定（4.2 匹配逻辑 + 4.3 API 层 repo 引用）
- **G3**: 后端整体收口（openapi.json 完整、4.5/4.6/4.7 契约一致）
- **G4**: Phase 4 整体验收（前后端契约 + 手动验证 + 门禁全通过）

## 降级策略

保留 backend-owner + 1 backend-worker + frontend-owner + reviewer
→ 前端改为 4.8 → 4.9 → 4.10 串行
→ 后端保持 W1 和 W5 两次局部并行
