/**
 * Search API client functions.
 * Wraps the /api/search/* endpoints for use in hooks and components.
 */
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import type { FocusMode, QuickSearchResult, DecomposeResult } from '../types/search-types';

const SEARCH_BASE = `${API_BASE}/search`;

export const searchApi = {
  /** GET /api/search/focus-modes */
  getFocusModes: async (): Promise<FocusMode[]> => {
    const res = await axios.get<FocusMode[]>(`${SEARCH_BASE}/focus-modes`);
    return res.data;
  },

  /** POST /api/search/decompose */
  decomposeQuery: async (
    query: string,
    focusMode = 'web',
    nQueries = 6,
  ): Promise<DecomposeResult> => {
    const res = await axios.post<DecomposeResult>(`${SEARCH_BASE}/decompose`, {
      query,
      focus_mode: focusMode,
      n_queries: nQueries,
    });
    return res.data;
  },

  /** POST /api/search — quick search (single iteration) */
  quickSearch: async (
    query: string,
    focusMode = 'web',
    maxSources = 10,
  ): Promise<QuickSearchResult> => {
    const res = await axios.post<QuickSearchResult>(SEARCH_BASE, {
      query,
      focus_mode: focusMode,
      max_sources: maxSources,
    });
    return res.data;
  },

  /** POST /api/search/{runId}/stop */
  stopSearch: async (runId: string): Promise<void> => {
    await axios.post(`${SEARCH_BASE}/${runId}/stop`);
  },

  /**
   * POST /api/search/deep — deep research with SSE streaming.
   * Returns an EventSource-like reader. Use useSearchStream hook instead
   * for React integration.
   */
  deepSearchUrl: (query: string, focusMode = 'web', maxIterations = 3) => ({
    url: `${SEARCH_BASE}/deep`,
    body: { query, focus_mode: focusMode, max_iterations: maxIterations },
  }),
};
