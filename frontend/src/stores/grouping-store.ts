import { create } from "zustand";
import { generateGrouping, listGroups } from "../lib/api";
import type { CommodityGroup } from "../types/grouping";
import { getTaskStatus } from "../lib/api";
import { useProjectStore } from "./project-store";

interface GroupingState {
  groups: CommodityGroup[];
  selectedGroupId: string | null;
  isLoading: boolean;
  isGenerating: boolean;
  error: string | null;

  loadGroups: (projectId: string) => Promise<void>;
  generateGrouping: (projectId: string) => Promise<void>;
  selectGroup: (groupId: string | null) => void;
}

export const useGroupingStore = create<GroupingState>((set, get) => ({
  groups: [],
  selectedGroupId: null,
  isLoading: false,
  isGenerating: false,
  error: null,

  loadGroups: async (projectId: string) => {
    set({ isLoading: true, error: null });
    try {
      const groups = await listGroups(projectId);
      set({ groups, isLoading: false });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to load groups", isLoading: false });
    }
  },

  generateGrouping: async (projectId: string) => {
    set({ isGenerating: true, error: null });
    try {
      const resp = await generateGrouping(projectId);
      const taskId = resp.taskId;
      
      // Poll task status
      const pollTimer = setInterval(async () => {
        try {
          const status = await getTaskStatus(taskId);
          if (status.status === "completed") {
            clearInterval(pollTimer);
            set({ isGenerating: false });
            await get().loadGroups(projectId);
            await useProjectStore.getState().loadProject(projectId);
          } else if (status.status === "failed") {
            clearInterval(pollTimer);
            set({ isGenerating: false, error: status.error || "Grouping generation failed" });
          }
        } catch (pollErr) {
          clearInterval(pollTimer);
          set({ isGenerating: false, error: pollErr instanceof Error ? pollErr.message : "Failed to poll task status" });
        }
      }, 2000);
      
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to start grouping generation", isGenerating: false });
    }
  },

  selectGroup: (groupId: string | null) => {
    set({ selectedGroupId: groupId });
  },
}));
