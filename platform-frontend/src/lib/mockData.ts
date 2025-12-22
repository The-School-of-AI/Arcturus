import type { Run, PlatformNode, PlatformEdge, Snapshot } from '../types';

export const mockRuns: Run[] = [
    {
        id: 'run-1',
        name: 'Research Competitors',
        createdAt: Date.now() - 10000000,
        status: 'completed',
        model: 'gemini-2.0-pro',
        ragEnabled: true,
    },
    {
        id: 'run-2',
        name: 'Debugging Login Flow',
        createdAt: Date.now() - 3600000,
        status: 'failed',
        model: 'mistral:latest',
        ragEnabled: false,
    },
    {
        id: 'run-3',
        name: 'Generate Unit Tests',
        createdAt: Date.now(),
        status: 'running',
        model: 'gemini-2.0-pro',
        ragEnabled: true,
    }
];

export const mockNodes: PlatformNode[] = [
    {
        id: '1',
        type: 'agentNode',
        position: { x: 0, y: 0 },
        data: { label: 'Planner', type: 'Planner', status: 'completed', result: 'Plan created.' }
    },
    {
        id: '2',
        type: 'agentNode',
        position: { x: 0, y: 150 },
        data: { label: 'Retriever', type: 'Retriever', status: 'completed', result: 'Found 5 docs.' }
    },
    {
        id: '3',
        type: 'agentNode',
        position: { x: 0, y: 300 },
        data: { label: 'Thinker', type: 'Thinker', status: 'running', logs: ['Analyzing...', 'Reasoning...'] }
    },
    {
        id: '4',
        type: 'agentNode',
        position: { x: 0, y: 450 },
        data: { label: 'Coder', type: 'Coder', status: 'pending' }
    }
];

export const mockEdges: PlatformEdge[] = [
    { id: 'e1-2', source: '1', target: '2', type: 'custom', animated: false, style: { stroke: '#888888' } },
    { id: 'e2-3', source: '2', target: '3', type: 'custom', animated: false, style: { stroke: '#888888' } },
    { id: 'e3-4', source: '3', target: '4', type: 'custom', animated: false, style: { stroke: '#888888' } },
];
