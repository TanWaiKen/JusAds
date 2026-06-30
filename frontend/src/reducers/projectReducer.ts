import type { ProjectStore, ProjectAction } from "@/types/compliance";
import { normalizeViolations } from "@/services/complianceApi";

/**
 * Initial state for the project store.
 */
export const initialProjectStore: ProjectStore = {
  projects: new Map(),
  activeProjectId: null,
};

/**
 * Reducer for managing compliance project state.
 *
 * Enforces state transition rules:
 * - NAVIGATE_TO_STEP only allows navigation to steps already in completedSteps
 * - SET_RESULT auto-advances currentStep to "review" and adds "check" to completedSteps
 * - SET_REMIX_RESULT auto-advances currentStep to "compare" and adds "remix" to completedSteps
 *
 * Requirements: 1.1, 1.2, 2.3, 2.4, 2.5, 2.6
 */
export function projectReducer(
  state: ProjectStore,
  action: ProjectAction
): ProjectStore {
  switch (action.type) {
    case "CREATE_PROJECT": {
      const newProjects = new Map(state.projects);
      newProjects.set(action.payload.id, action.payload);
      return { projects: newProjects, activeProjectId: action.payload.id };
    }

    case "SET_ACTIVE_PROJECT":
      return { ...state, activeProjectId: action.projectId };

    case "ADVANCE_STEP": {
      const project = state.projects.get(action.projectId);
      if (!project) return state;
      const newProjects = new Map(state.projects);
      newProjects.set(action.projectId, {
        ...project,
        completedSteps: [...project.completedSteps, project.currentStep],
        currentStep: action.to,
        error: null,
      });
      return { ...state, projects: newProjects };
    }

    case "SET_RESULT": {
      const project = state.projects.get(action.projectId);
      if (!project) return state;
      const newProjects = new Map(state.projects);
      newProjects.set(action.projectId, {
        ...project,
        result: {
          ...action.result,
          violations: normalizeViolations(action.result),
        },
        completedSteps: [...project.completedSteps, "check"],
        currentStep: "review",
        error: null,
      });
      return { ...state, projects: newProjects };
    }

    case "SET_REMIX_RESULT": {
      const project = state.projects.get(action.projectId);
      if (!project) return state;
      const newProjects = new Map(state.projects);
      newProjects.set(action.projectId, {
        ...project,
        remixResult: action.remixResult,
        completedSteps: [...project.completedSteps, "remix"],
        currentStep: "compare",
        error: null,
      });
      return { ...state, projects: newProjects };
    }

    case "SET_ERROR": {
      const project = state.projects.get(action.projectId);
      if (!project) return state;
      const newProjects = new Map(state.projects);
      newProjects.set(action.projectId, { ...project, error: action.error });
      return { ...state, projects: newProjects };
    }

    case "CLEAR_ERROR": {
      const project = state.projects.get(action.projectId);
      if (!project) return state;
      const newProjects = new Map(state.projects);
      newProjects.set(action.projectId, { ...project, error: null });
      return { ...state, projects: newProjects };
    }

    case "NAVIGATE_TO_STEP": {
      const project = state.projects.get(action.projectId);
      if (!project) return state;

      // Determine the "frontier" — the furthest step ever reached.
      // This is the max of currentStep and all completedSteps.
      const stepOrder: string[] = ["upload", "check", "review", "remix", "compare"];
      const currentIdx = stepOrder.indexOf(project.currentStep);
      const maxCompletedIdx = project.completedSteps.reduce(
        (max, s) => Math.max(max, stepOrder.indexOf(s)),
        -1
      );
      const frontierIdx = Math.max(currentIdx, maxCompletedIdx);
      const targetIdx = stepOrder.indexOf(action.step);

      // Allow navigating to any step at or below the frontier
      if (targetIdx > frontierIdx) return state;

      // When navigating away from current step, add it to completedSteps
      // so we can always return to it
      const updatedCompleted = project.completedSteps.includes(project.currentStep)
        ? project.completedSteps
        : [...project.completedSteps, project.currentStep];

      const newProjects = new Map(state.projects);
      newProjects.set(action.projectId, {
        ...project,
        completedSteps: updatedCompleted,
        currentStep: action.step,
      });
      return { ...state, projects: newProjects };
    }

    default:
      return state;
  }
}
