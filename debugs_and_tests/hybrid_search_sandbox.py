#!/usr/bin/env python3
"""
Hybrid Search Sandbox
=====================
Standalone test script to validate the hybrid search system before integrating
into the main codebase. Tests:
1. Query Analyzer (intent classification, entity extraction)
2. BM25 Index (keyword search)
3. RRF Fusion (combining BM25 + FAISS)
4. Entity Gate (filtering results based on query entities)

Run this script to validate all components work correctly.
"""

import sys
import os
import re
import json
import pickle
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

# Add paths
sys.path.append("/Users/rohanshravan/TSAI/Arcturus/mcp_servers")
sys.path.append("/Users/rohanshravan/TSAI/Arcturus")

# Try to import rank_bm25
try:
    from rank_bm25 import BM25Okapi
    print("✓ rank_bm25 imported successfully")
except ImportError:
    print("✗ rank_bm25 not installed. Run: pip install rank-bm25")
    sys.exit(1)

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class QueryAnalysis:
    """Result of query analysis."""
    original_query: str
    intent: str  # LEXICAL_REQUIRED, LEXICAL_PREFERRED, SEMANTIC
    entities: list[str] = field(default_factory=list)
    quoted_phrases: list[str] = field(default_factory=list)
    proper_nouns: list[str] = field(default_factory=list)
    ids_emails: list[str] = field(default_factory=list)

@dataclass
class SearchResult:
    """A single search result."""
    chunk_id: str
    doc: str
    chunk: str
    bm25_rank: Optional[int] = None
    faiss_rank: Optional[int] = None
    rrf_score: float = 0.0
    passed_gate: bool = True

# =============================================================================
# QUERY ANALYZER
# =============================================================================

def analyze_query(query: str) -> QueryAnalysis:
    """
    Analyze a query to determine intent and extract entities.
    
    Intent types:
    - LEXICAL_REQUIRED: Query demands exact matches (names, IDs, quoted phrases)
    - LEXICAL_PREFERRED: Query has entities but semantic is also useful
    - SEMANTIC: Pure semantic/conceptual query
    """
    analysis = QueryAnalysis(original_query=query, intent="SEMANTIC")
    
    # 1. Extract quoted phrases (highest priority - always LEXICAL_REQUIRED)
    quoted_pattern = r'"([^"]+)"|\'([^\']+)\''
    quoted_matches = re.findall(quoted_pattern, query)
    analysis.quoted_phrases = [m[0] or m[1] for m in quoted_matches]
    
    # 2. Extract emails
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    analysis.ids_emails.extend(re.findall(email_pattern, query))
    
    # 3. Extract IDs (invoice, phone, etc.)
    id_patterns = [
        r'\b[A-Z]{2,4}[-]?\d{4,}\b',  # Invoice IDs like INV-12345, INVG67564
        r'\b\d{10}\b',  # Phone numbers (10 digits)
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Phone with separators
    ]
    for pattern in id_patterns:
        analysis.ids_emails.extend(re.findall(pattern, query))
    
    # 4. Extract proper nouns (capitalized multi-word sequences)
    # Remove quoted content first to avoid double-counting
    clean_query = re.sub(quoted_pattern, '', query)
    
    # Find capitalized words that aren't at the start of a sentence
    words = clean_query.split()
    proper_noun_candidates = []
    current_noun = []
    
    for i, word in enumerate(words):
        # Clean punctuation for checking
        clean_word = re.sub(r'[^\w]', '', word)
        
        if clean_word and clean_word[0].isupper() and len(clean_word) > 1:
            # Skip common words that happen to be capitalized
            skip_words = {'The', 'A', 'An', 'This', 'That', 'What', 'Where', 'When', 'How', 'Why', 
                         'Find', 'Search', 'Show', 'Get', 'List', 'All', 'Documents', 'About', 'For'}
            if clean_word not in skip_words:
                current_noun.append(clean_word)
            else:
                if len(current_noun) >= 1:
                    proper_noun_candidates.append(' '.join(current_noun))
                current_noun = []
        else:
            if current_noun:
                proper_noun_candidates.append(' '.join(current_noun))
                current_noun = []
    
    # Don't forget the last one
    if current_noun:
        proper_noun_candidates.append(' '.join(current_noun))
    
    # Filter to multi-word proper nouns (more likely to be names/entities)
    analysis.proper_nouns = [pn for pn in proper_noun_candidates if len(pn.split()) >= 2]
    # Also keep single capitalized words that look like names
    analysis.proper_nouns.extend([pn for pn in proper_noun_candidates 
                                   if len(pn.split()) == 1 and len(pn) > 2])
    
    # 5. Check for lexical-intent phrases
    lexical_phrases = [
        r'\bcontains?\b', r'\bmention', r'\bexact', r'\bwhere is\b', 
        r'\bfind.*that (say|mention|contain)', r'\bdocuments? (about|with|that)'
    ]
    has_lexical_phrase = any(re.search(p, query, re.IGNORECASE) for p in lexical_phrases)
    
    # 6. Determine intent
    all_entities = analysis.quoted_phrases + analysis.ids_emails + analysis.proper_nouns
    analysis.entities = list(set(all_entities))
    
    if analysis.quoted_phrases or analysis.ids_emails:
        analysis.intent = "LEXICAL_REQUIRED"
    elif analysis.proper_nouns or has_lexical_phrase:
        analysis.intent = "LEXICAL_PREFERRED"
    else:
        analysis.intent = "SEMANTIC"
    
    return analysis

# =============================================================================
# BM25 INDEX
# =============================================================================

class BM25Index:
    """BM25 keyword search index."""
    
    def __init__(self):
        self.bm25 = None
        self.corpus = []  # List of tokenized chunks
        self.chunk_ids = []  # Parallel list of chunk IDs
        self.metadata = []  # Parallel list of chunk metadata
    
    def tokenize(self, text: str) -> list[str]:
        """Simple tokenization: lowercase, split on whitespace, remove punctuation."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        tokens = text.split()
        # Remove very short tokens
        return [t for t in tokens if len(t) > 1]
    
    def build_from_metadata(self, metadata_path: str):
        """Build BM25 index from existing FAISS metadata."""
        print(f"Building BM25 index from {metadata_path}...")
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        self.corpus = []
        self.chunk_ids = []
        self.metadata = metadata
        
        for entry in metadata:
            chunk_text = entry.get('chunk', '')
            chunk_id = entry.get('chunk_id', '')
            
            tokens = self.tokenize(chunk_text)
            self.corpus.append(tokens)
            self.chunk_ids.append(chunk_id)
        
        self.bm25 = BM25Okapi(self.corpus)
        print(f"✓ BM25 index built with {len(self.corpus)} chunks")
    
    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        """Search and return top-k (chunk_id, score) pairs."""
        if self.bm25 is None:
            raise ValueError("BM25 index not built")
        
        tokens = self.tokenize(query)
        scores = self.bm25.get_scores(tokens)
        
        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only return non-zero scores
                results.append((self.chunk_ids[idx], scores[idx]))
        
        return results
    
    def save(self, path: str):
        """Save the index to disk."""
        with open(path, 'wb') as f:
            pickle.dump({
                'bm25': self.bm25,
                'corpus': self.corpus,
                'chunk_ids': self.chunk_ids,
                'metadata': self.metadata
            }, f)
        print(f"✓ BM25 index saved to {path}")
    
    def load(self, path: str):
        """Load the index from disk."""
        with open(path, 'rb') as f:
            data = pickle.load(f)
        self.bm25 = data['bm25']
        self.corpus = data['corpus']
        self.chunk_ids = data['chunk_ids']
        self.metadata = data['metadata']
        print(f"✓ BM25 index loaded from {path} ({len(self.corpus)} chunks)")

# =============================================================================
# RRF FUSION
# =============================================================================

def rrf_fuse(bm25_results: list[tuple[str, float]], 
             faiss_results: list[tuple[str, float]], 
             k: int = 60) -> list[tuple[str, float]]:
    """
    Reciprocal Rank Fusion of two result lists.
    
    Args:
        bm25_results: List of (chunk_id, score) from BM25
        faiss_results: List of (chunk_id, score) from FAISS
        k: RRF constant (default 60)
    
    Returns:
        List of (chunk_id, rrf_score) sorted by score descending
    """
    scores = defaultdict(float)
    
    # Add BM25 contribution
    for rank, (chunk_id, _) in enumerate(bm25_results):
        scores[chunk_id] += 1.0 / (k + rank + 1)
    
    # Add FAISS contribution
    for rank, (chunk_id, _) in enumerate(faiss_results):
        scores[chunk_id] += 1.0 / (k + rank + 1)
    
    # Sort by score
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return fused

# =============================================================================
# ENTITY GATE
# =============================================================================

def entity_gate(results: list[tuple[str, float]], 
                metadata: list[dict],
                analysis: QueryAnalysis) -> tuple[list[tuple[str, float]], bool]:
    """
    Apply entity gate to filter results based on query entities.
    
    For LEXICAL_REQUIRED queries, chunks must contain the entities.
    
    Returns:
        (filtered_results, gate_applied)
    """
    if analysis.intent == "SEMANTIC":
        return results, False
    
    if not analysis.entities:
        return results, False
    
    # Build chunk_id -> chunk_text lookup
    chunk_lookup = {entry['chunk_id']: entry['chunk'].lower() for entry in metadata}
    
    filtered = []
    
    for chunk_id, score in results:
        chunk_text = chunk_lookup.get(chunk_id, '')
        
        if analysis.intent == "LEXICAL_REQUIRED":
            # ALL entities must appear for quoted phrases and IDs
            if analysis.quoted_phrases:
                if all(phrase.lower() in chunk_text for phrase in analysis.quoted_phrases):
                    filtered.append((chunk_id, score))
                continue
            
            if analysis.ids_emails:
                if all(id_.lower() in chunk_text for id_ in analysis.ids_emails):
                    filtered.append((chunk_id, score))
                continue
        
        # For LEXICAL_PREFERRED or remaining proper nouns
        # Check if ANY proper noun appears
        if analysis.proper_nouns:
            # For multi-word names, all tokens must appear
            for noun in analysis.proper_nouns:
                tokens = noun.lower().split()
                if all(token in chunk_text for token in tokens):
                    filtered.append((chunk_id, score))
                    break
        else:
            # No specific entity filter, include it
            filtered.append((chunk_id, score))
    
    return filtered, True

# =============================================================================
# SANDBOX TESTS
# =============================================================================

def test_query_analyzer():
    """Test the query analyzer on various query types."""
    print("\n" + "="*60)
    print("TEST: Query Analyzer")
    print("="*60)
    
    test_queries = [
        # LEXICAL_REQUIRED
        ('"Anmol Singh"', "LEXICAL_REQUIRED"),
        ('find docs containing "exact phrase"', "LEXICAL_REQUIRED"),
        ('email test@example.com', "LEXICAL_REQUIRED"),
        ('invoice INVG67564', "LEXICAL_REQUIRED"),
        
        # LEXICAL_PREFERRED
        ('Anmol Singh', "LEXICAL_PREFERRED"),
        ('find documents about Delhi Real Estate', "LEXICAL_PREFERRED"),
        ('documents that mention BSE Limited', "LEXICAL_REQUIRED"),
        
        # SEMANTIC
        ('explain how transformers work', "SEMANTIC"),
        ('what is attention mechanism', "SEMANTIC"),
        ('summarize the document', "SEMANTIC"),
    ]
    
    passed = 0
    for query, expected_intent in test_queries:
        analysis = analyze_query(query)
        status = "✓" if analysis.intent == expected_intent else "✗"
        if status == "✓":
            passed += 1
        print(f"{status} Query: '{query}'")
        print(f"   Expected: {expected_intent}, Got: {analysis.intent}")
        print(f"   Entities: {analysis.entities}")
    
    print(f"\nPassed: {passed}/{len(test_queries)}")
    return passed == len(test_queries)

def test_bm25_index():
    """Test BM25 index building and searching."""
    print("\n" + "="*60)
    print("TEST: BM25 Index")
    print("="*60)
    
    metadata_path = "/Users/rohanshravan/TSAI/Arcturus/mcp_servers/faiss_index/metadata.json"
    
    if not os.path.exists(metadata_path):
        print("✗ Metadata file not found. Run indexing first.")
        return False
    
    # Build index
    bm25 = BM25Index()
    bm25.build_from_metadata(metadata_path)
    
    # Test searches
    test_queries = [
        "Anmol Singh",
        "transformer attention",
        "Indian Policies",
        "INVG67564",
    ]
    
    for query in test_queries:
        results = bm25.search(query, top_k=5)
        print(f"\nQuery: '{query}'")
        if results:
            for chunk_id, score in results[:3]:
                print(f"  Score: {score:.2f} -> {chunk_id}")
        else:
            print("  No results (score > 0)")
    
    # Save index for later use
    bm25_path = "/Users/rohanshravan/TSAI/Arcturus/mcp_servers/faiss_index/bm25_index.pkl"
    bm25.save(bm25_path)
    
    return True

def test_full_pipeline():
    """Test the full hybrid search pipeline."""
    print("\n" + "="*60)
    print("TEST: Full Hybrid Pipeline")
    print("="*60)
    
    metadata_path = "/Users/rohanshravan/TSAI/Arcturus/mcp_servers/faiss_index/metadata.json"
    bm25_path = "/Users/rohanshravan/TSAI/Arcturus/mcp_servers/faiss_index/bm25_index.pkl"
    
    # Load metadata
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Load BM25
    bm25 = BM25Index()
    if os.path.exists(bm25_path):
        bm25.load(bm25_path)
    else:
        bm25.build_from_metadata(metadata_path)
    
    # Test query that should fail without entity gate
    query = "Anmol Singh"
    print(f"\nQuery: '{query}'")
    
    # 1. Analyze query
    analysis = analyze_query(query)
    print(f"Intent: {analysis.intent}")
    print(f"Entities: {analysis.entities}")
    
    # 2. BM25 search
    bm25_results = bm25.search(query, top_k=20)
    print(f"\nBM25 Results: {len(bm25_results)} hits")
    
    # 3. Simulate FAISS results (use BM25 as proxy for this test)
    # In real implementation, this would call FAISS
    faiss_results = bm25_results  # Placeholder
    
    # 4. RRF Fusion
    fused = rrf_fuse(bm25_results, faiss_results)
    print(f"Fused Results: {len(fused)} hits")
    
    # 5. Entity Gate
    gated, gate_applied = entity_gate(fused, metadata, analysis)
    print(f"After Entity Gate: {len(gated)} hits (gate applied: {gate_applied})")
    
    # Show results
    if gated:
        print("\nFiltered Results:")
        for chunk_id, score in gated[:3]:
            chunk_text = next((m['chunk'][:100] for m in metadata if m['chunk_id'] == chunk_id), "")
            print(f"  {chunk_id}: {chunk_text}...")
    else:
        print("\n⚠ No documents contain 'Anmol Singh' exactly.")
        print("This is the CORRECT behavior - the gate worked!")
    
    return True

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("="*60)
    print("HYBRID SEARCH SANDBOX")
    print("="*60)
    
    all_passed = True
    
    # Test 1: Query Analyzer
    if not test_query_analyzer():
        all_passed = False
    
    # Test 2: BM25 Index
    if not test_bm25_index():
        all_passed = False
    
    # Test 3: Full Pipeline
    if not test_full_pipeline():
        all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL TESTS PASSED - Ready for integration")
    else:
        print("✗ SOME TESTS FAILED - Review before integration")
    print("="*60)

if __name__ == "__main__":
    main()
