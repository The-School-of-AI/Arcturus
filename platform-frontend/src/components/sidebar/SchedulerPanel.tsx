import React, { useEffect, useState } from 'react';
import { Plus, Search, Clock, Trash2, CalendarClock, Play, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { JobFormDialog } from '@/features/scheduler/components/JobFormDialog';

export const SchedulerPanel: React.FC = () => {
    const { jobs, fetchJobs, createJob, deleteJob, selectedJobId, selectJob, triggerJob, triggeredJobIds } = useAppStore();
    const [searchQuery, setSearchQuery] = useState('');
    const [isCreateOpen, setIsCreateOpen] = useState(false);

    useEffect(() => {
        fetchJobs();
        const interval = setInterval(fetchJobs, 60000);
        return () => clearInterval(interval);
    }, [fetchJobs]);

    const filteredJobs = React.useMemo(() => {
        if (!searchQuery.trim()) return jobs;
        return jobs.filter((j: any) =>
            j.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            j.query.toLowerCase().includes(searchQuery.toLowerCase())
        );
    }, [jobs, searchQuery]);

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground">
            {/* Top bar */}
            <div className="p-2 border-b border-border/50 bg-muted/20 space-y-2 shrink-0">
                <div className="flex items-center gap-1.5">
                    <div className="relative flex-1 group">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                        <Input
                            className="w-full bg-background/50 border-transparent focus:bg-background focus:border-border rounded-md text-xs pl-8 pr-2 h-8 transition-all placeholder:text-muted-foreground"
                            placeholder="Search jobs..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background/80"
                        title="New Job"
                        onClick={() => setIsCreateOpen(true)}
                    >
                        <Plus className="w-4 h-4" />
                    </Button>
                </div>
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                    <CalendarClock className="w-3 h-3" />
                    {jobs.length} scheduled job{jobs.length !== 1 ? 's' : ''}
                </div>
            </div>

            {/* Job list */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
                {filteredJobs.map((job: any) => {
                    const isActive = selectedJobId === job.id;
                    const isRunning = triggeredJobIds.has(job.id);
                    return (
                        <div
                            key={job.id}
                            onClick={() => selectJob(job.id)}
                            className={cn(
                                "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer hover:shadow-md",
                                isRunning
                                    ? "border-primary/40 bg-primary/5 animate-pulse"
                                    : isActive
                                        ? "border-info/40 hover:border-info/60 bg-info/5"
                                        : "border-border/50 hover:border-primary/50 hover:bg-accent/50"
                            )}
                        >
                            <div className="flex justify-between items-start gap-3">
                                <div className="flex-1 min-w-0">
                                    <p className={cn(
                                        "text-[13px] leading-relaxed font-medium transition-all duration-300",
                                        isRunning ? "text-primary" :
                                            isActive ? "text-info" : "text-foreground group-hover:text-foreground/80"
                                    )}>
                                        {job.name}
                                    </p>
                                    <Badge variant="outline" className="mt-1 font-mono text-xs bg-muted/50">
                                        {job.cron_expression}
                                    </Badge>
                                </div>
                                {isRunning ? (
                                    <Badge variant="outline" className="font-mono text-2xs shrink-0 bg-primary/10 text-primary border-primary/30 animate-pulse">
                                        <Loader2 className="w-3 h-3 mr-1 animate-spin inline" />
                                        RUNNING
                                    </Badge>
                                ) : (
                                    <Badge variant="outline" className={cn(
                                        "font-mono text-2xs shrink-0",
                                        job.status === 'running' ? "bg-primary/10 text-primary border-primary/30" :
                                            job.status === 'failed' ? "bg-red-500/10 text-red-500 border-red-500/30" :
                                                "bg-green-500/10 text-green-500 border-green-500/30"
                                    )}>
                                        {job.status || 'SCHEDULED'}
                                    </Badge>
                                )}
                            </div>

                            {/* Footer - visible when active */}
                            {isActive && (
                                <div className="mt-4 pt-3 border-t border-border/50 flex items-center justify-between animate-in fade-in slide-in-from-top-2 duration-200">
                                    <div className="flex items-center gap-3">
                                        <span className="flex items-center gap-1 text-2xs text-muted-foreground font-mono">
                                            <Clock className="w-3 h-3" />
                                            {job.next_run ? format(new Date(job.next_run), 'MMM d, h:mm a') : '—'}
                                        </span>
                                        <button
                                            className="p-1 hover:bg-info/10 rounded text-muted-foreground hover:text-info transition-all duration-200"
                                            onClick={(e) => { e.stopPropagation(); triggerJob(job.id); }}
                                            title="Run now"
                                        >
                                            <Play className="w-3 h-3" />
                                        </button>
                                        <button
                                            className="p-1 hover:bg-red-500/10 rounded text-muted-foreground hover:text-red-400 transition-all duration-200"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                if (confirm('Delete this job?')) deleteJob(job.id);
                                            }}
                                            title="Delete job"
                                        >
                                            <Trash2 className="w-3 h-3" />
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}

                {filteredJobs.length === 0 && (
                    <div className="py-20 flex flex-col items-center justify-center text-center opacity-40 gap-4">
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

            {/* Create Dialog */}
            <JobFormDialog
                open={isCreateOpen}
                onOpenChange={setIsCreateOpen}
                title="Create Scheduled Task"
                submitLabel="Schedule Task"
                onSubmit={async (data) => {
                    await createJob({ name: data.name, cron: data.cron, query: data.query, agent_type: 'PlannerAgent' });
                    setIsCreateOpen(false);
                }}
            />
        </div>
    );
};
