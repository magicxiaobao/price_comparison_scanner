import { useParams } from "react-router-dom";
import { ImportStage } from "../components/stages/import-stage";

function ProjectWorkbench() {
  const { id } = useParams<{ id: string }>();

  if (!id) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <p className="text-red-500">项目 ID 缺失</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-xl font-bold">项目工作台</h1>
      <div className="mt-6">
        <ImportStage projectId={id} />
      </div>
    </div>
  );
}

export default ProjectWorkbench;
