import axios from 'axios';
import type { Run, Space, PlatformNode, PlatformEdge } from '../types';

export const API_BASE = 'http://localhost:8000/api';

export interface API_Run {
    id: string;
    status: string;
    created_at: string;
    query: string;
    model?: string;  // Model used for this run
    total_tokens?: number;
    space_id?: string | null;  // Phase 4: optional space for run
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
            total_tokens: r.total_tokens,
            space_id: r.space_id ?? undefined
        }));
    },

    // Trigger new run (model optional - backend uses settings default if not provided). Phase 4: optional space_id.
    createRun: async (query: string, model?: string, space_id?: string | null): Promise<API_Run> => {
        const payload: { query: string; model?: string; space_id?: string } = { query };
        if (model) payload.model = model;
        if (space_id) payload.space_id = space_id;
        const res = await axios.post(`${API_BASE}/runs`, payload);
        return res.data;
    },

    // Phase 4: Spaces (Perplexity-style project hubs)
    getSpaces: async (): Promise<Space[]> => {
        try {
            const res = await axios.get<{ status: string; spaces: Space[] }>(`${API_BASE}/remme/spaces`);
            return res.data?.spaces ?? [];
        } catch (e) {
            console.error('Failed to fetch spaces', e);
            return [];
        }
    },

    createSpace: async (name: string, description?: string, sync_policy?: 'sync' | 'local_only'): Promise<Space> => {
        const payload: { name: string; description?: string; sync_policy?: string } = { name, description: description ?? '' };
        if (sync_policy) payload.sync_policy = sync_policy;
        const res = await axios.post<{ status: string; space_id: string; name: string; description: string }>(
            `${API_BASE}/remme/spaces`,
            payload
        );
        return { space_id: res.data.space_id, name: res.data.name, description: res.data.description };
    },

    addMemory: async (text: string, category?: string, space_id?: string | null): Promise<void> => {
        const payload: { text: string; category?: string; space_id?: string } = { text, category: category ?? 'general' };
        if (space_id) payload.space_id = space_id;
        await axios.post(`${API_BASE}/remme/add`, payload);
    },

    getMemories: async (space_id?: string | null): Promise<{ memories: any[] }> => {
        const params = space_id ? { space_id } : {};
        const res = await axios.get(`${API_BASE}/remme/memories`, { params });
        return res.data;
    },

    // Get specific run graph
    // Get specific run graph
    getRunGraph: async (runId: string): Promise<{ nodes: PlatformNode[], edges: PlatformEdge[], graph: any }> => {
        const res = await axios.get<API_RunDetail>(`${API_BASE}/runs/${runId}`);
        return {
            nodes: res.data.graph.nodes,
            edges: res.data.graph.edges,
            // Pass the whole graph object (minus nodes/edges if desired, or duplicate) to access globals
            graph: res.data.graph
        };
    },

    // Stop execution
    stopRun: async (runId: string): Promise<void> => {
        await axios.post(`${API_BASE}/runs/${runId}/stop`);
    },

    executeNode: async (runId: string, nodeId: string, mode: 'remaining' | 'all_from_here' | 'single' | 'all', input?: string): Promise<any> => {
        const res = await axios.post(`${API_BASE}/runs/${runId}/nodes/${nodeId}/execute`, { mode, input });
        return res.data;
    },

    // Delete run
    deleteRun: async (runId: string): Promise<void> => {
        await axios.delete(`${API_BASE}/runs/${runId}`);
    },

    // Generic access for Extensions
    get: axios.get,
    post: axios.post,
    put: axios.put,
    patch: axios.patch,
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

    renameApp: async (appId: string, name: string): Promise<void> => {
        await axios.post(`${API_BASE}/apps/${appId}/rename`, { name });
    },

    deleteApp: async (appId: string): Promise<void> => {
        await axios.delete(`${API_BASE}/apps/${appId}`);
    },

    hydrateApp: async (appId: string, userPrompt?: string): Promise<any> => {
        const res = await axios.post(`${API_BASE}/apps/${appId}/hydrate`, { user_prompt: userPrompt });
        return res.data;
    },

    generateApp: async (name: string, prompt: string): Promise<any> => {
        const res = await axios.post(`${API_BASE}/apps/generate`, { name, prompt });
        return res.data;
    },

    // Chat Sessions
    getChatSessions: async (targetType: string, targetId: string): Promise<any[]> => {
        const res = await axios.get(`${API_BASE}/chat/sessions`, { params: { target_type: targetType, target_id: targetId } });
        return res.data.sessions;
    },

    getChatSession: async (sessionId: string, targetType: string, targetId: string): Promise<any> => {
        const res = await axios.get(`${API_BASE}/chat/session/${sessionId}`, { params: { target_type: targetType, target_id: targetId } });
        return res.data.session;
    },

    saveChatSession: async (session: any): Promise<void> => {
        await axios.post(`${API_BASE}/chat/session`, session);
    },

    deleteChatSession: async (sessionId: string, targetType: string, targetId: string): Promise<void> => {
        await axios.delete(`${API_BASE}/chat/session/${sessionId}`, { params: { target_type: targetType, target_id: targetId } });
    },

    // Studio (Forge)
    listArtifacts: async (): Promise<any[]> => {
        const res = await axios.get(`${API_BASE}/studio`);
        return res.data;
    },

    getArtifact: async (id: string): Promise<any> => {
        const res = await axios.get(`${API_BASE}/studio/${id}`);
        return res.data;
    },

    createArtifact: async (type: 'slides' | 'documents' | 'sheets', payload: { prompt: string; title?: string; parameters?: Record<string, any> }): Promise<any> => {
        const res = await axios.post(`${API_BASE}/studio/${type}`, payload);
        return res.data;
    },

    approveOutline: async (id: string, approved: boolean, modifications?: Record<string, any>): Promise<any> => {
        const res = await axios.post(`${API_BASE}/studio/${id}/outline/approve`, { approved, modifications });
        return res.data;
    },

    listRevisions: async (id: string): Promise<any[]> => {
        const res = await axios.get(`${API_BASE}/studio/${id}/revisions`);
        return res.data;
    },

    getRevision: async (artifactId: string, revisionId: string): Promise<any> => {
        const res = await axios.get(`${API_BASE}/studio/${artifactId}/revisions/${revisionId}`);
        return res.data;
    },

    restoreRevision: async (artifactId: string, revisionId: string, baseRevisionId?: string): Promise<any> => {
        const payload: { base_revision_id?: string } = {};
        if (baseRevisionId) payload.base_revision_id = baseRevisionId;
        const res = await axios.post(`${API_BASE}/studio/${artifactId}/revisions/${revisionId}/restore`, payload);
        return res.data;
    },

    // Studio Phase 2 — Export & Themes
    listThemes: async (params?: {
        include_variants?: boolean;
        base_id?: string;
        limit?: number;
    }): Promise<any[]> => {
        const res = await axios.get(`${API_BASE}/studio/themes`, { params });
        return res.data;
    },

    exportArtifact: async (id: string, format: string, themeId?: string, strictLayout?: boolean, generateImages?: boolean): Promise<any> => {
        const payload: { format: string; theme_id?: string; strict_layout?: boolean; generate_images?: boolean } = { format };
        if (themeId) payload.theme_id = themeId;
        if (strictLayout !== undefined) payload.strict_layout = strictLayout;
        if (generateImages) payload.generate_images = true;
        const res = await axios.post(`${API_BASE}/studio/${id}/export`, payload);
        return res.data;
    },

    listExportJobs: async (id: string): Promise<any[]> => {
        const res = await axios.get(`${API_BASE}/studio/${id}/exports`);
        return res.data;
    },

    getExportJob: async (artifactId: string, jobId: string): Promise<any> => {
        const res = await axios.get(`${API_BASE}/studio/${artifactId}/exports/${jobId}`);
        return res.data;
    },

    getExportJobGlobal: async (jobId: string): Promise<any> => {
        const res = await axios.get(`${API_BASE}/studio/exports/${jobId}`);
        return res.data;
    },

    getExportDownloadUrl: (artifactId: string, jobId: string): string => {
        return `${API_BASE}/studio/${artifactId}/exports/${jobId}/download`;
    },

    // Slide image preview
    listSlideImages: async (artifactId: string): Promise<string[]> => {
        const res = await axios.get(`${API_BASE}/studio/${artifactId}/images`);
        return res.data.slide_ids;
    },

    getSlideImageUrl: (artifactId: string, slideId: string): string => {
        return `${API_BASE}/studio/${artifactId}/images/${slideId}`;
    },

    generateSlideImages: async (artifactId: string): Promise<void> => {
        await axios.post(`${API_BASE}/studio/${artifactId}/generate-images`);
    },

    deleteArtifact: async (id: string): Promise<void> => {
        await axios.delete(`${API_BASE}/studio/${id}`);
    },

    clearAllArtifacts: async (): Promise<{ deleted: number }> => {
        const res = await axios.delete(`${API_BASE}/studio`);
        return res.data;
    },

    editArtifact: async (artifactId: string, payload: { instruction: string; base_revision_id?: string; mode?: string }): Promise<any> => {
        const res = await axios.post(`${API_BASE}/studio/${artifactId}/edit`, payload);
        return res.data;
    },

    analyzeSheetUpload: async (artifactId: string, file: File): Promise<any> => {
        const formData = new FormData();
        formData.append('file', file);
        const { data } = await axios.post(
            `${API_BASE}/studio/${artifactId}/sheets/analyze-upload`,
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' } }
        );
        return data;
    },
};
