import { describe, it, expect } from 'vitest';
import {
  calculateHomaIr,
  calculateTgHdlRatio,
  glucoseToMgDl,
  insulinToMicroUnits,
  hba1cToPercent,
  classify,
  classifyBp,
  classifyWaist,
  bandRanges,
  formatBandRange,
  normalizeLabPoints,
  buildHomaIrSeries,
  summarizeSeries,
  calculateBmiImperial,
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

  it('classifies very high, low, blood pressure and waist levels', () => {
    expect(classify('homaIr', 5.2)).toBe('veryHigh');
    expect(classify('bmi', 17)).toBe('low');
    expect(classify('bmi', 32)).toBe('high');
    expect(classifyBp(125, 78)).toBe('borderline');
    expect(classifyBp(118, 92)).toBe('veryHigh');
    expect(classifyBp(null, null)).toBeNull();
    expect(classifyWaist(95, 'M')).toBe('high');
    expect(classifyWaist(105, 'Male')).toBe('veryHigh');
    expect(classifyWaist(85, 'F')).toBe('high');
    expect(classifyWaist(85, null)).toBeNull();
  });

  it('builds display ranges from the bands', () => {
    expect(bandRanges('homaIr').map(r => formatBandRange(r))).toEqual([
      '< 2.5',
      '2.5 – 3.4',
      '3.5 – 4.9',
      '≥ 5',
    ]);
    expect(bandRanges('glucose').map(r => formatBandRange(r))).toEqual([
      '< 100',
      '100 – 125',
      '126 – 199',
      '≥ 200',
    ]);
    expect(
      bandRanges('waistMale', 1 / 2.54).map(r => formatBandRange(r))
    ).toEqual(['< 35.4', '35.4 – 40.1', '≥ 40.2']);
  });

  it('does not pair glucose and insulin from different lab results on the same day', () => {
    const glucose = normalizeLabPoints(
      [point(1, 20, '2026-06-10', 200, 'mg/dL')],
      glucoseToMgDl
    );
    const insulin = normalizeLabPoints(
      [point(2, 21, '2026-06-10', 100, 'µIU/mL')],
      insulinToMicroUnits
    );
    expect(buildHomaIrSeries(glucose, insulin)).toEqual([]);
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

  it('calculates BMI from lb and inches', () => {
    expect(calculateBmiImperial(200, 70)).toBe(28.7);
    expect(calculateBmiImperial(220, 70)).toBe(31.6);
    expect(calculateBmiImperial(200, null)).toBeNull();
    expect(calculateBmiImperial(0, 70)).toBeNull();
  });
});
