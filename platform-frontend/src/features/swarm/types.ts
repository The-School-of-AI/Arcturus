// features/swarm/types.ts — Swarm UI shared TypeScript types

export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'failed';
export type TaskPriority = 'low' | 'medium' | 'high' | 'critical';

export interface SwarmTask {
  task_id: string;
  title: string;
  status: TaskStatus;
  assigned_to: string;
  priority: TaskPriority;
  dependencies: string[];
  token_used: number;
  cost_usd: number;
  result: string | null;
}

export interface SwarmStatus {
  run_id: string;
  tasks: SwarmTask[];
  tokens_used: number;
  cost_usd: number;
  paused: boolean;
}

export interface SwarmEvent {
  timestamp: string;
  type: string;
  source: string;
  data: Record<string, unknown>;
}

export interface AgentLogEntry {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

export interface SwarmTemplate {
  name: string;
  description: string;
  tasks_template: Array<{
    title: string;
    description: string;
    assigned_to: string;
    priority: TaskPriority;
  }>;
}

export type InterventionAction = 'pause' | 'resume' | 'message' | 'reassign' | 'abort';

export interface InterventionPayload {
  action: InterventionAction;
  agent_id?: string;
  content?: string;
  task_id?: string;
  new_role?: string;
}
