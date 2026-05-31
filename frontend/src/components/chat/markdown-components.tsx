/**
 * ReactMarkdown component overrides.
 * AI responses may include HTML with style="..." (string). React requires style={{ }}.
 */
import { createElement, type HTMLAttributes } from 'react';
import type { Components } from 'react-markdown';

type HtmlProps = HTMLAttributes<HTMLElement>;

function safeProps({ style, ...rest }: HtmlProps): HtmlProps {
  if (typeof style === 'string') {
    return rest;
  }
  return style !== undefined ? { ...rest, style } : rest;
}

function safeTag(tag: keyof JSX.IntrinsicElements) {
  return (props: HtmlProps) => createElement(tag, safeProps(props));
}

const TAGS: Array<keyof JSX.IntrinsicElements> = [
  'div',
  'span',
  'p',
  'a',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'ul',
  'ol',
  'li',
  'blockquote',
  'table',
  'thead',
  'tbody',
  'tr',
  'th',
  'td',
  'pre',
  'code',
  'strong',
  'em',
  'hr',
  'img'
];

export const markdownComponents: Components = Object.fromEntries(
  TAGS.map((tag) => [tag, safeTag(tag)])
) as Components;
