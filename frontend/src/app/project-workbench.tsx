import { useParams } from "react-router-dom";

function ProjectWorkbench() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-xl font-bold">项目工作台</h1>
      <p className="text-gray-500">项目 ID: {id}</p>
      <p className="text-gray-400">（Phase 1+ 填充）</p>
    </div>
  );
}

export default ProjectWorkbench;
