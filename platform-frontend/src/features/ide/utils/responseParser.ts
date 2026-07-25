
export interface ToolCall {
    name: string;
    arguments: Record<string, any>;
}

export function parseToolCalls(content: string): ToolCall[] {
    // 1. Extract ALL code blocks and map them by optional ID (and keep track of latest)
    const blockMap = new Map<string, string>();
    let lastBlockContent: string | null = null;

    // Regex to find code blocks, optionally followed by <<ID>>
    // Group 1: Content inside backticks
    // Group 2: ID tag (optional, e.g. <<MyBlock>>)
    // Matches ```lang ... ``` <<ID>>
    const blockRegex = /```(?:\w+)?\s*([\s\S]*?)\s*```\s*(?:<<([A-Za-z0-9_]+)>>)?/g;

    let blockMatch;
    // Iterate through all blocks to build context
    while ((blockMatch = blockRegex.exec(content)) !== null) {
        const blockContent = blockMatch[1];
        const blockId = blockMatch[2]; // undefined if no tag

        // Only consider it a "code block" for injection if it doesn't look like a tool call response
        if (!blockContent.trim().startsWith('{') || !blockContent.includes('"tool"')) {
            lastBlockContent = blockContent;
            if (blockId) {
                blockMap.set(blockId, blockContent);
            }
        }
    }

    // 2. Extract Tool Calls
    // We iterate again to find the actual JSON blocks
    // Regex that handles any language identifier (json, tool_code, etc.) or none
    const toolRegex = /```\s*(?:\w+)?\s*([\s\S]*?)\s*```/g;
    const toolCalls: ToolCall[] = [];
    let match;

    while ((match = toolRegex.exec(content)) !== null) {
        try {
            const rawJson = match[1];
            const jsonCall = JSON.parse(rawJson);

            if (jsonCall.tool || jsonCall.name) {
                let args = jsonCall.args || jsonCall.arguments || {};

                // 3. Perform Substitution on String Arguments
                args = substituteArgs(args, blockMap, lastBlockContent);

                toolCalls.push({
                    name: jsonCall.tool || jsonCall.name,
                    arguments: args
                });
            }
        } catch (e) {
            // Ignore non-JSON blocks
        }
    }

    // 4. Fallback: Parse XML-style tool calls (e.g. <list_dir path="." /> or <read_file><path>src/App.tsx</path></read_file>)
    if (toolCalls.length === 0) {
        const xmlToolCalls = parseXmlToolCalls(content);
        toolCalls.push(...xmlToolCalls);
    }

    return toolCalls;
}

/**
 * Parse XML-style tool calls that some models emit instead of JSON.
 * Handles both self-closing (<tool_name arg="val" />) and
 * wrapped (<tool_name><arg>val</arg></tool_name>) formats.
 */
function parseXmlToolCalls(content: string): ToolCall[] {
    const toolNames = [
        'read_file', 'write_file', 'replace_in_file', 'multi_replace_file_content',
        'list_dir', 'run_command', 'search_web', 'find_by_name', 'grep_search',
        'view_file_outline', 'read_terminal', 'read_url', 'command_status',
        'run_script', 'apply_diff', 'replace_symbol'
    ];
    const results: ToolCall[] = [];
    const namePattern = toolNames.join('|');

    // Self-closing: <tool_name key="value" key2="value2" />
    const selfClosingRegex = new RegExp(`<(${namePattern})\\s+([^>]*?)\\s*/>`, 'g');
    let m;
    while ((m = selfClosingRegex.exec(content)) !== null) {
        const name = m[1];
        const attrsStr = m[2];
        const args: Record<string, string> = {};
        const attrRegex = /(\w+)="([^"]*)"/g;
        let a;
        while ((a = attrRegex.exec(attrsStr)) !== null) {
            args[a[1]] = a[2];
        }
        results.push({ name, arguments: args });
    }

    // Wrapped: <tool_name><arg>value</arg></tool_name>
    const wrappedRegex = new RegExp(`<(${namePattern})>([\\s\\S]*?)<\\/\\1>`, 'g');
    while ((m = wrappedRegex.exec(content)) !== null) {
        const name = m[1];
        const inner = m[2];
        const args: Record<string, string> = {};
        const childRegex = /<(\w+)>([\s\S]*?)<\/\1>/g;
        let c;
        while ((c = childRegex.exec(inner)) !== null) {
            args[c[1]] = c[2];
        }
        if (Object.keys(args).length > 0) {
            results.push({ name, arguments: args });
        }
    }

    return results;
}

function substituteArgs(args: any, blockMap: Map<string, string>, lastBlock: string | null): any {
    if (typeof args === 'string') {
        const trimmed = args.trim();
        // Check for {{CODE_BLOCK}} or {{LAST_CODE_BLOCK}}
        if (trimmed === '{{CODE_BLOCK}}' || trimmed === '{{LAST_CODE_BLOCK}}') {
            return lastBlock || args;
        }

        // Check for {{ID}} regex match
        // Note: We use a regex to match the EXACT whole string for safety, or substring?
        // User asked for usage like content: "{{BLOCK}}"
        // If they embed it like "some text {{BLOCK}}", we should probably replace.
        // But for code injection, usually it's the WHOLE payload.
        // Let's do exact match OR regex replacement.

        // If exact match with ID
        const exactIdMatch = trimmed.match(/^{{([A-Za-z0-9_]+)}}$/);
        if (exactIdMatch) {
            const id = exactIdMatch[1];
            if (blockMap.has(id)) return blockMap.get(id);
        }

        return args;
    } else if (Array.isArray(args)) {
        return args.map(item => substituteArgs(item, blockMap, lastBlock));
    } else if (typeof args === 'object' && args !== null) {
        const newArgs: any = {};
        for (const key in args) {
            newArgs[key] = substituteArgs(args[key], blockMap, lastBlock);
        }
        return newArgs;
    }
    return args;
}
