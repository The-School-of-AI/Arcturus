import React, { useEffect, useState, useMemo } from 'react';
import { useAppStore } from '@/store';
import {
    CalendarClock, Play, Clock, RefreshCw, CheckCircle2,
    XCircle, Loader2, AlertCircle, Trash2, ChevronDown, ChevronUp, Pencil
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { formatDistanceToNow, format } from 'date-fns';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useTheme } from '@/components/theme';
import { JobFormDialog } from './JobFormDialog';

/** Strip code fences that LLMs add around markdown (anywhere in text, not just wrapping) */
function cleanMarkdown(text: string): string {
    // Remove all ```markdown ... ``` or ```md ... ``` or bare ``` ... ``` fences,
    // replacing them with their inner content so ReactMarkdown renders it as markdown
    return text.trim().replace(/```(?:markdown|md)?\s*\n([\s\S]*?)```/g, '$1');
}

/** Expandable markdown text block */
const ExpandableText: React.FC<{ text: string; className?: string }> = ({ text, className }) => {
    const [expanded, setExpanded] = useState(false);
    const { theme } = useTheme();
    const isLong = text.length > 200;
    const cleaned = cleanMarkdown(text);

    return (
        <div className={className}>
            <div className={cn(
                "text-[13px] leading-relaxed prose prose-sm max-w-none",
                theme === 'dark' ? "prose-invert" : "",
                "[&_h1]:text-base [&_h1]:font-semibold [&_h1]:mt-3 [&_h1]:mb-1.5",
                "[&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mt-2.5 [&_h2]:mb-1",
                "[&_h3]:text-[13px] [&_h3]:font-medium [&_h3]:mt-2 [&_h3]:mb-0.5",
                "[&_p]:text-[13px] [&_p]:leading-relaxed [&_p]:my-1.5",
                "[&_li]:text-[13px] [&_ul]:my-1 [&_ol]:my-1",
                "[&_table]:text-xs [&_table]:border-collapse [&_table]:w-full",
                "[&_th]:border [&_th]:border-border/50 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:font-semibold [&_th]:bg-muted/30",
                "[&_td]:border [&_td]:border-border/50 [&_td]:px-2 [&_td]:py-1",
                "[&_strong]:font-semibold",
                "[&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:italic [&_blockquote]:text-muted-foreground",
                "[&_pre]:bg-muted/50 [&_pre]:rounded-md [&_pre]:p-2 [&_pre]:text-xs [&_pre]:overflow-x-auto",
                "[&_code]:text-xs [&_code]:bg-muted/50 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded",
                !expanded && isLong && "line-clamp-4"
            )}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{cleaned}</ReactMarkdown>
            </div>
            {isLong && (
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="mt-1 text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
                >
                    {expanded ? <><ChevronUp className="w-3 h-3" /> Show less</> : <><ChevronDown className="w-3 h-3" /> Show full output</>}
                </button>
            )}
        </div>
    );
};

export const SchedulerDashboard: React.FC = () => {
    const {
        jobs, selectedJobId, jobHistory, jobHistoryLoading, triggeredJobIds,
        fetchJobs, fetchJobHistory, triggerJob, deleteJob, selectJob, deleteJobHistoryEntry, updateJob
    } = useAppStore();
    const { theme } = useTheme();
    const isDark = theme === 'dark';

    const selectedJob = jobs.find((j: any) => j.id === selectedJobId);
    const isJobRunning = selectedJobId ? triggeredJobIds.has(selectedJobId) : false;

    const [isEditOpen, setIsEditOpen] = useState(false);

    const editInitialValues = useMemo(() => {
        if (!selectedJob) return undefined;
        return { name: selectedJob.name, cron: selectedJob.cron_expression, query: selectedJob.query };
    }, [selectedJob]);

    // Auto-refresh history when selected job changes
    useEffect(() => {
        if (selectedJobId) {
            fetchJobHistory(selectedJobId);
            const interval = setInterval(() => fetchJobHistory(selectedJobId), 30000);
            return () => clearInterval(interval);
        }
    }, [selectedJobId, fetchJobHistory]);

    // No job selected - show empty state
    if (!selectedJob) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-center p-12 opacity-40">
                <div className="p-8 bg-muted/50 rounded-full mb-6">
                    <CalendarClock className="w-16 h-16" />
                </div>
                <h2 className="text-xl font-bold tracking-tight">Select a Job</h2>
                <p className="text-sm text-muted-foreground mt-2 max-w-sm">
                    Choose a scheduled job from the left panel to view its execution history and details.
                </p>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            {/* Job Header */}
            <div className="flex-none p-4 border-b border-border/50 bg-background backdrop-blur-sm">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                            <div className={cn("p-2 rounded-lg border shrink-0", isDark ? "bg-info/10 border-info/20" : "bg-teal-50 border-teal-200")}>
                                <CalendarClock className={cn("w-4 h-4", isDark ? "text-info" : "text-teal-600")} />
                            </div>
                            <div className="min-w-0">
                                <h1 className="text-base font-bold tracking-tight truncate">{selectedJob.name}</h1>
                                <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                                    <Badge variant="outline" className="font-mono text-xs bg-muted/50">
                                        {selectedJob.cron_expression}
                                    </Badge>
                                    <Badge variant="outline" className={cn(
                                        "font-mono text-xs",
                                        selectedJob.status === 'running' ? "bg-primary/10 text-primary border-primary/30" :
                                            selectedJob.status === 'failed' ? "bg-red-500/10 text-red-500 border-red-500/30" :
                                                "bg-green-500/10 text-green-500 border-green-500/30"
                                    )}>
                                        {selectedJob.status || 'SCHEDULED'}
                                    </Badge>
                                    {selectedJob.skill_id && (
                                        <Badge variant="outline" className="text-xs bg-purple-500/10 text-purple-400 border-purple-500/30">
                                            Skill: {selectedJob.skill_id}
                                        </Badge>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Query */}
                        <div className="mt-3 p-2.5 bg-muted/50 rounded-lg border border-border/30">
                            <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground/60 mb-0.5">Instructions</p>
                            <p className="text-xs text-foreground/80 font-mono leading-relaxed">"{selectedJob.query}"</p>
                        </div>

                        {/* Meta */}
                        <div className="flex items-center gap-6 mt-3 text-xs text-muted-foreground">
                            <div className="flex flex-col gap-0.5">
                                <span className="text-2xs uppercase tracking-wider opacity-70">Next Run</span>
                                <span className={cn("flex items-center gap-1.5 font-medium text-[11px]", isDark ? "text-info" : "text-teal-600")}>
                                    <Clock className="w-3 h-3" />
                                    {selectedJob.next_run ? format(new Date(selectedJob.next_run), 'MMM d, h:mm a') : 'Calculating...'}
                                </span>
                            </div>
                            {selectedJob.last_run && (
                                <div className="flex flex-col gap-0.5">
                                    <span className="text-2xs uppercase tracking-wider opacity-70">Last Run</span>
                                    <span className="font-medium text-[11px]">
                                        {formatDistanceToNow(new Date(selectedJob.last_run))} ago
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1.5 shrink-0">
                        <Button
                            variant="outline"
                            size="sm"
                            className={cn(
                                "gap-1.5 h-8 text-xs",
                                isJobRunning
                                    ? isDark ? "text-primary border-primary/30 bg-primary/10 animate-pulse" : "text-amber-600 border-amber-300 bg-amber-50 animate-pulse"
                                    : isDark ? "text-info border-info/30 hover:bg-info/10 hover:border-info" : "text-teal-600 border-teal-300 hover:bg-teal-50 hover:border-teal-400"
                            )}
                            onClick={() => !isJobRunning && triggerJob(selectedJob.id)}
                            disabled={isJobRunning}
                        >
                            {isJobRunning ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                                <Play className="w-3 h-3 fill-current" />
                            )}
                            {isJobRunning ? 'Running...' : 'Run Now'}
                        </Button>
                        <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setIsEditOpen(true)}>
                            <Pencil className="w-3 h-3" />
                        </Button>
                        <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => { fetchJobs(); fetchJobHistory(selectedJob.id); }}>
                            <RefreshCw className="w-3 h-3" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                            onClick={() => { if (confirm(`Delete "${selectedJob.name}"?`)) deleteJob(selectedJob.id); }}
                        >
                            <Trash2 className="w-3 h-3" />
                        </Button>
                    </div>
                </div>
            </div>

            {/* Running Banner */}
            {isJobRunning && (
                <div className={cn("flex-none px-4 py-2 border-b", isDark ? "border-primary/20 bg-primary/5" : "border-amber-200 bg-amber-50")}>
                    <div className="flex items-center gap-2">
                        <Loader2 className={cn("w-3.5 h-3.5 animate-spin", isDark ? "text-primary" : "text-amber-600")} />
                        <span className={cn("text-xs font-medium", isDark ? "text-primary" : "text-amber-600")}>Job is executing...</span>
                        <span className="text-xs text-muted-foreground">Results will appear automatically when complete.</span>
                    </div>
                </div>
            )}

            {/* Execution History — first entry is "Latest Result" */}
            <div className="flex-1 overflow-hidden flex flex-col">
                <div className="flex-none px-4 pt-3 pb-1.5 flex items-center justify-between">
                    <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground/60">
                        Execution History
                    </h3>
                    <span className="text-xs text-muted-foreground font-mono">
                        {jobHistory.length} run{jobHistory.length !== 1 ? 's' : ''}
                    </span>
                </div>

                <ScrollArea className="flex-1 px-4 pb-4">
                    {jobHistoryLoading && jobHistory.length === 0 ? (
                        <div className="flex items-center justify-center py-16 opacity-50">
                            <Loader2 className="w-5 h-5 animate-spin" />
                        </div>
                    ) : jobHistory.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-16 text-center opacity-40 gap-3">
                            <AlertCircle className="w-8 h-8" />
                            <p className="text-sm">No execution history yet.</p>
                            <p className="text-xs text-muted-foreground">Results will appear here after the job runs.</p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {jobHistory.map((entry: any, i: number) => {
                                const isLatest = i === 0;
                                const isSuccess = entry.status === 'success';
                                const isPartial = entry.status === 'partial_failure';

                                return (
                                    <div
                                        key={entry.run_id || i}
                                        className={cn(
                                            "group/entry p-3 rounded-lg border transition-all bg-background",
                                            isLatest
                                                ? isDark ? "border-info/30 bg-info/5" : "border-teal-300 bg-teal-50/50"
                                                : isSuccess
                                                    ? "border-green-500/20 hover:border-green-500/30"
                                                    : isPartial
                                                        ? "border-amber-500/20 hover:border-amber-500/30"
                                                        : "border-red-500/20 hover:border-red-500/30"
                                        )}
                                    >
                                        <div className="flex items-center justify-between gap-3">
                                            <div className="flex items-center gap-2 min-w-0">
                                                {isLatest ? (
                                                    <CheckCircle2 className={cn("w-3.5 h-3.5 shrink-0", isDark ? "text-info" : "text-teal-600")} />
                                                ) : isSuccess ? (
                                                    <CheckCircle2 className="w-3.5 h-3.5 text-green-400 shrink-0" />
                                                ) : isPartial ? (
                                                    <AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                                                ) : (
                                                    <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
                                                )}
                                                <span className={cn(
                                                    "text-xs font-bold uppercase",
                                                    isLatest ? (isDark ? "text-info" : "text-teal-600") :
                                                        isSuccess ? "text-green-500" :
                                                            isPartial ? "text-amber-500" : "text-red-500"
                                                )}>
                                                    {isLatest ? 'LATEST RESULT' : isPartial ? 'PARTIAL FAILURE' : entry.status}
                                                </span>
                                                <span className="text-2xs text-muted-foreground font-mono truncate">
                                                    {entry.run_id}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2 shrink-0">
                                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                    {entry.started_at && (
                                                        <span className="flex items-center gap-1">
                                                            <Clock className="w-2.5 h-2.5" />
                                                            {format(new Date(entry.started_at), 'MMM d, h:mm a')}
                                                        </span>
                                                    )}
                                                    {entry.started_at && entry.finished_at && (
                                                        <span className="opacity-60">
                                                            ({formatDistanceToNow(new Date(entry.started_at))} ago)
                                                        </span>
                                                    )}
                                                </div>
                                                <button
                                                    className="p-1 rounded opacity-0 group-hover/entry:opacity-100 hover:bg-red-500/10 text-muted-foreground hover:text-red-400 transition-all"
                                                    title="Delete this run"
                                                    onClick={() => {
                                                        if (entry.run_id && selectedJobId) {
                                                            deleteJobHistoryEntry(selectedJobId, entry.run_id);
                                                        }
                                                    }}
                                                >
                                                    <Trash2 className="w-3 h-3" />
                                                </button>
                                            </div>
                                        </div>

                                        {/* Output or Error */}
                                        {entry.output_summary && (
                                            <ExpandableText
                                                text={entry.output_summary}
                                                className={cn(
                                                    "mt-2 pl-5.5",
                                                    isLatest ? "text-foreground/80" :
                                                        isPartial ? "text-amber-400/80" : "text-foreground/60"
                                                )}
                                            />
                                        )}
                                        {entry.error && (
                                            <ExpandableText
                                                text={entry.error}
                                                className="mt-2 pl-5.5 text-red-400/80 font-mono"
                                            />
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </ScrollArea>
            </div>

            {/* Edit Dialog — reuses the same form as Create */}
            <JobFormDialog
                open={isEditOpen}
                onOpenChange={setIsEditOpen}
                title="Edit Job"
                submitLabel="Save Changes"
                initialValues={editInitialValues}
                onSubmit={async (data) => {
                    if (!selectedJobId) return;
                    await updateJob(selectedJobId, data);
                    setIsEditOpen(false);
                }}
            />
        </div>
    );
};
