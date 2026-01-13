import React from 'react';
import { Terminal as TerminalIcon, Plus, Maximize2, X } from 'lucide-react';

export const TerminalPanel: React.FC = () => {
    return (
        <div className="h-full flex flex-col bg-[#18181b] border-t border-[#27272a]">
            {/* Terminal Header */}
            <div className="h-9 min-h-[36px] flex items-center justify-between px-4 border-b border-[#27272a] bg-[#18181b]">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 text-xs font-medium text-[#d4d4d8] cursor-pointer hover:text-white transition-colors">
                        <TerminalIcon className="w-3.5 h-3.5" />
                        <span>TERMINAL</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs font-medium text-[#71717a] cursor-pointer hover:text-[#d4d4d8] transition-colors">
                        <span>OUTPUT</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs font-medium text-[#71717a] cursor-pointer hover:text-[#d4d4d8] transition-colors">
                        <span>PROBLEMS</span>
                    </div>
                </div>

                <div className="flex items-center gap-1">
                    <button className="p-1 hover:bg-[#27272a] rounded-md text-[#a1a1aa] hover:text-white transition-colors">
                        <Plus className="w-3.5 h-3.5" />
                    </button>
                    <button className="p-1 hover:bg-[#27272a] rounded-md text-[#a1a1aa] hover:text-white transition-colors">
                        <Maximize2 className="w-3.5 h-3.5" />
                    </button>
                    <button className="p-1 hover:bg-[#27272a] rounded-md text-[#a1a1aa] hover:text-white transition-colors">
                        <X className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>

            {/* Terminal Body (xterm container) */}
            <div className="flex-1 p-2 font-mono text-sm text-[#d4d4d8] overflow-auto">
                <div className="opacity-50">
                    $ echo "Terminal integration pending..."<br />
                    Terminal integration pending...<br />
                    $ _
                </div>
            </div>
        </div>
    );
};
