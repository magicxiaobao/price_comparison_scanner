import { useEffect, useState } from "react";
import { useProjectStore } from "../stores/project-store";
import ProjectList from "../components/project-list";
import CreateProjectDialog from "../components/create-project-dialog";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Separator } from "../components/ui/separator";
import { Card } from "../components/ui/card";

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
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <header className="flex-none h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-blue-600 flex items-center justify-center text-white font-bold tracking-tighter shadow-sm">
            NQ
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">支出依据扫描配置与工作台</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => navigate("/rules")}>
            规则管理
          </Button>
          <Separator orientation="vertical" className="h-4" />
          <Button variant="ghost" size="sm" onClick={() => navigate("/preferences")}>
            应用偏好设置
          </Button>
        </div>
      </header>

      <main className="flex-1 max-w-5xl w-full mx-auto px-12 py-10">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">最近项目</h2>
            <p className="text-slate-500 text-sm mt-1.5 font-medium">选择一个项目进入工作台，或基于结构化模板创建新项目</p>
          </div>
          <Button onClick={() => setDialogOpen(true)}>
            + 新建项目
          </Button>
        </div>

        <Card className="overflow-hidden">
          {isLoading ? (
            <div className="p-16 text-center">
              <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
              <p className="mt-4 text-slate-500 font-medium">加载项目中，请稍候...</p>
            </div>
          ) : (
            <div className="p-2">
               <ProjectList projects={projects} onDelete={handleDelete} />
            </div>
          )}
        </Card>
      </main>

      <CreateProjectDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreate={handleCreate}
      />
    </div>
  );
}

export default HomePage;
