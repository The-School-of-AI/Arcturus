import asyncio
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shared.state import get_multi_mcp

async def test_tools():
    mcp = get_multi_mcp()
    await mcp.start()
    
    # Give servers 2 seconds to initialize caching
    await asyncio.sleep(2)
    
    results = []
    def log(title, res):
        print(f"\n{'='*50}\n{title}\n{'-'*50}\n{res}\n{'='*50}")
        results.append(f"### {title}\n```text\n{res}\n```\n")

    # 1. Data Analysis (CSV)
    print("Testing Data Analysis...")
    csv_path = "sample_data.csv"
    res1 = await mcp.function_wrapper("analyze_data_file", csv_path, "What is the total revenue across all years?")
    log("2.5 Multimodal Search: Data Analysis (CSV)", res1)
    
    # 2. Workspace Search
    print("Testing Workspace Search...")
    res3 = await mcp.function_wrapper("search_workspace_files", "delivery readme", ".")
    log("2.6 Internal Knowledge: Workspace Search", res3)
    
    # 3. Spaces & Collections
    print("Testing Spaces (Create)...")
    res4 = await mcp.function_wrapper("create_space", "p02_final_review")
    log("2.6 Internal Knowledge: Create Space", res4)
    
    print("Testing Spaces (Add)...")
    res5 = await mcp.function_wrapper("add_to_space", "p02_final_review", "All backend tests and multimodal scripts verified by agent.")
    log("2.6 Internal Knowledge: Add to Space", res5)
    
    print("Testing Spaces (Search)...")
    res6 = await mcp.function_wrapper("search_space", "p02_final_review")
    log("2.6 Internal Knowledge: Search Space", res6)
    
    # 4. Image Analysis (using the generated image)
    import glob
    images = glob.glob(r"C:\Users\nishc\.gemini\antigravity\brain\1047b03c-7d5b-4902-b6e1-07db590f97ad\oracle_test_image_*.png")
    if images:
        print("Testing Image Analysis...")
        res_img = await mcp.function_wrapper("analyze_image", images[0], "Describe the UI in this screenshot.")
        log("2.5 Multimodal Search: Image Analysis", res_img)

    with open("test_results_teja.md", "w", encoding="utf-8") as f:
        f.write("# P02 Oracle Feature Verification Results\n\n")
        f.write("This artifact contains the raw outputs directly from the MCP server tooling to prove exact feature functionality.\n\n")
        f.write("\n".join(results))
        
    await mcp.stop()

if __name__ == "__main__":
    asyncio.run(test_tools())
