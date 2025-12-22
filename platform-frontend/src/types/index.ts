import type { Node, Edge } from 'reactflow';

export type AgentType = 'Planner' | 'Retriever' | 'Thinker' | 'Coder' | 'Executor' | 'Evaluator' | 'Summarizer' | 'User';

export type RunStatus = 'running' | 'completed' | 'failed' | 'paused';

export interface Run {
    id: string;
    name: string;
    createdAt: number;
    status: RunStatus;
    model: string;
    ragEnabled: boolean;
}

export interface AgentNodeData {
    label: string;
    type: AgentType | 'Generic';
    status: 'pending' | 'running' | 'completed' | 'failed';
    description?: string;
    output?: string;
    error?: string;
    result?: string;
    logs?: string[];
    isDark?: boolean; // For styling
}

export type PlatformNode = Node<AgentNodeData>;
export type PlatformEdge = Edge;

export interface Snapshot {
    id: string;
    timestamp: number;
    nodeId: string | null;
    chatHistory: ChatMessage[];
    codeContent: string;
    webUrl: string | null;
    webContent: string | null;
    htmlOutput: string | null;
    graphState: {
        nodes: PlatformNode[];
        edges: PlatformEdge[];
    };
}

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: number;
}
