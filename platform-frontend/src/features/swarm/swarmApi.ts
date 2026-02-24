// features/swarm/swarmApi.ts — typed axios wrappers for /api/swarm/*
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import type { SwarmStatus, AgentLogEntry, SwarmTemplate, InterventionPayload } from './types';

const base = `${API_BASE}/swarm`;

export const swarmApi = {
    /** Start a new swarm run. Returns { run_id, status } */
    startRun: (query: string, tokenBudget = 8000, costBudget = 0.1) =>
        axios.post<{ run_id: string; status: string }>(`${base}/run`, {
            query,
            token_budget: tokenBudget,
            cost_budget_usd: costBudget,
        }).then(r => r.data),

    /** Get DAG snapshot for a run */
    getStatus: (runId: string) =>
        axios.get<SwarmStatus>(`${base}/${runId}/status`).then(r => r.data),

    /** Get conversation log for a specific agent */
    peekAgent: (runId: string, agentId: string) =>
        axios.get<{ log: AgentLogEntry[] }>(`${base}/${runId}/peek/${agentId}`).then(r => r.data.log),

    /** Send an intervention action */
    intervene: (runId: string, payload: InterventionPayload) =>
        axios.post(`${base}/${runId}/intervene`, payload).then(r => r.data),

    /** Template CRUD */
    listTemplates: () =>
        axios.get<SwarmTemplate[]>(`${base}/templates`).then(r => r.data),

    saveTemplate: (template: SwarmTemplate) =>
        axios.post(`${base}/templates`, template).then(r => r.data),

    deleteTemplate: (name: string) =>
        axios.delete(`${base}/templates/${encodeURIComponent(name)}`).then(r => r.data),
};
