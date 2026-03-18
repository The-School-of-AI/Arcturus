import React, { useState, useEffect } from 'react';
import { useTheme } from '@/components/theme';

interface TodoItem {
    id: string;
    text: string;
    done: boolean;
}

interface TodoListWidgetProps {
    title?: string;
    items?: TodoItem[];
    onUpdate?: (items: TodoItem[]) => void;
}

const TodoListWidget: React.FC<TodoListWidgetProps> = ({ title = 'Tasks', items: initialItems = [], onUpdate }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';
    const [items, setItems] = useState<TodoItem[]>(initialItems);

    useEffect(() => { setItems(initialItems); }, [initialItems]);

    const toggle = (id: string) => {
        const updated = items.map(it => it.id === id ? { ...it, done: !it.done } : it);
        setItems(updated);
        onUpdate?.(updated);
    };

    const doneCount = items.filter(i => i.done).length;
    const progress = items.length ? Math.round((doneCount / items.length) * 100) : 0;

    return (
        <div className={`w-full rounded-lg border overflow-hidden ${isDark ? 'bg-gray-800/50 border-gray-700' : 'bg-white border-gray-200 shadow-sm'}`}>
            <div className={`px-4 py-2 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                <div className="flex items-center justify-between">
                    <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{title}</h3>
                    <span className={`text-xs font-mono ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{doneCount}/{items.length}</span>
                </div>
                <div className={`mt-2 h-1.5 rounded-full overflow-hidden ${isDark ? 'bg-gray-700' : 'bg-gray-200'}`}>
                    <div
                        className="h-full rounded-full bg-green-500 transition-all duration-300"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>
            <div className="p-2 max-h-64 overflow-y-auto scrollbar-hide">
                {items.map(item => (
                    <div
                        key={item.id}
                        onClick={() => toggle(item.id)}
                        className={`flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer transition-colors ${isDark ? 'hover:bg-gray-700/40' : 'hover:bg-gray-50'}`}
                    >
                        <div className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                            item.done
                                ? 'bg-green-500 border-green-500'
                                : isDark ? 'border-gray-600' : 'border-gray-300'
                        }`}>
                            {item.done && <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                        </div>
                        <span className={`text-sm ${item.done ? 'line-through opacity-50' : ''} ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                            {item.text}
                        </span>
                    </div>
                ))}
                {items.length === 0 && <p className="text-xs text-center text-muted-foreground italic py-4">No tasks</p>}
            </div>
        </div>
    );
};

export default TodoListWidget;
