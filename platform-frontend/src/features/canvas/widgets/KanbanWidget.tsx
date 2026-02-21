import React, { useState, useEffect } from 'react';
import {
    DndContext,
    closestCorners,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragOverlay,
    defaultDropAnimationSideEffects,
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
    useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

interface Task {
    id: string;
    content: string;
    columnId: string;
}

interface Column {
    id: string;
    title: string;
}

interface KanbanWidgetProps {
    initialTasks?: Task[];
    columns?: Column[];
    title?: string;
    onTaskUpdate?: (tasks: Task[]) => void;
}

const TaskItem = ({ task }: { task: Task }) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging
    } = useSortable({ id: task.id });

    // Determine badge color based on content keywords (simple heuristic for professional feel)
    const getPriorityColor = (content: string) => {
        if (content.toLowerCase().includes('security') || content.toLowerCase().includes('audit')) return 'bg-red-500/20 text-red-400 border-red-500/30';
        if (content.toLowerCase().includes('design') || content.toLowerCase().includes('ux')) return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
        if (content.toLowerCase().includes('performance')) return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    };

    const style = {
        transform: CSS.Translate.toString(transform),
        transition,
        opacity: isDragging ? 0.3 : 1,
        zIndex: isDragging ? 50 : 1,
    };

    return (
        <div
            ref={setNodeRef}
            style={style}
            {...attributes}
            {...listeners}
            className={`group relative p-4 mb-3 bg-gray-800/80 backdrop-blur-sm border border-gray-700 rounded-lg shadow-lg cursor-grab active:cursor-grabbing hover:border-blue-500/50 hover:bg-gray-700/80 transition-all duration-200 ease-out`}
        >
            <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium tracking-wide uppercase ${getPriorityColor(task.content)}`}>
                        {task.content.toLowerCase().includes('security') ? 'High Priority' : 'Standard'}
                    </span>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <div className="w-1.5 h-1.5 rounded-full bg-gray-600" />
                        <div className="w-1.5 h-1.5 rounded-full bg-gray-600" />
                    </div>
                </div>
                <p className="text-sm text-gray-100 font-medium leading-relaxed">
                    {task.content}
                </p>
                <div className="mt-1 flex items-center gap-2 text-[10px] text-gray-500">
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>Restored Today</span>
                </div>
            </div>

            {/* Hover subtle glow */}
            <div className="absolute inset-0 bg-blue-500/5 opacity-0 group-hover:opacity-100 rounded-lg transition-opacity pointer-events-none" />
        </div>
    );
};

const DroppableColumn = ({ column, tasks, children }: { column: Column; tasks: Task[]; children: React.ReactNode }) => {
    const { setNodeRef, isOver } = useSortable({
        id: column.id,
        data: {
            type: 'Column',
            column,
        },
    });

    return (
        <div
            ref={setNodeRef}
            className={`w-72 flex-shrink-0 flex flex-col bg-gray-900/40 rounded-xl p-4 border transition-all duration-300 ${isOver ? 'border-blue-500/60 bg-blue-500/5 ring-1 ring-blue-500/20' : 'border-gray-800'
                }`}
        >
            <div className="flex items-center justify-between mb-5 px-1">
                <div className="flex items-center gap-2">
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">{column.title}</h4>
                    <span className="bg-gray-800 text-gray-500 text-[10px] font-bold px-2 py-0.5 rounded-full border border-gray-700">
                        {tasks.length}
                    </span>
                </div>
                <button className="text-gray-600 hover:text-blue-400 p-1 hover:bg-blue-500/10 rounded transition-all">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                </button>
            </div>

            <SortableContext
                items={tasks.map(t => t.id)}
                strategy={verticalListSortingStrategy}
            >
                <div className="flex-1 min-h-[300px] scrollbar-hide">
                    {children}
                </div>
            </SortableContext>
        </div>
    );
};

const KanbanWidget: React.FC<KanbanWidgetProps> = ({
    initialTasks = [],
    columns = [
        { id: 'todo', title: 'To Do' },
        { id: 'in_progress', title: 'In Progress' },
        { id: 'done', title: 'Done' }
    ],
    title,
    onTaskUpdate
}) => {
    const [tasks, setTasks] = useState<Task[]>(initialTasks);
    const [activeId, setActiveId] = useState<string | null>(null);

    // Sync state if initialTasks changes from server
    useEffect(() => {
        setTasks(initialTasks);
    }, [initialTasks]);

    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    const handleDragStart = (event: any) => {
        setActiveId(event.active.id);
    };

    const handleDragOver = (event: any) => {
        const { active, over } = event;
        if (!over) return;

        const activeId = active.id;
        const overId = over.id;

        if (activeId === overId) return;

        const activeTask = tasks.find(t => t.id === activeId);
        if (!activeTask) return;

        // 1. Dragging over another task
        const overTask = tasks.find(t => t.id === overId);
        if (overTask && activeTask.columnId !== overTask.columnId) {
            setTasks((prev) => {
                const updated = prev.map(t => t.id === activeId ? { ...t, columnId: overTask.columnId } : t);
                // Optimistic broadcast
                onTaskUpdate?.(updated);
                return updated;
            });
            return;
        }

        // 2. Dragging over a column container directly
        const isOverColumn = columns.some(c => c.id === overId);
        if (isOverColumn && activeTask.columnId !== overId) {
            setTasks((prev) => {
                const updated = prev.map(t => t.id === activeId ? { ...t, columnId: overId as string } : t);
                onTaskUpdate?.(updated);
                return updated;
            });
        }
    };

    const handleDragEnd = (event: any) => {
        const { active, over } = event;
        setActiveId(null);

        if (!over) return;

        if (active.id !== over.id) {
            const oldIndex = tasks.findIndex(t => t.id === active.id);
            const newIndex = tasks.findIndex(t => t.id === over.id);

            if (oldIndex !== -1 && newIndex !== -1) {
                const updatedTasks = arrayMove(tasks, oldIndex, newIndex);
                setTasks(updatedTasks);
                onTaskUpdate?.(updatedTasks);
            }
        }
    };

    return (
        <div className="w-full bg-gray-950/90 rounded-2xl overflow-hidden border border-gray-800 shadow-2xl flex flex-col ring-1 ring-white/5">
            {title && (
                <div className="bg-gradient-to-r from-gray-900 via-gray-800 to-gray-900 px-6 py-4 border-b border-gray-800 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-1.5 bg-blue-600/20 rounded-lg border border-blue-500/30">
                            <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                            </svg>
                        </div>
                        <h3 className="text-sm font-bold text-gray-200 tracking-tight">{title}</h3>
                    </div>
                    <div className="flex items-center gap-4">
                        <span className="text-[10px] text-gray-500 font-mono tracking-tighter uppercase">Board Sync Active</span>
                        <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)] animate-pulse" />
                    </div>
                </div>
            )}
            <div className="p-6 flex space-x-6 overflow-x-auto min-h-[500px] custom-scrollbar">
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCorners}
                    onDragStart={handleDragStart}
                    onDragOver={handleDragOver}
                    onDragEnd={handleDragEnd}
                >
                    {columns.map(column => {
                        const columnTasks = tasks.filter(t => t.columnId === column.id);
                        return (
                            <DroppableColumn key={column.id} column={column} tasks={columnTasks}>
                                {columnTasks.map(task => (
                                    <TaskItem key={task.id} task={task} />
                                ))}
                            </DroppableColumn>
                        );
                    })}
                    <DragOverlay dropAnimation={{
                        duration: 250,
                        easing: 'cubic-bezier(0.18, 0.67, 0.6, 1.22)',
                    }}>
                        {activeId ? (
                            <div className="p-4 bg-blue-600/90 backdrop-blur-md border border-blue-400 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] text-sm text-white scale-105 rotate-1 cursor-grabbing ring-4 ring-blue-500/20">
                                <p className="font-bold mb-1 opacity-70 text-[10px] uppercase">Moving Task</p>
                                {tasks.find(t => t.id === activeId)?.content}
                            </div>
                        ) : null}
                    </DragOverlay>
                </DndContext>
            </div>

            <style dangerouslySetInnerHTML={{
                __html: `
                .custom-scrollbar::-webkit-scrollbar {
                    height: 8px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: transparent;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: #1f2937;
                    border-radius: 10px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: #374151;
                }
                .scrollbar-hide::-webkit-scrollbar {
                    display: none;
                }
            `}} />
        </div>
    );
};

export default KanbanWidget;
