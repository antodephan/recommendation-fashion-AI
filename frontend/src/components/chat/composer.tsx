'use client';

import { useRef, useState } from 'react';
import { Paperclip, Send, Image as ImageIcon, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/input';
import { api } from '@/lib/api';
import { useTranslation } from '@/store/locale';
import toast from 'react-hot-toast';

interface Props {
  onSend: (content: string, imageUrl?: string) => Promise<void>;
  disabled?: boolean;
}

export function Composer({ onSend, disabled }: Props) {
  const { t } = useTranslation();
  const [value, setValue] = useState('');
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function upload(file: File) {
    const isImage =
      file.type.startsWith('image/') ||
      /\.(jpe?g|png|webp|heic|heif)$/i.test(file.name);
    if (!isImage) {
      toast.error(t('chat.uploadImagesOnly'));
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      toast.error(t('chat.uploadTooLarge'));
      return;
    }
    setUploading(true);
    const toastId = toast.loading(t('chat.uploadLoading'));
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post<{ url: string }>('/uploads/image', fd);
      const base = process.env.NEXT_PUBLIC_API_URL || '';
      const preview = res.url.startsWith('http') ? res.url : `${base}${res.url}`;
      setImageUrl(preview);
      toast.success(t('chat.uploadSuccess'), { id: toastId });
    } catch (err: any) {
      const msg =
        err?.status === 401
          ? t('chat.sessionExpired')
          : err?.status === 422
            ? err.message || t('chat.uploadUnsupported')
            : err?.code === 'network_error'
              ? err.message
              : err.message || t('chat.uploadFailed');
      toast.error(msg, { id: toastId });
    } finally {
      setUploading(false);
    }
  }

  async function submit() {
    const text = value.trim();
    if (!text && !imageUrl) return;
    setValue('');
    const img = imageUrl;
    setImageUrl(null);
    await onSend(text, img ?? undefined);
  }

  return (
    <div
      className="border-t bg-background/80 p-4 backdrop-blur"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        const f = e.dataTransfer.files?.[0];
        if (f) upload(f);
      }}
    >
      {imageUrl && (
        <div className="mb-3 inline-flex items-center gap-3 rounded-lg border bg-card p-2 text-xs">
          <img src={imageUrl} alt="" className="h-12 w-12 rounded-md object-cover" />
          <span className="text-muted-foreground">{t('chat.imageAttached')}</span>
          <button onClick={() => setImageUrl(null)} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      <div className="flex items-end gap-2 rounded-2xl border bg-card px-3 py-2 shadow-sm">
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          accept="image/*"
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => fileRef.current?.click()}
          disabled={uploading || disabled}
        >
          {uploading ? <ImageIcon className="h-4 w-4 animate-pulse" /> : <Paperclip className="h-4 w-4" />}
        </Button>
        <Textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={t('chat.placeholder')}
          rows={1}
          className="min-h-[44px] resize-none border-0 bg-transparent shadow-none focus-visible:ring-0"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          disabled={disabled}
        />
        <Button onClick={submit} disabled={disabled || (!value.trim() && !imageUrl)} variant="accent" size="icon">
          <Send className="h-4 w-4" />
        </Button>
      </div>
      <p className="mt-2 text-center text-xs text-muted-foreground">{t('chat.disclaimer')}</p>
    </div>
  );
}
