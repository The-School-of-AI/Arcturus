import React, { useEffect, useState } from 'react';
import { useAppStore } from '@/store'; // For explorerRootPath
import { API_BASE } from '@/lib/api';
import axios from 'axios';
import { CheckCircle2, Circle, Loader2, FileText, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TaskItem {
    id: string;
    text: string;
    completed: boolean;
    indent: number;
}

export const PlanSidebar = () => {
    const { explorerRootPath } = useAppStore();
    const [tasks, setTasks] = useState<TaskItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [planPath, setPlanPath] = useState<string | null>(null);

    // Effect to find and load task.md
    useEffect(() => {
        if (!explorerRootPath) return;

        const loadPlan = async () => {
            setLoading(true);
            setError(null);
            try {
                // 1. Check if task.md exists in root
                // For now, assume it's at root/task.md
                // Ideally we'd search, but let's start simple.
                const targetPath = `${explorerRootPath}/task.md`;

                // 2. Fetch content
                const res = await axios.get(`${API_BASE}/rag/document_content`, {
                    params: { path: targetPath }
                });

                if (res.data && res.data.content) {
                    setPlanPath(targetPath);
                    parseTasks(res.data.content);
                } else {
                    // Try .plan.md?
                    setError("No task.md found");
                    setTasks([]);
                }
            } catch (e) {
                console.error("Failed to load plan", e);
                setError("No task.md found in root");
                setTasks([]);
            } finally {
                setLoading(false);
            }
        };

        loadPlan();
    }, [explorerRootPath]);

    const parseTasks = (content: string) => {
        const lines = content.split('\n');
        const parsed: TaskItem[] = [];

        lines.forEach((line, index) => {
            // Match "- [ ]" or "- [x]" or "- [/]"
            const match = line.match(/^(\s*)-\s*\[([ x/])\]\s*(.*)/);
            if (match) {
                const indent = match[1].length;
                const statusChar = match[2];
                const text = match[3].trim();

                // Exclude HTML comments often used for IDs <!- id: 0 ->
                const cleanText = text.replace(/<!--.*-->/, '').trim();

                parsed.push({
                    id: `Line-${index}`,
                    text: cleanText,
                    completed: statusChar === 'x' || statusChar === 'X', // Treat '/' as in-progress (not checked visually yet?)
                    indent: indent
                });
            }
        });
        setTasks(parsed);
    };

    if (!explorerRootPath) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground/50 p-4 text-center">
                <FileText className="w-8 h-8 mb-2 opacity-50" />
                <span className="text-xs">Open a workspace to view plans</span>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center text-muted-foreground">
                <Loader2 className="w-5 h-5 animate-spin" />
            </div>
        );
    }

    if (error && tasks.length === 0) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground/50 p-4 text-center">
                <AlertCircle className="w-8 h-8 mb-2 opacity-50" />
                <span className="text-xs">{error}</span>
                <span className="text-[10px] mt-2 opacity-60">Create a task.md file in your project root.</span>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-background">
            <div className="px-4 py-3 border-b border-border/40">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Active Plan</h3>
                {planPath && <p className="text-[9px] text-muted-foreground/50 truncate mt-1">{planPath.split('/').pop()}</p>}
            </div>

            <div className="flex-1 overflow-y-auto p-2">
                <div className="space-y-0.5">
                    {tasks.map(task => (
                        <div
                            key={task.id}
                            className={cn(
                                "flex items-start gap-2 px-2 py-1.5 rounded-md hover:bg-muted/50 transition-colors group select-none text-sm",
                                task.completed ? "opacity-50" : "opacity-100"
                            )}
                            style={{ paddingLeft: `${(task.indent / 2) * 8 + 8}px` }}
                        >
                            <div className={cn(
                                "mt-0.5",
                                task.completed ? "text-green-500" : "text-muted-foreground group-hover:text-foreground"
                            )}>
                                {task.completed ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Circle className="w-3.5 h-3.5" />}
                            </div>
                            <span className={cn(
                                "leading-relaxed text-[13px]",
                                task.completed && "line-through"
                            )}>
                                {task.text}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};
