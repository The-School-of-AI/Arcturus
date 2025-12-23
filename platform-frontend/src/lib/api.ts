import axios from 'axios';
import type { Run, PlatformNode, PlatformEdge } from '../types';

const API_BASE = 'http://localhost:8000';

export interface API_Run {
    id: string;
    status: string;
    created_at: string;
    query: string;
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
            model: 'gemini-2.0-pro', // Default or from API
            ragEnabled: true
        }));
    },

    // Trigger new run
    createRun: async (query: string, model: string): Promise<API_Run> => {
        const res = await axios.post(`${API_BASE}/runs`, { query, model });
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
    }
};
