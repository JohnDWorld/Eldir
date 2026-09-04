import { describe, expect, it } from 'vitest';

import { isNavItemActive, NAV_ITEMS } from '@/lib/nav';

describe('navigation', () => {
  it('marque Ops actif seulement sur la racine', () => {
    const ops = NAV_ITEMS[0]!;
    expect(isNavItemActive(ops, '/')).toBe(true);
    expect(isNavItemActive(ops, '/projects')).toBe(false);
  });

  it('marque un onglet actif sur ses sous-routes', () => {
    const settings = NAV_ITEMS.find((i) => i.to === '/settings')!;
    expect(isNavItemActive(settings, '/settings')).toBe(true);
    expect(isNavItemActive(settings, '/settings/git')).toBe(true);
    expect(isNavItemActive(settings, '/costs')).toBe(false);
  });

  it('expose un pictogramme et un libellé pour chaque entrée', () => {
    for (const item of NAV_ITEMS) {
      expect(item.glyph).toBeTruthy();
      expect(item.label).toBeTruthy();
    }
  });
});
