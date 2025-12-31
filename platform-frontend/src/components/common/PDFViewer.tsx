import React, { useEffect, useState } from 'react';
import { Worker, Viewer } from '@react-pdf-viewer/core';
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout';
import { pageNavigationPlugin } from '@react-pdf-viewer/page-navigation';
import { searchPlugin } from '@react-pdf-viewer/search';
import { Loader2 } from 'lucide-react';

// Import styles (make sure these are imported in your global css or here)
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';
import '@react-pdf-viewer/page-navigation/lib/styles/index.css';
import '@react-pdf-viewer/search/lib/styles/index.css';

interface PDFViewerProps {
    url: string;
    theme?: 'light' | 'dark';
    className?: string;
}

export const PDFViewer: React.FC<PDFViewerProps> = ({ url, theme = 'light', className }) => {
    const defaultLayoutPluginInstance = defaultLayoutPlugin();
    const pageNavigationPluginInstance = pageNavigationPlugin();
    const searchPluginInstance = searchPlugin();

    return (
        <div className={`h-full w-full overflow-hidden ${className}`}>
            <style>{`
                .rpv-core__text-layer-text::selection,
                .rpv-core__text-layer-text ::selection {
                    background-color: rgba(255, 221, 0, 0.9) !important;
                }
            `}</style>
            <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.4.120/build/pdf.worker.min.js">
                <div style={{ height: '100%', width: '100%' }}>
                    <Viewer
                        fileUrl={url}
                        plugins={[
                            defaultLayoutPluginInstance,
                            pageNavigationPluginInstance,
                            searchPluginInstance
                        ]}
                        theme={theme}
                        renderLoader={(percentages: number) => (
                            <div className="flex flex-col items-center justify-center p-10 space-y-4">
                                <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
                                <span className="text-xs text-muted-foreground font-mono">
                                    Loading PDF... {Math.round(percentages)}%
                                </span>
                            </div>
                        )}
                    />
                </div>
            </Worker>
        </div>
    );
};
