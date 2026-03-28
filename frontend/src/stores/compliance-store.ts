import { create } from "zustand";
import {
  listRequirements,
  createRequirement,
  updateRequirement,
  deleteRequirement,
  getComplianceMatrix,
  evaluateCompliance,
  confirmMatch,
  acceptMatch,
} from "../lib/api";
import { getTaskStatus } from "../lib/api";
import { useProjectStore } from "./project-store";
import type {
  RequirementItem,
  RequirementCreate,
  RequirementUpdate,
  ComplianceMatrix,
} from "../types/compliance";

interface ComplianceState {
  requirements: RequirementItem[];
  matrix: ComplianceMatrix | null;
  selectedMatchId: string | null;
  isEvaluating: boolean;
  isLoading: boolean;
  error: string | null;

  loadRequirements: (projectId: string) => Promise<void>;
  addRequirement: (projectId: string, data: RequirementCreate) => Promise<void>;
  editRequirement: (reqId: string, data: RequirementUpdate) => Promise<void>;
  removeRequirement: (reqId: string, projectId: string) => Promise<void>;
  loadMatrix: (projectId: string) => Promise<void>;
  runEvaluation: (projectId: string) => Promise<void>;
  confirmMatchStatus: (matchId: string, projectId: string, status: string) => Promise<void>;
  acceptMatchResult: (matchId: string, projectId: string, isAcceptable: boolean) => Promise<void>;
  setSelectedMatch: (matchId: string | null) => void;
}

export const useComplianceStore = create<ComplianceState>((set, get) => ({
  requirements: [],
  matrix: null,
  selectedMatchId: null,
  isEvaluating: false,
  isLoading: false,
  error: null,

  loadRequirements: async (projectId: string) => {
    set({ isLoading: true, error: null });
    try {
      const requirements = await listRequirements(projectId);
      set({ requirements, isLoading: false });
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "加载需求项失败",
        isLoading: false,
      });
    }
  },

  addRequirement: async (projectId: string, data: RequirementCreate) => {
    try {
      const newReq = await createRequirement(projectId, data);
      set((s) => ({ requirements: [...s.requirements, newReq] }));
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "创建需求项失败" });
    }
  },

  editRequirement: async (reqId: string, data: RequirementUpdate) => {
    try {
      const updated = await updateRequirement(reqId, data);
      set((s) => ({
        requirements: s.requirements.map((r) => (r.id === reqId ? updated : r)),
      }));
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "更新需求项失败" });
    }
  },

  removeRequirement: async (reqId: string, projectId: string) => {
    try {
      await deleteRequirement(reqId, projectId);
      set((s) => ({
        requirements: s.requirements.filter((r) => r.id !== reqId),
      }));
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "删除需求项失败" });
    }
  },

  loadMatrix: async (projectId: string) => {
    set({ isLoading: true, error: null });
    try {
      const matrix = await getComplianceMatrix(projectId);
      set({ matrix, isLoading: false });
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "加载符合性矩阵失败",
        isLoading: false,
      });
    }
  },

  runEvaluation: async (projectId: string) => {
    set({ isEvaluating: true, error: null });
    try {
      const resp = await evaluateCompliance(projectId);
      const taskId = resp.taskId;

      const pollTimer = setInterval(async () => {
        try {
          const status = await getTaskStatus(taskId);
          if (status.status === "completed") {
            clearInterval(pollTimer);
            set({ isEvaluating: false });
            await get().loadMatrix(projectId);
            await useProjectStore.getState().loadProject(projectId);
          } else if (status.status === "failed") {
            clearInterval(pollTimer);
            set({
              isEvaluating: false,
              error: status.error || "符合性匹配失败",
            });
          }
        } catch (pollErr) {
          clearInterval(pollTimer);
          set({
            isEvaluating: false,
            error: pollErr instanceof Error ? pollErr.message : "轮询任务状态失败",
          });
        }
      }, 2000);
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "启动符合性匹配失败",
        isEvaluating: false,
      });
    }
  },

  confirmMatchStatus: async (matchId: string, projectId: string, status: string) => {
    try {
      await confirmMatch(matchId, projectId, status);
      await get().loadMatrix(projectId);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "确认匹配状态失败" });
    }
  },

  acceptMatchResult: async (matchId: string, projectId: string, isAcceptable: boolean) => {
    try {
      await acceptMatch(matchId, projectId, isAcceptable);
      await get().loadMatrix(projectId);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "标记可接受失败" });
    }
  },

  setSelectedMatch: (matchId: string | null) => {
    set({ selectedMatchId: matchId });
  },
}));
