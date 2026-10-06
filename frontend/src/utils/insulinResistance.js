/**
 * Insulin-resistance metrics: unit normalisation, HOMA-IR and TG/HDL
 * calculation, and orientative clinical bands.
 */

export const HOMA_IR_DIVISOR = 405;

const GLUCOSE_MMOL_TO_MGDL = 18.016;
const INSULIN_PMOL_PER_UIU = 6;
const TG_MMOL_TO_MGDL = 88.57;
const HDL_MMOL_TO_MGDL = 38.67;

const normUnit = unit =>
  (unit || '')
    .toString()
    .trim()
    .toLowerCase()
    .replace(/μ/g, 'µ')
    .replace(/\s+/g, '');

const toNumber = value => {
  if (value === null || value === undefined || value === '') return null;
  const n = typeof value === 'number' ? value : parseFloat(value);
  return Number.isFinite(n) ? n : null;
};

const MGDL_UNITS = ['mg/dl', 'mg/100ml', ''];
const MMOL_UNITS = ['mmol/l'];

const convertMassConcentration = (value, unit, mmolFactor) => {
  const n = toNumber(value);
  if (n === null || n <= 0) return null;
  const u = normUnit(unit);
  if (MGDL_UNITS.includes(u)) return n;
  if (MMOL_UNITS.includes(u)) return n * mmolFactor;
  return null;
};

/** Glucose in mg/dL, or null when the value/unit is unusable. */
export const glucoseToMgDl = (value, unit) =>
  convertMassConcentration(value, unit, GLUCOSE_MMOL_TO_MGDL);

/** Triglycerides in mg/dL, or null when the value/unit is unusable. */
export const triglyceridesToMgDl = (value, unit) =>
  convertMassConcentration(value, unit, TG_MMOL_TO_MGDL);

/** HDL cholesterol in mg/dL, or null when the value/unit is unusable. */
export const hdlToMgDl = (value, unit) =>
  convertMassConcentration(value, unit, HDL_MMOL_TO_MGDL);

/** Insulin in µU/mL, or null when the value/unit is unusable. */
export const insulinToMicroUnits = (value, unit) => {
  const n = toNumber(value);
  if (n === null || n <= 0) return null;
  const u = normUnit(unit);
  if (['µu/ml', 'uu/ml', 'µiu/ml', 'uiu/ml', 'mu/l', 'miu/l', ''].includes(u)) {
    return n;
  }
  if (u === 'pmol/l') return n / INSULIN_PMOL_PER_UIU;
  return null;
};

/** HOMA-IR = glucose (mg/dL) × insulin (µU/mL) / 405. */
export const calculateHomaIr = (glucoseMgDl, insulinMicroUnits) => {
  const g = toNumber(glucoseMgDl);
  const i = toNumber(insulinMicroUnits);
  if (g === null || i === null || g <= 0 || i <= 0) return null;
  return round((g * i) / HOMA_IR_DIVISOR, 2);
};

/** Triglyceride/HDL ratio, both in mg/dL. */
export const calculateTgHdlRatio = (tgMgDl, hdlMgDl) => {
  const tg = toNumber(tgMgDl);
  const hdl = toNumber(hdlMgDl);
  if (tg === null || hdl === null || tg <= 0 || hdl <= 0) return null;
  return round(tg / hdl, 2);
};

export const round = (value, decimals = 1) => {
  const n = toNumber(value);
  if (n === null) return null;
  const f = 10 ** decimals;
  return Math.round(n * f) / f;
};

/**
 * Orientative bands. Cut-offs vary by population and laboratory; the UI
 * labels them as reference only, the clinician has the final word.
 */
export const BANDS = {
  homaIr: [
    { max: 2.5, level: 'normal' },
    { max: 3.5, level: 'borderline' },
    { max: 5, level: 'high' },
    { max: Infinity, level: 'veryHigh' },
  ],
  glucose: [
    { max: 100, level: 'normal' },
    { max: 126, level: 'borderline' },
    { max: 200, level: 'high' },
    { max: Infinity, level: 'veryHigh' },
  ],
  hba1c: [
    { max: 5.7, level: 'normal' },
    { max: 6.5, level: 'borderline' },
    { max: 8, level: 'high' },
    { max: Infinity, level: 'veryHigh' },
  ],
  tgHdl: [
    { max: 2, level: 'normal' },
    { max: 3, level: 'borderline' },
    { max: 5, level: 'high' },
    { max: Infinity, level: 'veryHigh' },
  ],
  insulin: [
    { max: 15, level: 'normal' },
    { max: 25, level: 'borderline' },
    { max: 50, level: 'high' },
    { max: Infinity, level: 'veryHigh' },
  ],
  // WHO: underweight, normal, overweight, obesity I, obesity II+.
  bmi: [
    { max: 18.5, level: 'low' },
    { max: 25, level: 'normal' },
    { max: 30, level: 'borderline' },
    { max: 35, level: 'high' },
    { max: Infinity, level: 'veryHigh' },
  ],
  // ACC/AHA: normal, elevated, stage 1, stage 2.
  systolic: [
    { max: 120, level: 'normal' },
    { max: 130, level: 'borderline' },
    { max: 140, level: 'high' },
    { max: Infinity, level: 'veryHigh' },
  ],
  diastolic: [
    { max: 80, level: 'normal' },
    { max: 90, level: 'high' },
    { max: Infinity, level: 'veryHigh' },
  ],
  // Waist in cm: IDF (South/Central America) for "high", ATP III for "very high".
  waistMale: [
    { max: 90, level: 'normal' },
    { max: 102, level: 'high' },
    { max: Infinity, level: 'veryHigh' },
  ],
  waistFemale: [
    { max: 80, level: 'normal' },
    { max: 88, level: 'high' },
    { max: Infinity, level: 'veryHigh' },
  ],
};

const BAND_STEPS = { glucose: 1, insulin: 1, systolic: 1, diastolic: 1 };

const LEVEL_SEVERITY = ['low', 'normal', 'borderline', 'high', 'veryHigh'];

/** Returns the band level for a value, or null. Upper bound is exclusive. */
export const classify = (metric, value) => {
  const n = toNumber(value);
  const bands = BANDS[metric];
  if (n === null || !bands) return null;
  return bands.find(b => n < b.max)?.level ?? null;
};

/** Blood pressure level: the worse of the systolic and diastolic levels. */
export const classifyBp = (systolic, diastolic) => {
  const levels = [
    classify('systolic', systolic),
    classify('diastolic', diastolic),
  ].filter(Boolean);
  if (levels.length === 0) return null;
  return levels.reduce((a, b) =>
    LEVEL_SEVERITY.indexOf(b) > LEVEL_SEVERITY.indexOf(a) ? b : a
  );
};

/** Waist band key for the patient's sex, or null when it is unknown. */
export const waistBandKey = gender => {
  const g = String(gender || '')
    .trim()
    .toLowerCase();
  if (['m', 'male', 'masculino', 'hombre'].includes(g)) return 'waistMale';
  if (['f', 'female', 'femenino', 'mujer'].includes(g)) return 'waistFemale';
  return null;
};

export const classifyWaist = (waistCm, gender) => {
  const key = waistBandKey(gender);
  return key ? classify(key, waistCm) : null;
};

/**
 * Bands as display ranges [{ level, min, upper, below }]: `below` is the
 * exclusive upper bound, `upper` the last value inside the band. `factor`
 * converts the cut-offs to another unit (e.g. cm → in).
 */
export const bandRanges = (metric, factor = 1) => {
  const bands = BANDS[metric];
  if (!bands) return [];
  const step = factor === 1 ? (BAND_STEPS[metric] ?? 0.1) : 0.1;
  let min = null;
  return bands.map(b => {
    const below = Number.isFinite(b.max) ? round(b.max * factor, 1) : null;
    const range = {
      level: b.level,
      min,
      below,
      upper: below === null ? null : round(below - step, 1),
    };
    min = below;
    return range;
  });
};

export const formatBandRange = (range, format = String) => {
  if (range.min === null) return `< ${format(range.below)}`;
  if (range.below === null) return `≥ ${format(range.min)}`;
  return `${format(range.min)} – ${format(range.upper)}`;
};

export const LEVEL_COLORS = {
  low: 'blue',
  normal: 'teal',
  borderline: 'yellow',
  high: 'orange',
  veryHigh: 'red',
};

/** Date key (YYYY-MM-DD) for a lab trend data point. */
export const pointDate = point => {
  const raw =
    point?.recorded_date ||
    point?.lab_result?.completed_date ||
    point?.created_at;
  if (!raw) return null;
  return raw.toString().slice(0, 10);
};

/**
 * Normalises lab trend points into [{ date, labResultId, value }] sorted by
 * date, dropping points whose value or unit cannot be used.
 */
export const normalizeLabPoints = (points, converter) => {
  const seen = new Set();
  const out = [];
  (points || []).forEach(p => {
    const key = p?.is_legacy ? `legacy-${p.lab_result?.id}` : p?.id;
    if (key !== undefined && seen.has(key)) return;
    if (key !== undefined) seen.add(key);
    const date = pointDate(p);
    const value = converter(p?.value, p?.unit);
    if (!date || value === null) return;
    out.push({ date, labResultId: p?.lab_result?.id ?? null, value });
  });
  return out.sort((a, b) => a.date.localeCompare(b.date));
};

/**
 * Pairs two normalised series by lab result (same sample); points without a
 * lab result fall back to an identical date. Then applies `combine`. Returns [{ date, value }].
 */
export const pairSeries = (seriesA, seriesB, combine) => {
  const byLab = new Map();
  const byDate = new Map();
  const byDateWithoutLab = new Map();
  (seriesB || []).forEach(b => {
    if (b.labResultId !== null) byLab.set(b.labResultId, b);
    else if (!byDateWithoutLab.has(b.date)) byDateWithoutLab.set(b.date, b);
    if (!byDate.has(b.date)) byDate.set(b.date, b);
  });
  const used = new Set();
  const out = [];
  (seriesA || []).forEach(a => {
    // Two different lab results are different samples even on the same day.
    const match =
      a.labResultId !== null
        ? byLab.get(a.labResultId) || byDateWithoutLab.get(a.date)
        : byDate.get(a.date);
    if (!match || used.has(match)) return;
    const value = combine(a.value, match.value);
    if (value === null) return;
    used.add(match);
    out.push({ date: a.date, value });
  });
  return out.sort((x, y) => x.date.localeCompare(y.date));
};

/** HOMA-IR series from normalised glucose (mg/dL) and insulin (µU/mL). */
export const buildHomaIrSeries = (glucose, insulin) =>
  pairSeries(glucose, insulin, calculateHomaIr);

/** TG/HDL series from normalised triglycerides and HDL (mg/dL). */
export const buildTgHdlSeries = (triglycerides, hdl) =>
  pairSeries(triglycerides, hdl, calculateTgHdlRatio);

/** Latest point and change versus the first point of a series. */
export const summarizeSeries = series => {
  if (!series || series.length === 0) return null;
  const first = series[0];
  const latest = series[series.length - 1];
  return {
    latest: latest.value,
    latestDate: latest.date,
    first: first.value,
    change: series.length > 1 ? round(latest.value - first.value, 2) : null,
    count: series.length,
  };
};

/** HbA1c in %, accepting % (NGSP) or mmol/mol (IFCC). */
export const hba1cToPercent = (value, unit) => {
  const n = toNumber(value);
  if (n === null || n <= 0) return null;
  const u = normUnit(unit);
  if (u === '%' || u === '') return n;
  if (u === 'mmol/mol') return round(n / 10.929 + 2.15, 1);
  return null;
};

/** BMI from storage units (weight in lb, height in inches). */
export const calculateBmiImperial = (weightLbs, heightInches) => {
  const w = toNumber(weightLbs);
  const h = toNumber(heightInches);
  if (w === null || h === null || w <= 0 || h <= 0) return null;
  return round((w / (h * h)) * 703, 1);
};
