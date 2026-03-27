import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { useProjectStore } from "../stores/project-store";
import { ImportStage } from "../components/stages/import-stage";
import { StandardizeStage } from "../components/stages/standardize-stage";

function ProjectWorkbench() {
  const { id } = useParams<{ id: string }>();
  const { loadProject, loadFiles, loadTables, files, tables } =
    useProjectStore();

  useEffect(() => {
    if (id) {
      loadProject(id);
      loadFiles(id);
      loadTables(id);
    }
  }, [id, loadProject, loadFiles, loadTables]);

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
      <div className="mt-6 space-y-8">
        <ImportStage projectId={id} files={files} tables={tables} />
        <StandardizeStage projectId={id} files={files} />
      </div>
    </div>
  );
}

export default ProjectWorkbench;
