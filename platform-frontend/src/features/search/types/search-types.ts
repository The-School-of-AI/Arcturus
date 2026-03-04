/**
 * TypeScript interfaces for the Oracle search feature.
 * Maps to the backend Pydantic models in routers/search.py
 * and dataclasses in search/synthesizer.py, search/focus_modes.py.
 */

export interface FocusMode {
  name: string;
  label: string;
  description: string;
  citation_format: string;
}

export interface SearchCitation {
  index: number;
  url: string;
  title: string;
  timestamp?: string;
  credibility?: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface QuickSearchResult {
  status: 'completed' | 'error';
  markdown: string;
  citations: SearchCitation[];
  source_count: number;
  executive_summary?: string;
  contradictions?: string[];
}

export interface DecomposeResult {
  query: string;
  sub_queries: string[];
}

/** SSE event from /api/search/deep */
export interface DeepSearchEvent {
  type: 'phase' | 'sources' | 'synthesis' | 'gap' | 'done' | 'error';
  // phase events
  phase?: string;
  iteration?: number;
  query?: string;
  sub_queries?: string[];
  sub_query_count?: number;
  source_count?: number;
  // sources events
  new_sources?: number;
  total_sources?: number;
  sample_urls?: string[];
  // synthesis events
  markdown?: string;
  citation_count?: number;
  executive_summary?: string;
  contradictions?: string[];
  // gap events
  gaps?: string[];
  message?: string;
  // done events
  run_id?: string;
  final_report?: string;
  citations?: SearchCitation[];
  // error events
  error?: string;
}
