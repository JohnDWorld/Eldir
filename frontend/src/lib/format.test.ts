import { describe, expect, it } from 'vitest';

import { formatAge, formatCost, formatTokens } from '@/lib/format';

describe('formatage', () => {
  it("dit l'âge d'une session sans ambiguïté", () => {
    const ilYA = (minutes: number) =>
      new Date(Date.now() - minutes * 60_000).toISOString();
    // L'ancien format affichait « 00:35 » pour trente-cinq minutes.
    expect(formatAge(ilYA(35))).toBe('il y a 35 min');
    expect(formatAge(ilYA(181))).toBe('il y a 3 h');
    expect(formatAge(ilYA(60 * 26))).toBe('hier');
    expect(formatAge(ilYA(60 * 24 * 3))).toBe('il y a 3 j');
  });

  it('adapte la précision du coût au montant', () => {
    expect(formatCost(0)).toBe('$0');
    expect(formatCost(0.0004)).toBe('$0.0004');
    expect(formatCost(0.0786)).toBe('$0.079');
    expect(formatCost(2.31)).toBe('$2.31');
  });

  it('abrège les tokens', () => {
    expect(formatTokens(0)).toBe('0');
    expect(formatTokens(950)).toBe('950');
    expect(formatTokens(1_500)).toBe('1.5k');
    expect(formatTokens(2_400_000)).toBe('2.40M');
  });
});
