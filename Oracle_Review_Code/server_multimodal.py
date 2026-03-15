import os
import json
import base64
import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Optional, List
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

# Initialize FastMCP Server
mcp = FastMCP("multimodal")

@mcp.tool()
async def analyze_image(image_path: str, prompt: str) -> str:
    """
    Perform visual question answering and description extraction on an image.
    Uses Gemini Vision models to analyze local images.
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
    except ImportError:
        return "[Error] langchain-google-genai is not installed."

    if not os.path.exists(image_path):
        return f"[Error] Image not found at path: {image_path}"

    try:
        # Determine MIME type
        ext = image_path.split('.')[-1].lower()
        mime_type = f"image/{ext}" if ext in ["jpg", "jpeg", "png", "webp"] else "image/jpeg"

        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        # Use Gemini model, leveraging environment API key
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GEMINI_API_KEY"))
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                },
            ]
        )
        
        response = await llm.ainvoke([message])
        return str(response.content)
    except Exception as e:
        return f"[Error] Failed to analyze image: {str(e)}"

@mcp.tool()
async def analyze_pdf_document(pdf_path: str, prompt: str) -> str:
    """
    Extracts content from a PDF and uses an LLM to answer questions about the document.
    Good for deep document intelligence.
    """
    try:
        import pymupdf4llm
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        return "[Error] pymupdf4llm or langchain-google-genai not installed."

    if not os.path.exists(pdf_path):
        return f"[Error] PDF not found at path: {pdf_path}"

    try:
        # Extract markdown from PDF
        md_text = pymupdf4llm.to_markdown(pdf_path)
        
        # If the prompt just wants the text, return it (clamped to avoid massive context sizes if not needed)
        if prompt.lower().strip() in ["extract text", "get content", "read document"]:
            return md_text[:25000]

        # Otherwise use an LLM to answer the prompt based on the content
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GEMINI_API_KEY"))
        
        # We clamp the text if it's too huge, but Gemini Flash handles 1M tokens natively. 
        # For safety and speed, we will send up to 100k characters.
        context = md_text[:100000] 
        
        final_prompt = f"Document Content:\n{context}\n\nUser Question: {prompt}\n\nPlease analyze the document and answer the user's question."
        response = await llm.ainvoke(final_prompt)
        return str(response.content)

    except Exception as e:
        return f"[Error] Failed to process PDF: {str(e)}"

@mcp.tool()
async def analyze_data_file(file_path: str, prompt: str) -> str:
    """
    Parses CSV files, generates statistical summaries (mean, sum, count, min, max for numeric columns),
    and answers questions about the data. (Excel files must be converted to CSV first).
    """
    if not os.path.exists(file_path):
        return f"[Error] Data file not found at path: {file_path}"
    
    if not file_path.lower().endswith('.csv'):
        return f"[Error] Only .csv files are currently supported. Please provide a CSV file."

    try:
        columns = defaultdict(list)
        row_count = 0
        
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_count += 1
                for key, val in row.items():
                    columns[key].append(val)
        
        # Generate stats
        stats_summary = []
        stats_summary.append(f"Total Rows: {row_count}")
        
        sample_data = {}
        for col, values in columns.items():
            if not col: continue
            
            # Save a small sample for the LLM
            sample_data[col] = values[:5]

            # Try to convert to float to see if numeric
            numeric_vals = []
            for v in values:
                try:
                    if v and str(v).strip() != "":
                        numeric_vals.append(float(v))
                except ValueError:
                    pass
            
            if len(numeric_vals) > (len(values) * 0.5): # if mostly numeric
                stats_summary.append(f"Column '{col}' (Numeric): Count={len(numeric_vals)}, Mean={statistics.mean(numeric_vals):.2f}, Min={min(numeric_vals)}, Max={max(numeric_vals)}")
            else:
                # categorical or string
                unique_vals = set(values)
                stats_summary.append(f"Column '{col}' (Categorical): {len(unique_vals)} unique values. Sample: {values[:3]}")

        stats_text = "\n".join(stats_summary)
        
        # LLM Analysis
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GEMINI_API_KEY"))
            
            final_prompt = (
                f"Data File Analysis for '{os.path.basename(file_path)}':\n\n"
                f"Statistical Summary:\n{stats_text}\n\n"
                f"Sample Data (first 5 rows):\n{json.dumps(sample_data, indent=2)}\n\n"
                f"User Question: {prompt}\n\n"
                f"Based on the statistical summary and sample data, please answer the user's question."
            )
            response = await llm.ainvoke(final_prompt)
            return str(response.content)
            
        except ImportError:
            # Fallback to just returning stats if no LLM
            return f"Stats:\n{stats_text}\n\nQuery: {prompt} (LLM not available to answer queries)"

    except Exception as e:
        return f"[Error] Data analysis failed: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
