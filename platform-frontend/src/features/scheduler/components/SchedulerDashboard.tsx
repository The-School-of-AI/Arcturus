import React, { useEffect, useState } from 'react';
import { useAppStore } from '@/store';
import {
    CalendarClock, Plus, Trash2, Play,
    MoreVertical, RefreshCw, Clock
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { formatDistanceToNow, format } from 'date-fns';

export const SchedulerDashboard: React.FC = () => {
    const { jobs, fetchJobs, createJob, deleteJob } = useAppStore();
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(false);

    // Form State
    const [editingJobId, setEditingJobId] = useState<string | null>(null);
    const [newName, setNewName] = useState('');
    const [newCron, setNewCron] = useState('0 9 * * *');
    const [newQuery, setNewQuery] = useState('');

    // Simple Mode State
    const [mode, setMode] = useState<'simple' | 'advanced'>('simple');
    const [simpleFrequency, setSimpleFrequency] = useState('daily');
    const [simpleTime, setSimpleTime] = useState('09:00');

    useEffect(() => {
        fetchJobs();
        const interval = setInterval(fetchJobs, 60000); // Poll every minute
        return () => clearInterval(interval);
    }, [fetchJobs]);

    const generateCronFromSimple = () => {
        if (simpleFrequency === 'every_10_min') return '*/10 * * * *';
        if (simpleFrequency === 'hourly') return '0 * * * *';

        const [hours, mins] = simpleTime.split(':').map(Number);

        if (simpleFrequency === 'daily') {
            return `${mins || 0} ${hours || 0} * * *`;
        }

        if (simpleFrequency === 'weekly') {
            return `${mins || 0} ${hours || 0} * * 1`; // Monday default
        }

        return '0 9 * * *';
    };

    const openCreateDialog = () => {
        setEditingJobId(null);
        setNewName('');
        setNewQuery('');
        setNewCron('0 9 * * *');
        setMode('simple');
        setSimpleFrequency('daily');
        setSimpleTime('09:00');
        setIsCreateOpen(true);
    };

    const openEditDialog = (job: any) => {
        setEditingJobId(job.id);
        setNewName(job.name);
        setNewQuery(job.query);
        setNewCron(job.cron_expression);
        setMode('advanced'); // Default to advanced for editing existing
        setIsCreateOpen(true);
    };

    const handleSave = async () => {
        const finalCron = mode === 'simple' ? generateCronFromSimple() : newCron;

        if (!newName || !finalCron || !newQuery) return;

        setIsLoading(true);
        try {
            if (editingJobId) {
                // Delete old and create new (MVP approach since update API might vary)
                await deleteJob(editingJobId);
            }

            await createJob({
                name: newName,
                cron: finalCron,
                query: newQuery,
                agent_type: 'PlannerAgent'
            });

            setIsCreateOpen(false);
        } catch (e) {
            console.error(e);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-background/50 backdrop-blur-sm">
            {/* Header */}
            <div className="p-6 border-b border-border/50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-3 bg-neon-cyan/10 rounded-xl border border-neon-cyan/20">
                        <CalendarClock className="w-6 h-6 text-neon-cyan" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold tracking-tight">Scheduler</h1>
                        <p className="text-xs text-muted-foreground uppercase tracking-widest">
                            {jobs.length} Active Jobs
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => fetchJobs()}
                        className="gap-2"
                    >
                        <RefreshCw className="w-4 h-4" />
                        Refresh
                    </Button>
                    <Button
                        size="sm"
                        onClick={() => openCreateDialog()}
                        className="bg-neon-cyan text-black hover:bg-neon-cyan/90 gap-2 font-semibold"
                    >
                        <Plus className="w-4 h-4" />
                        Create Job
                    </Button>
                </div>
            </div>

            {/* List */}
            <ScrollArea className="flex-1 p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {jobs.map(job => (
                        <div
                            key={job.id}
                            className="group relative bg-card/50 border border-border/50 rounded-xl p-5 hover:border-neon-cyan/50 hover:bg-neon-cyan/5 transition-all duration-300 flex flex-col gap-4"
                        >
                            <div className="flex justify-between items-start">
                                <div>
                                    <h3 className="font-bold text-lg truncate pr-4">{job.name}</h3>
                                    <div className="flex items-center gap-2 mt-1">
                                        <Badge variant="outline" className="font-mono text-[10px] bg-muted/50">
                                            {job.cron_expression}
                                        </Badge>
                                        <Badge variant="outline" className={cn(
                                            "font-mono text-[10px]",
                                            job.status === 'running' ? "bg-neon-yellow/10 text-neon-yellow border-neon-yellow/30" :
                                                job.status === 'failed' ? "bg-red-500/10 text-red-500 border-red-500/30" :
                                                    "bg-green-500/10 text-green-500 border-green-500/30"
                                        )}>
                                            {job.status || 'SCHEDULED'}
                                        </Badge>
                                    </div>
                                </div>
                                <div className="hidden group-hover:flex gap-1 transition-opacity">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-8 w-8 hover:bg-white/10"
                                        onClick={() => openEditDialog(job)}
                                        title="Edit Job"
                                    >
                                        <MoreVertical className="w-4 h-4" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-8 w-8 hover:text-red-400 hover:bg-red-500/10"
                                        onClick={() => confirm('Delete job?') && deleteJob(job.id)}
                                        title="Delete Job"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </Button>
                                </div>
                            </div>

                            <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                                <p className="text-sm font-mono text-muted-foreground line-clamp-2">
                                    "{job.query}"
                                </p>
                            </div>

                            {/* Latest Result Preview */}
                            {job.last_output && (
                                <div className="p-2.5 bg-neon-cyan/5 rounded-lg border border-neon-cyan/10 space-y-1">
                                    <div className="flex items-center justify-between">
                                        <span className="text-[9px] font-bold uppercase text-neon-cyan/70 tracking-tighter">Latest Result</span>
                                    </div>
                                    <p className="text-[10px] text-foreground/70 line-clamp-2 leading-tight">
                                        {job.last_output}
                                    </p>
                                </div>
                            )}

                            <div className="mt-auto pt-4 border-t border-white/5 flex items-center justify-between text-xs text-muted-foreground">
                                <div className="flex flex-col gap-0.5">
                                    <span className="uppercase tracking-wider text-[9px] opacity-70">Next Run</span>
                                    <span className="flex items-center gap-1.5 font-medium text-neon-cyan">
                                        <Clock className="w-3 h-3" />
                                        {job.next_run ? format(new Date(job.next_run), 'MMM d, h:mm a') : 'Calculating...'}
                                    </span>
                                </div>
                                {job.last_run && (
                                    <div className="flex flex-col gap-0.5 text-right">
                                        <span className="uppercase tracking-wider text-[9px] opacity-70">Last Run</span>
                                        <span className="flex items-center gap-1.5 font-medium">
                                            {formatDistanceToNow(new Date(job.last_run))} ago
                                        </span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}

                    {/* Empty State */}
                    {jobs.length === 0 && (
                        <div className="col-span-full py-20 flex flex-col items-center justify-center text-center opacity-40 gap-4">
                            <div className="p-6 bg-muted/50 rounded-full">
                                <CalendarClock className="w-12 h-12" />
                            </div>
                            <div>
                                <h3 className="text-lg font-medium">No Scheduled Jobs</h3>
                                <p className="text-sm">Create a cron job to run agents automatically.</p>
                            </div>
                        </div>
                    )}
                </div>
            </ScrollArea>

            {/* Create/Edit Dialog */}
            <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{editingJobId ? 'Edit Scheduled Task' : 'Create Scheduled Task'}</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <label className="text-xs font-medium uppercase text-muted-foreground">Task Name</label>
                            <Input
                                placeholder="e.g. Morning Briefing"
                                value={newName}
                                onChange={(e) => setNewName(e.target.value)}
                            />
                        </div>

                        {/* Mode Toggle */}
                        <div className="flex items-center gap-4 border-b border-border/50 pb-2">
                            <button
                                onClick={() => setMode('simple')}
                                className={cn(
                                    "text-xs font-bold uppercase transition-colors hover:text-white",
                                    mode === 'simple' ? "text-neon-cyan border-b-2 border-neon-cyan" : "text-muted-foreground"
                                )}
                            >
                                Simple Mode
                            </button>
                            <button
                                onClick={() => setMode('advanced')}
                                className={cn(
                                    "text-xs font-bold uppercase transition-colors hover:text-white",
                                    mode === 'advanced' ? "text-neon-cyan border-b-2 border-neon-cyan" : "text-muted-foreground"
                                )}
                            >
                                Advanced (Cron)
                            </button>
                        </div>

                        {/* Simple Mode UI */}
                        {mode === 'simple' && (
                            <div className="space-y-3 bg-white/5 p-3 rounded-md border border-white/10">
                                <div className="space-y-1">
                                    <label className="text-[10px] font-medium uppercase text-muted-foreground">Frequency</label>
                                    <select
                                        className="w-full bg-black/50 border border-white/10 rounded-md p-2 text-sm text-white focus:outline-none focus:border-neon-cyan"
                                        value={simpleFrequency}
                                        onChange={(e) => setSimpleFrequency(e.target.value)}
                                    >
                                        <option value="every_10_min">Every 10 Minutes</option>
                                        <option value="hourly">Hourly</option>
                                        <option value="daily">Daily</option>
                                        <option value="weekly">Weekly</option>
                                    </select>
                                </div>

                                {(simpleFrequency === 'daily' || simpleFrequency === 'weekly') && (
                                    <div className="space-y-1">
                                        <label className="text-[10px] font-medium uppercase text-muted-foreground">Time</label>
                                        <Input
                                            type="time"
                                            value={simpleTime}
                                            onChange={(e) => setSimpleTime(e.target.value)}
                                            className="bg-black/50"
                                        />
                                    </div>
                                )}

                                <div className="text-[10px] text-muted-foreground pt-1">
                                    Will run as: <code className="text-neon-cyan">{generateCronFromSimple()}</code>
                                </div>
                            </div>
                        )}

                        {/* Advanced Mode UI */}
                        {mode === 'advanced' && (
                            <div className="space-y-2">
                                <label className="text-xs font-medium uppercase text-muted-foreground">Cron Expression</label>
                                <div className="flex gap-2">
                                    <Input
                                        placeholder="* * * * *"
                                        className="font-mono bg-muted/50"
                                        value={newCron}
                                        onChange={(e) => setNewCron(e.target.value)}
                                    />
                                    <div className="text-[10px] text-muted-foreground flex flex-col justify-center min-w-[100px]">
                                        <div>* * * * *</div>
                                        <div>min hr day mo wkd</div>
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="space-y-2">
                            <label className="text-xs font-medium uppercase text-muted-foreground">Agent Instructions</label>
                            <div className="relative">
                                <Input
                                    placeholder="What should the agent do?"
                                    value={newQuery}
                                    onChange={(e) => setNewQuery(e.target.value)}
                                />
                                <Play className="w-3 h-3 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                            </div>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
                        <Button
                            className="bg-neon-cyan text-black hover:bg-neon-cyan/90"
                            disabled={isLoading}
                            onClick={handleSave}
                        >
                            {isLoading ? 'Saving...' : (editingJobId ? 'Update Task' : 'Schedule Task')}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
