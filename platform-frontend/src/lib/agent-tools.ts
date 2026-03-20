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
        description: "Read the contents of a file. Use this to examine code or config files. Path MUST be relative to project root.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Relative path to the file (e.g. 'src/index.js')." }
            },
            required: ["path"]
        }
    },
    {
        name: "write_file",
        description: "Create or overwrite a file with new content. Path MUST be relative to project root.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Relative path to the file (e.g. 'src/NewComponent.tsx')." },
                content: { type: "string", description: "The content to write to the file." }
            },
            required: ["path", "content"]
        }
    },
    {
        name: "replace_in_file",
        description: "Replace ONE occurrence of a text block in a file. CRITICAL: target MUST be unique! If target appears multiple times, this will fail. Include surrounding context to make it unique. Example: target='def hello():' not just 'hello'. Path MUST be relative to project root. This is NOT a 'replace all' tool.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Relative path to the file." },
                target: { type: "string", description: "The EXACT and UNIQUE text block to replace. Include enough context (e.g. full line or multiline) to ensure uniqueness." },
                replacement: { type: "string", description: "The new text to insert in place of target." }
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
                path: { type: "string", description: "Relative path to the directory (e.g. './' or 'src'). Defaults to project root." }
            },
            required: ["path"]
        }
    },
    {
        name: "run_command",
        description: "Execute a shell command in a non-interactive environment. Use this to run tests, git commands, or scripts.",
        parameters: {
            type: "object",
            properties: {
                command: { type: "string", description: "The command to run." },
                cwd: { type: "string", description: "Relative path to the working directory." }
            },
            required: ["command"]
        }
    },
    {
        name: "search_web",
        description: "Search the web for real-time information or documentation.",
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
        description: "Search for files by name or pattern in the project.",
        parameters: {
            type: "object",
            properties: {
                pattern: { type: "string", description: "The filename or glob pattern (e.g. 'App.tsx' or 'components/*')." },
                root: { type: "string", description: "Optional: Relative directory to start searching from. Defaults to './'." }
            },
            required: ["pattern"]
        }
    },
    {
        name: "grep_search",
        description: "Search for a string or regex pattern within all files in the project.",
        parameters: {
            type: "object",
            properties: {
                query: { type: "string", description: "The text or regex to search for." },
                root: { type: "string", description: "Optional: Relative directory to start searching from. Defaults to './'." }
            },
            required: ["query"]
        }
    },
    {
        name: "view_file_outline",
        description: "Get a high-level map of a file including classes and functions. Path MUST be relative to project root.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Relative path to the file." }
            },
            required: ["path"]
        }
    },
    {
        name: "read_terminal",
        description: "Read the recent output history of the integrated terminal.",
        parameters: {
            type: "object",
            properties: {},
            required: []
        }
    },
    {
        name: "multi_replace_file_content",
        description: "Perform MULTIPLE separate replacements in a single file. CRITICAL: Each target MUST be unique in the file! This is NOT 'replace all' - each target replaces exactly ONE occurrence. If a target appears multiple times, include more context (e.g. the full line). For bulk renaming, use write_file to rewrite the entire file instead.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Relative path to the file." },
                changes: {
                    type: "array",
                    items: {
                        type: "object",
                        properties: {
                            target: { type: "string", description: "UNIQUE text to find (include enough context)." },
                            replacement: { type: "string", description: "Text to replace it with." }
                        },
                        required: ["target", "replacement"]
                    },
                    description: "List of replacement pairs. Each target MUST be unique!"
                }
            },
            required: ["path", "changes"]
        }
    },
    {
        name: "read_url",
        description: "Read the full text content of a specific URL.",
        parameters: {
            type: "object",
            properties: {
                url: { type: "string", description: "The URL to read." }
            },
            required: ["url"]
        }
    },
    {
        name: "command_status",
        description: "Check the status and output of a background command using its PID.",
        parameters: {
            type: "object",
            properties: {
                pid: { type: "string", description: "The Process ID (PID) to check." }
            },
            required: ["pid"]
        }
    },
    {
        name: "run_script",
        description: "Execute a command synchronously (blocking). Use for quick scripts, tests, or build checks that complete in under 60 seconds. For long-running processes, use run_command instead.",
        parameters: {
            type: "object",
            properties: {
                command: { type: "string", description: "The command to execute synchronously (e.g. 'python3 test.py', 'npm test')." },
                cwd: { type: "string", description: "Optional working directory relative to project root." }
            },
            required: ["command"]
        }
    },
    {
        name: "apply_diff",
        description: "Apply a unified diff patch to a file. Useful for precise multi-line edits where replace_in_file is too rigid. The diff should be in standard unified diff format.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Relative path to the file to patch." },
                diff: { type: "string", description: "The unified diff content to apply (with --- +++ @@ headers)." }
            },
            required: ["path", "diff"]
        }
    },
    {
        name: "replace_symbol",
        description: "Replace an entire function or class definition by its name using AST parsing. Safer than text-based replacement for refactoring. Works with Python files.",
        parameters: {
            type: "object",
            properties: {
                path: { type: "string", description: "Relative path to the Python file." },
                symbol: { type: "string", description: "The function or class name to replace (e.g. 'calculate_total', 'MyClass')." },
                content: { type: "string", description: "The new function/class definition to insert." }
            },
            required: ["path", "symbol", "content"]
        }
    }
];
