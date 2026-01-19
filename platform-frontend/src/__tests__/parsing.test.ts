// @ts-nocheck
import { describe, it, expect } from 'vitest';
import { parseToolCalls } from '../features/ide/utils/responseParser';

describe('Agent Response Parsing', () => {
    it('should parse a standard tool call with json identifier', () => {
        const input = `
Here is my plan.
\`\`\`json
{
    "tool": "read_file",
    "args": {
        "path": "test.py"
    }
}
\`\`\`
        `;
        const calls = parseToolCalls(input);
        expect(calls).toHaveLength(1);
        expect(calls[0].name).toBe('read_file');
        expect(calls[0].arguments).toEqual({ path: 'test.py' });
    });

    it('should parse a tool call WITHOUT json identifier', () => {
        const input = `
\`\`\`
{
    "tool": "list_dir",
    "args": { "path": "." }
}
\`\`\`
        `;
        const calls = parseToolCalls(input);
        expect(calls).toHaveLength(1);
        expect(calls[0].name).toBe('list_dir');
    });

    it('should parse nested objects correctly (Fix for previous bug)', () => {
        const input = `
\`\`\`json
{
    "tool": "write_file",
    "args": {
        "path": "config.json",
        "content": "{\\n  \\"nested\\": true\\n}" 
    }
}
\`\`\`
        `;
        const calls = parseToolCalls(input);
        expect(calls).toHaveLength(1);
        expect(calls[0].name).toBe('write_file');
        expect(calls[0].arguments.content).toContain('"nested": true');
    });

    it('should handle extra whitespace and newlines', () => {
        const input = `
        \`\`\`   json   
        { "tool": "test", "args": {} }
        \`\`\`
        `;
        const calls = parseToolCalls(input);
        expect(calls).toHaveLength(1);
        expect(calls[0].name).toBe('test');
    });

    it('should ignore code blocks that are not tool calls', () => {
        const input = `
Here is some python code:
\`\`\`python
print("hello")
\`\`\`

And here is the tool call:
\`\`\`json
{ "tool": "run_script", "args": { "command": "python script.py" } }
\`\`\`
        `;
        const calls = parseToolCalls(input);
        // It should match the json one
        // The python one *might* match the regex (since regex is generic), but JSON.parse will likely fail or "tool" property check will fail.
        // Actually, "print..." is not valid JSON, so JSON.parse throws, loop continues.
        expect(calls).toHaveLength(1);
        expect(calls[0].name).toBe('run_script');
    });

    it('should ignore blocks with valid JSON but no tool/name property', () => {
        const input = `
\`\`\`json
{ "foo": "bar" }
\`\`\`
        `;
        const calls = parseToolCalls(input);
        expect(calls).toHaveLength(0);
    });

    // --- Smart Code Injection Tests ---

    it('should substitute {{CODE_BLOCK}} with the last code block', () => {
        const input = `
Here is the code:
\`\`\`python
print("Hello World")
\`\`\`

Now save it:
\`\`\`json
{
    "tool": "write_file",
    "args": {
        "path": "test.py",
        "content": "{{CODE_BLOCK}}"
    }
}
\`\`\`
        `;
        const calls = parseToolCalls(input);
        expect(calls).toHaveLength(1);
        expect(calls[0].arguments.content).toContain('print("Hello World")');
    });

    it('should substitute {{TAG}} with the tagged code block', () => {
        const input = `
Block A:
\`\`\`text
AAAA
\`\`\` <<BLOCK_A>>

Block B:
\`\`\`text
BBBB
\`\`\` <<BLOCK_B>>

Save A:
\`\`\`json
{ "tool": "test", "args": { "content": "{{BLOCK_A}}" } }
\`\`\`
        `;
        const calls = parseToolCalls(input);
        expect(calls).toHaveLength(1);
        expect(calls[0].arguments.content).toContain('AAAA');
        expect(calls[0].arguments.content).not.toContain('BBBB');
    });

    it('should handle nested substitution in objects', () => {
        const input = `
\`\`\`text
SECRET
\`\`\` <<SEC>>

\`\`\`json
{ "tool": "test", "args": { "nested": { "val": "{{SEC}}" } } }
\`\`\`
        `;
        const calls = parseToolCalls(input);
        expect(calls[0].arguments.nested.val).toContain('SECRET');
    });
});

