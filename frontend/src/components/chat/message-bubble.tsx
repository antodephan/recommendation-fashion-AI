'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { motion } from 'framer-motion';
import { User, Sparkles } from 'lucide-react';
import { ChatMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import { markdownComponents } from '@/components/chat/markdown-components';
import {
  OutfitRecommendationCards,
  OutfitRecPayload
} from '@/components/chat/outfit-recommendation-cards';

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const recs = message.extra?.recommendations as OutfitRecPayload | undefined;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={cn('flex gap-3 px-4 py-3', isUser && 'flex-row-reverse')}
    >
      <div
        className={cn(
          'mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-full',
          isUser ? 'bg-secondary text-foreground' : 'bg-accent text-accent-foreground'
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          'max-w-[80ch] rounded-2xl px-4 py-3 text-sm prose-chat',
          isUser ? 'bg-secondary' : 'bg-card border'
        )}
      >
        {message.image_url && (
          <img
            src={message.image_url}
            alt="attachment"
            className="mb-3 max-h-64 rounded-lg border object-cover"
          />
        )}
        {message.content ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight]}
            components={markdownComponents}
          >
            {message.content}
          </ReactMarkdown>
        ) : (
          <span className="text-muted-foreground">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </span>
        )}
        {recs && !isUser && <OutfitRecommendationCards data={recs} />}
      </div>
    </motion.div>
  );
}
