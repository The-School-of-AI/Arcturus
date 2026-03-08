/**
 * P07 Echo — Voice pipeline API client.
 * All endpoints under /api/voice/ for state, start, personas, session.
 */

import axios from 'axios';
import { API_BASE } from '@/lib/api';

const VOICE_BASE = `${API_BASE}/voice`;

export type VoiceState = 'IDLE' | 'LISTENING' | 'THINKING' | 'SPEAKING' | 'unavailable';

export interface VoiceStateResponse {
  state: VoiceState;
  message?: string | null;
}

export interface VoicePersonasResponse {
  active: string | null;
  personas: Record<string, { voice_name?: string; rate?: string; pitch?: string; volume?: string; description?: string }>;
}

export interface VoiceSessionResponse {
  session_id: string | null;
  turn_count: number;
  turns: Array<{ user_transcript?: string; tts_text?: string; [key: string]: unknown }>;
  conversation_history: Array<{ role: string; content: string }>;
}

export interface VoiceSessionsListResponse {
  sessions: Array<{ session_id: string; started_at?: string; ended_at?: string; total_turns: number; file_path?: string }>;
  count: number;
}

export const voiceApi = {
  startListening: async (): Promise<{ status: string }> => {
    const res = await axios.post<{ status: string }>(`${VOICE_BASE}/start`);
    return res.data;
  },

  getState: async (): Promise<VoiceStateResponse> => {
    try {
      const res = await axios.get<VoiceStateResponse>(`${VOICE_BASE}/state`, { timeout: 3000 });
      return res.data;
    } catch (err) {
      return { state: 'unavailable' };
    }
  },

  getPersonas: async (): Promise<VoicePersonasResponse> => {
    const res = await axios.get<VoicePersonasResponse>(`${VOICE_BASE}/personas`);
    return res.data;
  },

  setPersona: async (persona: string): Promise<{ status: string; active: string | null; voice_name?: string }> => {
    const res = await axios.put(`${VOICE_BASE}/persona`, { persona });
    return res.data;
  },

  getSession: async (): Promise<VoiceSessionResponse> => {
    const res = await axios.get<VoiceSessionResponse>(`${VOICE_BASE}/session`);
    return res.data;
  },

  getSessions: async (days = 7): Promise<VoiceSessionsListResponse> => {
    const res = await axios.get<VoiceSessionsListResponse>(`${VOICE_BASE}/sessions`, { params: { days } });
    return res.data;
  },

  getSessionDetail: async (sessionId: string): Promise<Record<string, unknown>> => {
    const res = await axios.get(`${VOICE_BASE}/sessions/${sessionId}`);
    return res.data;
  },

  clearSession: async (): Promise<{ status: string; saved_to?: string }> => {
    const res = await axios.delete(`${VOICE_BASE}/session`);
    return res.data;
  },
};
