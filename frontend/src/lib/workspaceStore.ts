"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { CalculateRequest } from "./types";

export interface AcousticProject {
  id: string;
  name: string;
  request: CalculateRequest;
  updatedAt: string;
}

interface WorkspaceState {
  activeProjectId: string | null;
  request: CalculateRequest | null;
  projects: AcousticProject[];
  setRequest: (request: CalculateRequest) => void;
  saveProject: (name?: string) => string;
  openProject: (id: string) => void;
  duplicateProject: (id: string) => void;
  removeProject: (id: string) => void;
  newProject: () => void;
}

function projectId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `room-${Date.now()}`;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      activeProjectId: null,
      request: null,
      projects: [],
      setRequest: (request) => {
        const { activeProjectId } = get();
        set((state) => ({
          request,
          projects: activeProjectId
            ? state.projects.map((project) => project.id === activeProjectId
              ? { ...project, request, updatedAt: new Date().toISOString() }
              : project)
            : state.projects,
        }));
      },
      saveProject: (name) => {
        const { request, activeProjectId, projects } = get();
        if (!request) return "";
        if (activeProjectId) {
          set({ projects: projects.map((project) => project.id === activeProjectId
            ? { ...project, name: name || project.name, request, updatedAt: new Date().toISOString() }
            : project) });
          return activeProjectId;
        }
        const id = projectId();
        const project: AcousticProject = {
          id,
          name: name || `Sala ${projects.length + 1}`,
          request,
          updatedAt: new Date().toISOString(),
        };
        set({ activeProjectId: id, projects: [project, ...projects] });
        return id;
      },
      openProject: (id) => {
        const project = get().projects.find((item) => item.id === id);
        if (project) set({ activeProjectId: id, request: project.request });
      },
      duplicateProject: (id) => {
        const project = get().projects.find((item) => item.id === id);
        if (!project) return;
        const copy = { ...project, id: projectId(), name: `${project.name} (copia)`, updatedAt: new Date().toISOString() };
        set((state) => ({ projects: [copy, ...state.projects], activeProjectId: copy.id, request: copy.request }));
      },
      removeProject: (id) => set((state) => ({
        projects: state.projects.filter((project) => project.id !== id),
        activeProjectId: state.activeProjectId === id ? null : state.activeProjectId,
        request: state.activeProjectId === id ? null : state.request,
      })),
      newProject: () => set({ activeProjectId: null, request: null }),
    }),
    {
      name: "acoustic-workspace-v1",
      storage: createJSONStorage(() => localStorage),
      partialize: ({ activeProjectId, request, projects }) => ({ activeProjectId, request, projects }),
    },
  ),
);
