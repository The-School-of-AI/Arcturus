
const accumulatedContent = `[System Tool Output]:

> Tool Output (run_command):
\`\`\`
STDOUT:
Hello
STDERR:
World
\`\`\`
`;

const regex = />?\s*Tool Output \((.*?)\):?\s*?\n+```(?:[\w-]*\n)?([\s\S]*?)```/g;
let match;
const results = [];
while ((match = regex.exec(accumulatedContent)) !== null) {
    results.push({ name: match[1], output: match[2] });
}

console.log("Input Length:", accumulatedContent.length);
console.log("Matches Found:", results.length);
if (results.length > 0) {
    console.log("Match 1 Name:", results[0].name.trim());
    console.log("Match 1 Output:", results[0].output.trim());
} else {
    console.log("No matches found.");
}
