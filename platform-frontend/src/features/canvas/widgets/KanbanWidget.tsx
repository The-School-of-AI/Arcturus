import React, { useState } from 'react';
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

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    return (
        <div
            ref={setNodeRef}
            style={style}
            {...attributes}
            {...listeners}
            className="p-3 mb-2 bg-gray-700 border border-gray-600 rounded shadow-sm text-sm text-gray-200 cursor-grab active:cursor-grabbing hover:border-blue-500 transition-colors"
        >
            {task.content}
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
        const overTask = tasks.find(t => t.id === overId);
        const overColumn = columns.find(c => c.id === overId);

        if (!activeTask) return;

        // If dragging over a task in a different column
        if (overTask && activeTask.columnId !== overTask.columnId) {
            const updatedTasks = tasks.map(t => {
                if (t.id === activeId) {
                    return { ...t, columnId: overTask.columnId };
                }
                return t;
            });
            setTasks(updatedTasks);
            onTaskUpdate?.(updatedTasks);
        }

        // If dragging over an empty column
        if (overColumn && activeTask.columnId !== overColumn.id) {
            const updatedTasks = tasks.map(t => {
                if (t.id === activeId) {
                    return { ...t, columnId: overColumn.id };
                }
                return t;
            });
            setTasks(updatedTasks);
            onTaskUpdate?.(updatedTasks);
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
        <div className="w-full bg-gray-900 rounded-lg overflow-hidden border border-gray-700 shadow-xl flex flex-col">
            {title && (
                <div className="bg-gray-800 px-4 py-2 border-b border-gray-700">
                    <h3 className="text-sm font-semibold text-gray-300">{title}</h3>
                </div>
            )}
            <div className="p-4 flex space-x-4 overflow-x-auto min-h-[400px]">
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCorners}
                    onDragStart={handleDragStart}
                    onDragOver={handleDragOver}
                    onDragEnd={handleDragEnd}
                >
                    {columns.map(column => (
                        <div key={column.id} className="w-64 flex-shrink-0 bg-gray-800/50 rounded-lg p-3 border border-gray-700">
                            <h4 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-4 px-1">{column.title}</h4>
                            <SortableContext
                                items={tasks.filter(t => t.columnId === column.id).map(t => t.id)}
                                strategy={verticalListSortingStrategy}
                            >
                                <div className="min-h-[100px]">
                                    {tasks
                                        .filter(task => task.columnId === column.id)
                                        .map(task => (
                                            <TaskItem key={task.id} task={task} />
                                        ))}
                                </div>
                            </SortableContext>
                        </div>
                    ))}
                    <DragOverlay>
                        {activeId ? (
                            <div className="p-3 bg-blue-600/50 border border-blue-500 rounded shadow-lg text-sm text-white">
                                {tasks.find(t => t.id === activeId)?.content}
                            </div>
                        ) : null}
                    </DragOverlay>
                </DndContext>
            </div>
        </div>
    );
};

export default KanbanWidget;
