import { describe, it, expect } from 'vitest';
import {
  calculateHomaIr,
  calculateTgHdlRatio,
  glucoseToMgDl,
  insulinToMicroUnits,
  hba1cToPercent,
  classify,
  normalizeLabPoints,
  buildHomaIrSeries,
  summarizeSeries,
} from './insulinResistance';

const point = (id, labId, date, value, unit) => ({
  id,
  value,
  unit,
  recorded_date: date,
  created_at: date,
  lab_result: { id: labId, test_name: 'Panel', completed_date: date },
});

describe('insulinResistance utils', () => {
  it('calculates HOMA-IR from mg/dL glucose and µU/mL insulin', () => {
    expect(calculateHomaIr(90, 10)).toBe(2.22);
    expect(calculateHomaIr(105, 18)).toBe(4.67);
  });

  it('returns null for missing, zero or invalid inputs', () => {
    expect(calculateHomaIr(null, 10)).toBeNull();
    expect(calculateHomaIr(90, undefined)).toBeNull();
    expect(calculateHomaIr(0, 10)).toBeNull();
    expect(calculateHomaIr(90, -1)).toBeNull();
    expect(calculateHomaIr('abc', 10)).toBeNull();
    expect(calculateTgHdlRatio(150, 0)).toBeNull();
  });

  it('normalises units and rejects incompatible ones', () => {
    expect(glucoseToMgDl(5, 'mmol/L')).toBeCloseTo(90.08, 2);
    expect(glucoseToMgDl(95, 'mg/dL')).toBe(95);
    expect(glucoseToMgDl(95, 'g/L')).toBeNull();
    expect(insulinToMicroUnits(60, 'pmol/L')).toBe(10);
    expect(insulinToMicroUnits(12, 'uU/mL')).toBe(12);
    expect(insulinToMicroUnits(12, 'μIU/mL')).toBe(12);
    expect(insulinToMicroUnits(12, 'ng/mL')).toBeNull();
    expect(hba1cToPercent(48, 'mmol/mol')).toBe(6.5);
    expect(hba1cToPercent(5.4, '%')).toBe(5.4);
  });

  it('classifies with orientative bands', () => {
    expect(classify('homaIr', 1.8)).toBe('normal');
    expect(classify('homaIr', 2.5)).toBe('borderline');
    expect(classify('homaIr', 4)).toBe('high');
    expect(classify('hba1c', 6.5)).toBe('high');
    expect(classify('glucose', null)).toBeNull();
  });

  it('pairs glucose and insulin from the same lab result', () => {
    const glucose = normalizeLabPoints(
      [
        point(1, 10, '2026-01-10', 100, 'mg/dL'),
        point(2, 11, '2026-03-10', 5, 'mmol/L'),
        point(3, 12, '2026-05-10', 92, 'mg/dL'),
      ],
      glucoseToMgDl
    );
    const insulin = normalizeLabPoints(
      [
        point(4, 10, '2026-01-10', 20, 'µIU/mL'),
        point(5, 11, '2026-03-10', 60, 'pmol/L'),
        point(6, 13, '2026-06-01', 8, 'µIU/mL'),
      ],
      insulinToMicroUnits
    );
    const homa = buildHomaIrSeries(glucose, insulin);
    expect(homa).toEqual([
      { date: '2026-01-10', value: 4.94 },
      { date: '2026-03-10', value: 2.22 },
    ]);
    expect(summarizeSeries(homa)).toMatchObject({
      latest: 2.22,
      first: 4.94,
      change: -2.72,
      count: 2,
    });
  });

  it('drops points with incompatible units and deduplicates ids', () => {
    const series = normalizeLabPoints(
      [
        point(1, 10, '2026-01-10', 100, 'mg/dL'),
        point(1, 10, '2026-01-10', 100, 'mg/dL'),
        point(2, 11, '2026-02-10', 1, 'g/L'),
      ],
      glucoseToMgDl
    );
    expect(series).toHaveLength(1);
    expect(summarizeSeries([])).toBeNull();
  });
});
