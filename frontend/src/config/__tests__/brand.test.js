import { describe, expect, it } from 'vitest';
import { isModuleHidden } from '../brand';
import { getNavigationSections, getFeaturedItems } from '../navigation.config';

describe('SILHO module visibility', () => {
  it('hides modules outside the insulin-resistance pathway', () => {
    expect(isModuleHidden('/immunizations')).toBe(true);
    expect(isModuleHidden('/insurance/12')).toBe(true);
    expect(isModuleHidden('/lab-results')).toBe(false);
    expect(isModuleHidden('/immunizations-report')).toBe(false);
    expect(isModuleHidden(undefined)).toBe(false);
  });

  it('removes hidden modules from navigation and featured items', () => {
    const paths = Object.values(getNavigationSections('desktop', true)).flatMap(
      section => section.items.map(item => item.path)
    );
    expect(paths).toContain('/lab-results');
    expect(paths).toContain('/vitals');
    expect(paths.some(isModuleHidden)).toBe(false);
    expect(getFeaturedItems().some(item => isModuleHidden(item.path))).toBe(
      false
    );
  });
});
