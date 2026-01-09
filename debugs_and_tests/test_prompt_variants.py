#!/usr/bin/env python3
"""
Prompt Variant Testing Script
=============================
Tests 4 variants each for:
1. Semantic Chunking Prompts
2. Image Captioning Prompts

Uses the Transformer paper (1706.03762v7.pdf) as the test document.
"""

import sys
import os
import re
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable
import requests

# --- Config ---
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_TIMEOUT = 120
CHUNK_MODEL = "gemma3:4b"
VISION_MODEL = "gemma3:4b"

PDF_PATH = "/Users/rohanshravan/TSAI/Arcturus/data/pdfs/1706.03762v7.pdf"
IMAGE_DIR = Path("/Users/rohanshravan/TSAI/Arcturus/mcp_servers/documents/images")
RESULTS_FILE = Path("/Users/rohanshravan/TSAI/Arcturus/debugs_and_tests/prompt_test_results.json")

# Add paths for PDF extraction
sys.path.append("/Users/rohanshravan/TSAI/Arcturus/mcp_servers")
sys.path.append("/Users/rohanshravan/TSAI/Arcturus")

import pymupdf4llm
import base64
from PIL import Image
import io

# ============================================================================
# CHUNKING PROMPT VARIANTS
# ============================================================================

CHUNKING_PROMPTS = {
    "V1_ORIGINAL": """You are helping to segment a document into topic-based chunks. Unfortunately, the sentences are mixed up in this text block.

Does the TEXT BLOCK below have 2+ distinct topics? Should these two chunks appear in the **same paragraph or flow of writing**? Even if the subject changes slightly (e.g., One person to another), treat them as related **if they belong to the same broader context or topic** (like cricket, AI, or real estate). Also consider cues like continuity words (e.g., "However", "But", "Also") or references that link the sentences.

YES: Reply with first 15 words of second topic.
NO: Reply "SINGLE"

TEXT BLOCK: {text_preview}""",
    
    "V2_BOUNDARY_DETECTION": """You are a document segmentation assistant.

Below is an ordered list of sentences from a document. Your task is to find where the topic clearly changes.

INSTRUCTIONS:
1. Read the sentences carefully.
2. If there is a clear topic shift, reply with ONLY the sentence number where the NEW topic begins (e.g., "7").
3. If all sentences belong to the same topic, reply with "NONE".

SENTENCES:
{numbered_sentences}

ANSWER (number or NONE):""",

    "V3_BINARY_SPLIT": """Read the following text excerpt.

Does this text contain TWO or more distinctly different subjects or themes?
- A shift from "introduction" to "methodology" counts as different.
- A shift from "topic A" to "topic B" counts as different.
- Minor elaborations on the same subject do NOT count.

TEXT:
{text_preview}

Reply with exactly one word: YES or NO.""",

    "V4_EXTRACTIVE_BOUNDARY": """You are analyzing a document for topic boundaries.

Here is an excerpt. If there is a clear point where the subject changes, output the EXACT first 10 characters of the sentence that starts the new topic. Otherwise, output "CONTINUOUS".

RULES:
- Copy the characters exactly as they appear (including punctuation).
- Only mark a boundary if the subject genuinely changes.
- Do not mark boundaries for paragraph breaks or stylistic transitions.

TEXT:
{text_preview}

OUTPUT:"""
}

# ============================================================================
# IMAGE CAPTIONING PROMPT VARIANTS
# ============================================================================

IMAGE_PROMPTS = {
    "V1_ORIGINAL": """Look only at the attached image. If it's code, output it exactly as text. If it's a visual scene, describe it as you would for an image alt-text. Never generate new code. Return only the contents of the image.""",

    "V2_RAG_OPTIMIZED": """You are creating a searchable caption for a RAG (Retrieval-Augmented Generation) system.

CONTEXT FROM DOCUMENT:
{surrounding_text}

Analyze the attached image and produce a caption that:
1. Extracts ALL visible text labels, titles, and annotations.
2. Describes the type of visual (diagram, chart, photo, table, code).
3. Explains what information this image conveys.

Your caption should help someone find this image when searching for related concepts.""",

    "V3_STRUCTURED_EXTRACTION": """Analyze this image and respond in the following format:

TYPE: [diagram/chart/photo/table/code/other]
VISIBLE_TEXT: [List all text visible in the image, separated by semicolons]
DESCRIPTION: [One sentence describing what the image shows]
KEY_CONCEPTS: [Comma-separated list of concepts someone might search for]""",

    "V4_CONTEXT_AWARE": """The following text appears near this image in the document:
---
{surrounding_text}
---

Based on this context, describe what this image shows. Focus on:
1. Any text or labels visible in the image.
2. How the image relates to the surrounding text.
3. Key terms that would help retrieve this image in a search.

Keep your response concise (2-3 sentences max)."""
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_pdf_markdown(pdf_path: str) -> str:
    """Extract markdown from PDF."""
    print(f"Extracting markdown from {pdf_path}...")
    return pymupdf4llm.to_markdown(pdf_path, write_images=False)

def get_numbered_sentences(text: str, max_sentences: int = 15) -> str:
    """Convert text to numbered sentences for V2 prompt."""
    # Simple sentence split
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10][:max_sentences]
    return "\n".join([f"{i+1}. {s}" for i, s in enumerate(sentences)])

def get_text_preview(text: str, prefix_chars: int = 800, suffix_chars: int = 400) -> str:
    """Get prefix + suffix preview (for V1, V3, V4)."""
    if len(text) <= prefix_chars + suffix_chars:
        return text
    return f"{text[:prefix_chars]}\n...[MIDDLE OMITTED]...\n{text[-suffix_chars:]}"

def call_llm(prompt: str, model: str = CHUNK_MODEL) -> tuple[str, float]:
    """Call Ollama and return (response, time_taken)."""
    start = time.time()
    try:
        response = requests.post(OLLAMA_CHAT_URL, json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 100}
        }, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        result = response.json().get("message", {}).get("content", "").strip()
        return result, time.time() - start
    except Exception as e:
        return f"ERROR: {e}", time.time() - start

def call_vision_llm(prompt: str, image_path: str, model: str = VISION_MODEL) -> tuple[str, float]:
    """Call Ollama vision model with image."""
    start = time.time()
    try:
        # Load and encode image
        with Image.open(image_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            if max(img.size) > 1024:
                img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        
        response = requests.post(OLLAMA_GENERATE_URL, json={
            "model": model,
            "prompt": prompt,
            "images": [encoded],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 200}
        }, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        result = response.json().get("response", "").strip()
        return result, time.time() - start
    except Exception as e:
        return f"ERROR: {e}", time.time() - start

# ============================================================================
# TEST RUNNERS
# ============================================================================

def test_chunking_prompts(markdown: str) -> dict:
    """Test all chunking prompt variants on a sample of text."""
    print("\n" + "="*60)
    print("TESTING CHUNKING PROMPTS")
    print("="*60)
    
    # Take a ~1500 word sample from the middle of the document
    words = markdown.split()
    start_idx = len(words) // 4
    sample_text = " ".join(words[start_idx:start_idx + 1500])
    
    results = {}
    
    for variant_name, prompt_template in CHUNKING_PROMPTS.items():
        print(f"\n--- Testing {variant_name} ---")
        
        # Prepare the prompt based on variant
        if variant_name == "V2_BOUNDARY_DETECTION":
            formatted_prompt = prompt_template.format(
                numbered_sentences=get_numbered_sentences(sample_text)
            )
        else:
            formatted_prompt = prompt_template.format(
                text_preview=get_text_preview(sample_text)
            )
        
        # Run 3 trials for timing consistency
        responses = []
        times = []
        for trial in range(3):
            response, elapsed = call_llm(formatted_prompt)
            responses.append(response)
            times.append(elapsed)
            print(f"  Trial {trial+1}: {elapsed:.2f}s - Response: {response[:80]}...")
        
        results[variant_name] = {
            "responses": responses,
            "avg_time": sum(times) / len(times),
            "prompt_length": len(formatted_prompt),
            "sample_response": responses[0]
        }
        
        # Quick quality assessment
        if variant_name == "V1_ORIGINAL":
            is_valid = responses[0] == "SINGLE" or len(responses[0].split()) >= 5
        elif variant_name == "V2_BOUNDARY_DETECTION":
            is_valid = responses[0] == "NONE" or responses[0].isdigit()
        elif variant_name == "V3_BINARY_SPLIT":
            is_valid = responses[0].upper() in ["YES", "NO"]
        elif variant_name == "V4_EXTRACTIVE_BOUNDARY":
            is_valid = responses[0] == "CONTINUOUS" or len(responses[0]) >= 5
        else:
            is_valid = True
            
        results[variant_name]["valid_format"] = is_valid
        print(f"  Valid format: {is_valid}")
    
    return results

def test_image_prompts() -> dict:
    """Test all image captioning prompt variants."""
    print("\n" + "="*60)
    print("TESTING IMAGE CAPTIONING PROMPTS")
    print("="*60)
    
    # Find images from the Transformer PDF
    pdf_images = list(IMAGE_DIR.glob("1706.03762v7.pdf-*.png"))
    if not pdf_images:
        print("No images found! Run document indexing first.")
        return {}
    
    # Take first 2 images for testing
    test_images = pdf_images[:2]
    print(f"Found {len(pdf_images)} images, testing on {len(test_images)}")
    
    # Sample surrounding context (simulated)
    sample_context = """The Transformer follows this overall architecture using stacked self-attention and point-wise, fully connected layers for both the encoder and decoder, shown in the left and right halves of Figure 1, respectively."""
    
    results = {}
    
    for variant_name, prompt_template in IMAGE_PROMPTS.items():
        print(f"\n--- Testing {variant_name} ---")
        
        variant_results = []
        
        for img_path in test_images:
            print(f"  Image: {img_path.name}")
            
            # Prepare prompt
            if "{surrounding_text}" in prompt_template:
                prompt = prompt_template.format(surrounding_text=sample_context)
            else:
                prompt = prompt_template
            
            response, elapsed = call_vision_llm(prompt, str(img_path))
            
            variant_results.append({
                "image": img_path.name,
                "response": response,
                "time": elapsed,
                "response_length": len(response)
            })
            
            print(f"    Time: {elapsed:.2f}s")
            print(f"    Response: {response[:100]}...")
        
        avg_time = sum(r["time"] for r in variant_results) / len(variant_results)
        avg_length = sum(r["response_length"] for r in variant_results) / len(variant_results)
        
        results[variant_name] = {
            "images_tested": len(test_images),
            "avg_time": avg_time,
            "avg_response_length": avg_length,
            "prompt_length": len(prompt),
            "details": variant_results
        }
        
        print(f"  Avg time: {avg_time:.2f}s, Avg response length: {avg_length:.0f} chars")
    
    return results

def analyze_results(chunking_results: dict, image_results: dict) -> dict:
    """Analyze and score all results."""
    print("\n" + "="*60)
    print("ANALYSIS SUMMARY")
    print("="*60)
    
    analysis = {"chunking": {}, "captioning": {}}
    
    # Chunking analysis
    print("\n### CHUNKING PROMPTS ###")
    for variant, data in chunking_results.items():
        score = 0
        
        # Speed score (lower is better, max 3 points)
        if data["avg_time"] < 1.0:
            score += 3
        elif data["avg_time"] < 2.0:
            score += 2
        elif data["avg_time"] < 3.0:
            score += 1
        
        # Format validity (2 points)
        if data["valid_format"]:
            score += 2
        
        # Prompt efficiency (shorter = better, max 2 points)
        if data["prompt_length"] < 500:
            score += 2
        elif data["prompt_length"] < 800:
            score += 1
        
        # Consistency (all 3 trials same response = 2 points)
        if len(set(data["responses"])) == 1:
            score += 2
        
        analysis["chunking"][variant] = {
            "score": score,
            "avg_time": data["avg_time"],
            "valid_format": data["valid_format"],
            "consistent": len(set(data["responses"])) == 1,
            "sample_response": data["sample_response"]
        }
        
        print(f"{variant}: Score={score}/9, Time={data['avg_time']:.2f}s, Valid={data['valid_format']}, Consistent={len(set(data['responses'])) == 1}")
    
    # Image analysis
    print("\n### IMAGE CAPTIONING PROMPTS ###")
    for variant, data in image_results.items():
        score = 0
        
        # Speed score (max 3 points)
        if data["avg_time"] < 3.0:
            score += 3
        elif data["avg_time"] < 5.0:
            score += 2
        elif data["avg_time"] < 8.0:
            score += 1
        
        # Response richness (longer = more detail, max 3 points)
        if data["avg_response_length"] > 300:
            score += 3
        elif data["avg_response_length"] > 150:
            score += 2
        elif data["avg_response_length"] > 50:
            score += 1
        
        # Prompt efficiency (max 2 points)
        if data["prompt_length"] < 300:
            score += 2
        elif data["prompt_length"] < 500:
            score += 1
        
        analysis["captioning"][variant] = {
            "score": score,
            "avg_time": data["avg_time"],
            "avg_response_length": data["avg_response_length"],
            "details": data["details"]
        }
        
        print(f"{variant}: Score={score}/8, Time={data['avg_time']:.2f}s, AvgLen={data['avg_response_length']:.0f}")
    
    return analysis

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("="*60)
    print("PROMPT VARIANT TESTING SCRIPT")
    print("="*60)
    
    # 1. Extract markdown
    markdown = extract_pdf_markdown(PDF_PATH)
    print(f"Extracted {len(markdown)} characters from PDF")
    
    # 2. Test chunking prompts
    chunking_results = test_chunking_prompts(markdown)
    
    # 3. Test image prompts
    image_results = test_image_prompts()
    
    # 4. Analyze
    analysis = analyze_results(chunking_results, image_results)
    
    # 5. Save results
    full_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pdf": PDF_PATH,
        "chunking_results": chunking_results,
        "image_results": image_results,
        "analysis": analysis
    }
    
    RESULTS_FILE.write_text(json.dumps(full_results, indent=2, default=str))
    print(f"\nResults saved to: {RESULTS_FILE}")
    
    # 6. Print recommendations
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    
    best_chunking = max(analysis["chunking"].items(), key=lambda x: x[1]["score"])
    best_captioning = max(analysis["captioning"].items(), key=lambda x: x[1]["score"])
    
    print(f"\nBest Chunking Prompt: {best_chunking[0]} (Score: {best_chunking[1]['score']}/9)")
    print(f"Best Captioning Prompt: {best_captioning[0]} (Score: {best_captioning[1]['score']}/8)")

if __name__ == "__main__":
    main()
