/**
 * Main search hook — manages search state and coordinates API calls.
 * Used by SearchPage and any component that needs search functionality.
 */
import { useState, useEffect, useCallback } from 'react';
import { searchApi } from './useSearchApi';
import { useSearchStream } from './useSearchStream';
import type {
  FocusMode,
  QuickSearchResult,
  DecomposeResult,
} from '../types/search-types';

interface UseSearchReturn {
  // State
  query: string;
  setQuery: (q: string) => void;
  focusMode: string;
  setFocusMode: (m: string) => void;
  focusModes: FocusMode[];
  isSearching: boolean;
  quickResult: QuickSearchResult | null;
  decomposedQueries: string[] | null;
  error: string | null;

  // Actions
  performQuickSearch: () => Promise<void>;
  previewDecomposition: () => Promise<void>;
  clearResults: () => void;

  // Deep search (SSE) pass-through
  deepSearch: ReturnType<typeof useSearchStream>;
}

export function useSearch(): UseSearchReturn {
  const [query, setQuery] = useState('');
  const [focusMode, setFocusMode] = useState('web');
  const [focusModes, setFocusModes] = useState<FocusMode[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [quickResult, setQuickResult] = useState<QuickSearchResult | null>(null);
  const [decomposedQueries, setDecomposedQueries] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const deepSearch = useSearchStream();

  // Fetch focus modes on mount
  useEffect(() => {
    searchApi.getFocusModes().then(setFocusModes).catch(() => {});
  }, []);

  const performQuickSearch = useCallback(async () => {
    if (!query.trim()) return;
    setIsSearching(true);
    setError(null);
    setQuickResult(null);
    try {
      const result = await searchApi.quickSearch(query, focusMode);
      setQuickResult(result);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Search failed');
    } finally {
      setIsSearching(false);
    }
  }, [query, focusMode]);

  const previewDecomposition = useCallback(async () => {
    if (!query.trim()) return;
    setError(null);
    try {
      const result = await searchApi.decomposeQuery(query, focusMode);
      setDecomposedQueries(result.sub_queries);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Decomposition failed');
    }
  }, [query, focusMode]);

  const clearResults = useCallback(() => {
    setQuickResult(null);
    setDecomposedQueries(null);
    setError(null);
  }, []);

  return {
    query, setQuery,
    focusMode, setFocusMode,
    focusModes,
    isSearching,
    quickResult,
    decomposedQueries,
    error,
    performQuickSearch,
    previewDecomposition,
    clearResults,
    deepSearch,
  };
}
