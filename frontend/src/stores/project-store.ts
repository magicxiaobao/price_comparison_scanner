import { create } from "zustand";
import type { ProjectSummary, ProjectDetail } from "../types/project";
import type { SupplierFile, RawTable } from "../types/file";
import type { TaskInfo } from "../types/task";
import type { ProblemGroup } from "../types/problem";
import * as api from "../lib/api";

interface ImportProgress {
  totalFiles: number;
  confirmedFiles: number;
  selectedTables: number;
  totalTables: number;
  allConfirmed: boolean;
}

interface ProjectStore {
  // === Phase 0 已有 ===
  projects: ProjectSummary[];
  currentProject: ProjectDetail | null;
  isLoading: boolean;

  loadProjects: () => Promise<void>;
  loadProject: (id: string) => Promise<void>;
  createProject: (name: string) => Promise<ProjectDetail>;
  deleteProject: (id: string) => Promise<void>;
  clearProject: () => void;

  // === Phase 1 新增 ===
  files: SupplierFile[];
  tables: RawTable[];
  activeTasks: Record<string, TaskInfo>;

  loadFiles: (projectId: string) => Promise<void>;
  loadTables: (projectId: string) => Promise<void>;
  addUploadTask: (taskId: string, fileId: string) => void;
  updateTaskStatus: (taskId: string, status: TaskInfo) => void;
  removeTask: (taskId: string) => void;
  importProgress: () => ImportProgress;

  // === Phase 4 新增 ===
  problems: ProblemGroup[];
  refreshProblems: (projectId: string) => Promise<void>;
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  // === Phase 0 ===
  projects: [],
  currentProject: null,
  isLoading: false,

  loadProjects: async () => {
    set({ isLoading: true });
    try {
      const projects = await api.listProjects();
      set({ projects, isLoading: false });
    } catch (error) {
      console.error("[loadProjects] failed:", error);
      set({ isLoading: false });
    }
  },

  loadProject: async (id: string) => {
    set({ isLoading: true });
    try {
      const project = await api.getProject(id);
      set({ currentProject: project, isLoading: false });
    } catch (error) {
      console.error("[loadProject] failed:", error);
      set({ isLoading: false });
    }
  },

  createProject: async (name: string) => {
    try {
      const project = await api.createProject({ name });
      await get().loadProjects();
      return project;
    } catch (error) {
      console.error("[createProject] failed:", error);
      throw error;
    }
  },

  deleteProject: async (id: string) => {
    try {
      await api.deleteProject(id);
      await get().loadProjects();
      if (get().currentProject?.id === id) {
        set({ currentProject: null });
      }
    } catch (error) {
      console.error("[deleteProject] failed:", error);
      throw error;
    }
  },

  clearProject: () =>
    set({ currentProject: null, files: [], tables: [], activeTasks: {}, problems: [] }),

  // === Phase 1 新增 ===
  files: [],
  tables: [],
  activeTasks: {},

  loadFiles: async (projectId: string) => {
    try {
      const files = await api.listFiles(projectId);
      set({ files });
    } catch (error) {
      console.error("[loadFiles] failed:", error);
    }
  },

  loadTables: async (projectId: string) => {
    try {
      const tables = await api.listTables(projectId);
      set({ tables });
    } catch (error) {
      console.error("[loadTables] failed:", error);
    }
  },

  addUploadTask: (taskId: string, _fileId: string) => {
    const placeholder: TaskInfo = {
      task_id: taskId,
      task_type: "parse_file",
      status: "queued",
      progress: 0,
      error: null,
      created_at: new Date().toISOString(),
      started_at: null,
      completed_at: null,
      result: null,
    };
    set((state) => ({
      activeTasks: { ...state.activeTasks, [taskId]: placeholder },
    }));
  },

  updateTaskStatus: (taskId: string, status: TaskInfo) => {
    set((state) => ({
      activeTasks: { ...state.activeTasks, [taskId]: status },
    }));
  },

  removeTask: (taskId: string) => {
    set((state) => {
      const next = { ...state.activeTasks };
      delete next[taskId];
      return { activeTasks: next };
    });
  },

  importProgress: () => {
    const { files, tables } = get();
    const confirmedFiles = files.filter((f) => f.supplier_confirmed).length;
    return {
      totalFiles: files.length,
      confirmedFiles,
      selectedTables: tables.filter((t) => t.selected).length,
      totalTables: tables.length,
      allConfirmed: files.length > 0 && confirmedFiles === files.length,
    };
  },

  // === Phase 4 新增 ===
  problems: [],

  refreshProblems: async (projectId: string) => {
    try {
      const problems = await api.getProblems(projectId);
      set({ problems });
    } catch {
      set({ problems: [] });
    }
  },
}));
