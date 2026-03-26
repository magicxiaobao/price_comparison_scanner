# Task 0.8: 首页 — 项目列表 + 新建项目（连通后端）

## 输入条件

- Task 0.4 完成（后端项目 CRUD API 可用）
- Task 0.7 完成（前端 API Client + ProjectStore 就绪）

## 输出物

- 修改: `frontend/src/app/home-page.tsx`（从空壳改为完整实现）
- 创建: `frontend/src/components/project-list.tsx`
- 创建: `frontend/src/components/create-project-dialog.tsx`

## 禁止修改

- 不修改 `backend/` 下任何文件
- 不修改 `src/lib/api.ts`（已稳定）
- 不修改 `src/stores/project-store.ts`（已稳定）
- 不修改 `src/App.tsx`（路由已稳定）
- 不修改 `vite.config.ts`

## 实现规格

### components/project-list.tsx

```typescript
import { useProjectStore } from "../stores/project-store";
import { useNavigate } from "react-router-dom";
import type { ProjectSummary } from "../types/project";

interface ProjectListProps {
  projects: ProjectSummary[];
  onDelete: (id: string) => void;
}

function ProjectList({ projects, onDelete }: ProjectListProps) {
  const navigate = useNavigate();

  if (projects.length === 0) {
    return <p className="text-gray-500 py-8 text-center">暂无项目，点击"新建项目"开始</p>;
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left px-4 py-3 font-medium">项目名称</th>
            <th className="text-left px-4 py-3 font-medium">供应商数</th>
            <th className="text-left px-4 py-3 font-medium">状态</th>
            <th className="text-left px-4 py-3 font-medium">更新时间</th>
            <th className="text-right px-4 py-3 font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => (
            <tr
              key={p.id}
              className="border-t hover:bg-gray-50 cursor-pointer"
              onClick={() => navigate(`/project/${p.id}`)}
            >
              <td className="px-4 py-3 font-medium">{p.name}</td>
              <td className="px-4 py-3 text-gray-600">{p.supplier_count} 家</td>
              <td className="px-4 py-3 text-gray-600">{p.current_stage}</td>
              <td className="px-4 py-3 text-gray-500">{formatTime(p.updated_at)}</td>
              <td className="px-4 py-3 text-right">
                <button
                  className="text-red-500 hover:text-red-700 text-xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(p.id);
                  }}
                >
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default ProjectList;
```

### components/create-project-dialog.tsx

```typescript
import { useState } from "react";

interface CreateProjectDialogProps {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string) => Promise<void>;
}

function CreateProjectDialog({ open, onClose, onCreate }: CreateProjectDialogProps) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setLoading(true);
    try {
      await onCreate(name.trim());
      setName("");
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-96 shadow-xl">
        <h2 className="text-lg font-semibold mb-4">新建项目</h2>
        <input
          type="text"
          className="w-full border rounded px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="请输入项目名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          autoFocus
        />
        <div className="flex justify-end gap-2">
          <button
            className="px-4 py-2 border rounded hover:bg-gray-100"
            onClick={onClose}
            disabled={loading}
          >
            取消
          </button>
          <button
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            onClick={handleSubmit}
            disabled={!name.trim() || loading}
          >
            {loading ? "创建中..." : "创建"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default CreateProjectDialog;
```

### app/home-page.tsx（完整实现）

```typescript
import { useEffect, useState } from "react";
import { useProjectStore } from "../stores/project-store";
import ProjectList from "../components/project-list";
import CreateProjectDialog from "../components/create-project-dialog";
import { useNavigate } from "react-router-dom";

function HomePage() {
  const { projects, isLoading, loadProjects, createProject, deleteProject } = useProjectStore();
  const [dialogOpen, setDialogOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleCreate = async (name: string) => {
    const project = await createProject(name);
    navigate(`/project/${project.id}`);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确认删除此项目？")) return;
    await deleteProject(id);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-2xl font-bold mb-6">三方比价支出依据扫描工具</h1>

      <div className="flex gap-4 mb-8">
        <button
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          onClick={() => setDialogOpen(true)}
        >
          + 新建项目
        </button>
        <a
          href="#/rules"
          className="px-4 py-2 border rounded hover:bg-gray-100"
        >
          规则管理
        </a>
      </div>

      <h2 className="text-lg font-semibold mb-4">最近项目</h2>

      {isLoading ? (
        <p className="text-gray-500">加载中...</p>
      ) : (
        <ProjectList projects={projects} onDelete={handleDelete} />
      )}

      <CreateProjectDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreate={handleCreate}
      />
    </div>
  );
}

export default HomePage;
```

## 测试与验收

```bash
cd frontend
pnpm lint                             # exit 0
pnpm tsc --noEmit                     # exit 0
```

**手动集成测试：**

```bash
# 终端 1：启动后端
cd backend
DEV_MODE=1 uvicorn main:app --host 127.0.0.1 --port 17396 --reload

# 终端 2：启动前端
cd frontend
pnpm dev
```

在浏览器中访问 `http://localhost:5173`，验证：

1. **首页加载** → 显示标题"三方比价支出依据扫描工具"和空项目列表
2. **新建项目** → 点击"新建项目" → 弹出对话框 → 输入"测试项目" → 点击"创建" → 跳转到工作台页面
3. **返回首页** → 浏览器后退 → 首页显示"测试项目"在列表中
4. **再建一个项目** → "测试项目2" → 列表中两个项目，最新的在前面
5. **删除项目** → 点击"删除" → 确认 → 项目从列表消失
6. **空名称保护** → 新建对话框中不输入名称 → "创建"按钮置灰

**断言清单：**
- `pnpm lint` → 退出码 0
- `pnpm tsc --noEmit` → 退出码 0
- 首页可加载并显示标题
- 新建项目 → 后端返回 200 → 跳转到 `/project/:id`
- 项目列表从后端加载并按时间倒序展示
- 删除项目 → 后端返回 200 → 列表刷新
- Vite proxy 正常工作（前端 → 后端无跨域问题）

## 提交

```bash
git add frontend/src/app/home-page.tsx frontend/src/components/project-list.tsx \
       frontend/src/components/create-project-dialog.tsx
git commit -m "Phase 0.8: 首页连通后端 — 项目列表 + 新建项目 + 删除项目"
```
