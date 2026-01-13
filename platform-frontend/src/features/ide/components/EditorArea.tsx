import React from 'react';
import Editor from '@monaco-editor/react';

import { FileCode } from 'lucide-react';

export const EditorArea: React.FC = () => {
    // const { theme } = useTheme(); // layout is forced dark usually, but we can check if we want to support light

    return (
        <div className="h-full w-full flex flex-col bg-[#1e1e1e]">
            {/* Editor Tabs (Visual Only for now) */}
            <div className="flex items-center bg-[#18181b] border-b border-[#27272a] overflow-x-auto no-scrollbar">
                <div className="flex items-center gap-2 px-3 py-2 bg-[#1e1e1e] border-t-2 border-t-[#eab308] border-r border-r-[#27272a] min-w-[120px]">
                    <FileCode className="w-3.5 h-3.5 text-[#eab308]" />
                    <span className="text-xs text-[#d4d4d8] font-medium truncate">IdeLayout.tsx</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-2 text-[#71717a] hover:bg-[#27272a] cursor-pointer min-w-[120px] border-r border-r-[#27272a]/50">
                    <span className="text-xs truncate">ideStore.ts</span>
                </div>
            </div>

            {/* Monaco Instance */}
            <div className="flex-1 w-full h-full overflow-hidden">
                <Editor
                    height="100%"
                    defaultLanguage="typescript"
                    defaultValue="// Welcome to Arcturus IDE"
                    theme="vs-dark"
                    options={{
                        minimap: { enabled: true },
                        fontSize: 14,
                        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                        padding: { top: 16 },
                        scrollBeyondLastLine: false,
                        automaticLayout: true,
                    }}
                />
            </div>
        </div>
    );
};
