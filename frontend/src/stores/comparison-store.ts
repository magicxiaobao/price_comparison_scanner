import { create } from "zustand";
import {
  generateComparison,
  getComparison,
  exportReport,
  getTaskStatus,
} from "../lib/api";
import type { ComparisonResult } from "../types/comparison";

interface ComparisonStore {
  results: ComparisonResult[];
  isGenerating: boolean;
  isExporting: boolean;
  exportTaskId: string | null;
  isLoading: boolean;
  error: string | null;
  exportProgress: number;
  exportError: string | null;
  exportFilePath: string | null;

  loadResults: (projectId: string) => Promise<void>;
  generateComparison: (projectId: string) => Promise<void>;
  exportReport: (projectId: string) => Promise<void>;
  clearExportResult: () => void;
}

const POLL_INTERVAL = 2000;
const POLL_TIMEOUT = 300000;

export const useComparisonStore = create<ComparisonStore>((set, get) => ({
  results: [],
  isGenerating: false,
  isExporting: false,
  exportTaskId: null,
  isLoading: false,
  error: null,
  exportProgress: 0,
  exportError: null,
  exportFilePath: null,

  loadResults: async (projectId: string) => {
    set({ isLoading: true, error: null });
    try {
      const results = await getComparison(projectId);
      set({ results, isLoading: false });
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "加载比价结果失败",
        isLoading: false,
      });
    }
  },

  generateComparison: async (projectId: string) => {
    set({ isGenerating: true, error: null });
    try {
      const resp = await generateComparison(projectId);
      const taskId = resp.taskId;
      const startTime = Date.now();

      const pollTimer = setInterval(async () => {
        try {
          if (Date.now() - startTime > POLL_TIMEOUT) {
            clearInterval(pollTimer);
            set({ isGenerating: false, error: "生成比价超时，请重试" });
            return;
          }
          const status = await getTaskStatus(taskId);
          if (status.status === "completed") {
            clearInterval(pollTimer);
            set({ isGenerating: false });
            await get().loadResults(projectId);
          } else if (status.status === "failed") {
            clearInterval(pollTimer);
            set({
              isGenerating: false,
              error: status.error || "生成比价失败",
            });
          }
        } catch (pollErr) {
          clearInterval(pollTimer);
          set({
            isGenerating: false,
            error:
              pollErr instanceof Error ? pollErr.message : "轮询任务状态失败",
          });
        }
      }, POLL_INTERVAL);
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "启动比价生成失败",
        isGenerating: false,
      });
    }
  },

  exportReport: async (projectId: string) => {
    set({
      isExporting: true,
      exportError: null,
      exportProgress: 0,
      exportFilePath: null,
    });
    try {
      const resp = await exportReport(projectId);
      const taskId = resp.taskId;
      set({ exportTaskId: taskId });
      const startTime = Date.now();

      const pollTimer = setInterval(async () => {
        try {
          if (Date.now() - startTime > POLL_TIMEOUT) {
            clearInterval(pollTimer);
            set({
              isExporting: false,
              exportTaskId: null,
              exportError: "导出超时，请重试",
            });
            return;
          }
          const status = await getTaskStatus(taskId);
          set({ exportProgress: status.progress });
          if (status.status === "completed") {
            clearInterval(pollTimer);
            set({
              isExporting: false,
              exportTaskId: null,
              exportProgress: 1,
            });
          } else if (status.status === "failed") {
            clearInterval(pollTimer);
            set({
              isExporting: false,
              exportTaskId: null,
              exportError: status.error || "导出失败",
            });
          }
        } catch (pollErr) {
          clearInterval(pollTimer);
          set({
            isExporting: false,
            exportTaskId: null,
            exportError:
              pollErr instanceof Error ? pollErr.message : "轮询导出状态失败",
          });
        }
      }, POLL_INTERVAL);
    } catch (e) {
      set({
        isExporting: false,
        exportError: e instanceof Error ? e.message : "启动导出失败",
      });
    }
  },

  clearExportResult: () => {
    set({ exportFilePath: null, exportError: null, exportProgress: 0 });
  },
}));
