import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
    Run,
    PlatformNode,
    PlatformEdge,
    Snapshot,
} from '../types';
import { applyNodeChanges, applyEdgeChanges, type NodeChange, type EdgeChange } from 'reactflow';

// --- Slices Types ---

interface RunSlice {
    runs: Run[];
    currentRun: Run | null;
    addRun: (run: Run) => void;
    setCurrentRun: (runId: string) => void;
    updateRunStatus: (input: { id: string, status: Run['status'] }) => void;
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
            setCurrentRun: (runId) => set((state) => ({
                currentRun: state.runs.find((r) => r.id === runId) || null
            })),
            updateRunStatus: ({ id, status }) => set((state) => ({
                runs: state.runs.map((r) => r.id === id ? { ...r, status } : r),
                currentRun: state.currentRun?.id === id ? { ...state.currentRun, status } : state.currentRun
            })),

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
            selectNode: (nodeId) => set({ selectedNodeId: nodeId }),

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
                runs: state.runs,
                apiKey: state.apiKey,
                localModel: state.localModel
                // Don't persist ephemeral graph state or huge snapshots for now unless needed
            }),
        }
    )
);
