import axios from 'axios';
import type { Run, PlatformNode, PlatformEdge } from '../types';

export const API_BASE = 'http://localhost:8000';

export interface API_Run {
    id: string;
    status: string;
    created_at: string;
    query: string;
    model?: string;  // Model used for this run
    total_tokens?: number;
}

export interface API_RunDetail {
    id: string;
    status: string;
    graph: {
        nodes: any[];
        edges: any[];
    };
}

export const api = {
    // List all runs
    getRuns: async (): Promise<Run[]> => {
        const res = await axios.get<API_Run[]>(`${API_BASE}/runs`);
        return res.data.map(r => ({
            id: r.id,
            name: r.query, // Map query to name
            createdAt: new Date(r.created_at).getTime(), // Map string to timestamp
            status: r.status as Run['status'],
            model: r.model || 'default', // Use model from response or 'default'
            ragEnabled: true,
            total_tokens: r.total_tokens
        }));
    },

    // Trigger new run (model optional - backend uses settings default if not provided)
    createRun: async (query: string, model?: string): Promise<API_Run> => {
        const payload: { query: string; model?: string } = { query };
        if (model) payload.model = model;
        const res = await axios.post(`${API_BASE}/runs`, payload);
        return res.data;
    },

    // Get specific run graph
    getRunGraph: async (runId: string): Promise<{ nodes: PlatformNode[], edges: PlatformEdge[] }> => {
        const res = await axios.get<API_RunDetail>(`${API_BASE}/runs/${runId}`);
        return {
            nodes: res.data.graph.nodes,
            edges: res.data.graph.edges
        };
    },

    // Stop execution
    stopRun: async (runId: string): Promise<void> => {
        await axios.post(`${API_BASE}/runs/${runId}/stop`);
    },

    // Delete run
    deleteRun: async (runId: string): Promise<void> => {
        await axios.delete(`${API_BASE}/runs/${runId}`);
    },

    // Generic access for Extensions
    get: axios.get,
    post: axios.post,
    delete: axios.delete,

    // Apps
    getApps: async (): Promise<any[]> => {
        const res = await axios.get(`${API_BASE}/apps`);
        return res.data;
    },

    getApp: async (appId: string): Promise<any> => {
        const res = await axios.get(`${API_BASE}/apps/${appId}`);
        return res.data;
    },

    saveApp: async (app: any): Promise<void> => {
        await axios.post(`${API_BASE}/apps/save`, app);
    },

    deleteApp: async (appId: string): Promise<void> => {
        await axios.delete(`${API_BASE}/apps/${appId}`);
    },

    hydrateApp: async (appId: string): Promise<any> => {
        const res = await axios.post(`${API_BASE}/apps/${appId}/hydrate`);
        return res.data;
    }
};
