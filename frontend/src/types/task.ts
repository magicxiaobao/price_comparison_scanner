export type TaskStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface TaskInfo {
  task_id: string;
  task_type: string;
  status: TaskStatus;
  progress: number; // 0.0 - 1.0
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}
