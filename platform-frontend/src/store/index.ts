import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
    Run,
    PlatformNode,
    PlatformEdge,
    Snapshot,
} from '../types';
import { applyNodeChanges, applyEdgeChanges, type NodeChange, type EdgeChange } from 'reactflow';
import { api } from '../lib/api';

// --- Slices Types ---

interface RunSlice {
    runs: Run[];
    currentRun: Run | null;
    addRun: (run: Run) => void;
    setCurrentRun: (runId: string) => void;
    updateRunStatus: (input: { id: string, status: Run['status'] }) => void;
    fetchRuns: () => Promise<void>;
    createNewRun: (query: string, model: string) => Promise<void>;
    refreshCurrentRun: () => Promise<void>;
    pollingInterval: ReturnType<typeof setInterval> | null;
    startPolling: (runId: string) => void;
    stopPolling: () => void;
    deleteRun: (runId: string) => Promise<void>;
}

interface GraphSlice {
    nodes: PlatformNode[];
    edges: PlatformEdge[];
    selectedNodeId: string | null;
    setNodes: (nodes: PlatformNode[]) => void;
    setEdges: (edges: PlatformEdge[]) => void;
    onNodesChange: (changes: NodeChange[]) => void;
    onEdgesChange: (changes: EdgeChange[]) => void;
    selectNode: (nodeId: string | null) => void;
}

interface WorkspaceSlice {
    activeTab: 'code' | 'output' | 'web' | 'html';
    setActiveTab: (tab: 'code' | 'output' | 'web' | 'html') => void;
    codeContent: string;
    setCodeContent: (code: string) => void;
    webUrl: string;
    setWebUrl: (url: string) => void;
    logs: string[];
    addLog: (log: string) => void;
}

interface ReplaySlice {
    snapshots: Snapshot[];
    currentSnapshotIndex: number;
    isReplayMode: boolean;
    loadSnapshot: (index: number) => void;
    addSnapshot: (snapshot: Snapshot) => void;
    toggleReplayMode: (active: boolean) => void;
}

interface SettingsSlice {
    apiKey: string;
    setApiKey: (key: string) => void;
    theme: 'dark' | 'light'; // although we force dark mostly
    localModel: string;
    setLocalModel: (model: string) => void;
}

// --- Store Creation ---

interface AppState extends RunSlice, GraphSlice, WorkspaceSlice, ReplaySlice, SettingsSlice { }

export const useAppStore = create<AppState>()(
    persist(
        (set, get) => ({
            // Runs
            runs: [],
            currentRun: null,
            addRun: (run) => set((state) => ({ runs: [run, ...state.runs] })),
            setCurrentRun: (runId) => {
                const run = get().runs.find((r) => r.id === runId) || null;
                // Reset panel state when switching runs
                set({
                    currentRun: run,
                    selectedNodeId: null,
                    codeContent: '',
                    logs: [],
                    nodes: [],
                    edges: []
                });
                // If run exists, fetch its latest graph immediately
                if (run) {
                    get().refreshCurrentRun();
                }
            },
            updateRunStatus: ({ id, status }) => set((state) => ({
                runs: state.runs.map((r) => r.id === id ? { ...r, status } : r),
                currentRun: state.currentRun?.id === id ? { ...state.currentRun, status } : state.currentRun
            })),

            deleteRun: async (runId) => {
                try {
                    await api.deleteRun(runId);
                    set((state) => ({
                        runs: state.runs.filter((r) => r.id !== runId),
                        currentRun: state.currentRun?.id === runId ? null : state.currentRun
                    }));
                } catch (e) {
                    console.error("Failed to delete run", e);
                }
            },

            // API Actions
            fetchRuns: async () => {
                try {
                    const fetched = await api.getRuns();
                    // Enforce sorting
                    fetched.sort((a, b) => b.createdAt - a.createdAt);
                    set({ runs: fetched });
                } catch (e: any) {
                    console.error("Failed to fetch runs. Check if backend is running at http://localhost:8000 and if CORS is allowed.");
                    if (e.response) {
                        console.error("Response data:", e.response.data);
                        console.error("Response status:", e.response.status);
                    } else if (e.request) {
                        console.error("Request was made but no response received. This often indicates a CORS block or backend offline.");
                    } else {
                        console.error("Error setting up request:", e.message);
                    }
                }
            },

            createNewRun: async (query, model) => {
                try {
                    const res = await api.createRun(query, model);
                    const newRun: Run = {
                        id: res.id,
                        name: res.query,
                        createdAt: Date.now(),
                        status: 'running',
                        model: model,
                        ragEnabled: true
                    };
                    get().addRun(newRun);

                    // Reset Graph State Immediately
                    set({ nodes: [], edges: [], selectedNodeId: null, codeContent: '', logs: [] });

                    get().setCurrentRun(newRun.id);

                    // Start polling
                    get().startPolling(newRun.id);
                } catch (e) {
                    console.error("Failed to create run", e);
                }
            },

            refreshCurrentRun: async () => {
                const runId = get().currentRun?.id;
                if (!runId) return;
                try {
                    const graphData = await api.getRunGraph(runId);
                    set({
                        nodes: graphData.nodes,
                        edges: graphData.edges,
                        isReplayMode: false, // Ensure we are in live mode
                        currentSnapshotIndex: -1
                    });
                } catch (e) {
                    console.error("Failed to refresh graph", e);
                }
            },

            // Polling Logic
            pollingInterval: null,
            startPolling: (runId) => {
                const interval = setInterval(async () => {
                    await get().refreshCurrentRun();
                    // Check if completed? (Optimization later)
                }, 2000);
                set({ pollingInterval: interval });
            },
            stopPolling: () => {
                const interval = get().pollingInterval;
                if (interval) clearInterval(interval);
                set({ pollingInterval: null });
            },

            // Graph
            nodes: [],
            edges: [],
            selectedNodeId: null,
            setNodes: (nodes) => set({ nodes }),
            setEdges: (edges) => set({ edges }),
            onNodesChange: (changes) => set({
                nodes: applyNodeChanges(changes, get().nodes) as PlatformNode[]
            }),
            onEdgesChange: (changes) => set({
                edges: applyEdgeChanges(changes, get().edges)
            }),
            selectNode: (nodeId) => {
                const node = get().nodes.find(n => n.id === nodeId);
                set({ selectedNodeId: nodeId });

                if (node && node.data) {
                    // Populate panels
                    set({
                        codeContent: node.data.output || '// Waiting for output',
                        logs: [
                            `Status: ${node.data.status}`,
                            `Type: ${node.data.type}`,
                            node.data.error ? `Error: ${node.data.error}` : ''
                        ].filter(Boolean)
                    });
                }
            },

            // Workspace
            activeTab: 'code',
            setActiveTab: (tab) => set({ activeTab: tab }),
            codeContent: '// Agent code will appear here',
            setCodeContent: (code) => set({ codeContent: code }),
            webUrl: '',
            setWebUrl: (url) => set({ webUrl: url }),
            logs: [],
            addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),

            // Replay
            snapshots: [],
            currentSnapshotIndex: -1,
            isReplayMode: false,
            loadSnapshot: (index) => {
                const snapshot = get().snapshots[index];
                if (!snapshot) return;
                set({
                    currentSnapshotIndex: index,
                    nodes: snapshot.graphState.nodes,
                    edges: snapshot.graphState.edges,
                    codeContent: snapshot.codeContent,
                    webUrl: snapshot.webUrl || '',
                    // trigger other UI updates...
                });
            },
            addSnapshot: (snapshot) => set((state) => ({
                snapshots: [...state.snapshots, snapshot],
                currentSnapshotIndex: state.snapshots.length // pointing to new one
            })),
            toggleReplayMode: (active) => set({ isReplayMode: active }),

            // Settings
            apiKey: '',
            setApiKey: (key) => set({ apiKey: key }),
            theme: 'dark',
            localModel: 'mistral:latest',
            setLocalModel: (model) => set({ localModel: model }),
        }),
        {
            name: 'agent-platform-storage',
            partialize: (state) => ({
                // Only persist user settings, not runs (which should come fresh from API)
                apiKey: state.apiKey,
                localModel: state.localModel
            }),
        }
    )
);
