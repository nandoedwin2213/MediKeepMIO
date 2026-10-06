import { useCallback, useEffect, useMemo, useState } from 'react';
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
  ScrollArea,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core';
import {
  IconArrowDownRight,
  IconArrowRight,
  IconArrowUpRight,
  IconTarget,
} from '@tabler/icons-react';
import {
  CartesianGrid,
  Line,
  LineChart,
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
import { LevelScale, ScoreHero, fmt } from './MetabolicRisk';

const KEY_INDICATORS = [
  'homa_ir',
  'tyg',
  'bmi',
  'waist',
  'hba1c',
  'triglycerides',
  'blood_pressure',
];

const CHART_KEYS = [
  'score',
  'weight',
  'waist',
  'bmi',
  'homa_ir',
  'tyg',
  'hba1c',
  'glucose',
  'triglycerides',
  'systolic',
];

const DIRECTION_COLORS = { improved: 'teal', worsened: 'red', same: 'gray' };

function directionIcon(row) {
  if (typeof row.delta === 'number' && row.delta !== 0)
    return row.delta > 0 ? IconArrowUpRight : IconArrowDownRight;
  if (row.direction === 'improved') return IconArrowDownRight;
  if (row.direction === 'worsened') return IconArrowUpRight;
  return IconArrowRight;
}

function signed(value, locale) {
  if (value === null || value === undefined) return '';
  const text = fmt(Math.abs(value), locale);
  return value > 0 ? `+${text}` : value < 0 ? `−${text}` : text;
}

function KeyIndicatorCard({ indicatorKey, indicators, locale }) {
  const { t } = useTranslation('medical');
  const indicator = indicators?.[indicatorKey];
  return (
    <Card withBorder radius="lg" padding="md" className="silho-ir-metric">
      <Group justify="space-between" align="flex-start" gap={4} wrap="nowrap">
        <Text fw={700} size="sm">
          {t(`metabolic.indicators.${indicatorKey}`, indicatorKey)}
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
        <Text className="silho-ir-value" fw={700} size="26px" mt={4}>
          {fmt(indicator.value, locale)}
          {indicator.unit && (
            <Text span size="xs" c="dimmed" fw={500}>
              {' '}
              {indicator.unit}
            </Text>
          )}
        </Text>
      ) : (
        <Text size="sm" c="dimmed" mt={6}>
          {t('metabolic.health.noValue', 'No measurement yet')}
        </Text>
      )}
      <Text size="xs" mt={6}>
        {t(`metabolic.explain.${indicatorKey}`, '')}
      </Text>
      {indicatorKey === 'blood_pressure' ? (
        ['systolic', 'diastolic'].map(side =>
          indicators?.[side] ? (
            <Box key={side}>
              <Text size="xs" fw={600} c="dimmed" mt="xs">
                {t(`metabolic.indicators.${side}`, side)}
              </Text>
              <LevelScale
                bands={indicators[side].bands}
                level={indicators[side].level}
                locale={locale}
              />
            </Box>
          ) : null
        )
      ) : (
        <LevelScale
          bands={indicator?.bands}
          level={indicator?.level}
          locale={locale}
        />
      )}
    </Card>
  );
}

function ChangeRow({ row, locale }) {
  const { t } = useTranslation('medical');
  const color = DIRECTION_COLORS[row.direction] || 'gray';
  const Icon = directionIcon(row);
  const hasValues =
    row.from !== null &&
    row.from !== undefined &&
    row.to !== null &&
    row.to !== undefined;
  return (
    <Group gap="sm" wrap="nowrap" align="center">
      <ThemeIcon size="md" radius="xl" variant="light" color={color}>
        <Icon size={16} />
      </ThemeIcon>
      <Box style={{ flex: 1, minWidth: 0 }}>
        <Text size="sm" fw={600}>
          {t(`metabolic.indicators.${row.key}`, row.key)}
        </Text>
        <Text size="xs" c="dimmed">
          {hasValues
            ? `${fmt(row.from, locale)} → ${fmt(row.to, locale)}${row.unit ? ` ${row.unit}` : ''}`
            : `${t(`insulinResistance.levels.${row.from_level}`, row.from_level)} → ${t(`insulinResistance.levels.${row.to_level}`, row.to_level)}`}
        </Text>
      </Box>
      <Stack gap={0} align="flex-end">
        {hasValues && row.delta !== null && row.delta !== undefined && (
          <Text size="sm" fw={700} c={color}>
            {signed(row.delta, locale)}
          </Text>
        )}
        <Text size="xs" c={color}>
          {t(`metabolic.health.direction.${row.direction}`, row.direction)}
        </Text>
      </Stack>
    </Group>
  );
}

function WhyChangedCard({ change, formatDate, locale }) {
  const { t } = useTranslation('medical');
  let headline = t(
    'metabolic.health.why.none',
    'There is no previous evaluation to compare yet.'
  );
  let color = 'gray';
  if (
    change &&
    change.score_delta !== null &&
    change.score_delta !== undefined
  ) {
    if (change.score_delta > 0) {
      headline = t(
        'metabolic.health.why.improved',
        'Your score improved {{delta}} points',
        { delta: change.score_delta }
      );
      color = 'teal';
    } else if (change.score_delta < 0) {
      headline = t(
        'metabolic.health.why.worsened',
        'Your score dropped {{delta}} points',
        { delta: Math.abs(change.score_delta) }
      );
      color = 'red';
    } else {
      headline = t('metabolic.health.why.same', 'Your score stayed the same');
    }
  }
  return (
    <Card withBorder radius="lg" padding="lg" className="silho-ir-metric">
      <Text fw={700}>
        {t('metabolic.health.why.title', 'Why did your risk change?')}
      </Text>
      <Text fw={800} size="lg" c={color} mt={6}>
        {headline}
      </Text>
      {change && (
        <>
          <Text size="xs" c="dimmed">
            {t('metabolic.health.why.period', 'From {{from}} to {{to}}', {
              from: change.from_date ? formatDate(change.from_date) : '–',
              to: change.to_date ? formatDate(change.to_date) : '–',
            })}
          </Text>
          {change.drivers.length > 0 ? (
            <Stack gap="xs" mt="sm">
              <Text size="sm" fw={600}>
                {t('metabolic.health.why.mainly', 'Mainly because of:')}
              </Text>
              {change.drivers.map(row => (
                <ChangeRow key={row.key} row={row} locale={locale} />
              ))}
            </Stack>
          ) : (
            <Text size="sm" c="dimmed" mt="sm">
              {t(
                'metabolic.health.why.noDrivers',
                'No score factor changed level.'
              )}
            </Text>
          )}
          {change.other_changes.length > 0 && (
            <Stack gap="xs" mt="md">
              <Text size="sm" fw={600}>
                {t('metabolic.health.why.others', 'Other changes:')}
              </Text>
              {change.other_changes.map(row => (
                <ChangeRow key={row.key} row={row} locale={locale} />
              ))}
            </Stack>
          )}
        </>
      )}
    </Card>
  );
}

function ProgressCard({ windows, formatDate, locale }) {
  const { t } = useTranslation('medical');
  const options = windows.filter(w => w.key !== 'baseline');
  const firstAvailable = [...options].reverse().find(w => w.snapshot)?.key;
  const [selected, setSelected] = useState(firstAvailable || 'latest');
  const current = options.find(w => w.key === selected);
  const baseline = windows.find(w => w.key === 'baseline')?.snapshot;
  const rows = current?.comparison || [];
  return (
    <Card withBorder radius="lg" padding="lg" className="silho-ir-metric">
      <Text fw={700}>
        {t('metabolic.health.progress.title', 'Your progress')}
      </Text>
      <Text size="sm" c="dimmed" mb="xs">
        {t('metabolic.health.progress.compare', 'Compare the start with:')}
      </Text>
      <ScrollArea type="auto" offsetScrollbars>
        <SegmentedControl
          size="xs"
          value={selected}
          onChange={setSelected}
          data={options.map(w => ({
            value: w.key,
            label: t(`metabolic.health.windows.${w.key}`, w.key),
            disabled: !w.snapshot,
          }))}
        />
      </ScrollArea>
      {baseline && current?.snapshot && (
        <Text size="xs" c="dimmed" mt="xs">
          {t('metabolic.health.why.period', 'From {{from}} to {{to}}', {
            from: formatDate(baseline.data_date),
            to: formatDate(current.snapshot.data_date),
          })}
          {current.snapshot.score !== null &&
            baseline.score !== null &&
            ` · ${t('metabolic.scoreShort', 'Score')} ${fmt(baseline.score, locale)} → ${fmt(current.snapshot.score, locale)}`}
        </Text>
      )}
      {rows.length === 0 ? (
        <Text size="sm" c="dimmed" mt="sm">
          {current?.snapshot
            ? t(
                'metabolic.health.progress.empty',
                'Your progress appears once you have measurements on two different dates.'
              )
            : t(
                'metabolic.health.progress.notReached',
                'There are no measurements for this period yet.'
              )}
        </Text>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm" mt="sm">
          {rows.map(row => (
            <ChangeRow key={row.key} row={row} locale={locale} />
          ))}
        </SimpleGrid>
      )}
    </Card>
  );
}

function EvolutionCard({ timeline, formatDate, locale }) {
  const { t } = useTranslation('medical');
  const available = CHART_KEYS.filter(key =>
    key === 'score'
      ? timeline.some(s => s.score !== null && s.score !== undefined)
      : timeline.some(s => s.values?.[key])
  );
  const [selected, setSelected] = useState(available[0] || 'score');
  const data = timeline
    .map(s => ({
      date: s.data_date,
      value: selected === 'score' ? s.score : s.values?.[selected]?.value,
    }))
    .filter(p => p.value !== null && p.value !== undefined);
  const unit =
    selected === 'score'
      ? ''
      : timeline.find(s => s.values?.[selected])?.values[selected].unit || '';
  return (
    <Card withBorder radius="lg" padding="lg" className="silho-ir-chart">
      <Text fw={700} mb="xs">
        {t('metabolic.health.chart.title', 'My evolution')}
      </Text>
      {available.length > 0 && (
        <ScrollArea type="auto" offsetScrollbars>
          <SegmentedControl
            size="xs"
            value={selected}
            onChange={setSelected}
            data={available.map(key => ({
              value: key,
              label:
                key === 'score'
                  ? t('metabolic.scoreShort', 'Score')
                  : t(`metabolic.indicators.${key}`, key),
            }))}
          />
        </ScrollArea>
      )}
      {data.length < 2 ? (
        <Text size="sm" c="dimmed" mt="sm">
          {t(
            'metabolic.health.chart.empty',
            'The chart appears with two or more measurements.'
          )}
        </Text>
      ) : (
        <Box h={240} mt="sm">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 12, left: -8 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="date"
                tickFormatter={d => formatDate(d)}
                tick={{ fontSize: 11, fill: 'currentColor' }}
              />
              <YAxis
                domain={selected === 'score' ? [0, 100] : ['auto', 'auto']}
                tick={{ fontSize: 11, fill: 'currentColor' }}
              />
              <Tooltip
                labelFormatter={d => formatDate(d)}
                formatter={v => [`${fmt(v, locale)} ${unit}`.trim()]}
                contentStyle={{ color: '#102040' }}
              />
              <Line
                type="monotone"
                dataKey="value"
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

const MetabolicHealth = () => {
  const { t, i18n } = useTranslation('medical');
  const navigate = useNavigate();
  const { patient } = usePatientWithStaticData();
  const patientId = patient?.patient?.id;
  const { formatDate } = useDateFormat();
  const locale = i18n.language;

  const [evaluation, setEvaluation] = useState(null);
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(
    async signal => {
      if (!patientId) return;
      setLoading(true);
      setError(null);
      try {
        const evalResponse = await metabolicApi.evaluate(patientId, signal);
        const progressResponse = await metabolicApi
          .getProgress(patientId, signal)
          .catch(() => null);
        if (signal?.aborted) return;
        setEvaluation(evalResponse);
        setProgress(progressResponse);
      } catch (err) {
        if (signal?.aborted) return;
        logger.error('metabolic_health_load_failed', {
          component: 'MetabolicHealth',
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
  const timeline = useMemo(() => progress?.timeline || [], [progress]);

  return (
    <Container size="xl" py="md" className="silho-ir-page">
      <PageHeader
        title={t('metabolic.health.title', 'My metabolic health')}
        icon="💚"
      />
      <Stack gap="lg" mt="md">
        <Text c="dimmed">
          {t(
            'metabolic.health.subtitle',
            'How am I? What is raising my risk? What should I improve? Am I improving?'
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
              <WhyChangedCard
                change={progress?.change}
                formatDate={formatDate}
                locale={locale}
              />
            </SimpleGrid>
            <Group gap="sm">
              <Button
                variant="light"
                leftSection={<IconTarget size={16} />}
                onClick={() => navigate('/metabolic-risk')}
              >
                {t(
                  'metabolic.factors.title',
                  'What is affecting your metabolism?'
                )}
              </Button>
            </Group>
            <Box>
              <Title order={3}>
                {t('metabolic.health.keyTitle', 'My indicators')}
              </Title>
              <Text size="sm" c="dimmed" mb="sm">
                {t(
                  'metabolic.health.keySubtitle',
                  'What each value means and which level you are in.'
                )}
              </Text>
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
                {KEY_INDICATORS.map(key => (
                  <KeyIndicatorCard
                    key={key}
                    indicatorKey={key}
                    indicators={result.indicators}
                    locale={locale}
                  />
                ))}
              </SimpleGrid>
            </Box>
            {progress && (
              <>
                <ProgressCard
                  key={progress.windows.length}
                  windows={progress.windows}
                  formatDate={formatDate}
                  locale={locale}
                />
                <EvolutionCard
                  timeline={timeline}
                  formatDate={formatDate}
                  locale={locale}
                />
              </>
            )}
          </>
        )}
      </Stack>
    </Container>
  );
};

export default MetabolicHealth;
