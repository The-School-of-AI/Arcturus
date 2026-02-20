import React from 'react';
import LineChartWidget from './widgets/LineChartWidget';
import MonacoWidget from './widgets/MonacoWidget';
import SandboxFrame from './SandboxFrame';

const ButtonWidget = ({ text, onClick }: { text: string; onClick: () => void }) => (
    <button
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
        onClick={onClick}
    >
        {text}
    </button>
);

const TextWidget = ({ content, style }: { content: string; style?: React.CSSProperties }) => (
    <div style={style}>{content}</div>
);

const ContainerWidget = ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
);

// Map of component discriminator to React component
export const WidgetRegistry: Record<string, React.FC<any>> = {
    "Button": ButtonWidget,
    "Text": TextWidget,
    "Container": ContainerWidget,
    "LineChart": LineChartWidget,
    "MonacoEditor": MonacoWidget,
    "Sandbox": SandboxFrame,
};

export const getWidget = (name: string) => {
    return WidgetRegistry[name] || (() => <div>Unknown Widget: {name}</div>);
};
