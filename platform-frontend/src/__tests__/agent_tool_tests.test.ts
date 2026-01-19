/**
 * COMPREHENSIVE AGENT TOOL TESTS
 * 
 * This file simulates REAL agent responses (like an LLM would generate)
 * and tests that:
 * 1. The response parser correctly extracts tool calls
 * 2. The tool executor correctly handles each tool
 * 
 * All 16 tools are tested with various response formats the LLM might use.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { parseToolCalls } from '../features/ide/utils/responseParser';
import { executeAgentTool, ToolContext } from '../features/ide/utils/agentTools';

// ============================================================
// SIMULATED AGENT RESPONSES
// These are exactly what an LLM would output in response to user requests
// ============================================================

const AGENT_RESPONSES = {
    // === READ FILE ===
    read_file_json: `I'll read the file for you.

\`\`\`json
{
  "tool": "read_file",
  "args": {
    "path": "vector_add.py"
  }
}
\`\`\``,

    read_file_tool_code: `<think>The user wants to see the contents of the file.</think>

\`\`\`tool_code
{
  "tool": "read_file",
  "args": {
    "path": "src/main.ts"
  }
}
\`\`\``,

    // === WRITE FILE ===
    write_file_with_code_block: `I'll create a new Python file with the hello world function.

\`\`\`python
def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
\`\`\` <<CODE>>

\`\`\`json
{
  "tool": "write_file",
  "args": {
    "path": "hello.py",
    "content": "{{CODE}}"
  }
}
\`\`\``,

    // === REPLACE IN FILE ===
    replace_in_file: `I'll change the function name from "old_name" to "new_name".

\`\`\`json
{
  "tool": "replace_in_file",
  "args": {
    "path": "utils.py",
    "target": "def old_name():",
    "replacement": "def new_name():"
  }
}
\`\`\``,

    // === REPLACE SYMBOL ===
    replace_symbol: `I'll replace the symbol "t" with "torch" in the file.

\`\`\`json
{
  "tool": "replace_symbol",
  "args": {
    "path": "/Users/test/project/vector_add.py",
    "symbol": "add_vectors",
    "content": "def add_vectors(vec1, vec2):\\n    return vec1 + vec2"
  }
}
\`\`\``,

    // === LIST DIR ===
    list_dir: `Let me check what files are in the current directory.

\`\`\`json
{
  "tool": "list_dir",
  "args": {
    "path": "./"
  }
}
\`\`\``,

    // === FIND BY NAME ===
    find_by_name: `I'll search for all Python files in the project.

\`\`\`json
{
  "tool": "find_by_name",
  "args": {
    "pattern": "*.py",
    "root": "./"
  }
}
\`\`\``,

    // === GREP SEARCH ===
    grep_search: `Let me search for all occurrences of "import torch".

\`\`\`json
{
  "tool": "grep_search",
  "args": {
    "query": "import torch",
    "root": "./"
  }
}
\`\`\``,

    // === VIEW FILE OUTLINE ===
    view_file_outline: `I'll get the outline of the file to see its structure.

\`\`\`json
{
  "tool": "view_file_outline",
  "args": {
    "path": "main.py"
  }
}
\`\`\``,

    // === RUN COMMAND ===
    run_command: `I'll run the tests for you.

\`\`\`json
{
  "tool": "run_command",
  "args": {
    "command": "npm test",
    "cwd": "./"
  }
}
\`\`\``,

    // === COMMAND STATUS ===
    command_status: `Let me check the status of the previous command.

\`\`\`json
{
  "tool": "command_status",
  "args": {
    "pid": "12345"
  }
}
\`\`\``,

    // === RUN SCRIPT ===
    run_script: `I'll execute the script directly.

\`\`\`json
{
  "tool": "run_script",
  "args": {
    "command": "python3 setup.py install"
  }
}
\`\`\``,

    // === READ TERMINAL ===
    read_terminal: `Let me read the current terminal output.

\`\`\`json
{
  "tool": "read_terminal",
  "args": {}
}
\`\`\``,

    // === APPLY DIFF ===
    apply_diff: `I'll apply the following diff to the file:

\`\`\`diff
--- a/main.py
+++ b/main.py
@@ -1,3 +1,3 @@
-def old_function():
+def new_function():
     pass
\`\`\` <<DIFF>>

\`\`\`json
{
  "tool": "apply_diff",
  "args": {
    "path": "main.py",
    "diff": "{{DIFF}}"
  }
}
\`\`\``,

    // === MULTI REPLACE FILE CONTENT ===
    multi_replace_file_content: `I'll make multiple replacements in the file.

\`\`\`json
{
  "tool": "multi_replace_file_content",
  "args": {
    "path": "config.json",
    "changes": [
      { "target": "debug: false", "replacement": "debug: true" },
      { "target": "port: 3000", "replacement": "port: 8080" }
    ]
  }
}
\`\`\``,

    // === SEARCH WEB ===
    search_web: `Let me search the web for PyTorch documentation.

\`\`\`json
{
  "tool": "search_web",
  "args": {
    "query": "PyTorch tensor operations documentation"
  }
}
\`\`\``,

    // === READ URL ===
    read_url: `I'll fetch the content from that URL.

\`\`\`json
{
  "tool": "read_url",
  "args": {
    "url": "https://pytorch.org/docs/stable/tensors.html"
  }
}
\`\`\``,

    // === EDGE CASES ===

    // Multiple tools in one response
    multiple_tools: `I'll read the file first, then modify it.

\`\`\`json
{
  "tool": "read_file",
  "args": { "path": "first.py" }
}
\`\`\`

\`\`\`json
{
  "tool": "read_file",
  "args": { "path": "second.py" }
}
\`\`\``,

    // No tools (just text)
    no_tools: `I understand you want to refactor the code. However, I need more information about which specific functions you'd like me to change. Could you please clarify?`,

    // Malformed JSON (should not parse)
    malformed_json: `I'll try to run something:

\`\`\`json
{
  "tool": "read_file"
  // missing closing brace and args
\`\`\``,

    // Alternative language identifiers
    alternative_language_python: `<think>User wants to execute some code</think>

\`\`\`python
{
  "tool": "run_command",
  "args": { "command": "python --version" }
}
\`\`\``,

    alternative_language_typescript: `Let me check the version:

\`\`\`typescript
{
  "tool": "run_command",
  "args": { "command": "node --version" }
}
\`\`\``,

    // Using "name" instead of "tool"
    name_instead_of_tool: `Let me read that file:

\`\`\`json
{
  "name": "read_file",
  "arguments": { "path": "test.py" }
}
\`\`\``,

    // Empty code block
    empty_code_block: `Here's the result:

\`\`\`json
\`\`\``,

    // Smart code injection with LAST_CODE_BLOCK
    smart_injection_last_block: `Here's the new implementation:

\`\`\`typescript
export function calculateSum(a: number, b: number): number {
    return a + b;
}
\`\`\`

\`\`\`json
{
  "tool": "write_file",
  "args": {
    "path": "math.ts",
    "content": "{{LAST_CODE_BLOCK}}"
  }
}
\`\`\``,
};


// ============================================================
// PARSER TESTS
// ============================================================

describe('Response Parser - Real Agent Responses', () => {

    describe('Basic Tool Extraction', () => {

        it('should parse read_file with json language tag', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.read_file_json);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('read_file');
            expect(calls[0].arguments.path).toBe('vector_add.py');
        });

        it('should parse read_file with tool_code language tag', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.read_file_tool_code);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('read_file');
            expect(calls[0].arguments.path).toBe('src/main.ts');
        });

        it('should parse write_file', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.write_file_with_code_block);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('write_file');
            expect(calls[0].arguments.path).toBe('hello.py');
            // Content should be substituted from the code block
            expect(calls[0].arguments.content).toContain('def hello_world()');
        });

        it('should parse replace_in_file', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.replace_in_file);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('replace_in_file');
            expect(calls[0].arguments.path).toBe('utils.py');
            expect(calls[0].arguments.target).toBe('def old_name():');
            expect(calls[0].arguments.replacement).toBe('def new_name():');
        });

        it('should parse replace_symbol', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.replace_symbol);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('replace_symbol');
            expect(calls[0].arguments.symbol).toBe('add_vectors');
        });

        it('should parse list_dir', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.list_dir);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('list_dir');
            expect(calls[0].arguments.path).toBe('./');
        });

        it('should parse find_by_name', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.find_by_name);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('find_by_name');
            expect(calls[0].arguments.pattern).toBe('*.py');
        });

        it('should parse grep_search', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.grep_search);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('grep_search');
            expect(calls[0].arguments.query).toBe('import torch');
        });

        it('should parse view_file_outline', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.view_file_outline);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('view_file_outline');
            expect(calls[0].arguments.path).toBe('main.py');
        });

        it('should parse run_command', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.run_command);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('run_command');
            expect(calls[0].arguments.command).toBe('npm test');
        });

        it('should parse command_status', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.command_status);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('command_status');
            expect(calls[0].arguments.pid).toBe('12345');
        });

        it('should parse run_script', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.run_script);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('run_script');
            expect(calls[0].arguments.command).toBe('python3 setup.py install');
        });

        it('should parse read_terminal', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.read_terminal);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('read_terminal');
        });

        it('should parse apply_diff with code injection', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.apply_diff);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('apply_diff');
            expect(calls[0].arguments.path).toBe('main.py');
            // Diff content should be substituted
            expect(calls[0].arguments.diff).toContain('-def old_function()');
        });

        it('should parse multi_replace_file_content', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.multi_replace_file_content);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('multi_replace_file_content');
            expect(calls[0].arguments.changes).toHaveLength(2);
        });

        it('should parse search_web', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.search_web);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('search_web');
            expect(calls[0].arguments.query).toContain('PyTorch');
        });

        it('should parse read_url', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.read_url);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('read_url');
            expect(calls[0].arguments.url).toContain('pytorch.org');
        });

    });

    describe('Edge Cases', () => {

        it('should parse multiple tools in one response', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.multiple_tools);
            expect(calls).toHaveLength(2);
            expect(calls[0].arguments.path).toBe('first.py');
            expect(calls[1].arguments.path).toBe('second.py');
        });

        it('should return empty array for response with no tools', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.no_tools);
            expect(calls).toHaveLength(0);
        });

        it('should handle malformed JSON gracefully', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.malformed_json);
            expect(calls).toHaveLength(0);
        });

        it('should handle python language tag', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.alternative_language_python);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('run_command');
        });

        it('should handle typescript language tag', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.alternative_language_typescript);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('run_command');
        });

        it('should handle "name" instead of "tool"', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.name_instead_of_tool);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('read_file');
            expect(calls[0].arguments.path).toBe('test.py');
        });

        it('should handle empty code blocks gracefully', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.empty_code_block);
            expect(calls).toHaveLength(0);
        });

        it('should perform smart code injection with LAST_CODE_BLOCK', () => {
            const calls = parseToolCalls(AGENT_RESPONSES.smart_injection_last_block);
            expect(calls).toHaveLength(1);
            expect(calls[0].name).toBe('write_file');
            expect(calls[0].arguments.content).toContain('export function calculateSum');
        });

    });

});


// ============================================================
// TOOL EXECUTION TESTS
// ============================================================

describe('Tool Executor - All Tools', () => {
    let mockContext: ToolContext;
    let mockElectronAPI: any;

    beforeEach(() => {
        mockElectronAPI = {
            invoke: vi.fn()
        };

        // Set up global window.electronAPI
        (global as any).window = {
            electronAPI: mockElectronAPI
        };

        // Set up mock crypto for UUID generation using vi.stubGlobal
        vi.stubGlobal('crypto', {
            randomUUID: () => 'test-uuid-1234'
        });

        mockContext = {
            projectRoot: '/Users/test/project',
            permissions: {
                blocked_commands: ['rm', 'sudo'],
                sensitive_patterns: []
            },
            startReview: vi.fn((req, cb) => cb('allow_always')), // Auto-approve
            openIdeDocument: vi.fn(),
            closeIdeDocument: vi.fn(),
            refreshExplorerFiles: vi.fn(),
            checkContentSafety: vi.fn(() => ({ safe: true, violations: [] })),
            checkPathSafety: vi.fn(() => ({ safe: true })),
            getContentTypeFromPath: vi.fn((p) => p.split('.').pop() || null),
            API_BASE: 'http://localhost:8000'
        };
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('read_file', () => {
        it('should read a file successfully', async () => {
            mockElectronAPI.invoke.mockImplementation(async (channel: string, args: any) => {
                if (channel === 'fs:isGitignored') return { ignored: false };
                if (channel === 'fs:readFile') return { success: true, content: '# Hello World' };
                return { success: false };
            });

            const result = await executeAgentTool(
                { name: 'read_file', arguments: { path: 'README.md' } },
                mockContext
            );

            expect(result).toBe('# Hello World');
            expect(mockContext.openIdeDocument).toHaveBeenCalled();
        });

        it('should reject paths outside project root', async () => {
            const result = await executeAgentTool(
                { name: 'read_file', arguments: { path: '/etc/passwd' } },
                mockContext
            );

            expect(result).toContain('Access denied');
        });

        it('should reject gitignored files', async () => {
            mockElectronAPI.invoke.mockImplementation(async (channel: string) => {
                if (channel === 'fs:isGitignored') return { ignored: true };
                return { success: true };
            });

            const result = await executeAgentTool(
                { name: 'read_file', arguments: { path: 'node_modules/test.js' } },
                mockContext
            );

            expect(result).toContain('gitignored');
        });
    });

    describe('write_file', () => {
        it('should write to a file with inline diff review', async () => {
            mockElectronAPI.invoke.mockImplementation(async (channel: string) => {
                if (channel === 'fs:readFile') return { success: true, content: 'old content' };
                if (channel === 'fs:writeFile') return { success: true };
                return { success: false };
            });

            const result = await executeAgentTool(
                { name: 'write_file', arguments: { path: 'test.txt', content: 'new content' } },
                mockContext
            );

            expect(result).toContain('Success');
            expect(mockContext.startReview).toHaveBeenCalled();
            expect(mockContext.openIdeDocument).toHaveBeenCalled();
        });
    });

    describe('replace_in_file', () => {
        it('should replace text in a file', async () => {
            mockElectronAPI.invoke.mockImplementation(async (channel: string) => {
                if (channel === 'fs:readFile') return { success: true, content: 'Hello World' };
                if (channel === 'fs:writeFile') return { success: true };
                return { success: false };
            });

            const result = await executeAgentTool(
                { name: 'replace_in_file', arguments: { path: 'test.txt', target: 'World', replacement: 'Universe' } },
                mockContext
            );

            expect(result).toContain('Success');
        });

        it('should error if target not found', async () => {
            mockElectronAPI.invoke.mockImplementation(async (channel: string) => {
                if (channel === 'fs:readFile') return { success: true, content: 'Hello World' };
                return { success: false };
            });

            const result = await executeAgentTool(
                { name: 'replace_in_file', arguments: { path: 'test.txt', target: 'NotExists', replacement: 'Replaced' } },
                mockContext
            );

            expect(result).toContain('Target text not found');
        });
    });

    describe('replace_symbol', () => {
        it('should write temp files and execute Python script', async () => {
            mockElectronAPI.invoke.mockImplementation(async (channel: string) => {
                if (channel === 'fs:writeFile') return { success: true };
                if (channel === 'fs:delete') return { success: true };
                if (channel === 'shell:exec') return { success: true, stdout: 'Successfully replaced', stderr: '' };
                return { success: false };
            });

            const result = await executeAgentTool(
                { name: 'replace_symbol', arguments: { path: 'test.py', symbol: 'old_func', content: 'def new_func(): pass' } },
                mockContext
            );

            expect(result).toContain('Success');
            // Verify temp files were written
            expect(mockElectronAPI.invoke).toHaveBeenCalledWith('fs:writeFile', expect.objectContaining({
                path: expect.stringContaining('/tmp/symbol_')
            }));
        });

        it('should return error if temp file write fails', async () => {
            mockElectronAPI.invoke.mockImplementation(async (channel: string) => {
                if (channel === 'fs:writeFile') return { success: false, error: 'Permission denied' };
                return { success: false };
            });

            const result = await executeAgentTool(
                { name: 'replace_symbol', arguments: { path: 'test.py', symbol: 'func', content: 'new code' } },
                mockContext
            );

            expect(result).toContain('Failed to write temp');
        });
    });

    describe('list_dir', () => {
        it('should list directory contents', async () => {
            mockElectronAPI.invoke.mockResolvedValue({
                success: true,
                files: [
                    { name: 'file1.txt', type: 'file' },
                    { name: 'folder1', type: 'folder' }
                ]
            });

            const result = await executeAgentTool(
                { name: 'list_dir', arguments: { path: './' } },
                mockContext
            );

            expect(result).toContain('[FILE] file1.txt');
            expect(result).toContain('[DIR] folder1');
        });
    });

    describe('find_by_name', () => {
        it('should find files by pattern', async () => {
            mockElectronAPI.invoke.mockResolvedValue({
                success: true,
                files: ['src/main.py', 'src/utils.py']
            });

            const result = await executeAgentTool(
                { name: 'find_by_name', arguments: { pattern: '*.py', root: './' } },
                mockContext
            );

            expect(result).toContain('main.py');
            expect(result).toContain('utils.py');
        });
    });

    describe('grep_search', () => {
        it('should search for patterns in files', async () => {
            mockElectronAPI.invoke.mockResolvedValue({
                success: true,
                files: ['src/main.py:5: import torch']
            });

            const result = await executeAgentTool(
                { name: 'grep_search', arguments: { query: 'import torch', root: './' } },
                mockContext
            );

            expect(result).toContain('import torch');
        });
    });

    describe('run_command', () => {
        it('should execute a command', async () => {
            mockElectronAPI.invoke.mockImplementation(async (channel: string) => {
                if (channel === 'shell:spawn') return { success: true, pid: 12345 };
                if (channel === 'shell:status') return { success: true, status: 'done', stdout: 'OK', stderr: '' };
                return { success: false };
            });

            const result = await executeAgentTool(
                { name: 'run_command', arguments: { command: 'echo hello' } },
                mockContext
            );

            expect(result).toContain('OK');
        });

        it('should block dangerous commands', async () => {
            mockContext.permissions.blocked_commands = ['rm'];

            const result = await executeAgentTool(
                { name: 'run_command', arguments: { command: 'rm -rf /' } },
                mockContext
            );

            expect(result).toContain('BLOCKED');
        });
    });

    describe('multi_replace_file_content', () => {
        it('should apply multiple replacements', async () => {
            mockElectronAPI.invoke.mockImplementation(async (channel: string) => {
                if (channel === 'fs:readFile') return { success: true, content: '{"debug": false, "port": 3000}' };
                if (channel === 'fs:writeFile') return { success: true };
                return { success: false };
            });

            const result = await executeAgentTool(
                {
                    name: 'multi_replace_file_content',
                    arguments: {
                        path: 'config.json',
                        changes: [
                            { target: '"debug": false', replacement: '"debug": true' },
                            { target: '"port": 3000', replacement: '"port": 8080' }
                        ]
                    }
                },
                mockContext
            );

            expect(result).toContain('Success');
        });
    });

    describe('Unknown tool', () => {
        it('should return error for unknown tool', async () => {
            const result = await executeAgentTool(
                { name: 'unknown_tool', arguments: {} },
                mockContext
            );

            expect(result).toContain('Unknown tool');
        });
    });

});


// ============================================================
// INTEGRATION TESTS - Parse + Execute Pipeline
// ============================================================

describe('Full Pipeline - Parse and Execute', () => {
    let mockContext: ToolContext;
    let mockElectronAPI: any;

    beforeEach(() => {
        mockElectronAPI = {
            invoke: vi.fn().mockImplementation(async (channel: string) => {
                if (channel === 'fs:isGitignored') return { ignored: false };
                if (channel === 'fs:readFile') return { success: true, content: '# Test File Content' };
                if (channel === 'fs:writeFile') return { success: true };
                if (channel === 'fs:readDir') return { success: true, files: [{ name: 'test.py', type: 'file' }] };
                return { success: true };
            })
        };

        (global as any).window = { electronAPI: mockElectronAPI };
        vi.stubGlobal('crypto', { randomUUID: () => 'test-uuid' });

        mockContext = {
            projectRoot: '/Users/test/project',
            permissions: { blocked_commands: [], sensitive_patterns: [] },
            startReview: vi.fn((req, cb) => cb('allow_always')),
            openIdeDocument: vi.fn(),
            closeIdeDocument: vi.fn(),
            refreshExplorerFiles: vi.fn(),
            checkContentSafety: vi.fn(() => ({ safe: true, violations: [] })),
            checkPathSafety: vi.fn(() => ({ safe: true })),
            getContentTypeFromPath: vi.fn((p) => p.split('.').pop() || null),
            API_BASE: 'http://localhost:8000'
        };
    });

    it('should parse and execute read_file from real agent response', async () => {
        const agentResponse = AGENT_RESPONSES.read_file_json;
        const toolCalls = parseToolCalls(agentResponse);

        expect(toolCalls).toHaveLength(1);

        const result = await executeAgentTool(toolCalls[0], mockContext);
        expect(result).toBe('# Test File Content');
    });

    it('should parse and execute tool_code language tag response', async () => {
        const agentResponse = AGENT_RESPONSES.read_file_tool_code;
        const toolCalls = parseToolCalls(agentResponse);

        expect(toolCalls).toHaveLength(1);
        expect(toolCalls[0].name).toBe('read_file');

        const result = await executeAgentTool(toolCalls[0], mockContext);
        expect(result).toBe('# Test File Content');
    });

    it('should handle write_file with smart code injection', async () => {
        const agentResponse = AGENT_RESPONSES.write_file_with_code_block;
        const toolCalls = parseToolCalls(agentResponse);

        expect(toolCalls).toHaveLength(1);
        expect(toolCalls[0].name).toBe('write_file');
        expect(toolCalls[0].arguments.content).toContain('def hello_world()');

        const result = await executeAgentTool(toolCalls[0], mockContext);
        expect(result).toContain('Success');
    });

});
