import React from 'react';

export const McpBrowser: React.FC = () => {
    return (
        <div className="w-full h-full flex flex-col bg-background">
            <div className="flex-1 w-full h-full overflow-hidden">
                <iframe
                    src="https://mcp.alphavantage.co/"
                    className="w-full h-full border-0"
                    title="Alpha Vantage MCP Docs"
                />
            </div>
        </div>
    );
};
