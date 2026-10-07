import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Checkbox,
  Container,
  Divider,
  Group,
  Loader,
  RingProgress,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconBarbell,
  IconCalendarWeek,
  IconChevronLeft,
  IconChevronRight,
  IconWalk,
  IconRuler,
  IconScale,
  IconToolsKitchen2,
} from '@tabler/icons-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
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

const MEALS = ['breakfast', 'lunch', 'dinner', 'snack'];
const WEEKLY_ICONS = { weight: IconScale, waist: IconRuler };

const addDays = (iso, days) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};
const todayIso = () => {
  const d = new Date();
  const offset = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - offset).toISOString().slice(0, 10);
};

export const adherenceColor = percent => {
  if (percent == null) return 'gray';
  if (percent >= 80) return 'green';
  if (percent >= 60) return 'yellow';
  if (percent >= 40) return 'orange';
  return 'red';
};

function useWeekT() {
  const { t, i18n } = useTranslation('medical');
  const w = (key, opts) => t(`metabolic.week.${key}`, opts);
  return { t, w, i18n };
}

function AdherenceHero({ week }) {
  const { w } = useWeekT();
  const { percent, done, expected } = week.adherence;
  const color = adherenceColor(percent);
  let headline = w('score.none');
  if (percent != null) {
    headline = w(week.is_current ? 'score.current' : 'score.past', {
      percent,
    });
  }
  return (
    <Card withBorder radius="lg" padding="lg" data-testid="adherence-hero">
      <Group wrap="nowrap" gap="lg" align="center">
        <RingProgress
          size={120}
          thickness={12}
          roundCaps
          sections={[{ value: percent || 0, color }]}
          label={
            <Center>
              <Text fw={800} size="xl" c={color}>
                {percent == null ? '–' : `${percent}%`}
              </Text>
            </Center>
          }
        />
        <Box style={{ minWidth: 0 }}>
          <Text size="xs" tt="uppercase" fw={700} c="dimmed">
            {w('score.label')}
          </Text>
          <Title order={3} mt={4}>
            {headline}
          </Title>
          {expected > 0 && (
            <Text size="sm" c="dimmed" mt={4}>
              {w('score.tasks', { done, expected })}
            </Text>
          )}
        </Box>
      </Group>
    </Card>
  );
}

function DayCard({ day, onToggle, saving }) {
  const { t, w, i18n } = useWeekT();
  const { formatDate } = useDateFormat();
  const mv = key => t(`metabolic.movement.${key}`);
  const numberFmt = new Intl.NumberFormat(i18n.language);
  const { aerobic, strength } = day;
  const meals = MEALS.filter(m => day.meals?.[m]);
  return (
    <Card
      withBorder
      radius="lg"
      padding="md"
      data-testid={`day-${day.date}`}
      style={
        day.is_today
          ? { borderColor: 'var(--mantine-color-blue-filled)', borderWidth: 2 }
          : undefined
      }
    >
      <Group justify="space-between" wrap="nowrap">
        <Box>
          <Text fw={700}>{w(`weekdays.${day.weekday}`)}</Text>
          <Text size="xs" c="dimmed">
            {formatDate(day.date)}
          </Text>
        </Box>
        {day.is_today && <Badge color="blue">{w('today')}</Badge>}
        {day.is_future && (
          <Badge color="gray" variant="light">
            {w('future')}
          </Badge>
        )}
      </Group>

      {meals.length > 0 && (
        <>
          <Divider my="sm" label={w('sections.meals')} labelPosition="left" />
          <Stack gap={6}>
            {meals.map(meal => {
              const recipe = day.meals[meal];
              return (
                <Group key={meal} gap="xs" wrap="nowrap" align="flex-start">
                  <ThemeIcon size="sm" variant="light" color="teal" mt={2}>
                    <IconToolsKitchen2 size={12} />
                  </ThemeIcon>
                  <Box style={{ minWidth: 0 }}>
                    <Text size="xs" c="dimmed">
                      {w(`meals.${meal}`)}
                    </Text>
                    <Anchor
                      component={Link}
                      to={`/metabolic-recipes?recipe=${recipe.id}`}
                      size="sm"
                    >
                      {recipe.name}
                    </Anchor>
                  </Box>
                </Group>
              );
            })}
          </Stack>
        </>
      )}

      {day.steps_target != null && (
        <>
          <Divider
            my="sm"
            label={w('sections.activity')}
            labelPosition="left"
          />
          <Stack gap={6}>
            {aerobic && (
              <Group gap="xs" wrap="nowrap" align="flex-start">
                <ThemeIcon size="sm" variant="light" color="orange" mt={2}>
                  <IconWalk size={12} />
                </ThemeIcon>
                <Text size="sm">
                  {w('aerobic', {
                    minutes: aerobic.minutes,
                    type: aerobic.type ? mv(`options.${aerobic.type}`) : '',
                    intensity: aerobic.intensity
                      ? mv(`intensity.${aerobic.intensity}`)
                      : '',
                  })}
                </Text>
              </Group>
            )}
            {strength && (
              <Group gap="xs" wrap="nowrap" align="flex-start">
                <ThemeIcon size="sm" variant="light" color="grape" mt={2}>
                  <IconBarbell size={12} />
                </ThemeIcon>
                <Box>
                  <Text size="sm">
                    {w('strength', {
                      sets: `${strength.sets_min}–${strength.sets_max}`,
                      reps: `${strength.reps_min}–${strength.reps_max}`,
                    })}
                  </Text>
                  {strength.exercises?.length > 0 && (
                    <Text size="xs" c="dimmed">
                      {strength.exercises
                        .map(e => mv(`options.${e}`))
                        .join(' · ')}
                    </Text>
                  )}
                </Box>
              </Group>
            )}
            {!aerobic && !strength && (
              <Text size="sm" c="dimmed">
                {w('rest')}
              </Text>
            )}
            {(day.mobility || day.balance) && (
              <Text size="xs" c="dimmed">
                {[
                  day.mobility &&
                    w('mobility', { minutes: day.mobility.minutes }),
                  day.balance && w('balance', { minutes: day.balance.minutes }),
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </Text>
            )}
            <Text size="sm" fw={600}>
              {w('steps', { steps: numberFmt.format(day.steps_target) })}
            </Text>
            {day.steps != null && (
              <Text
                size="xs"
                c={day.steps >= day.steps_target ? 'teal' : 'dimmed'}
              >
                {w('stepsTracked', { steps: numberFmt.format(day.steps) })}
              </Text>
            )}
            {day.walk_after_meals && (
              <Text size="xs" c="dimmed">
                {mv('fields.walkAfterMealsText')}
              </Text>
            )}
          </Stack>
        </>
      )}

      {day.items.length > 0 && (
        <>
          <Divider
            my="sm"
            label={w('sections.checklist')}
            labelPosition="left"
          />
          <Stack gap={8}>
            {day.items.map(({ item, done, source }) => (
              <Checkbox
                key={item}
                label={w(`items.${item}`)}
                description={
                  source === 'wearable' ? w('fromWearable') : undefined
                }
                checked={done}
                disabled={day.is_future || saving || source === 'wearable'}
                color="green"
                onChange={e =>
                  onToggle(day.date, item, e.currentTarget.checked)
                }
              />
            ))}
          </Stack>
        </>
      )}
    </Card>
  );
}

function WeeklyMeasurements({ week, onToggle, saving }) {
  const { w } = useWeekT();
  const today = todayIso();
  const startsInFuture = week.start > today;
  const logDate = week.end < today ? week.end : today;
  return (
    <Card withBorder radius="lg" padding="md">
      <Group justify="space-between" mb="sm">
        <Text fw={700}>{w('weekly.title')}</Text>
        <Anchor component={Link} to="/vitals" size="sm">
          {w('goVitals')}
        </Anchor>
      </Group>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        {week.weekly.map(({ item, done, source }) => {
          const Icon = WEEKLY_ICONS[item];
          return (
            <Group key={item} gap="sm" wrap="nowrap">
              <ThemeIcon variant="light" color={done ? 'green' : 'gray'}>
                <Icon size={16} />
              </ThemeIcon>
              <Box>
                <Checkbox
                  label={w(`items.${item}`)}
                  checked={done}
                  color="green"
                  disabled={startsInFuture || saving || source === 'vitals'}
                  onChange={e =>
                    onToggle(logDate, item, e.currentTarget.checked)
                  }
                />
                {source === 'vitals' && (
                  <Text size="xs" c="dimmed" ml={30}>
                    {w('fromVitals')}
                  </Text>
                )}
              </Box>
            </Group>
          );
        })}
      </SimpleGrid>
    </Card>
  );
}

function History({ weeks }) {
  const { w } = useWeekT();
  const { formatDate } = useDateFormat();
  const first = (weeks || []).findIndex(x => x.percent != null);
  const data = (first < 0 ? [] : weeks.slice(first)).map(x => ({
    label: formatDate(x.start),
    percent: x.percent,
  }));
  if (data.length === 0) return null;
  return (
    <Card withBorder radius="lg" padding="md">
      <Text fw={700} mb="sm">
        {w('history.title')}
      </Text>
      <Box h={220}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
            <Tooltip formatter={v => [`${v}%`, w('score.label')]} />
            <Bar
              dataKey="percent"
              fill="var(--mantine-color-teal-filled)"
              radius={[6, 6, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </Box>
    </Card>
  );
}

export default function MetabolicWeek() {
  const { t, w } = useWeekT();
  const { formatDate } = useDateFormat();
  const { patient } = usePatientWithStaticData();
  const patientId = patient?.patient?.id;
  const [start, setStart] = useState(null);
  const [week, setWeek] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(
    async (signal, quiet = false) => {
      if (!patientId) return;
      if (!quiet) setLoading(true);
      setError(null);
      try {
        const [weekData, historyData] = await Promise.all([
          metabolicApi.getWeek(patientId, start ? { start } : {}, signal),
          metabolicApi.getAdherenceHistory(patientId, { weeks: 8 }, signal),
        ]);
        if (signal?.aborted) return;
        setWeek(weekData);
        setHistory(historyData?.weeks || []);
      } catch (err) {
        if (signal?.aborted || err?.name === 'AbortError') return;
        logger.error('metabolic_week_load_error', err?.message, {
          component: 'MetabolicWeek',
        });
        setError(w('loadError'));
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [patientId, start]
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const toggle = async (date, item, done) => {
    setSaving(true);
    setWeek(prev =>
      prev
        ? {
            ...prev,
            days: prev.days.map(d =>
              d.date === date
                ? {
                    ...d,
                    items: d.items.map(i =>
                      i.item === item ? { ...i, done } : i
                    ),
                  }
                : d
            ),
            weekly: prev.weekly.map(x =>
              x.item === item ? { ...x, done, source: done ? 'log' : null } : x
            ),
          }
        : prev
    );
    try {
      await metabolicApi.logAdherence(patientId, {
        log_date: date,
        item,
        done,
      });
    } catch (err) {
      logger.error('metabolic_week_save_error', err?.message, {
        component: 'MetabolicWeek',
      });
      notifications.show({ color: 'red', message: w('saveError') });
    } finally {
      await load(undefined, true);
      setSaving(false);
    }
  };

  const hasPlans = week && (week.plans?.exercise || week.plans?.nutrition);

  return (
    <Container size="lg" py="md" className="silho-ir-page">
      <PageHeader title={w('title')} icon="📅" />
      <Text c="dimmed" mt="md">
        {w('subtitle')}
      </Text>
      {!patientId ? (
        <Alert color="blue" mt="md">
          {t('metabolic.selectPatient')}
        </Alert>
      ) : (
        <Stack gap="lg" mt="lg">
          <Group justify="space-between" wrap="wrap">
            <Group gap="xs" wrap="nowrap">
              <ActionIcon
                variant="light"
                size="lg"
                aria-label={w('prev')}
                onClick={() => week && setStart(addDays(week.start, -7))}
              >
                <IconChevronLeft size={18} />
              </ActionIcon>
              <Group gap={6} wrap="nowrap">
                <IconCalendarWeek size={18} />
                <Text fw={600} data-testid="week-range">
                  {week
                    ? w('range', {
                        start: formatDate(week.start),
                        end: formatDate(week.end),
                      })
                    : ''}
                </Text>
              </Group>
              <ActionIcon
                variant="light"
                size="lg"
                aria-label={w('next')}
                onClick={() => week && setStart(addDays(week.start, 7))}
              >
                <IconChevronRight size={18} />
              </ActionIcon>
            </Group>
            {week && !week.is_current && (
              <Button variant="subtle" onClick={() => setStart(null)}>
                {w('thisWeek')}
              </Button>
            )}
          </Group>

          {error && <Alert color="red">{error}</Alert>}
          {loading && !week && (
            <Center py="xl">
              <Loader />
            </Center>
          )}

          {week && !hasPlans && (
            <Alert color="blue" variant="light">
              <Text size="sm">{w('noPlans')}</Text>
              <Group gap="md" mt="xs">
                <Anchor component={Link} to="/metabolic-movement" size="sm">
                  {w('goMovement')}
                </Anchor>
                <Anchor component={Link} to="/metabolic-nutrition" size="sm">
                  {w('goNutrition')}
                </Anchor>
              </Group>
            </Alert>
          )}

          {week && hasPlans && (
            <>
              <AdherenceHero week={week} />
              {week.weekly.length > 0 && (
                <WeeklyMeasurements
                  week={week}
                  onToggle={toggle}
                  saving={saving}
                />
              )}
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
                {week.days.map(day => (
                  <DayCard
                    key={day.date}
                    day={day}
                    onToggle={toggle}
                    saving={saving}
                  />
                ))}
              </SimpleGrid>
              <History weeks={history} />
            </>
          )}

          <Alert color="gray" variant="light">
            {w('disclaimer')}
          </Alert>
        </Stack>
      )}
    </Container>
  );
}
