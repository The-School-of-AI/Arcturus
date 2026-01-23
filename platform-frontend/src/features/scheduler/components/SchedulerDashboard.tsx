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
    const [newName, setNewName] = useState('');
    const [newCron, setNewCron] = useState('0 9 * * *');
    const [newQuery, setNewQuery] = useState('');

    useEffect(() => {
        fetchJobs();
        const interval = setInterval(fetchJobs, 60000); // Poll every minute
        return () => clearInterval(interval);
    }, [fetchJobs]);

    const handleCreate = async () => {
        if (!newName || !newCron || !newQuery) return;
        setIsLoading(true);
        try {
            await createJob({
                name: newName,
                cron: newCron,
                query: newQuery,
                agent_type: 'PlannerAgent'
            });
            setIsCreateOpen(false);
            setNewName('');
            setNewQuery('');
            setNewCron('0 9 * * *');
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
                        onClick={() => setIsCreateOpen(true)}
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
                                        <Badge variant="outline" className="font-mono text-[10px] bg-muted/50 text-muted-foreground">
                                            ID: {job.id}
                                        </Badge>
                                    </div>
                                </div>
                                <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-8 w-8 hover:text-red-400 hover:bg-red-500/10"
                                        onClick={() => confirm('Delete job?') && deleteJob(job.id)}
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

            {/* Create Dialog */}
            <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create Scheduled Task</DialogTitle>
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
                            onClick={handleCreate}
                        >
                            {isLoading ? 'Scheduling...' : 'Schedule Task'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
