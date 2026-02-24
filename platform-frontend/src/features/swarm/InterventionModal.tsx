// features/swarm/InterventionModal.tsx
// Modal for sending manual intervention actions to the swarm:
// pause, resume, send message, reassign task, abort task.

import React, { useState } from 'react';
import { Zap, Pause, Play, MessageSquare, RefreshCw, XCircle } from 'lucide-react';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { useSwarmStore } from './useSwarmStore';
import { swarmApi } from './swarmApi';
import type { InterventionAction } from './types';
import { cn } from '@/lib/utils';

type ActionOption = {
    id: InterventionAction;
    label: string;
    icon: React.FC<{ className?: string }>;
    color: string;
    description: string;
};

const ACTIONS: ActionOption[] = [
    { id: 'message', label: 'Send Message', icon: MessageSquare, color: 'text-primary', description: 'Inject a message to the selected agent' },
    { id: 'pause', label: 'Pause Swarm', icon: Pause, color: 'text-yellow-400', description: 'Pause execution between dispatches' },
    { id: 'resume', label: 'Resume Swarm', icon: Play, color: 'text-green-400', description: 'Resume a paused swarm' },
    { id: 'reassign', label: 'Reassign Task', icon: RefreshCw, color: 'text-blue-400', description: 'Move a task to a different worker role' },
    { id: 'abort', label: 'Abort Task', icon: XCircle, color: 'text-red-400', description: 'Immediately mark a task as failed' },
];

export const InterventionModal: React.FC = () => {
    const activeRunId = useSwarmStore(s => s.activeRunId);
    const isOpen = useSwarmStore(s => s.isInterventionOpen);
    const setOpen = useSwarmStore(s => s.setInterventionOpen);
    const selectedAgentId = useSwarmStore(s => s.selectedAgentId);
    const tasks = useSwarmStore(s => s.tasks);

    const [selectedAction, setSelectedAction] = useState<InterventionAction>('message');
    const [content, setContent] = useState('');
    const [taskId, setTaskId] = useState('');
    const [newRole, setNewRole] = useState('');
    const [isSending, setIsSending] = useState(false);
    const [feedback, setFeedback] = useState<string | null>(null);

    const handleSend = async () => {
        if (!activeRunId) return;
        setIsSending(true);
        setFeedback(null);
        try {
            await swarmApi.intervene(activeRunId, {
                action: selectedAction,
                agent_id: selectedAgentId ?? undefined,
                content: content || undefined,
                task_id: taskId || undefined,
                new_role: newRole || undefined,
            });
            setFeedback('✓ Intervention sent successfully');
            setTimeout(() => setOpen(false), 1000);
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : 'Failed to send intervention';
            setFeedback(`✗ ${msg}`);
        } finally {
            setIsSending(false);
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={setOpen}>
            <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-foreground">
                        <Zap className="w-4 h-4 text-primary" />
                        Manual Intervention
                    </DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-2">
                    {/* Action selector */}
                    <div className="grid grid-cols-1 gap-1.5">
                        {ACTIONS.map(action => {
                            const Icon = action.icon;
                            return (
                                <button
                                    key={action.id}
                                    onClick={() => setSelectedAction(action.id)}
                                    className={cn(
                                        'flex items-center gap-3 p-2.5 rounded-lg border text-left transition-all',
                                        selectedAction === action.id
                                            ? 'border-primary bg-primary/10'
                                            : 'border-border hover:border-primary/40 hover:bg-muted/50'
                                    )}
                                >
                                    <Icon className={cn('w-4 h-4 shrink-0', action.color)} />
                                    <div>
                                        <p className="text-xs font-semibold text-foreground">{action.label}</p>
                                        <p className="text-[10px] text-muted-foreground">{action.description}</p>
                                    </div>
                                </button>
                            );
                        })}
                    </div>

                    {/* Context inputs */}
                    {selectedAction === 'message' && (
                        <div className="space-y-1.5">
                            <Label className="text-xs text-muted-foreground">
                                Target: <span className="text-foreground font-mono">{selectedAgentId ?? '(none selected)'}</span>
                            </Label>
                            <Textarea
                                placeholder="Type your message to the agent…"
                                value={content}
                                onChange={e => setContent(e.target.value)}
                                className="text-sm resize-none h-24 bg-muted border-input"
                            />
                        </div>
                    )}

                    {(selectedAction === 'reassign' || selectedAction === 'abort') && (
                        <div className="space-y-2">
                            <div className="space-y-1">
                                <Label className="text-xs">Task</Label>
                                <select
                                    className="w-full text-xs rounded-md border border-input bg-muted px-2 py-1.5 text-foreground"
                                    value={taskId}
                                    onChange={e => setTaskId(e.target.value)}
                                >
                                    <option value="">Select a task…</option>
                                    {tasks.filter(t => t.status !== 'completed').map(t => (
                                        <option key={t.task_id} value={t.task_id}>{t.title}</option>
                                    ))}
                                </select>
                            </div>
                            {selectedAction === 'reassign' && (
                                <div className="space-y-1">
                                    <Label className="text-xs">New Role</Label>
                                    <Input
                                        placeholder="e.g. web_researcher"
                                        value={newRole}
                                        onChange={e => setNewRole(e.target.value)}
                                        className="text-xs bg-muted border-input"
                                    />
                                </div>
                            )}
                        </div>
                    )}

                    {feedback && (
                        <p className={cn(
                            'text-xs text-center py-1 rounded',
                            feedback.startsWith('✓') ? 'text-green-400' : 'text-red-400'
                        )}>
                            {feedback}
                        </p>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => setOpen(false)} className="border-border text-foreground">
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSend}
                        disabled={isSending}
                        className="bg-primary text-white hover:bg-primary/90"
                    >
                        {isSending ? 'Sending…' : 'Send'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
