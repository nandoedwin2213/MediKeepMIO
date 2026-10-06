import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Container,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Title,
  useMantineColorScheme,
} from '@mantine/core';
import {
  IconArrowDownRight,
  IconArrowUpRight,
  IconFlask,
  IconHeartbeat,
  IconInfoCircle,
} from '@tabler/icons-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { PageHeader } from '../../components';
import { usePatientWithStaticData } from '../../hooks/useGlobalData';
import { useUserPreferences } from '../../contexts/UserPreferencesContext';
import { useDateFormat } from '../../hooks/useDateFormat';
import { apiService } from '../../services/api';
import labTestComponentApi from '../../services/api/labTestComponentApi';
import logger from '../../services/logger';
import { convertForDisplay } from '../../utils/unitConversion';
import {
  LEVEL_COLORS,
  buildHomaIrSeries,
  buildTgHdlSeries,
  calculateBmiImperial,
  classify,
  glucoseToMgDl,
  hba1cToPercent,
  hdlToMgDl,
  insulinToMicroUnits,
  normalizeLabPoints,
  round,
  summarizeSeries,
  triglyceridesToMgDl,
} from '../../utils/insulinResistance';

const LAB_QUERIES = {
  glucose: { names: ['Glucose', 'Fasting Glucose'], convert: glucoseToMgDl },
  insulin: {
    names: ['Insulin', 'Fasting Insulin'],
    convert: insulinToMicroUnits,
  },
  hba1c: { names: ['Hemoglobin A1c'], convert: hba1cToPercent },
  triglycerides: { names: ['Triglycerides'], convert: triglyceridesToMgDl },
  hdl: { names: ['HDL Cholesterol'], convert: hdlToMgDl },
};

const GOLD = '#C9A45C';
const CYAN = '#4FD8F0';
const NAVY = '#2B4A85';
const NAVY_LIGHT = '#8FB0F0';
const CYAN_LINE = '#1FA9C4';

// IDF cut-offs for South/Central American populations: ≥90 cm men, ≥80 cm women.
const classifyWaist = (waistCm, gender) => {
  if (waistCm === null || waistCm === undefined) return null;
  const g = String(gender || '')
    .trim()
    .toLowerCase();
  let cutoff = null;
  if (['m', 'male', 'masculino', 'hombre'].includes(g)) cutoff = 90;
  if (['f', 'female', 'femenino', 'mujer'].includes(g)) cutoff = 80;
  if (cutoff === null) return null;
  return waistCm >= cutoff ? 'high' : 'normal';
};

const fetchTrendWithRetry = async (patientId, name, signal) => {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      return await labTestComponentApi.getTrendsByPatientAndTest(
        patientId,
        name,
        { limit: 100 },
        signal
      );
    } catch (err) {
      if (signal?.aborted) throw err;
      if (attempt === 1) throw err;
    }
  }
  return null;
};

const fetchLabSeries = async (patientId, { names, convert }, signal) => {
  const points = [];
  let failed = false;
  for (const name of names) {
    try {
      const res = await fetchTrendWithRetry(patientId, name, signal);
      points.push(...(res?.data_points || []));
    } catch (err) {
      if (signal?.aborted) throw err;
      failed = true;
      logger.warn('insulin_resistance_trend_failed', {
        component: 'InsulinResistance',
        testName: name,
        error: err?.message,
      });
    }
  }
  return { series: normalizeLabPoints(points, convert), failed };
};

const vitalSeries = (vitals, pick) =>
  (vitals || [])
    .map(v => ({
      date: (v.recorded_date || '').toString().slice(0, 10),
      value: pick(v),
    }))
    .filter(p => p.date && p.value !== null && p.value !== undefined)
    .sort((a, b) => a.date.localeCompare(b.date));

function MetricCard({
  label,
  unit,
  summary,
  level,
  levelLabel,
  formatDate,
  lowerIsBetter = true,
}) {
  const { t } = useTranslation('medical');
  const change = summary?.change;
  const improving =
    change === null || change === undefined || change === 0
      ? null
      : lowerIsBetter
        ? change < 0
        : change > 0;
  return (
    <Card className="silho-ir-metric" withBorder radius="lg" padding="md">
      <Group justify="space-between" align="flex-start" gap={4}>
        <Text size="sm" fw={600} c="dimmed">
          {label}
        </Text>
        {level && (
          <Badge color={LEVEL_COLORS[level]} variant="light" size="sm">
            {levelLabel}
          </Badge>
        )}
      </Group>
      {summary ? (
        <>
          <Group gap={6} align="baseline" mt={6}>
            <Text className="silho-ir-value" fw={700} size="28px">
              {summary.latest}
            </Text>
            <Text size="sm" c="dimmed">
              {unit}
            </Text>
          </Group>
          <Group gap={6} mt={4}>
            {improving !== null && (
              <Group gap={2} c={improving ? 'teal' : 'red'}>
                {change < 0 ? (
                  <IconArrowDownRight size={16} />
                ) : (
                  <IconArrowUpRight size={16} />
                )}
                <Text size="xs" fw={600}>
                  {change > 0 ? `+${change}` : change}
                </Text>
              </Group>
            )}
            <Text size="xs" c="dimmed">
              {formatDate(summary.latestDate)}
            </Text>
          </Group>
        </>
      ) : (
        <Text size="sm" c="dimmed" mt={8}>
          {t('insulinResistance.noData', 'No data yet')}
        </Text>
      )}
    </Card>
  );
}

function TrendCard({ title, lines, reference, formatDate }) {
  const { t } = useTranslation('medical');
  const { colorScheme } = useMantineColorScheme();
  const dark = colorScheme === 'dark';
  const axisTick = { fontSize: 11, fill: dark ? '#C9D4EA' : '#41506B' };
  const data = useMemo(() => {
    const byDate = new Map();
    lines.forEach(line => {
      line.series.forEach(p => {
        const row = byDate.get(p.date) || { date: p.date };
        row[line.key] = p.value;
        byDate.set(p.date, row);
      });
    });
    return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  }, [lines]);

  return (
    <Card className="silho-ir-chart" withBorder radius="lg" padding="md">
      <Text fw={600} mb="xs">
        {title}
      </Text>
      {data.length === 0 ? (
        <Center h={200}>
          <Text size="sm" c="dimmed">
            {t('insulinResistance.noData', 'No data yet')}
          </Text>
        </Center>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart
            data={data}
            margin={{ top: 8, right: 12, left: -12, bottom: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={dark ? 'rgba(201,212,234,0.18)' : 'rgba(43,74,133,0.18)'}
            />
            <XAxis dataKey="date" tickFormatter={formatDate} tick={axisTick} />
            <YAxis yAxisId="left" tick={axisTick} domain={['auto', 'auto']} />
            {lines.some(l => l.axis === 'right') && (
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={axisTick}
                domain={['auto', 'auto']}
              />
            )}
            <Tooltip
              labelFormatter={formatDate}
              contentStyle={{
                background: dark ? '#0B1A33' : '#FFFFFF',
                border: '1px solid rgba(201,164,92,0.45)',
                borderRadius: 8,
              }}
              labelStyle={{
                color: dark ? '#E5CF95' : '#0B1A33',
                fontWeight: 600,
              }}
              itemStyle={{ color: dark ? '#E8EEF8' : '#152B55' }}
              formatter={(value, name) => {
                const line = lines.find(l => l.key === name);
                return [`${value} ${line?.unit || ''}`, line?.label || name];
              }}
            />
            {reference && (
              <ReferenceLine
                yAxisId="left"
                y={reference.value}
                stroke={GOLD}
                strokeDasharray="6 4"
                label={{
                  value: reference.label,
                  fontSize: 10,
                  fill: GOLD,
                  position: 'insideTopRight',
                }}
              />
            )}
            {lines.map(line => (
              <Line
                key={line.key}
                type="monotone"
                dataKey={line.key}
                name={line.key}
                yAxisId={line.axis || 'left'}
                stroke={dark && line.color === NAVY ? NAVY_LIGHT : line.color}
                strokeWidth={2.5}
                dot={{ r: 3 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}

const InsulinResistance = () => {
  const { t } = useTranslation('medical');
  const navigate = useNavigate();
  const { patient } = usePatientWithStaticData();
  const currentPatient = patient?.patient;
  const patientId = currentPatient?.id;
  const patientHeight = currentPatient?.height;
  const { unitSystem } = useUserPreferences();
  const { formatDate } = useDateFormat();

  const [labs, setLabs] = useState(null);
  const [vitals, setVitals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [partial, setPartial] = useState(false);

  const load = useCallback(
    async signal => {
      if (!patientId) return;
      setLoading(true);
      setError(null);
      try {
        const keys = Object.keys(LAB_QUERIES);
        const labSeries = [];
        for (const k of keys) {
          labSeries.push(
            await fetchLabSeries(patientId, LAB_QUERIES[k], signal)
          );
        }
        let vitalsFailed = false;
        const vitalsResponse = await apiService
          .getPatientEntities('vitals', patientId, signal)
          .catch(() => {
            vitalsFailed = true;
            return [];
          });
        if (signal?.aborted) return;
        setLabs(
          Object.fromEntries(keys.map((k, i) => [k, labSeries[i].series]))
        );
        setPartial(vitalsFailed || labSeries.some(r => r.failed));
        const list = Array.isArray(vitalsResponse)
          ? vitalsResponse
          : vitalsResponse?.data || [];
        setVitals(list);
      } catch (err) {
        if (signal?.aborted) return;
        logger.error('insulin_resistance_load_failed', {
          component: 'InsulinResistance',
          error: err?.message,
        });
        setError(t('insulinResistance.loadError', 'Could not load the data.'));
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [patientId, t]
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const series = useMemo(() => {
    const l = labs || {};
    const weightUnit = unitSystem === 'metric' ? 'kg' : 'lb';
    return {
      glucose: l.glucose || [],
      insulin: l.insulin || [],
      hba1c: l.hba1c || [],
      homaIr: buildHomaIrSeries(l.glucose || [], l.insulin || []),
      tgHdl: buildTgHdlSeries(l.triglycerides || [], l.hdl || []),
      weight: vitalSeries(vitals, v =>
        v.weight
          ? round(convertForDisplay(v.weight, 'weight', unitSystem), 1)
          : null
      ),
      bmi: vitalSeries(vitals, v =>
        v.bmi
          ? round(v.bmi, 1)
          : calculateBmiImperial(v.weight, v.height || patientHeight)
      ),
      waist: vitalSeries(vitals, v =>
        v.waist_circumference
          ? round(
              convertForDisplay(v.waist_circumference, 'waist', unitSystem),
              1
            )
          : null
      ),
      waistCm: vitalSeries(vitals, v =>
        v.waist_circumference ? round(v.waist_circumference * 2.54, 1) : null
      ),
      systolic: vitalSeries(vitals, v => v.systolic_bp ?? null),
      diastolic: vitalSeries(vitals, v => v.diastolic_bp ?? null),
      weightUnit,
      waistUnit: unitSystem === 'metric' ? 'cm' : 'in',
    };
  }, [labs, vitals, unitSystem, patientHeight]);

  const summaries = useMemo(
    () => ({
      homaIr: summarizeSeries(series.homaIr),
      glucose: summarizeSeries(
        series.glucose.map(p => ({ ...p, value: round(p.value, 0) }))
      ),
      insulin: summarizeSeries(
        series.insulin.map(p => ({ ...p, value: round(p.value, 1) }))
      ),
      hba1c: summarizeSeries(series.hba1c),
      tgHdl: summarizeSeries(series.tgHdl),
      weight: summarizeSeries(series.weight),
      bmi: summarizeSeries(series.bmi),
      waist: summarizeSeries(series.waist),
      systolic: summarizeSeries(series.systolic),
    }),
    [series]
  );

  const levelLabel = level =>
    level ? t(`insulinResistance.levels.${level}`, level) : null;
  const fmt = useCallback(d => (d ? formatDate(d) : ''), [formatDate]);

  if (!currentPatient) {
    return (
      <Container size="xl" py="md">
        <PageHeader
          title={t('insulinResistance.title', 'Insulin resistance')}
          icon="🧬"
        />
        <Alert color="blue" mt="md">
          {t(
            'insulinResistance.selectPatient',
            'Select a patient to see the panel.'
          )}
        </Alert>
      </Container>
    );
  }

  const homa = summaries.homaIr;
  const waistLevel = classifyWaist(
    series.waistCm[series.waistCm.length - 1]?.value,
    currentPatient?.gender
  );
  const homaLevel = classify('homaIr', homa?.latest);
  const bp = summaries.systolic
    ? `${summaries.systolic.latest}/${series.diastolic[series.diastolic.length - 1]?.value ?? '–'}`
    : null;
  const hasAnyData =
    series.glucose.length ||
    series.insulin.length ||
    series.hba1c.length ||
    series.tgHdl.length ||
    series.weight.length ||
    series.waist.length ||
    series.systolic.length;

  return (
    <Container size="xl" py="md">
      <PageHeader
        title={t('insulinResistance.title', 'Insulin resistance')}
        icon="🧬"
      />

      {partial && !error && (
        <Alert color="yellow" variant="light" mt="md">
          <Group justify="space-between" gap="sm">
            <Text size="sm">
              {t(
                'insulinResistance.partialError',
                'Some results could not be loaded; the values shown may be incomplete.'
              )}
            </Text>
            <Button size="xs" variant="light" onClick={() => load()}>
              {t('insulinResistance.retry', 'Retry')}
            </Button>
          </Group>
        </Alert>
      )}

      {error && (
        <Alert color="red" mt="md">
          {error}
        </Alert>
      )}

      {loading && !labs ? (
        <Center py="xl">
          <Loader color="yellow" />
        </Center>
      ) : (
        <Stack gap="lg" mt="md">
          <Card className="silho-ir-hero" radius="xl" padding="xl">
            <Group justify="space-between" align="center" wrap="wrap" gap="lg">
              <Stack gap={4} style={{ minWidth: 0 }}>
                <Text
                  className="silho-ir-eyebrow"
                  size="xs"
                  fw={700}
                  tt="uppercase"
                >
                  {t('insulinResistance.homaTitle', 'HOMA-IR index')}
                </Text>
                <Title order={2} className="silho-ir-patient">
                  {[currentPatient.first_name, currentPatient.last_name]
                    .filter(Boolean)
                    .join(' ')}
                </Title>
                <Text size="sm" className="silho-ir-muted">
                  {t(
                    'insulinResistance.formula',
                    'Automatic: fasting glucose (mg/dL) × fasting insulin (µU/mL) ÷ 405'
                  )}
                </Text>
                {homa?.latestDate && (
                  <Text size="xs" className="silho-ir-muted">
                    {t('insulinResistance.lastSample', 'Last sample')}:{' '}
                    {fmt(homa.latestDate)}
                  </Text>
                )}
              </Stack>
              <Stack gap={6} align="flex-end">
                <Text className="silho-ir-homa">
                  {homa ? homa.latest : '—'}
                </Text>
                {homaLevel ? (
                  <Badge
                    color={LEVEL_COLORS[homaLevel]}
                    size="lg"
                    variant="filled"
                  >
                    {levelLabel(homaLevel)}
                  </Badge>
                ) : (
                  <Text
                    size="xs"
                    className="silho-ir-muted"
                    ta="right"
                    maw={240}
                  >
                    {t(
                      'insulinResistance.homaMissing',
                      'Record fasting glucose and insulin from the same sample to calculate it.'
                    )}
                  </Text>
                )}
              </Stack>
            </Group>
          </Card>

          {!hasAnyData && (
            <Alert
              icon={<IconInfoCircle size={18} />}
              color="yellow"
              variant="light"
            >
              <Text size="sm" mb="sm">
                {t(
                  'insulinResistance.emptyState',
                  'There are no results yet. Add a lab result (glucose, insulin, HbA1c, lipids) or a vital signs record to start the follow-up.'
                )}
              </Text>
              <Group gap="sm">
                <Button
                  size="xs"
                  leftSection={<IconFlask size={14} />}
                  onClick={() => navigate('/lab-results')}
                >
                  {t('insulinResistance.addLab', 'Add lab result')}
                </Button>
                <Button
                  size="xs"
                  variant="light"
                  leftSection={<IconHeartbeat size={14} />}
                  onClick={() => navigate('/vitals')}
                >
                  {t('insulinResistance.addVitals', 'Add vital signs')}
                </Button>
              </Group>
            </Alert>
          )}

          <SimpleGrid cols={{ base: 2, sm: 3, lg: 4 }} spacing="md">
            <MetricCard
              label={t('insulinResistance.metrics.glucose', 'Fasting glucose')}
              unit="mg/dL"
              summary={summaries.glucose}
              level={classify('glucose', summaries.glucose?.latest)}
              levelLabel={levelLabel(
                classify('glucose', summaries.glucose?.latest)
              )}
              formatDate={fmt}
            />
            <MetricCard
              label={t('insulinResistance.metrics.insulin', 'Fasting insulin')}
              unit="µU/mL"
              summary={summaries.insulin}
              level={classify('insulin', summaries.insulin?.latest)}
              levelLabel={levelLabel(
                classify('insulin', summaries.insulin?.latest)
              )}
              formatDate={fmt}
            />
            <MetricCard
              label="HbA1c"
              unit="%"
              summary={summaries.hba1c}
              level={classify('hba1c', summaries.hba1c?.latest)}
              levelLabel={levelLabel(
                classify('hba1c', summaries.hba1c?.latest)
              )}
              formatDate={fmt}
            />
            <MetricCard
              label={t('insulinResistance.metrics.tgHdl', 'Triglycerides/HDL')}
              unit=""
              summary={summaries.tgHdl}
              level={classify('tgHdl', summaries.tgHdl?.latest)}
              levelLabel={levelLabel(
                classify('tgHdl', summaries.tgHdl?.latest)
              )}
              formatDate={fmt}
            />
            <MetricCard
              label={t('insulinResistance.metrics.weight', 'Weight')}
              unit={series.weightUnit}
              summary={summaries.weight}
              formatDate={fmt}
            />
            <MetricCard
              label={t('insulinResistance.metrics.waist', 'Waist')}
              unit={series.waistUnit}
              summary={summaries.waist}
              level={waistLevel}
              levelLabel={levelLabel(waistLevel)}
              formatDate={fmt}
            />
            <MetricCard
              label={t('insulinResistance.metrics.bmi', 'BMI')}
              unit="kg/m²"
              summary={summaries.bmi}
              level={classify('bmi', summaries.bmi?.latest)}
              levelLabel={levelLabel(classify('bmi', summaries.bmi?.latest))}
              formatDate={fmt}
            />
            <MetricCard
              label={t(
                'insulinResistance.metrics.bloodPressure',
                'Blood pressure'
              )}
              unit="mmHg"
              summary={
                summaries.systolic
                  ? { ...summaries.systolic, latest: bp, change: null }
                  : null
              }
              level={classify('systolic', summaries.systolic?.latest)}
              levelLabel={levelLabel(
                classify('systolic', summaries.systolic?.latest)
              )}
              formatDate={fmt}
            />
            <MetricCard
              label="HOMA-IR"
              unit=""
              summary={homa}
              level={homaLevel}
              levelLabel={levelLabel(homaLevel)}
              formatDate={fmt}
            />
          </SimpleGrid>

          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
            <TrendCard
              title={t('insulinResistance.charts.homaIr', 'HOMA-IR evolution')}
              formatDate={fmt}
              reference={{ value: 2.5, label: '2.5' }}
              lines={[
                {
                  key: 'homa',
                  label: 'HOMA-IR',
                  unit: '',
                  color: GOLD,
                  series: series.homaIr,
                },
              ]}
            />
            <TrendCard
              title={t(
                'insulinResistance.charts.glucoseInsulin',
                'Glucose and insulin'
              )}
              formatDate={fmt}
              lines={[
                {
                  key: 'glucose',
                  label: t(
                    'insulinResistance.metrics.glucose',
                    'Fasting glucose'
                  ),
                  unit: 'mg/dL',
                  color: NAVY,
                  series: series.glucose.map(p => ({
                    ...p,
                    value: round(p.value, 0),
                  })),
                },
                {
                  key: 'insulin',
                  axis: 'right',
                  label: t(
                    'insulinResistance.metrics.insulin',
                    'Fasting insulin'
                  ),
                  unit: 'µU/mL',
                  color: CYAN,
                  series: series.insulin.map(p => ({
                    ...p,
                    value: round(p.value, 1),
                  })),
                },
              ]}
            />
            <TrendCard
              title={t(
                'insulinResistance.charts.hba1cTgHdl',
                'HbA1c and triglycerides/HDL'
              )}
              formatDate={fmt}
              lines={[
                {
                  key: 'hba1c',
                  label: 'HbA1c',
                  unit: '%',
                  color: GOLD,
                  series: series.hba1c,
                },
                {
                  key: 'tgHdl',
                  axis: 'right',
                  label: t(
                    'insulinResistance.metrics.tgHdl',
                    'Triglycerides/HDL'
                  ),
                  unit: '',
                  color: CYAN,
                  series: series.tgHdl,
                },
              ]}
            />
            <TrendCard
              title={t('insulinResistance.charts.body', 'Weight and BMI')}
              formatDate={fmt}
              lines={[
                {
                  key: 'weight',
                  label: t('insulinResistance.metrics.weight', 'Weight'),
                  unit: series.weightUnit,
                  color: NAVY,
                  series: series.weight,
                },
                {
                  key: 'waist',
                  label: t('insulinResistance.metrics.waist', 'Waist'),
                  unit: series.waistUnit,
                  color: CYAN_LINE,
                  series: series.waist,
                },
                {
                  key: 'bmi',
                  axis: 'right',
                  label: t('insulinResistance.metrics.bmi', 'BMI'),
                  unit: 'kg/m²',
                  color: GOLD,
                  series: series.bmi,
                },
              ]}
            />
            <TrendCard
              title={t(
                'insulinResistance.metrics.bloodPressure',
                'Blood pressure'
              )}
              formatDate={fmt}
              reference={{ value: 130, label: '130' }}
              lines={[
                {
                  key: 'systolic',
                  label: t('insulinResistance.charts.systolic', 'Systolic'),
                  unit: 'mmHg',
                  color: NAVY,
                  series: series.systolic,
                },
                {
                  key: 'diastolic',
                  label: t('insulinResistance.charts.diastolic', 'Diastolic'),
                  unit: 'mmHg',
                  color: CYAN,
                  series: series.diastolic,
                },
              ]}
            />
          </SimpleGrid>

          <Text size="xs" c="dimmed">
            {t(
              'insulinResistance.disclaimer',
              'Reference ranges are orientative (HOMA-IR ≥ 2.5, HbA1c ≥ 5.7 %, fasting glucose ≥ 100 mg/dL, TG/HDL ≥ 2). Cut-offs vary by population and laboratory; interpretation belongs to the treating physician.'
            )}
          </Text>
        </Stack>
      )}
    </Container>
  );
};

export default InsulinResistance;
