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
