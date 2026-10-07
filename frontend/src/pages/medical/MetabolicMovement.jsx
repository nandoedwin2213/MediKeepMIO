import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Checkbox,
  Collapse,
  Container,
  Group,
  List,
  Loader,
  MultiSelect,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconActivityHeartbeat,
  IconAlertTriangle,
  IconBarbell,
  IconCheck,
  IconCopy,
  IconDeviceFloppy,
  IconPlus,
  IconRun,
  IconSparkles,
  IconStretching,
  IconTrash,
  IconTrendingUp,
  IconWalk,
  IconYoga,
} from '@tabler/icons-react';
import { PageHeader } from '../../components';
import { useAuth } from '../../contexts/AuthContext';
import { usePatientWithStaticData } from '../../hooks/useGlobalData';
import { useDateFormat } from '../../hooks/useDateFormat';
import metabolicApi from '../../services/api/metabolicApi';
import logger from '../../services/logger';
import { fmt, formatBand } from './MetabolicRisk';

const PRO_ROLES = [
  'admin',
  'administrator',
  'doctor',
  'nurse',
  'staff',
  'physio',
  'nutritionist',
];

const TESTS = [
  { key: 'sit_to_stand', field: 'sit_to_stand_30s', max: 60, step: 1 },
  { key: 'grip', field: 'grip_strength_kg', max: 100, step: 0.5, decimals: 1 },
  {
    key: 'gait_speed',
    field: 'gait_speed_m_s',
    max: 3,
    step: 0.05,
    decimals: 2,
  },
  { key: 'walk_test', field: 'walk_test_m', max: 1200, step: 5 },
  { key: 'rpe', field: 'rpe', max: 10, step: 1 },
];

const UNITS = {
  sit_to_stand: 'reps',
  grip: 'kg',
  gait_speed: 'm/s',
  walk_test: 'm',
  rpe: '/10',
};

const LEVEL_COLORS = {
  low: 'red',
  reduced: 'yellow',
  adequate: 'teal',
  light: 'teal',
  moderate: 'yellow',
  vigorous: 'orange',
  very_hard: 'red',
};

const OPTIONS = {
  types: [
    'brisk_walking',
    'walking_flat',
    'cycling',
    'stationary_bike',
    'aquatic',
    'dancing',
    'intervals',
  ],
  muscle_groups: ['lower_limbs', 'upper_limbs', 'core', 'grip'],
  strength_exercises: [
    'sit_to_stand',
    'wall_pushups',
    'band_rows',
    'glute_bridge',
    'calf_raises',
    'step_ups',
    'grip_squeeze',
  ],
  balance_exercises: ['single_leg_stance', 'tandem_walk', 'sit_to_stand_slow'],
  focus: ['hips', 'spine', 'shoulders'],
};

const INTENSITIES = [
  'light',
  'light_moderate',
  'moderate',
  'moderate_vigorous',
  'vigorous',
];

const today = () => new Date().toISOString().slice(0, 10);

function useMovementT() {
  const { t, i18n } = useTranslation('medical');
  const m = (key, opts) => t(`metabolic.movement.${key}`, opts);
  const opt = value => t(`metabolic.movement.options.${value}`, value);
  return { t, m, opt, locale: i18n.language };
}

function unitLabel(m, key) {
  return key === 'sit_to_stand' ? m('units.reps') : UNITS[key];
}

function FunctionalScale({ indicator, unit }) {
  const { m, locale } = useMovementT();
  const bands = indicator?.bands || [];
  if (!bands.length) {
    return (
      <Text size="xs" c="dimmed" mt="xs">
        {m('functional.noReference')}
      </Text>
    );
  }
  return (
    <Stack gap={4} mt="sm" className="silho-ir-ranges">
      <div className="silho-ir-scale">
        {bands.map(b => (
          <span
            key={b.level}
            className="silho-ir-scale-seg"
            data-active={b.level === indicator.level || undefined}
            style={{
              background: `var(--mantine-color-${LEVEL_COLORS[b.level]}-6)`,
            }}
          />
        ))}
      </div>
      {bands.map(b => {
        const active = b.level === indicator.level;
        return (
          <Group
            key={b.level}
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
                {m(`levels.${b.level}`)}
              </Text>
            </Group>
            <Text
              size="xs"
              fw={active ? 700 : 400}
              c={active ? undefined : 'dimmed'}
              style={{ whiteSpace: 'nowrap' }}
            >
              {formatBand(b, locale)} {unit}
            </Text>
          </Group>
        );
      })}
    </Stack>
  );
}

function TestCard({ testKey, indicator }) {
  const { m, locale } = useMovementT();
  const color = LEVEL_COLORS[indicator.level] || 'gray';
  return (
    <Card withBorder radius="md" padding="md">
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Text fw={600}>{m(`tests.${testKey}.name`)}</Text>
        {indicator.level && (
          <Badge color={color} variant="light" style={{ flexShrink: 0 }}>
            {m(`levels.${indicator.level}`)}
          </Badge>
        )}
      </Group>
      <Text fw={800} size="28px" mt={4} className="silho-ir-value">
        {fmt(indicator.value, locale)}{' '}
        <Text span size="sm" c="dimmed" fw={500}>
          {unitLabel(m, testKey)}
        </Text>
      </Text>
      {testKey === 'walk_test' && indicator.percent_predicted != null && (
        <Text size="sm" c="dimmed">
          {m('functional.percentPredicted', {
            pct: indicator.percent_predicted,
            predicted: fmt(indicator.predicted_m, locale),
          })}
        </Text>
      )}
      <Text size="sm" c="dimmed" mt={4}>
        {m(`tests.${testKey}.help`)}
      </Text>
      <FunctionalScale
        indicator={indicator}
        unit={testKey === 'walk_test' ? '%' : unitLabel(m, testKey)}
      />
    </Card>
  );
}

const emptyForm = () => ({
  assessed_at: today(),
  notes: '',
  ...Object.fromEntries(TESTS.map(test => [test.field, ''])),
});

function FunctionalSection({ patientId, formatDate }) {
  const { m, locale } = useMovementT();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const load = useCallback(
    async signal => {
      setLoading(true);
      setError(false);
      try {
        const res = await metabolicApi.getFunctional(patientId, signal);
        setItems(res?.items || []);
      } catch (err) {
        if (signal?.aborted) return;
        logger.error('functional_load_failed', { error: err?.message });
        setError(true);
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [patientId]
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const hasValue = TESTS.some(test => form[test.field] !== '');

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        assessed_at: `${form.assessed_at}T12:00:00`,
        notes: form.notes || null,
      };
      TESTS.forEach(test => {
        payload[test.field] = form[test.field] === '' ? null : form[test.field];
      });
      await metabolicApi.createFunctional(patientId, payload);
      notifications.show({ color: 'teal', message: m('functional.saved') });
      setForm(emptyForm());
      setOpen(false);
      load();
    } catch (err) {
      logger.error('functional_save_failed', { error: err?.message });
      notifications.show({ color: 'red', message: m('functional.saveError') });
    } finally {
      setSaving(false);
    }
  };

  const remove = async id => {
    try {
      await metabolicApi.deleteFunctional(patientId, id);
      notifications.show({ color: 'teal', message: m('functional.deleted') });
      load();
    } catch (err) {
      logger.error('functional_delete_failed', { error: err?.message });
      notifications.show({ color: 'red', message: m('error') });
    }
  };

  const latest = items[0];

  return (
    <Card withBorder radius="lg" padding="lg">
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Group gap="sm">
          <ThemeIcon variant="light" size="lg" radius="md">
            <IconActivityHeartbeat size={20} />
          </ThemeIcon>
          <div>
            <Title order={3}>{m('functional.title')}</Title>
            <Text size="sm" c="dimmed">
              {m('functional.subtitle')}
            </Text>
          </div>
        </Group>
        <Button
          leftSection={<IconPlus size={16} />}
          variant={open ? 'default' : 'filled'}
          onClick={() => setOpen(o => !o)}
        >
          {m('functional.add')}
        </Button>
      </Group>

      <Collapse in={open}>
        <Card withBorder radius="md" mt="md" padding="md">
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
            <TextInput
              type="date"
              label={m('functional.date')}
              value={form.assessed_at}
              max={today()}
              onChange={e =>
                setForm(f => ({ ...f, assessed_at: e.currentTarget.value }))
              }
            />
            {TESTS.map(test => (
              <NumberInput
                key={test.field}
                label={`${m(`tests.${test.key}.name`)} (${unitLabel(m, test.key)})`}
                description={m(`tests.${test.key}.how`)}
                min={0}
                max={test.max}
                step={test.step}
                decimalScale={test.decimals || 0}
                value={form[test.field]}
                onChange={v => setForm(f => ({ ...f, [test.field]: v }))}
              />
            ))}
          </SimpleGrid>
          <Textarea
            mt="sm"
            label={m('fields.notes')}
            autosize
            minRows={2}
            maxLength={2000}
            value={form.notes}
            onChange={e =>
              setForm(f => ({ ...f, notes: e.currentTarget.value }))
            }
          />
          <Group justify="flex-end" mt="md">
            {!hasValue && (
              <Text size="sm" c="dimmed">
                {m('functional.atLeastOne')}
              </Text>
            )}
            <Button
              leftSection={<IconDeviceFloppy size={16} />}
              loading={saving}
              disabled={!hasValue || !form.assessed_at}
              onClick={save}
            >
              {m('functional.save')}
            </Button>
          </Group>
        </Card>
      </Collapse>

      {loading ? (
        <Center py="lg">
          <Loader />
        </Center>
      ) : error ? (
        <Alert color="red" mt="md">
          {m('loadError')}
        </Alert>
      ) : !latest ? (
        <Text c="dimmed" mt="md">
          {m('functional.empty')}
        </Text>
      ) : (
        <>
          <Text size="sm" fw={600} mt="lg">
            {m('functional.latest', { date: formatDate(latest.assessed_at) })}
          </Text>
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} mt="xs">
            {TESTS.filter(test => latest.indicators?.[test.key]).map(test => (
              <TestCard
                key={test.key}
                testKey={test.key}
                indicator={latest.indicators[test.key]}
              />
            ))}
          </SimpleGrid>
          {latest.notes && (
            <Text size="sm" c="dimmed" mt="sm">
              {latest.notes}
            </Text>
          )}
          <Title order={5} mt="lg">
            {m('functional.history')}
          </Title>
          <Stack gap={6} mt="xs">
            {items.map(item => (
              <Group
                key={item.id}
                justify="space-between"
                wrap="nowrap"
                className="silho-mv-history"
              >
                <Group gap="xs" wrap="wrap">
                  <Text size="sm" fw={600} miw={90}>
                    {formatDate(item.assessed_at)}
                  </Text>
                  {TESTS.filter(test => item.indicators?.[test.key]).map(
                    test => {
                      const ind = item.indicators[test.key];
                      return (
                        <Badge
                          key={test.key}
                          variant="light"
                          color={LEVEL_COLORS[ind.level] || 'gray'}
                          tt="none"
                        >
                          {m(`tests.${test.key}.short`)}:{' '}
                          {fmt(ind.value, locale)} {unitLabel(m, test.key)}
                        </Badge>
                      );
                    }
                  )}
                </Group>
                <Button
                  size="xs"
                  variant="subtle"
                  color="red"
                  aria-label={m('functional.delete')}
                  onClick={() => remove(item.id)}
                >
                  <IconTrash size={16} />
                </Button>
              </Group>
            ))}
          </Stack>
        </>
      )}
    </Card>
  );
}

function SectionCard({ icon: Icon, color, title, children }) {
  return (
    <Card withBorder radius="md" padding="md">
      <Group gap="sm" mb="xs">
        <ThemeIcon variant="light" color={color} radius="md">
          <Icon size={18} />
        </ThemeIcon>
        <Text fw={700}>{title}</Text>
      </Group>
      {children}
    </Card>
  );
}

function Chips({ values }) {
  const { opt } = useMovementT();
  if (!values?.length) return null;
  return (
    <Group gap={6} mt="xs">
      {values.map(v => (
        <Badge key={v} variant="outline" tt="none">
          {opt(v)}
        </Badge>
      ))}
    </Group>
  );
}

function Notes({ text }) {
  return text ? (
    <Text size="sm" mt="xs" style={{ whiteSpace: 'pre-wrap' }}>
      {text}
    </Text>
  ) : null;
}

function Rationale({ keys }) {
  const { m } = useMovementT();
  if (!keys?.length) return null;
  return (
    <Card withBorder radius="md" padding="md">
      <Group gap="xs" mb="xs">
        <IconSparkles size={16} />
        <Text fw={600} size="sm">
          {m('plan.why')}
        </Text>
      </Group>
      <List size="sm" spacing={2}>
        {keys.map(key => (
          <List.Item key={key}>{m(`rationale.${key}`)}</List.Item>
        ))}
      </List>
    </Card>
  );
}

function PlanView({ plan, rationale }) {
  const { m } = useMovementT();
  const { aerobic, strength, mobility, balance, daily } = plan;
  return (
    <Stack gap="md">
      {plan.safety?.length > 0 && (
        <Alert
          color="yellow"
          icon={<IconAlertTriangle size={18} />}
          title={m('sections.safety')}
        >
          <List size="sm" spacing={4}>
            {plan.safety.map(key => (
              <List.Item key={key}>{m(`safety.${key}`)}</List.Item>
            ))}
          </List>
        </Alert>
      )}
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <SectionCard icon={IconRun} color="teal" title={m('sections.aerobic')}>
          <Text fw={600}>
            {m('fields.summaryDays', {
              days: aerobic.days_per_week,
              minutes: aerobic.minutes,
            })}
          </Text>
          <Text size="sm" c="dimmed">
            {m(`intensity.${aerobic.intensity}`)} ·{' '}
            {m('fields.rpeRange', {
              min: aerobic.rpe_min,
              max: aerobic.rpe_max,
            })}
          </Text>
          <Chips values={aerobic.types} />
          <Notes text={aerobic.notes} />
        </SectionCard>
        <SectionCard
          icon={IconBarbell}
          color="orange"
          title={m('sections.strength')}
        >
          <Text fw={600}>
            {m('fields.summaryStrength', {
              days: strength.days_per_week,
              sets: `${strength.sets_min}–${strength.sets_max}`,
              reps: `${strength.reps_min}–${strength.reps_max}`,
            })}
          </Text>
          <Text size="sm" c="dimmed">
            {m('fields.rpeRange', {
              min: strength.rpe_min,
              max: strength.rpe_max,
            })}
          </Text>
          <Chips values={strength.muscle_groups} />
          {strength.exercises?.length > 0 && (
            <List size="sm" mt="xs" spacing={2}>
              {strength.exercises.map(e => (
                <List.Item key={e}>
                  <OptionText value={e} />
                </List.Item>
              ))}
            </List>
          )}
          <Notes text={strength.notes} />
        </SectionCard>
        <SectionCard
          icon={IconStretching}
          color="grape"
          title={m('sections.mobility')}
        >
          <Text fw={600}>
            {m('fields.summaryDays', {
              days: mobility.days_per_week,
              minutes: mobility.minutes,
            })}
          </Text>
          <Chips values={mobility.focus} />
          <Notes text={mobility.notes} />
        </SectionCard>
        <SectionCard icon={IconYoga} color="blue" title={m('sections.balance')}>
          <Text fw={600}>
            {m('fields.summaryDays', {
              days: balance.days_per_week,
              minutes: balance.minutes,
            })}
          </Text>
          <Chips values={balance.exercises} />
          <Notes text={balance.notes} />
        </SectionCard>
      </SimpleGrid>
      <SectionCard icon={IconWalk} color="cyan" title={m('sections.daily')}>
        {daily.steps_target != null && (
          <Text fw={600}>
            {m('fields.summarySteps', {
              start: daily.steps_start ?? daily.steps_target,
              target: daily.steps_target,
            })}
          </Text>
        )}
        <List size="sm" mt="xs" spacing={4} icon={<IconCheck size={14} />}>
          {daily.walk_after_meals && (
            <List.Item>{m('fields.walkAfterMealsText')}</List.Item>
          )}
          {daily.break_sitting && (
            <List.Item>{m('fields.breakSittingText')}</List.Item>
          )}
        </List>
        <Notes text={daily.notes} />
      </SectionCard>
      {plan.progression?.length > 0 && (
        <SectionCard
          icon={IconTrendingUp}
          color="teal"
          title={m('sections.progression')}
        >
          <List size="sm" spacing={4}>
            {plan.progression.map(key => (
              <List.Item key={key}>{m(`progression.${key}`)}</List.Item>
            ))}
          </List>
        </SectionCard>
      )}
      <Rationale keys={rationale} />
    </Stack>
  );
}

function OptionText({ value }) {
  const { opt } = useMovementT();
  return opt(value);
}

function OptionSelect({ label, group, value, onChange }) {
  const { opt } = useMovementT();
  const known = OPTIONS[group];
  const data = [...known, ...value.filter(v => !known.includes(v))].map(v => ({
    value: v,
    label: opt(v),
  }));
  return (
    <MultiSelect
      label={label}
      data={data}
      value={value}
      onChange={onChange}
      clearable
    />
  );
}

function Num({ label, value, onChange, min = 0, max }) {
  return (
    <NumberInput
      label={label}
      value={value}
      min={min}
      max={max}
      allowDecimal={false}
      onChange={v => onChange(v === '' ? 0 : Number(v))}
    />
  );
}

function PlanEditor({ value, onChange }) {
  const { m } = useMovementT();
  const set = (section, key) => v =>
    onChange({ ...value, [section]: { ...value[section], [key]: v } });
  const notes = section => (
    <Textarea
      label={m('fields.notes')}
      autosize
      minRows={1}
      maxLength={1000}
      value={value[section].notes || ''}
      onChange={e => set(section, 'notes')(e.currentTarget.value || null)}
    />
  );
  const { aerobic, strength, mobility, balance, daily } = value;
  return (
    <Stack gap="md">
      <SectionCard icon={IconRun} color="teal" title={m('sections.aerobic')}>
        <SimpleGrid cols={{ base: 2, sm: 3, md: 5 }}>
          <Num
            label={m('fields.days')}
            max={7}
            value={aerobic.days_per_week}
            onChange={set('aerobic', 'days_per_week')}
          />
          <Num
            label={m('fields.minutes')}
            max={180}
            value={aerobic.minutes}
            onChange={set('aerobic', 'minutes')}
          />
          <Select
            label={m('fields.intensity')}
            data={INTENSITIES.map(v => ({
              value: v,
              label: m(`intensity.${v}`),
            }))}
            value={aerobic.intensity}
            allowDeselect={false}
            onChange={set('aerobic', 'intensity')}
          />
          <Num
            label={m('fields.rpeMin')}
            max={10}
            value={aerobic.rpe_min}
            onChange={set('aerobic', 'rpe_min')}
          />
          <Num
            label={m('fields.rpeMax')}
            max={10}
            value={aerobic.rpe_max}
            onChange={set('aerobic', 'rpe_max')}
          />
        </SimpleGrid>
        <Stack gap="xs" mt="xs">
          <OptionSelect
            label={m('fields.types')}
            group="types"
            value={aerobic.types}
            onChange={set('aerobic', 'types')}
          />
          {notes('aerobic')}
        </Stack>
      </SectionCard>
      <SectionCard
        icon={IconBarbell}
        color="orange"
        title={m('sections.strength')}
      >
        <SimpleGrid cols={{ base: 2, sm: 4, md: 7 }}>
          <Num
            label={m('fields.days')}
            max={7}
            value={strength.days_per_week}
            onChange={set('strength', 'days_per_week')}
          />
          <Num
            label={m('fields.setsMin')}
            max={10}
            value={strength.sets_min}
            onChange={set('strength', 'sets_min')}
          />
          <Num
            label={m('fields.setsMax')}
            max={10}
            value={strength.sets_max}
            onChange={set('strength', 'sets_max')}
          />
          <Num
            label={m('fields.repsMin')}
            max={50}
            value={strength.reps_min}
            onChange={set('strength', 'reps_min')}
          />
          <Num
            label={m('fields.repsMax')}
            max={50}
            value={strength.reps_max}
            onChange={set('strength', 'reps_max')}
          />
          <Num
            label={m('fields.rpeMin')}
            max={10}
            value={strength.rpe_min}
            onChange={set('strength', 'rpe_min')}
          />
          <Num
            label={m('fields.rpeMax')}
            max={10}
            value={strength.rpe_max}
            onChange={set('strength', 'rpe_max')}
          />
        </SimpleGrid>
        <Stack gap="xs" mt="xs">
          <OptionSelect
            label={m('fields.muscleGroups')}
            group="muscle_groups"
            value={strength.muscle_groups}
            onChange={set('strength', 'muscle_groups')}
          />
          <OptionSelect
            label={m('fields.exercises')}
            group="strength_exercises"
            value={strength.exercises}
            onChange={set('strength', 'exercises')}
          />
          {notes('strength')}
        </Stack>
      </SectionCard>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <SectionCard
          icon={IconStretching}
          color="grape"
          title={m('sections.mobility')}
        >
          <SimpleGrid cols={2}>
            <Num
              label={m('fields.days')}
              max={7}
              value={mobility.days_per_week}
              onChange={set('mobility', 'days_per_week')}
            />
            <Num
              label={m('fields.minutes')}
              max={120}
              value={mobility.minutes}
              onChange={set('mobility', 'minutes')}
            />
          </SimpleGrid>
          <Stack gap="xs" mt="xs">
            <OptionSelect
              label={m('fields.focus')}
              group="focus"
              value={mobility.focus}
              onChange={set('mobility', 'focus')}
            />
            {notes('mobility')}
          </Stack>
        </SectionCard>
        <SectionCard icon={IconYoga} color="blue" title={m('sections.balance')}>
          <SimpleGrid cols={2}>
            <Num
              label={m('fields.days')}
              max={7}
              value={balance.days_per_week}
              onChange={set('balance', 'days_per_week')}
            />
            <Num
              label={m('fields.minutes')}
              max={120}
              value={balance.minutes}
              onChange={set('balance', 'minutes')}
            />
          </SimpleGrid>
          <Stack gap="xs" mt="xs">
            <OptionSelect
              label={m('fields.exercises')}
              group="balance_exercises"
              value={balance.exercises}
              onChange={set('balance', 'exercises')}
            />
            {notes('balance')}
          </Stack>
        </SectionCard>
      </SimpleGrid>
      <SectionCard icon={IconWalk} color="cyan" title={m('sections.daily')}>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Num
            label={m('fields.stepsStart')}
            max={40000}
            value={daily.steps_start ?? 0}
            onChange={set('daily', 'steps_start')}
          />
          <Num
            label={m('fields.stepsTarget')}
            max={40000}
            value={daily.steps_target ?? 0}
            onChange={set('daily', 'steps_target')}
          />
        </SimpleGrid>
        <Stack gap="xs" mt="sm">
          <Checkbox
            label={m('fields.walkAfterMealsText')}
            checked={daily.walk_after_meals}
            onChange={e =>
              set('daily', 'walk_after_meals')(e.currentTarget.checked)
            }
          />
          <Checkbox
            label={m('fields.breakSittingText')}
            checked={daily.break_sitting}
            onChange={e =>
              set('daily', 'break_sitting')(e.currentTarget.checked)
            }
          />
          {notes('daily')}
        </Stack>
      </SectionCard>
    </Stack>
  );
}

const STATUS_COLORS = { draft: 'yellow', approved: 'teal', archived: 'gray' };

function ProfessionalPlans({ patientId, formatDate }) {
  const { m } = useMovementT();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [draftNotes, setDraftNotes] = useState('');
  const [busy, setBusy] = useState(null);

  const load = useCallback(
    async (signal, selectId) => {
      setLoading(true);
      setError(false);
      try {
        const res =
          (await metabolicApi.getExercisePlans(patientId, signal)) || [];
        setPlans(res);
        const pick =
          res.find(p => p.id === selectId) ||
          res.find(p => p.status === 'draft') ||
          res.find(p => p.status === 'approved') ||
          res[0];
        setSelectedId(pick?.id ?? null);
        setDraft(pick ? structuredClone(pick.plan) : null);
        setDraftNotes(pick?.notes || '');
      } catch (err) {
        if (signal?.aborted) return;
        logger.error('exercise_plans_load_failed', { error: err?.message });
        setError(true);
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [patientId]
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const selected = plans.find(p => p.id === selectedId);

  const run = async (name, fn, successKey) => {
    setBusy(name);
    try {
      const res = await fn();
      notifications.show({ color: 'teal', message: m(successKey) });
      await load(undefined, res?.id ?? selectedId);
    } catch (err) {
      logger.error('exercise_plan_action_failed', {
        action: name,
        error: err?.message,
      });
      notifications.show({ color: 'red', message: m('error') });
    } finally {
      setBusy(null);
    }
  };

  const select = plan => {
    setSelectedId(plan.id);
    setDraft(structuredClone(plan.plan));
    setDraftNotes(plan.notes || '');
  };

  const body = { plan: draft, notes: draftNotes || null };

  return (
    <Card withBorder radius="lg" padding="lg">
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Group gap="sm">
          <ThemeIcon variant="light" size="lg" radius="md" color="orange">
            <IconBarbell size={20} />
          </ThemeIcon>
          <div>
            <Title order={3}>{m('plan.title')}</Title>
            <Text size="sm" c="dimmed">
              {m('plan.subtitlePro')}
            </Text>
          </div>
        </Group>
        <Button
          leftSection={<IconSparkles size={16} />}
          loading={busy === 'generate'}
          onClick={() =>
            run(
              'generate',
              () => metabolicApi.generateExercisePlan(patientId),
              'plan.generated'
            )
          }
        >
          {m('plan.generate')}
        </Button>
      </Group>

      {loading ? (
        <Center py="lg">
          <Loader />
        </Center>
      ) : error ? (
        <Alert color="red" mt="md">
          {m('loadError')}
        </Alert>
      ) : !plans.length ? (
        <Text c="dimmed" mt="md">
          {m('plan.noneProfessional')}
        </Text>
      ) : (
        <>
          <Group gap="xs" mt="md">
            {plans.map(p => (
              <Button
                key={p.id}
                size="xs"
                variant={p.id === selectedId ? 'filled' : 'default'}
                onClick={() => select(p)}
                rightSection={
                  <Badge
                    size="xs"
                    color={STATUS_COLORS[p.status]}
                    variant="light"
                  >
                    {m(`plan.status.${p.status}`)}
                  </Badge>
                }
              >
                {formatDate(p.created_at)}
              </Button>
            ))}
          </Group>
          {selected && (
            <Box mt="md">
              {selected.status === 'approved' && selected.approved_at && (
                <Text size="sm" c="dimmed" mb="sm">
                  {m('plan.approvedOn', {
                    date: formatDate(selected.approved_at),
                  })}
                </Text>
              )}
              {selected.status === 'draft' ? (
                <>
                  <Alert color="yellow" mb="md">
                    {m('plan.draftNotice')}
                  </Alert>
                  <Box mb="md">
                    <Rationale keys={selected.rationale} />
                  </Box>
                  <PlanEditor value={draft} onChange={setDraft} />
                  <Textarea
                    mt="md"
                    label={m('plan.notes')}
                    autosize
                    minRows={2}
                    maxLength={2000}
                    value={draftNotes}
                    onChange={e => setDraftNotes(e.currentTarget.value)}
                  />
                  <Group justify="flex-end" mt="md" gap="sm">
                    <Button
                      variant="subtle"
                      color="red"
                      leftSection={<IconTrash size={16} />}
                      loading={busy === 'delete'}
                      onClick={() =>
                        run(
                          'delete',
                          () =>
                            metabolicApi.deleteExercisePlan(
                              patientId,
                              selected.id
                            ),
                          'plan.deleted'
                        )
                      }
                    >
                      {m('plan.delete')}
                    </Button>
                    <Button
                      variant="default"
                      leftSection={<IconDeviceFloppy size={16} />}
                      loading={busy === 'save'}
                      onClick={() =>
                        run(
                          'save',
                          () =>
                            metabolicApi.updateExercisePlan(
                              patientId,
                              selected.id,
                              body
                            ),
                          'plan.saved'
                        )
                      }
                    >
                      {m('plan.save')}
                    </Button>
                    <Button
                      color="teal"
                      leftSection={<IconCheck size={16} />}
                      loading={busy === 'approve'}
                      onClick={() =>
                        run(
                          'approve',
                          async () => {
                            await metabolicApi.updateExercisePlan(
                              patientId,
                              selected.id,
                              body
                            );
                            return metabolicApi.approveExercisePlan(
                              patientId,
                              selected.id
                            );
                          },
                          'plan.approved'
                        )
                      }
                    >
                      {m('plan.approve')}
                    </Button>
                  </Group>
                </>
              ) : (
                <>
                  <PlanView
                    plan={selected.plan}
                    rationale={selected.rationale}
                  />
                  <Notes text={selected.notes} />
                  <Group justify="flex-end" mt="md">
                    <Button
                      variant="default"
                      leftSection={<IconCopy size={16} />}
                      loading={busy === 'copy'}
                      onClick={() =>
                        run(
                          'copy',
                          () =>
                            metabolicApi.createExercisePlan(patientId, {
                              plan: selected.plan,
                              notes: selected.notes,
                            }),
                          'plan.copied'
                        )
                      }
                    >
                      {m('plan.newVersion')}
                    </Button>
                  </Group>
                </>
              )}
            </Box>
          )}
        </>
      )}
    </Card>
  );
}

function PatientPlan({ patientId, formatDate }) {
  const { m } = useMovementT();
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(false);
    metabolicApi
      .getExercisePlans(patientId, controller.signal)
      .then(res =>
        setPlan((res || []).find(p => p.status === 'approved') || null)
      )
      .catch(err => {
        if (controller.signal.aborted) return;
        logger.error('exercise_plan_load_failed', { error: err?.message });
        setError(true);
      })
      .finally(() => !controller.signal.aborted && setLoading(false));
    return () => controller.abort();
  }, [patientId]);

  return (
    <Card withBorder radius="lg" padding="lg">
      <Group gap="sm" mb="md">
        <ThemeIcon variant="light" size="lg" radius="md" color="orange">
          <IconBarbell size={20} />
        </ThemeIcon>
        <div>
          <Title order={3}>{m('plan.titlePatient')}</Title>
          {plan?.approved_at && (
            <Text size="sm" c="dimmed">
              {m('plan.approvedOn', { date: formatDate(plan.approved_at) })}
            </Text>
          )}
        </div>
      </Group>
      {loading ? (
        <Center py="lg">
          <Loader />
        </Center>
      ) : error ? (
        <Alert color="red">{m('loadError')}</Alert>
      ) : !plan ? (
        <Text c="dimmed">{m('plan.none')}</Text>
      ) : (
        <>
          <PlanView plan={plan.plan} />
          <Notes text={plan.notes} />
        </>
      )}
    </Card>
  );
}

export default function MetabolicMovement() {
  const { m, t } = useMovementT();
  const { patient } = usePatientWithStaticData();
  const { user } = useAuth();
  const { formatDate } = useDateFormat();
  const patientId = patient?.patient?.id;
  const professional = PRO_ROLES.includes(user?.role);

  return (
    <Container size="xl" py="md" className="silho-ir-page">
      <PageHeader title={m('title')} icon="🏃" />
      <Text c="dimmed" mt="md">
        {m('subtitle')}
      </Text>
      <Alert color="blue" variant="light" mt="md">
        {m('disclaimer')}
      </Alert>
      {!patientId ? (
        <Alert color="blue" mt="md">
          {t('metabolic.selectPatient')}
        </Alert>
      ) : (
        <Stack gap="lg" mt="lg">
          <FunctionalSection patientId={patientId} formatDate={formatDate} />
          {professional ? (
            <ProfessionalPlans patientId={patientId} formatDate={formatDate} />
          ) : (
            <PatientPlan patientId={patientId} formatDate={formatDate} />
          )}
        </Stack>
      )}
    </Container>
  );
}
