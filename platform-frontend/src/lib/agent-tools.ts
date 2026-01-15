export interface ToolDefinition {
    name: string;
    description: string;
    parameters: {
        type: "object";
        properties: Record<string, any>; // Allow any structure for now to strictly support nested arrays
        required: string[];
    };
}

export interface ToolCall {
    name: string;
    arguments: any;
}

export const availableTools: ToolDefinition[] = [
    {
        name: "read_file",
        description: "Read the contents of a file. Use this to examine code or config files.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Absolute path to the file to read." }
            },
            required: ["path"]
        }
    },
    {
        name: "write_file",
        description: "Create or overwrite a file with new content. Use this to create new components or scripts.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Absolute path to the file to write." },
                content: { type: "string", description: "The content to write to the file." }
            },
            required: ["path", "content"]
        }
    },
    {
        name: "replace_in_file",
        description: "Replace a specific block of text in a file. Use this for surgical edits without overwriting the whole file.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Absolute path to the file." },
                target: { type: "string", description: "The exact text block to replace. Must be unique in the file." },
                replacement: { type: "string", description: "The new text to insert." }
            },
            required: ["path", "target", "replacement"]
        }
    },
    {
        name: "list_dir",
        description: "List files and directories in a given path. Use this to explore the project structure.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Absolute path to the directory." }
            },
            required: ["path"]
        }
    },
    {
        name: "run_command",
        description: "Execute a shell command. Use this to run tests, git commands, or scripts. Returns stdout/stderr.",
        parameters: {
            type: "object",
            properties: {
                command: { type: "string", description: "The command to run (e.g., 'ls -la', 'npm test')." },
                cwd: { type: "string", description: "Working directory for the command." }
            },
            required: ["command"]
        }
    },
    {
        name: "search_web",
        description: "Search the web for real-time information. Returns a summary of top results with text content.",
        parameters: {
            type: "object",
            properties: {
                query: { type: "string", description: "The search query." }
            },
            required: ["query"]
        }
    },
    {
        name: "find_by_name",
        description: "Search for files by name or pattern in the project. Returns a list of matching paths.",
        parameters: {
            type: "object",
            properties: {
                pattern: { type: "string", description: "The filename or glob pattern to search for (e.g. 'App.tsx' or 'components/*')." },
                root: { type: "string", description: "Optional: The directory to start searching from. Defaults to project root." }
            },
            required: ["pattern"]
        }
    },
    {
        name: "grep_search",
        description: "Search for a specific string or pattern within all files in the project. Returns filenames containing the match.",
        parameters: {
            type: "object",
            properties: {
                query: { type: "string", description: "The text or regex to search for." },
                root: { type: "string", description: "Optional: The directory to start searching from. Defaults to project root." }
            },
            required: ["query"]
        }
    },
    {
        name: "view_file_outline",
        description: "Get a high-level map of a file including classes and functions with their line numbers. Use this to find where a specific function is defined.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Absolute path to the file to outline." }
            },
            required: ["path"]
        }
    },
    {
        name: "read_terminal",
        description: "Read the recent output history of the integrated terminal. Use this to see the results of previous commands or check server logs.",
        parameters: {
            type: "object",
            properties: {},
            required: []
        }
    },
    {
        name: "multi_replace_file_content",
        description: "Perform multiple replace operations in a single file atomically. Use this to patch a file in several places.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Absolute path to the file." },
                changes: {
                    type: "array",
                    items: {
                        type: "object",
                        properties: {
                            target: { type: "string", description: "Text to find." },
                            replacement: { type: "string", description: "Text to replace it with." }
                        },
                        required: ["target", "replacement"]
                    },
                    description: "List of replacement pairs."
                }
            },
            required: ["path", "changes"]
        }
    },
    {
        name: "read_url",
        description: "Read the specific content of a URL. Use this to read documentation pages.",
        parameters: {
            type: "object",
            properties: {
                url: { type: "string", description: "The URL to read." }
            },
            required: ["url"]
        }
    }
];
