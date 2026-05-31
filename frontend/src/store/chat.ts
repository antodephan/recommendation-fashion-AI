'use client';

import { create } from 'zustand';
import toast from 'react-hot-toast';
import { api, ChatMessage, Conversation } from '@/lib/api';

interface ChatState {
  conversations: Conversation[];
  activeId: string | null;
  messages: ChatMessage[];
  streaming: boolean;
  loadConversations: () => Promise<void>;
  selectConversation: (id: string | null) => Promise<void>;
  newConversation: () => void;
  deleteConversation: (id: string) => Promise<void>;
  rename: (id: string, title: string) => Promise<void>;
  sendStreaming: (content: string, imageUrl?: string) => Promise<void>;
}

export const useChat = create<ChatState>((set, get) => ({
  conversations: [],
  activeId: null,
  messages: [],
  streaming: false,

  async loadConversations() {
    const list = await api.get<Conversation[]>('/chat/conversations');
    set({ conversations: list });
  },

  async selectConversation(id) {
    if (!id) {
      set({ activeId: null, messages: [] });
      return;
    }
    const msgs = await api.get<ChatMessage[]>(`/chat/conversations/${id}`);
    set({ activeId: id, messages: msgs });
  },

  newConversation() {
    set({ activeId: null, messages: [] });
  },

  async deleteConversation(id) {
    await api.delete(`/chat/conversations/${id}`);
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeId: state.activeId === id ? null : state.activeId,
      messages: state.activeId === id ? [] : state.messages
    }));
  },

  async rename(id, title) {
    const updated = await api.patch<Conversation>(
      `/chat/conversations/${id}?title=${encodeURIComponent(title)}`
    );
    set((state) => ({
      conversations: state.conversations.map((c) => (c.id === id ? updated : c))
    }));
  },

  async sendStreaming(content, imageUrl) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    const tempUserMsg: ChatMessage = {
      id: `tmp-${Date.now()}`,
      conversation_id: get().activeId || 'pending',
      role: 'user',
      content,
      image_url: imageUrl ?? null,
      tokens: 0,
      extra: {},
      created_at: new Date().toISOString()
    };
    const tempAssistantMsg: ChatMessage = {
      id: `tmp-a-${Date.now()}`,
      conversation_id: get().activeId || 'pending',
      role: 'assistant',
      content: '',
      image_url: null,
      tokens: 0,
      extra: {},
      created_at: new Date().toISOString()
    };
    set((state) => ({
      messages: [...state.messages, tempUserMsg, tempAssistantMsg],
      streaming: true
    }));

    try {
      const base = process.env.NEXT_PUBLIC_API_URL || '';
      const res = await fetch(`${base}/api/v1/chat/stream`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          content,
          image_url: imageUrl?.replace(/^https?:\/\/[^/]+/, '') ?? imageUrl,
          conversation_id: get().activeId
        })
      });
      if (!res.ok || !res.body) {
        throw new Error(res.status === 401 ? 'Session expired' : 'Chat request failed');
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let conversationId: string | null = get().activeId;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split('\n\n');
        buffer = blocks.pop() || '';
        for (const block of blocks) {
          const event = block.match(/event: (.+)/)?.[1];
          const data = block.match(/data: (.+)/)?.[1];
          if (!event || !data) continue;
          let json: any;
          try {
            json = JSON.parse(data);
          } catch {
            continue;
          }
          if (event === 'meta' && json.conversation_id) {
            conversationId = json.conversation_id;
            set({ activeId: conversationId });
          } else if (event === 'delta') {
            set((state) => ({
              messages: state.messages.map((m, i) =>
                i === state.messages.length - 1 ? { ...m, content: m.content + json.content } : m
              )
            }));
          } else if (event === 'done') {
            set((state) => ({
              messages: state.messages.map((m, i) =>
                i === state.messages.length - 1
                  ? {
                      ...m,
                      id: json.id,
                      conversation_id: json.conversation_id,
                      content: json.content
                    }
                  : m
              )
            }));
          } else if (event === 'recommendations') {
            set((state) => ({
              messages: state.messages.map((m, i) =>
                i === state.messages.length - 1
                  ? { ...m, extra: { ...m.extra, recommendations: json } }
                  : m
              )
            }));
          } else if (event === 'error') {
            throw new Error(json.message || 'Chat stream failed');
          }
        }
      }
      await get().loadConversations();
    } catch (err: any) {
      set((state) => ({
        messages: state.messages.slice(0, -2),
        streaming: false
      }));
      toast.error(
        err?.message?.includes('fetch') || err?.name === 'TypeError'
          ? 'Mất kết nối API. Kiểm tra backend đang chạy (port 8000).'
          : err?.message || 'Chat failed'
      );
      return;
    }
    set({ streaming: false });
  }
}));
