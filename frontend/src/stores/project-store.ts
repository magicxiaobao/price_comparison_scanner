import { create } from "zustand";
import type { ProjectSummary, ProjectDetail } from "../types/project";
import * as api from "../lib/api";

interface ProjectStore {
  /** 最近项目列表 */
  projects: ProjectSummary[];
  /** 当前打开的项目 */
  currentProject: ProjectDetail | null;
  /** 加载状态 */
  isLoading: boolean;

  /** 加载项目列表 */
  loadProjects: () => Promise<void>;
  /** 加载项目详情 */
  loadProject: (id: string) => Promise<void>;
  /** 创建项目 */
  createProject: (name: string) => Promise<ProjectDetail>;
  /** 删除项目 */
  deleteProject: (id: string) => Promise<void>;
  /** 清除当前项目 */
  clearProject: () => void;
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  currentProject: null,
  isLoading: false,

  loadProjects: async () => {
    set({ isLoading: true });
    const projects = await api.listProjects();
    set({ projects, isLoading: false });
  },

  loadProject: async (id: string) => {
    set({ isLoading: true });
    const project = await api.getProject(id);
    set({ currentProject: project, isLoading: false });
  },

  createProject: async (name: string) => {
    const project = await api.createProject({ name });
    await get().loadProjects();
    return project;
  },

  deleteProject: async (id: string) => {
    await api.deleteProject(id);
    await get().loadProjects();
    if (get().currentProject?.id === id) {
      set({ currentProject: null });
    }
  },

  clearProject: () => set({ currentProject: null }),
}));
