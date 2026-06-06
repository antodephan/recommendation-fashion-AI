'use client';

import { useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';
import { Plus, MessageSquare, Trash2 } from 'lucide-react';
import { useChat } from '@/store/chat';
import { useTranslation } from '@/store/locale';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn, truncate } from '@/lib/utils';
import { Composer } from '@/components/chat/composer';

const MessageBubble = dynamic(
  () => import('@/components/chat/message-bubble').then((m) => m.MessageBubble),
  { loading: () => <Skeleton className="mb-4 h-16 w-full" /> }
);

export default function ChatPage() {
  const { t } = useTranslation();
  const {
    conversations,
    activeId,
    messages,
    streaming,
    loadConversations,
    selectConversation,
    newConversation,
    deleteConversation,
    sendStreaming
  } = useChat();

  const endRef = useRef<HTMLDivElement>(null);
  const messageCountRef = useRef(0);
  const conversationsLoaded = useRef(false);

  useEffect(() => {
    if (conversationsLoaded.current) return;
    conversationsLoaded.current = true;
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    const count = messages.length;
    if (count === 0 || count === messageCountRef.current) return;
    messageCountRef.current = count;
    endRef.current?.scrollIntoView({ behavior: streaming ? 'auto' : 'smooth' });
  }, [messages.length, streaming]);

  const suggestions = [
    t('chat.suggestion1'),
    t('chat.suggestion2'),
    t('chat.suggestion3'),
    t('chat.suggestion4')
  ];

  return (
    <div className="grid h-full grid-cols-[280px_1fr]">
      <aside className="flex h-screen flex-col border-r">
        <div className="p-3">
          <Button onClick={newConversation} variant="accent" className="w-full">
            <Plus className="h-4 w-4" /> {t('chat.newChat')}
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {conversations.length === 0 ? (
            <p className="px-4 py-6 text-sm text-muted-foreground">{t('chat.noConversations')}</p>
          ) : (
            conversations.map((c) => (
              <div
                key={c.id}
                className={cn(
                  'group flex cursor-pointer items-center gap-2 px-3 py-2 text-sm',
                  activeId === c.id ? 'bg-secondary' : 'hover:bg-secondary/50'
                )}
                onClick={() => selectConversation(c.id)}
              >
                <MessageSquare className="h-4 w-4 text-muted-foreground" />
                <span className="flex-1 truncate">{truncate(c.title, 28)}</span>
                <button
                  className="opacity-0 transition-opacity group-hover:opacity-100"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(c.id);
                  }}
                  aria-label={t('chat.delete')}
                >
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      <section className="flex h-screen flex-col">
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {messages.length === 0 ? (
            <EmptyState suggestions={suggestions} onPrompt={(p) => sendStreaming(p)} t={t} />
          ) : (
            <div className="mx-auto max-w-3xl px-4 py-6">
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              <div ref={endRef} />
            </div>
          )}
        </div>
        <div className="mx-auto w-full max-w-3xl">
          <Composer onSend={async (c, i) => sendStreaming(c, i)} disabled={streaming} />
        </div>
      </section>
    </div>
  );
}

function EmptyState({
  onPrompt,
  suggestions,
  t
}: {
  onPrompt: (p: string) => void;
  suggestions: string[];
  t: (key: string) => string;
}) {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center px-4 py-12 text-center">
      <h2 className="font-display text-3xl font-bold">{t('chat.emptyTitle')}</h2>
      <p className="mt-2 text-muted-foreground">{t('chat.emptySubtitle')}</p>
      <div className="mt-8 grid w-full gap-3 sm:grid-cols-2">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => onPrompt(s)}
            className="rounded-lg border bg-card p-4 text-left text-sm transition-colors hover:bg-secondary"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
