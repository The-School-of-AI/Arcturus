// features/swarm/useSwarmStore.ts
// Zustand store slice for the Swarm UI state

import { create } from 'zustand';
import type { SwarmTask, SwarmEvent, SwarmTemplate } from './types';
import { swarmApi } from './swarmApi';

interface SwarmStore {
    // Active run
    activeRunId: string | null;
    tasks: SwarmTask[];
    tokensUsed: number;
    costUsd: number;
    isPaused: boolean;

    // UI state
    selectedAgentId: string | null;
    isInterventionOpen: boolean;
    isTemplateDrawerOpen: boolean;
    templates: SwarmTemplate[];

    // Actions
    setActiveRunId: (id: string | null) => void;
    applyEvent: (event: SwarmEvent) => void;
    refreshStatus: (runId: string) => Promise<void>;
    setSelectedAgent: (agentId: string | null) => void;
    setInterventionOpen: (open: boolean) => void;
    setTemplateDrawerOpen: (open: boolean) => void;
    loadTemplates: () => Promise<void>;
}

export const useSwarmStore = create<SwarmStore>((set, get) => ({
    activeRunId: null,
    tasks: [],
    tokensUsed: 0,
    costUsd: 0,
    isPaused: false,
    selectedAgentId: null,
    isInterventionOpen: false,
    isTemplateDrawerOpen: false,
    templates: [],

    setActiveRunId: (id) => set({ activeRunId: id, tasks: [], tokensUsed: 0, costUsd: 0, selectedAgentId: null }),

    applyEvent: (event) => {
        const { type, data } = event;

        if (type === 'task_progress') {
            const d = data as { task_id: string; pct: number; result?: string };
            set(state => ({
                tasks: state.tasks.map(t =>
                    t.task_id === d.task_id
                        ? { ...t, status: d.pct === 100 ? 'completed' : 'in_progress', result: d.result ?? t.result }
                        : t
                ),
            }));
        }

        if (type === 'task_done') {
            const d = data as { task_id: string; status: 'completed' | 'failed'; result?: string };
            set(state => ({
                tasks: state.tasks.map(t =>
                    t.task_id === d.task_id ? { ...t, status: d.status, result: d.result ?? t.result } : t
                ),
            }));
        }

        if (type === 'swarm_done') {
            const d = data as { tokens: number; cost_usd: number };
            set({ tokensUsed: d.tokens, costUsd: d.cost_usd });
        }
    },

    refreshStatus: async (runId) => {
        try {
            const status = await swarmApi.getStatus(runId);
            set({
                tasks: status.tasks,
                tokensUsed: status.tokens_used,
                costUsd: status.cost_usd,
                isPaused: status.paused,
            });
        } catch {
            // silently ignore if run not yet initialised
        }
    },

    setSelectedAgent: (agentId) => set({ selectedAgentId: agentId }),
    setInterventionOpen: (open) => set({ isInterventionOpen: open }),
    setTemplateDrawerOpen: (open) => set({ isTemplateDrawerOpen: open }),

    loadTemplates: async () => {
        try {
            const templates = await swarmApi.listTemplates();
            set({ templates });
        } catch {
            set({ templates: [] });
        }
    },
}));
