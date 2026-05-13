/**
 * GitMark — glyph monochrome pour GitHub ou Forgejo.
 * Cf. DA/shared.jsx · GitMark.
 */

import type { Provider } from '@/lib/constants';

interface GitMarkProps {
  provider: Provider;
  size?: number;
  className?: string;
}

export function GitMark({ provider, size = 12, className }: GitMarkProps): JSX.Element {
  if (provider === 'forgejo') {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 16 16"
        fill="none"
        className={className}
        aria-label="forgejo"
      >
        <path
          d="M8 1.5c1.6 2.6-1 3.6 1 6.4 1 1.4 2.7 1 2.7 2.8a3.7 3.7 0 1 1-7.4 0c0-1.7 1.7-1.7 1.7-3.5S6.6 4 8 1.5z"
          stroke="currentColor"
          strokeWidth="1.1"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="currentColor"
      className={className}
      aria-label="github"
    >
      <path d="M8 .5a7.5 7.5 0 0 0-2.4 14.6c.4.1.5-.2.5-.4v-1.4c-2 .4-2.5-.9-2.5-.9-.3-.8-.8-1-.8-1-.7-.5.1-.5.1-.5.7.1 1.1.7 1.1.7.7 1.1 1.7.8 2.2.6.1-.5.3-.8.5-1-1.7-.2-3.4-.8-3.4-3.7 0-.8.3-1.5.7-2-.1-.2-.3-.9.1-1.9 0 0 .6-.2 2 .8a7 7 0 0 1 3.6 0c1.4-1 2-.8 2-.8.4 1 .2 1.7.1 1.9.5.5.8 1.2.8 2 0 2.9-1.7 3.5-3.4 3.7.3.2.5.7.5 1.4v2c0 .2.1.5.6.4A7.5 7.5 0 0 0 8 .5z" />
    </svg>
  );
}
