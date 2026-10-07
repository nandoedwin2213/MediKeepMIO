import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Container,
  Group,
  Loader,
  RingProgress,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconCheck,
  IconClipboardHeart,
  IconFileImport,
  IconFlask,
  IconHeartbeat,
  IconMinus,
} from '@tabler/icons-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { PageHeader } from '../../components';
import { usePatientWithStaticData } from '../../hooks/useGlobalData';
import { useDateFormat } from '../../hooks/useDateFormat';
import metabolicApi from '../../services/api/metabolicApi';
import logger from '../../services/logger';
import { LEVEL_COLORS } from '../../utils/insulinResistance';
import { BRAND } from '../../config/brand';

export const RISK_COLORS = {
  favorable: 'teal',
  initial: 'yellow',
  moderate: 'orange',
  high: 'red',
};

const INDEX_KEYS = [
  'homa_ir',
  'quicki',
  'tyg',
  'tyg_bmi',
  'mets_ir',
  'tg_hdl',
  'waist_height',
  'waist_hip',
];

const INDEX_INPUTS = {
  homa_ir: ['glucose', 'insulin'],
  quicki: ['glucose', 'insulin'],
  tyg: ['glucose', 'triglycerides'],
  tyg_bmi: ['glucose', 'triglycerides', 'bmi'],
  mets_ir: ['glucose', 'triglycerides', 'hdl', 'bmi'],
  tg_hdl: ['triglycerides', 'hdl'],
  waist_height: ['waist', 'height'],
  waist_hip: ['waist', 'hip'],
};

export const fmt = (value, locale) =>
  typeof value === 'number'
    ? value.toLocaleString(locale, { maximumFractionDigits: 3 })
    : value;

export const formatBand = (band, locale) => {
  if (band.min === null || band.min === undefined)
    return `< ${fmt(band.max, locale)}`;
  if (band.max === null || band.max === undefined)
    return `≥ ${fmt(band.min, locale)}`;
  return `${fmt(band.min, locale)} – ${fmt(band.max, locale)}`;
};

export function LevelScale({ bands, level, locale }) {
  const { t } = useTranslation('medical');
  if (!bands?.length) return null;
  return (
    <Stack gap={4} mt="sm" className="silho-ir-ranges">
      <div className="silho-ir-scale">
        {bands.map((b, i) => (
          <span
            key={`${b.level}-${i}`}
            className="silho-ir-scale-seg"
            data-active={b.level === level || undefined}
            style={{
              background: `var(--mantine-color-${LEVEL_COLORS[b.level]}-6)`,
            }}
          />
        ))}
      </div>
      {bands.map((b, i) => {
        const active = b.level === level;
        return (
          <Group
            key={`${b.level}-${i}`}
            gap={6}
            wrap="nowrap"
            justify="space-between"
            className="silho-ir-range"
            data-active={active || undefined}
          >
            <Group gap={6} wrap="nowrap">
              <Box
                className="silho-ir-dot"
                style={{
                  background: `var(--mantine-color-${LEVEL_COLORS[b.level]}-6)`,
                }}
              />
              <Text size="xs" fw={active ? 700 : 500}>
                {t(`insulinResistance.levels.${b.level}`, b.level)}
              </Text>
            </Group>
            <Text
              size="xs"
              fw={active ? 700 : 400}
              c={active ? undefined : 'dimmed'}
              style={{ whiteSpace: 'nowrap' }}
            >
              {formatBand(b, locale)}
            </Text>
          </Group>
        );
      })}
    </Stack>
  );
}

export function ScoreHero({ score, formatDate, assessedAt, versions }) {
  const { t } = useTranslation('medical');
  const has = score?.value !== null && score?.value !== undefined;
  const color = has ? RISK_COLORS[score.level] : 'gray';
  return (
    <Card className="silho-mr-hero" withBorder radius="lg" padding="lg">
      <Group align="center" gap="xl" wrap="wrap">
        <RingProgress
          size={170}
          thickness={14}
          roundCaps
          sections={[{ value: has ? score.value : 0, color }]}
          label={
            <Center>
              <Stack gap={0} align="center">
                <Text fw={800} size="40px" lh={1} className="silho-ir-value">
                  {has ? score.value : '–'}
                </Text>
                <Text size="xs" c="dimmed">
                  /100
                </Text>
              </Stack>
            </Center>
          }
        />
        <Stack gap={6} style={{ flex: 1, minWidth: 220 }}>
          <Text size="xs" fw={700} tt="uppercase" c="dimmed">
            {t('metabolic.scoreTitle', '{{brand}} Metabolic Score', {
              brand: BRAND.metabolicScoreBrand,
            })}
          </Text>
          {has ? (
            <Badge
              color={color}
              size="xl"
              variant="light"
              w="fit-content"
              maw="100%"
              h="auto"
              py={4}
              styles={{
                label: { whiteSpace: 'normal', overflow: 'visible' },
              }}
            >
              {t(`metabolic.risk.${score.level}`, score.level)}
            </Badge>
          ) : (
            <>
              <Text fw={700}>
                {t('metabolic.insufficient', 'Not enough data yet')}
              </Text>
              <Text size="sm" c="dimmed">
                {t(
                  'metabolic.insufficientHint',
                  'Record waist, blood pressure, labs and the metabolic history to calculate the score.'
                )}
              </Text>
            </>
          )}
          <Text size="sm" c="dimmed">
            {t('metabolic.coverage', 'Data used for the score: {{pct}}%', {
              pct: Math.round((score?.coverage || 0) * 100),
            })}
          </Text>
          {assessedAt && (
            <Text size="xs" c="dimmed">
              {t('metabolic.lastUpdate', 'Calculated on {{date}}', {
                date: formatDate(assessedAt),
              })}{' '}
              ·{' '}
              {t(
                'metabolic.versionInfo',
                'algorithm {{algo}} · configuration v{{config}}',
                versions
              )}
            </Text>
          )}
          <Text size="xs" c="dimmed" fs="italic">
            {t(
              'metabolic.disclaimer',
              'Internal follow-up indicator, not a validated diagnostic tool. Results require professional assessment.'
            )}
          </Text>
        </Stack>
      </Group>
    </Card>
  );
}

function SyndromeCard({ syndrome }) {
  const { t } = useTranslation('medical');
  if (!syndrome) return null;
  const color =
    syndrome.status === 'compatible'
      ? 'red'
      : syndrome.status === 'not_compatible'
        ? 'teal'
        : 'gray';
  return (
    <Card withBorder radius="lg" padding="lg" className="silho-ir-metric">
      <Group justify="space-between" align="flex-start">
        <Text fw={700}>
          {t('metabolic.syndrome.title', 'Metabolic syndrome criteria')}
        </Text>
        <Badge color={color} variant="light">
          {t(`metabolic.syndrome.status.${syndrome.status}`, syndrome.status)}
        </Badge>
      </Group>
      <Text size="sm" c="dimmed" mt={4}>
        {t(
          'metabolic.syndrome.count',
          '{{met}} of {{total}} criteria met ({{required}} needed)',
          syndrome
        )}
      </Text>
      <Stack gap={6} mt="sm">
        {syndrome.criteria.map(c => (
          <Group key={c.id} gap={8} wrap="nowrap">
            <ThemeIcon
              size="sm"
              radius="xl"
              variant="light"
              color={
                c.met === true ? 'orange' : c.met === false ? 'teal' : 'gray'
              }
            >
              {c.met === true ? (
                <IconAlertTriangle size={12} />
              ) : c.met === false ? (
                <IconCheck size={12} />
              ) : (
                <IconMinus size={12} />
              )}
            </ThemeIcon>
            <Text size="sm">
              {t(`metabolic.syndrome.criteria.${c.id}`, c.id)}
              {c.met === null && (
                <Text span size="xs" c="dimmed">
                  {' '}
                  · {t('metabolic.syndrome.noData', 'no data')}
                </Text>
              )}
              {c.values?.history && (
                <Text span size="xs" c="dimmed">
                  {' '}
                  · {t('metabolic.syndrome.history', 'by medical history')}
                </Text>
              )}
            </Text>
          </Group>
        ))}
      </Stack>
    </Card>
  );
}

function FactorCard({ factor, indicators, locale }) {
  const { t } = useTranslation('medical');
  const color = LEVEL_COLORS[factor.level];
  const value =
    typeof factor.value === 'string' &&
    ['smoking', 'alcohol'].includes(factor.key)
      ? t(
          `metabolic.profile.options.${factor.key}.${factor.value}`,
          factor.value
        )
      : fmt(factor.value, locale);
  return (
    <Card
      withBorder
      radius="lg"
      padding="md"
      className="silho-mr-factor"
      style={{ borderLeft: `4px solid var(--mantine-color-${color}-6)` }}
    >
      <Group justify="space-between" align="flex-start" gap={4} wrap="nowrap">
        <Text fw={700} size="sm">
          {t(`metabolic.factors.items.${factor.key}.${factor.level}`, {
            defaultValue: t(`metabolic.indicators.${factor.key}`, factor.key),
          })}
        </Text>
        <Badge color={color} variant="light" size="sm">
          {t(`insulinResistance.levels.${factor.level}`, factor.level)}
        </Badge>
      </Group>
      <Text size="lg" fw={700} mt={2}>
        {value}
        {factor.unit && (
          <Text span size="xs" c="dimmed" fw={500}>
            {' '}
            {factor.unit}
          </Text>
        )}
      </Text>
      {factor.key === 'blood_pressure' ? (
        <>
          <Text size="xs" fw={600} c="dimmed" mt="xs">
            {t('metabolic.indicators.systolic', 'systolic')}
          </Text>
          <LevelScale
            bands={indicators?.systolic?.bands}
            level={indicators?.systolic?.level}
            locale={locale}
          />
          <Text size="xs" fw={600} c="dimmed" mt="xs">
            {t('metabolic.indicators.diastolic', 'diastolic')}
          </Text>
          <LevelScale
            bands={indicators?.diastolic?.bands}
            level={indicators?.diastolic?.level}
            locale={locale}
          />
        </>
      ) : (
        <LevelScale
          bands={indicators?.[factor.key]?.bands}
          level={factor.level}
          locale={locale}
        />
      )}
    </Card>
  );
}

function IndexCard({ indexKey, indicator, locale, formatDate }) {
  const { t } = useTranslation('medical');
  return (
    <Card withBorder radius="lg" padding="md" className="silho-ir-metric">
      <Group justify="space-between" align="flex-start" gap={4}>
        <Text size="sm" fw={600} c="dimmed">
          {t(`metabolic.indicators.${indexKey}`, indexKey)}
        </Text>
        {indicator?.level && (
          <Badge
            color={LEVEL_COLORS[indicator.level]}
            variant="light"
            size="sm"
          >
            {t(`insulinResistance.levels.${indicator.level}`, indicator.level)}
          </Badge>
        )}
      </Group>
      {indicator ? (
        <>
          <Text className="silho-ir-value" fw={700} size="28px" mt={6}>
            {fmt(indicator.value, locale)}
          </Text>
          {indicator.date && (
            <Text size="xs" c="dimmed">
              {formatDate(indicator.date)}
            </Text>
          )}
        </>
      ) : (
        <Text size="sm" c="dimmed" mt={8}>
          {t('metabolic.indices.missing', 'Missing data: {{inputs}}', {
            inputs: INDEX_INPUTS[indexKey]
              .map(k => t(`metabolic.indicators.${k}`, k))
              .join(', '),
          })}
        </Text>
      )}
      <Text size="xs" mt={6}>
        {t(`metabolic.explain.${indexKey}`, '')}
      </Text>
      <LevelScale
        bands={indicator?.bands}
        level={indicator?.level}
        locale={locale}
      />
    </Card>
  );
}

function ScoreTrend({ assessments, formatDate }) {
  const { t } = useTranslation('medical');
  const data = [...assessments]
    .filter(a => a.score !== null && a.score !== undefined)
    .reverse()
    .map(a => ({ date: a.assessed_at, score: a.score }));
  return (
    <Card withBorder radius="lg" padding="md" className="silho-ir-chart">
      <Text fw={700} mb="xs">
        {t('metabolic.evolution.title', 'Score evolution')}
      </Text>
      {data.length < 2 ? (
        <Text size="sm" c="dimmed">
          {t(
            'metabolic.evolution.empty',
            'The evolution appears after two or more evaluations with new data.'
          )}
        </Text>
      ) : (
        <Box h={220}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 12, left: -12 }}>
              <ReferenceArea
                y1={80}
                y2={100}
                fill="#12b886"
                fillOpacity={0.08}
              />
              <ReferenceArea
                y1={60}
                y2={80}
                fill="#fab005"
                fillOpacity={0.08}
              />
              <ReferenceArea
                y1={40}
                y2={60}
                fill="#fd7e14"
                fillOpacity={0.08}
              />
              <ReferenceArea y1={0} y2={40} fill="#fa5252" fillOpacity={0.08} />
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="date"
                tickFormatter={d => formatDate(d)}
                tick={{ fontSize: 11, fill: 'currentColor' }}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 11, fill: 'currentColor' }}
              />
              <Tooltip labelFormatter={d => formatDate(d)} />
              <Line
                type="monotone"
                dataKey="score"
                name={t('metabolic.scoreShort', 'Score')}
                stroke="#C9A45C"
                strokeWidth={3}
                dot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </Box>
      )}
    </Card>
  );
}

const MetabolicRisk = () => {
  const { t, i18n } = useTranslation('medical');
  const navigate = useNavigate();
  const { patient } = usePatientWithStaticData();
  const patientId = patient?.patient?.id;
  const { formatDate } = useDateFormat();
  const locale = i18n.language;

  const [evaluation, setEvaluation] = useState(null);
  const [assessments, setAssessments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(
    async signal => {
      if (!patientId) return;
      setLoading(true);
      setError(null);
      try {
        const evalResponse = await metabolicApi.evaluate(patientId, signal);
        const history = await metabolicApi
          .getAssessments(patientId, signal)
          .catch(() => []);
        if (signal?.aborted) return;
        setEvaluation(evalResponse);
        setAssessments(Array.isArray(history) ? history : []);
      } catch (err) {
        if (signal?.aborted) return;
        logger.error('metabolic_risk_load_failed', {
          component: 'MetabolicRisk',
          error: err?.message,
        });
        setError(
          t('metabolic.loadError', 'Could not calculate the metabolic risk.')
        );
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

  const result = evaluation?.result;

  return (
    <Container size="xl" py="md" className="silho-ir-page">
      <PageHeader title={t('metabolic.title', 'Metabolic risk')} icon="🎯" />
      <Stack gap="lg" mt="md">
        <Text c="dimmed">
          {t(
            'metabolic.subtitle',
            'How am I? What is raising my risk? What should I improve?'
          )}
        </Text>
        {!patientId && (
          <Alert color="blue">
            {t(
              'metabolic.selectPatient',
              'Select a patient to see their metabolic risk.'
            )}
          </Alert>
        )}
        {error && (
          <Alert color="red" title={error}>
            <Button size="xs" variant="light" onClick={() => load()}>
              {t('metabolic.retry', 'Retry')}
            </Button>
          </Alert>
        )}
        {loading && !result && (
          <Center py="xl">
            <Loader />
          </Center>
        )}
        {result && (
          <>
            {result.alerts?.length > 0 && (
              <Alert
                color="red"
                variant="filled"
                icon={<IconAlertTriangle />}
                title={t(
                  'metabolic.alerts.title',
                  'Requires medical assessment'
                )}
              >
                <Stack gap={2}>
                  {result.alerts.map(a => (
                    <Text size="sm" key={a.id}>
                      {t(`metabolic.alerts.items.${a.id}`, a.id)}:{' '}
                      {fmt(a.value, locale)} ({a.op} {fmt(a.threshold, locale)})
                    </Text>
                  ))}
                </Stack>
              </Alert>
            )}
            <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
              <ScoreHero
                score={result.score}
                formatDate={formatDate}
                assessedAt={evaluation.assessed_at}
                versions={{
                  algo: result.algorithm_version,
                  config: result.config_version,
                }}
              />
              <SyndromeCard syndrome={result.metabolic_syndrome} />
            </SimpleGrid>

            <Group gap="sm">
              <Button
                leftSection={<IconClipboardHeart size={16} />}
                onClick={() => navigate('/metabolic-profile')}
              >
                {t('metabolic.actions.profile', 'Metabolic history and habits')}
              </Button>
              <Button
                variant="light"
                leftSection={<IconFlask size={16} />}
                onClick={() => navigate('/lab-results')}
              >
                {t('metabolic.actions.addLab', 'Lab results')}
              </Button>
              <Button
                variant="light"
                leftSection={<IconFileImport size={16} />}
                onClick={() => navigate('/metabolic-labs')}
              >
                {t('metabolic.actions.importLab', 'Import lab report')}
              </Button>
              <Button
                variant="light"
                leftSection={<IconHeartbeat size={16} />}
                onClick={() => navigate('/vitals')}
              >
                {t('metabolic.actions.addVitals', 'Vital signs')}
              </Button>
            </Group>

            <div>
              <Title order={3}>
                {t(
                  'metabolic.factors.title',
                  'What is affecting your metabolism?'
                )}
              </Title>
              <Text size="sm" c="dimmed" mb="sm">
                {t(
                  'metabolic.factors.subtitle',
                  'Ordered from the factor that raises your risk the most to the ones that are in range.'
                )}
              </Text>
              {result.factors.length === 0 ? (
                <Text size="sm" c="dimmed">
                  {t(
                    'metabolic.factors.empty',
                    'There is no data to analyse yet.'
                  )}
                </Text>
              ) : (
                <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
                  {result.factors.map(f => (
                    <FactorCard
                      key={f.key}
                      factor={f}
                      indicators={result.indicators}
                      locale={locale}
                    />
                  ))}
                </SimpleGrid>
              )}
            </div>

            <div>
              <Title order={3}>
                {t('metabolic.indices.title', 'Metabolic indices')}
              </Title>
              <Text size="sm" c="dimmed" mb="sm">
                {t(
                  'metabolic.indices.subtitle',
                  'Calculated automatically. Lab indices only combine values from the same sample.'
                )}
              </Text>
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
                {INDEX_KEYS.map(key => (
                  <IndexCard
                    key={key}
                    indexKey={key}
                    indicator={result.indicators[key]}
                    locale={locale}
                    formatDate={formatDate}
                  />
                ))}
              </SimpleGrid>
            </div>

            <ScoreTrend assessments={assessments} formatDate={formatDate} />

            {result.warnings?.length > 0 && (
              <Alert color="yellow">
                {result.warnings.map((w, i) => (
                  <Text size="sm" key={i}>
                    {t(
                      'metabolic.warnings.unknownUnit',
                      '{{variable}}: unit "{{unit}}" not recognised, value not used',
                      {
                        variable: t(
                          `metabolic.indicators.${w.variable}`,
                          w.variable
                        ),
                        unit: w.unit || '—',
                      }
                    )}
                  </Text>
                ))}
              </Alert>
            )}
          </>
        )}
      </Stack>
    </Container>
  );
};

export default MetabolicRisk;
