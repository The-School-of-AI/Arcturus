import React from 'react';
import { useTheme } from '@/components/theme';

interface TerminalWidgetProps {
    lines: string[];
    title?: string;
}

const TerminalWidget: React.FC<TerminalWidgetProps> = ({ lines = [], title = 'Terminal' }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';

    return (
        <div className={`w-full rounded-lg border overflow-hidden font-mono ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-gray-950 border-gray-800'}`}>
            <div className="flex items-center gap-2 px-4 py-2 bg-gray-800/80 border-b border-gray-700">
                <div className="flex gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
                    <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/80" />
                    <div className="w-2.5 h-2.5 rounded-full bg-green-500/80" />
                </div>
                <span className="text-[10px] text-gray-400 uppercase tracking-wider ml-2">{title}</span>
            </div>
            <div className="p-3 max-h-80 overflow-y-auto text-xs leading-5 scrollbar-hide">
                {lines.map((line, i) => {
                    // Color coding: lines starting with $ are commands, # are comments, > are output
                    let textColor = 'text-gray-300';
                    if (line.startsWith('$')) textColor = 'text-green-400';
                    else if (line.startsWith('#')) textColor = 'text-gray-500';
                    else if (line.startsWith('ERROR') || line.startsWith('error')) textColor = 'text-red-400';
                    else if (line.startsWith('WARN') || line.startsWith('warn')) textColor = 'text-yellow-400';
                    else if (line.startsWith('✓') || line.startsWith('OK') || line.startsWith('success')) textColor = 'text-green-400';

                    return (
                        <div key={i} className={`${textColor} whitespace-pre-wrap`}>
                            {line || '\u00A0'}
                        </div>
                    );
                })}
                <div className="text-green-400 animate-pulse">▊</div>
            </div>
        </div>
    );
};

export default TerminalWidget;
