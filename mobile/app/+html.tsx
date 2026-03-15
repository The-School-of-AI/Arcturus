import { ScrollViewStyleReset } from 'expo-router/html';

// This file is web-only and used to configure the root HTML for every
// web page during static rendering.
// The contents of this function only run in Node.js environments and
// do not have access to the DOM or browser APIs.
export default function Root({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />

        {/* 
          Disable body scrolling on web. This makes ScrollView components work closer to how they do on native. 
          However, body scrolling is often nice to have for mobile web. If you want to enable it, remove this line.
        */}
        <ScrollViewStyleReset />

        {/* Match Arcturus app theme: light = cool blue-grey, dark = deep navy (no white/black flicker). */}
        <style dangerouslySetInnerHTML={{ __html: appThemeStyles }} />
        {/* Add any additional <head> elements that you want globally available on web... */}
      </head>
      <body>{children}</body>
    </html>
  );
}

/* Arcturus design system — aligned with platform-frontend (index.css) and mobile Colors */
const appThemeStyles = `
:root {
  /* Light: crisp, airy, tech blue */
  --app-bg: hsl(210, 40%, 98%);
  --app-fg: hsl(222, 47%, 11%);
  --app-primary: hsl(221, 83%, 53%);
}
@media (prefers-color-scheme: dark) {
  :root {
    /* Dark: deep space, navy */
    --app-bg: hsl(222, 47%, 11%);
    --app-fg: hsl(210, 40%, 98%);
    --app-primary: hsl(217, 91%, 60%);
  }
}
html {
  background: var(--app-bg);
  color: var(--app-fg);
  -webkit-font-smoothing: antialiased;
}
body {
  margin: 0;
  background: var(--app-bg);
  color: var(--app-fg);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}`;
