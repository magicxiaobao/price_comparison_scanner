import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ProjectSummary } from "../types/project";
import { Badge } from "./ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "./ui/alert-dialog";

interface ProjectListProps {
  projects: ProjectSummary[];
  onDelete: (id: string) => void;
}

function ProjectList({ projects, onDelete }: ProjectListProps) {
  const navigate = useNavigate();
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  if (projects.length === 0) {
    return <p className="text-gray-500 py-8 text-center">暂无项目，点击"新建项目"开始</p>;
  }

  return (
    <>
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
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1.5">
                    <span className={`inline-flex w-5 h-5 rounded-full text-xs font-bold items-center justify-center ${p.supplier_count > 0 ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-400"}`}>
                      {p.supplier_count}
                    </span>
                    <span className="text-gray-500 text-xs">家</span>
                  </span>
                </td>
                <td className="px-4 py-3">
                  <StageBadge stage={p.current_stage} />
                </td>
                <td className="px-4 py-3 text-gray-500">{formatTime(p.updated_at)}</td>
                <td className="px-4 py-3 text-right">
                  <button
                    className="text-red-500 hover:text-red-700 text-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPendingDeleteId(p.id);
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

      <AlertDialog open={pendingDeleteId !== null} onOpenChange={(open) => { if (!open) setPendingDeleteId(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              确认删除此项目？删除后无法恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
              onClick={() => {
                if (pendingDeleteId) {
                  onDelete(pendingDeleteId);
                  setPendingDeleteId(null);
                }
              }}
            >
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function StageBadge({ stage }: { stage: string }) {
  let className: string;
  if (stage === "比价完成") {
    className = "bg-emerald-50 text-emerald-700 border-emerald-200";
  } else if (stage.includes("需重新处理")) {
    className = "bg-amber-50 text-amber-700 border-amber-200";
  } else if (stage === "导入文件") {
    className = "bg-slate-100 text-slate-600 border-slate-200";
  } else {
    className = "bg-blue-50 text-blue-700 border-blue-200";
  }
  return <Badge variant="outline" className={className}>{stage}</Badge>;
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
