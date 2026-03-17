import React, { useState } from 'react';
import { useTheme } from '@/components/theme';

interface JSONViewerWidgetProps {
    data: any;
    title?: string;
    defaultExpanded?: boolean;
}

const JSONNode: React.FC<{ name: string; value: any; depth: number; isDark: boolean; defaultExpanded: boolean }> = ({ name, value, depth, isDark, defaultExpanded }) => {
    const [expanded, setExpanded] = useState(defaultExpanded && depth < 2);
    const isObject = value !== null && typeof value === 'object';
    const isArray = Array.isArray(value);
    const entries = isObject ? Object.entries(value) : [];

    const indent = depth * 16;

    if (!isObject) {
        let color = isDark ? 'text-gray-300' : 'text-gray-700';
        if (typeof value === 'string') color = isDark ? 'text-green-400' : 'text-green-700';
        else if (typeof value === 'number') color = isDark ? 'text-blue-400' : 'text-blue-700';
        else if (typeof value === 'boolean') color = isDark ? 'text-amber-400' : 'text-amber-700';
        else if (value === null) color = isDark ? 'text-gray-500' : 'text-gray-400';

        return (
            <div className="flex items-start text-xs font-mono leading-5" style={{ paddingLeft: indent }}>
                <span className={isDark ? 'text-purple-400' : 'text-purple-700'}>{name}</span>
                <span className={isDark ? 'text-gray-500' : 'text-gray-400'}>:&nbsp;</span>
                <span className={color}>{value === null ? 'null' : typeof value === 'string' ? `"${value}"` : String(value)}</span>
            </div>
        );
    }

    return (
        <div>
            <div
                className="flex items-center text-xs font-mono leading-5 cursor-pointer hover:bg-primary/5 rounded"
                style={{ paddingLeft: indent }}
                onClick={() => setExpanded(!expanded)}
            >
                <span className={`mr-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>{expanded ? '▼' : '▶'}</span>
                <span className={isDark ? 'text-purple-400' : 'text-purple-700'}>{name}</span>
                <span className={isDark ? 'text-gray-500' : 'text-gray-400'}>
                    :&nbsp;{isArray ? `[${entries.length}]` : `{${entries.length}}`}
                </span>
            </div>
            {expanded && entries.map(([k, v]) => (
                <JSONNode key={k} name={k} value={v} depth={depth + 1} isDark={isDark} defaultExpanded={defaultExpanded} />
            ))}
        </div>
    );
};

const JSONViewerWidget: React.FC<JSONViewerWidgetProps> = ({ data, title, defaultExpanded = true }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';

    return (
        <div className={`w-full rounded-lg border overflow-hidden ${isDark ? 'bg-gray-800/50 border-gray-700' : 'bg-white border-gray-200 shadow-sm'}`}>
            {title && (
                <div className={`px-4 py-2 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{title}</h3>
                </div>
            )}
            <div className="p-3 max-h-96 overflow-y-auto scrollbar-hide">
                {typeof data === 'object' && data !== null ? (
                    Object.entries(data).map(([k, v]) => (
                        <JSONNode key={k} name={k} value={v} depth={0} isDark={isDark} defaultExpanded={defaultExpanded} />
                    ))
                ) : (
                    <span className={`text-xs font-mono ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{String(data)}</span>
                )}
            </div>
        </div>
    );
};

export default JSONViewerWidget;
