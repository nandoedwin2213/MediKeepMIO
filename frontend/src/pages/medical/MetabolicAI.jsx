import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Container,
  Group,
  List,
  Loader,
  MultiSelect,
  SimpleGrid,
  Slider,
  Stack,
  Text,
  Textarea,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle,
  IconArrowDownRight,
  IconArrowRight,
  IconArrowUpRight,
  IconBulb,
  IconCheck,
  IconDeviceFloppy,
  IconFlask,
  IconRefresh,
  IconSparkles,
  IconTrash,
} from '@tabler/icons-react';
import { PageHeader } from '../../components';
import { useAuth } from '../../contexts/AuthContext';
import { usePatientWithStaticData } from '../../hooks/useGlobalData';
import { useDateFormat } from '../../hooks/useDateFormat';
import metabolicApi from '../../services/api/metabolicApi';
import logger from '../../services/logger';

const PRO_ROLES = [
  'admin',
  'administrator',
  'doctor',
  'nurse',
  'staff',
  'physio',
  'nutritionist',
];

export const PRIORITY_CODES = [
  'reduce_waist',
  'increase_activity',
  'carb_quality',
  'strength',
  'blood_pressure',
  'healthy_fats',
  'liver',
  'sleep',
  'stop_smoking',
  'repeat_labs',
];

const LEVEL_COLORS = {
  normal: 'teal',
  borderline: 'yellow',
  low: 'yellow',
  high: 'orange',
  veryHigh: 'red',
};
export const RISK_COLORS = {
  favorable: 'green',
  initial: 'yellow',
  moderate: 'orange',
  high: 'red',
};
const STATUS_COLORS = { draft: 'yellow', approved: 'teal', archived: 'gray' };

const SIM_FIELDS = [
  { key: 'waist', min: -25, max: 0, step: 1 },
  { key: 'weight', min: -30, max: 0, step: 1 },
  { key: 'triglycerides', min: -200, max: 0, step: 5 },
  { key: 'glucose', min: -80, max: 0, step: 5 },
  { key: 'hba1c', min: -3, max: 0, step: 0.1 },
  { key: 'physical_activity', min: 0, max: 300, step: 15 },
];
const EMPTY_SIM = Object.fromEntries(SIM_FIELDS.map(f => [f.key, 0]));

function useAIT() {
  const { t } = useTranslation('medical');
  const a = (key, opts) => t(`metabolic.ai.${key}`, opts);
  const name = key => t(`metabolic.indicators.${key}`, key);
  const names = keys => (keys || []).map(name).join(', ');
  return { t, a, name, names };
}

const fmt = value =>
  typeof value === 'number'
    ? Number.isInteger(value)
      ? value
      : Number(value.toFixed(2))
    : value;

function SectionTitle({ icon: Icon, color, children }) {
  return (
    <Group gap="sm" mb="sm" wrap="nowrap">
      <ThemeIcon variant="light" color={color} radius="md">
        <Icon size={18} />
      </ThemeIcon>
      <Title order={4}>{children}</Title>
    </Group>
  );
}

function FactorBadges({ rows, a, name }) {
  return (
    <Group gap="xs">
      {rows.map(row => (
        <Badge
          key={row.key}
          color={LEVEL_COLORS[row.level] || 'gray'}
          variant="filled"
          size="lg"
          radius="sm"
          style={{ textTransform: 'none' }}
        >
          {name(row.key)}
          {typeof row.value === 'number'
            ? ` · ${fmt(row.value)}${row.unit ? ` ${row.unit}` : ''}`
            : ''}{' '}
          · {a(`levels.${row.level}`)}
        </Badge>
      ))}
    </Group>
  );
}

export function InsightView({ insight }) {
  const { a, name, names } = useAIT();
  const { formatDate } = useDateFormat();
  const content = insight.content || {};
  const concerns = content.concerns || [];
  const strengths = content.strengths || [];
  const change = content.change;
  const delta = change?.score_delta;
  return (
    <Stack gap="md">
      {content.needs_review && (
        <Alert color="red" icon={<IconAlertTriangle size={18} />}>
          {a('needsReview')}
        </Alert>
      )}
      <Card withBorder radius="md" padding="md" bg="var(--mantine-color-body)">
        <Group gap="sm" wrap="nowrap" align="flex-start">
          <ThemeIcon color="violet" radius="xl" size="lg">
            <IconSparkles size={20} />
          </ThemeIcon>
          <Text size="lg" fw={500}>
            {a(`pattern.${content.pattern}`, {
              factors: names(concerns.slice(0, 3).map(c => c.key)),
            })}
          </Text>
        </Group>
      </Card>
      {change && delta != null && (
        <Box>
          <Group gap="xs" mb={4}>
            <Badge
              color={delta > 0 ? 'green' : delta < 0 ? 'red' : 'gray'}
              size="lg"
              variant="filled"
            >
              {delta > 0 ? `+${delta}` : delta}
            </Badge>
            <Text fw={600}>
              {a(
                delta > 0
                  ? 'change.improved'
                  : delta < 0
                    ? 'change.worsened'
                    : 'change.same',
                { points: Math.abs(delta) }
              )}
            </Text>
          </Group>
          {change.drivers?.length > 0 && (
            <>
              <Text size="sm" c="dimmed">
                {a('change.mainly')}
              </Text>
              <List spacing={2} size="sm" mt={4}>
                {change.drivers.map(d => (
                  <List.Item
                    key={d.key}
                    icon={
                      d.direction === 'improved' ? (
                        <IconArrowDownRight size={16} color="teal" />
                      ) : (
                        <IconArrowUpRight size={16} color="red" />
                      )
                    }
                  >
                    {name(d.key)}
                    {d.from != null && d.to != null
                      ? `: ${fmt(d.from)} → ${fmt(d.to)}${d.unit ? ` ${d.unit}` : ''}`
                      : ''}
                  </List.Item>
                ))}
              </List>
            </>
          )}
        </Box>
      )}
      {concerns.length > 0 && (
        <Box>
          <Text fw={700} mb="xs">
            {a('concernsTitle')}
          </Text>
          <FactorBadges rows={concerns} a={a} name={name} />
          <Button
            component={Link}
            to="/metabolic-risk"
            variant="subtle"
            size="compact-sm"
            mt="xs"
            rightSection={<IconArrowRight size={14} />}
          >
            {a('rangesLink')}
          </Button>
        </Box>
      )}
      {strengths.length > 0 && (
        <Box>
          <Text fw={700} mb="xs">
            {a('strengthsTitle')}
          </Text>
          <FactorBadges rows={strengths} a={a} name={name} />
        </Box>
      )}
      {content.priorities?.length > 0 && (
        <Box>
          <Text fw={700} mb="xs">
            {a('prioritiesTitle')}
          </Text>
          <Stack gap="xs">
            {content.priorities.map((p, i) => (
              <Group key={p.code} gap="sm" wrap="nowrap" align="flex-start">
                <ThemeIcon radius="xl" size="md" color="indigo">
                  <Text size="xs" fw={700}>
                    {i + 1}
                  </Text>
                </ThemeIcon>
                <Box>
                  <Text fw={500}>{a(`priorities.${p.code}`)}</Text>
                  {p.because?.length > 0 && (
                    <Text size="xs" c="dimmed">
                      {a('becauseOf', { factors: names(p.because) })}
                    </Text>
                  )}
                </Box>
              </Group>
            ))}
          </Stack>
        </Box>
      )}
      {insight.note && (
        <Alert color="indigo" title={a('explain.noteTitle')}>
          <Text style={{ whiteSpace: 'pre-wrap' }}>{insight.note}</Text>
        </Alert>
      )}
      {insight.status === 'approved' && insight.approved_at && (
        <Text size="xs" c="dimmed">
          {a('explain.reviewed', { date: formatDate(insight.approved_at) })}
        </Text>
      )}
    </Stack>
  );
}

function DraftEditor({ draft, patientId, onChange }) {
  const { a } = useAIT();
  const [note, setNote] = useState(draft.note || '');
  const [priorities, setPriorities] = useState(
    (draft.content?.priorities || []).map(p => p.code)
  );
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    setNote(draft.note || '');
    setPriorities((draft.content?.priorities || []).map(p => p.code));
  }, [draft]);

  const run = async (kind, fn, message) => {
    setBusy(kind);
    try {
      await fn();
      if (message) notifications.show({ color: 'teal', message });
      await onChange();
    } catch (err) {
      logger.error('metabolic_ai_action_failed', { error: err?.message, kind });
      notifications.show({ color: 'red', message: a('explain.error') });
    } finally {
      setBusy(null);
    }
  };
  const save = () =>
    metabolicApi.updateInsight(patientId, draft.id, {
      note: note.trim() || null,
      priorities,
    });

  return (
    <Stack gap="sm">
      <MultiSelect
        label={a('explain.prioritiesLabel')}
        data={PRIORITY_CODES.map(code => ({
          value: code,
          label: a(`priorities.${code}`),
        }))}
        value={priorities}
        onChange={setPriorities}
        searchable
      />
      <Textarea
        label={a('explain.note')}
        placeholder={a('explain.notePlaceholder')}
        value={note}
        onChange={e => setNote(e.currentTarget.value)}
        autosize
        minRows={2}
        maxLength={4000}
      />
      <Group gap="sm">
        <Button
          variant="default"
          leftSection={<IconDeviceFloppy size={16} />}
          loading={busy === 'save'}
          onClick={() => run('save', save, a('explain.saved'))}
        >
          {a('explain.save')}
        </Button>
        <Button
          color="teal"
          leftSection={<IconCheck size={16} />}
          loading={busy === 'approve'}
          onClick={() =>
            run(
              'approve',
              async () => {
                await save();
                await metabolicApi.approveInsight(patientId, draft.id);
              },
              a('explain.approved')
            )
          }
        >
          {a('explain.approve')}
        </Button>
        <Button
          color="red"
          variant="subtle"
          leftSection={<IconTrash size={16} />}
          loading={busy === 'delete'}
          onClick={() =>
            run('delete', () => metabolicApi.deleteInsight(patientId, draft.id))
          }
        >
          {a('explain.delete')}
        </Button>
      </Group>
    </Stack>
  );
}

function ExplanationSection({ patientId, professional }) {
  const { a } = useAIT();
  const [insights, setInsights] = useState(null);
  const [error, setError] = useState(false);
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    try {
      setError(false);
      setInsights(await metabolicApi.getInsights(patientId));
    } catch (err) {
      logger.error('metabolic_ai_load_failed', { error: err?.message });
      setError(true);
    }
  }, [patientId]);

  useEffect(() => {
    load();
  }, [load]);

  const generate = async () => {
    setGenerating(true);
    try {
      await metabolicApi.generateInsight(patientId);
      await load();
    } catch (err) {
      logger.error('metabolic_ai_generate_failed', { error: err?.message });
      notifications.show({ color: 'red', message: a('explain.error') });
    } finally {
      setGenerating(false);
    }
  };

  const draft = (insights || []).find(i => i.status === 'draft');
  const approved = (insights || []).find(i => i.status === 'approved');

  return (
    <Card withBorder radius="md" padding="lg">
      <Group justify="space-between" mb="sm" wrap="wrap">
        <SectionTitle icon={IconBulb} color="violet">
          {a('explain.title')}
        </SectionTitle>
        {professional && (
          <Button
            leftSection={<IconRefresh size={16} />}
            loading={generating}
            onClick={generate}
            color="violet"
          >
            {draft || approved
              ? a('explain.regenerate')
              : a('explain.generate')}
          </Button>
        )}
      </Group>
      {error ? (
        <Alert color="red">{a('explain.error')}</Alert>
      ) : insights === null ? (
        <Center py="lg">
          <Loader />
        </Center>
      ) : (
        <Stack gap="lg">
          {professional && draft && (
            <Card withBorder radius="md" padding="md">
              <Group gap="xs" mb="sm">
                <Badge color={STATUS_COLORS.draft}>{a('status.draft')}</Badge>
                <Text size="sm" c="dimmed">
                  {a('explain.draftNotice')}
                </Text>
              </Group>
              <InsightView insight={draft} />
              <Box mt="md">
                <DraftEditor
                  draft={draft}
                  patientId={patientId}
                  onChange={load}
                />
              </Box>
            </Card>
          )}
          {approved ? (
            <Box>
              {professional && (
                <Badge color={STATUS_COLORS.approved} mb="sm">
                  {a('status.approved')}
                </Badge>
              )}
              <InsightView insight={approved} />
            </Box>
          ) : (
            !draft && (
              <Alert color="blue">
                {professional ? a('explain.emptyPro') : a('explain.pending')}
              </Alert>
            )
          )}
        </Stack>
      )}
    </Card>
  );
}

function ScoreBox({ label, score }) {
  const { t } = useAIT();
  const color = RISK_COLORS[score?.level] || 'gray';
  return (
    <Card withBorder radius="md" padding="md" ta="center">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text fz={40} fw={800} c={`${color}.6`} lh={1.1}>
        {score?.value ?? '—'}
      </Text>
      {score?.level && (
        <Badge color={color} variant="filled" mt={4}>
          {t(`metabolic.risk.${score.level}`, score.level)}
        </Badge>
      )}
    </Card>
  );
}

function SimulatorSection({ patientId }) {
  const { a, name, names } = useAIT();
  const [values, setValues] = useState(EMPTY_SIM);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);

  const simulate = async () => {
    setRunning(true);
    try {
      const body = Object.fromEntries(
        Object.entries(values).filter(([, v]) => v !== 0)
      );
      setResult(await metabolicApi.simulate(patientId, body));
    } catch (err) {
      logger.error('metabolic_simulation_failed', { error: err?.message });
      notifications.show({ color: 'red', message: a('explain.error') });
    } finally {
      setRunning(false);
    }
  };

  const missing = Object.entries(result?.applied || {})
    .filter(([, v]) => v.missing)
    .map(([k]) => k);
  const delta = result?.score_delta;

  return (
    <Card withBorder radius="md" padding="lg">
      <SectionTitle icon={IconFlask} color="cyan">
        {a('sim.title')}
      </SectionTitle>
      <Text c="dimmed" size="sm" mb="md">
        {a('sim.subtitle')}
      </Text>
      <Alert color="yellow" icon={<IconAlertTriangle size={18} />} mb="md">
        {a('sim.disclaimer')}
      </Alert>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg" verticalSpacing="lg">
        {SIM_FIELDS.map(f => (
          <Box key={f.key}>
            <Group justify="space-between" mb={4}>
              <Text size="sm" fw={500}>
                {a(`sim.fields.${f.key}`)}
              </Text>
              <Badge variant="outline" color="cyan">
                {values[f.key] > 0 ? `+${values[f.key]}` : values[f.key]}
              </Badge>
            </Group>
            <Slider
              min={f.min}
              max={f.max}
              step={f.step}
              value={values[f.key]}
              onChange={v =>
                setValues(prev => ({ ...prev, [f.key]: Number(v.toFixed(1)) }))
              }
              label={v => Number(v.toFixed(1))}
              color="cyan"
              aria-label={a(`sim.fields.${f.key}`)}
            />
          </Box>
        ))}
      </SimpleGrid>
      <Group mt="lg" gap="sm">
        <Button
          color="cyan"
          leftSection={<IconFlask size={16} />}
          loading={running}
          onClick={simulate}
        >
          {a('sim.run')}
        </Button>
        <Button
          variant="default"
          onClick={() => {
            setValues(EMPTY_SIM);
            setResult(null);
          }}
        >
          {a('sim.reset')}
        </Button>
      </Group>
      {result && (
        <Stack gap="md" mt="lg">
          <SimpleGrid cols={{ base: 1, xs: 3 }} spacing="md">
            <ScoreBox label={a('sim.current')} score={result.before} />
            <Center>
              <Stack gap={4} align="center">
                <IconArrowRight size={28} />
                {delta != null && (
                  <Badge
                    size="lg"
                    color={delta > 0 ? 'green' : delta < 0 ? 'red' : 'gray'}
                    variant="filled"
                  >
                    {a('sim.delta', {
                      points: delta > 0 ? `+${delta}` : delta,
                    })}
                  </Badge>
                )}
              </Stack>
            </Center>
            <ScoreBox label={a('sim.simulated')} score={result.after} />
          </SimpleGrid>
          {missing.length > 0 && (
            <Alert color="gray">
              {a('sim.missing', { items: names(missing) })}
            </Alert>
          )}
          {result.changes.length === 0 ? (
            <Text c="dimmed">{a('sim.noChanges')}</Text>
          ) : (
            <Box>
              <Text fw={700} mb="xs">
                {a('sim.summary')}
              </Text>
              <Stack gap="xs">
                {result.changes.map(c => (
                  <Group key={c.key} gap="sm" wrap="wrap">
                    {c.direction === 'improved' ? (
                      <IconArrowDownRight size={18} color="teal" />
                    ) : (
                      <IconArrowUpRight size={18} color="gray" />
                    )}
                    <Text fw={500}>{name(c.key)}</Text>
                    <Text size="sm">
                      {fmt(c.from)} → {fmt(c.to)}
                      {c.unit ? ` ${c.unit}` : ''}
                    </Text>
                    {c.level_changed && (
                      <Group gap={4}>
                        <Badge color={LEVEL_COLORS[c.from_level] || 'gray'}>
                          {a(`levels.${c.from_level}`)}
                        </Badge>
                        <IconArrowRight size={14} />
                        <Badge color={LEVEL_COLORS[c.to_level] || 'gray'}>
                          {a(`levels.${c.to_level}`)}
                        </Badge>
                      </Group>
                    )}
                  </Group>
                ))}
              </Stack>
            </Box>
          )}
        </Stack>
      )}
    </Card>
  );
}

export default function MetabolicAI() {
  const { t, a } = useAIT();
  const { user } = useAuth();
  const { patient } = usePatientWithStaticData();
  const patientId = patient?.patient?.id;
  const professional = PRO_ROLES.includes(user?.role);

  return (
    <Container size="lg" py="md" className="silho-ir-page">
      <PageHeader title={a('title')} icon="💡" />
      <Text c="dimmed" mt="md">
        {a('subtitle')}
      </Text>
      <Alert color="indigo" variant="light" mt="md">
        {a('disclaimer')}
      </Alert>
      {!patientId ? (
        <Alert color="blue" mt="md">
          {t('metabolic.selectPatient')}
        </Alert>
      ) : (
        <Stack gap="lg" mt="lg">
          <ExplanationSection
            patientId={patientId}
            professional={professional}
          />
          <SimulatorSection patientId={patientId} />
        </Stack>
      )}
    </Container>
  );
}
