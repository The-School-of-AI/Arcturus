import React from 'react';
import Editor from '@monaco-editor/react';

interface MonacoWidgetProps {
    code: string;
    language?: string;
    theme?: string;
    onCodeChange?: (newCode: string) => void;
    readOnly?: boolean;
}

const MonacoWidget: React.FC<MonacoWidgetProps> = ({
    code,
    language = 'javascript',
    theme = 'vs-dark',
    onCodeChange,
    readOnly = false
}) => {
    return (
        <div className="w-full h-96 border border-gray-700 rounded-lg overflow-hidden shadow-inner">
            <Editor
                height="100%"
                defaultLanguage={language}
                defaultValue={code}
                theme={theme}
                options={{
                    readOnly,
                    minimap: { enabled: false },
                    fontSize: 12,
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    padding: { top: 10, bottom: 10 }
                }}
                onChange={(value) => onCodeChange?.(value || '')}
            />
        </div>
    );
};

export default MonacoWidget;
