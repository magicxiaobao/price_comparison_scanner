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
