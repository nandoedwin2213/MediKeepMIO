export const PLAN_FEATURES = ['score', 'plans', 'week', 'ai', 'data'];

export function formatMoney(cents, currency, locale) {
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
    }).format(cents / 100);
  } catch {
    return `${(cents / 100).toFixed(2)} ${currency}`;
  }
}

export function monthlyEquivalent(plan) {
  return Math.round(plan.amount_cents / plan.months);
}

export function savingPercent(plan, plans) {
  const base = plans.find(p => p.months === 1);
  if (!base || plan.months <= 1) return 0;
  const full = base.amount_cents * plan.months;
  return Math.max(0, Math.round((1 - plan.amount_cents / full) * 100));
}
