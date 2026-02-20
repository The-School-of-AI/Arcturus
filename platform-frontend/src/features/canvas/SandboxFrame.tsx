import React, { useRef, useEffect } from 'react';

interface SandboxFrameProps {
    html: string;
    css?: string;
    js?: string;
    title?: string;
    onEvent?: (event: any) => void;
}

const SandboxFrame: React.FC<SandboxFrameProps> = ({ html, css = '', js = '', title = 'Arcturus Sandbox', onEvent }) => {
    const iframeRef = useRef<HTMLIFrameElement>(null);

    const fullContent = `
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <style>
        body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        ${css}
      </style>
    </head>
    <body>
      <div id="root">${html}</div>
      <script>
        // PostMessage bridge for callbacks
        window.Agent = {
          send: (type, data) => {
            window.parent.postMessage({ type, data, surface: 'sandbox' }, '*');
          }
        };

        // Inject dynamic scripts
        ${js}

        // Listen for parent messages
        window.addEventListener('message', (event) => {
          if (event.data.type === 'eval') {
            try {
              eval(event.data.code);
            } catch (e) {
              console.error('Eval error:', e);
            }
          }
        });
      </script>
    </body>
    </html>
  `;

    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            if (event.data.surface === 'sandbox' && onEvent) {
                onEvent(event.data);
            }
        };

        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, [onEvent]);

    return (
        <iframe
            ref={iframeRef}
            title={title}
            srcDoc={fullContent}
            className="w-full h-full border-none bg-white rounded-lg shadow-sm"
            sandbox="allow-scripts allow-forms allow-popups allow-modals"
        />
    );
};

export default SandboxFrame;
