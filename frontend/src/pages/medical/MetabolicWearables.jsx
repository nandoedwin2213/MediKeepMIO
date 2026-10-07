import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Badge,
  Button,
  Card,
  Container,
  FileButton,
  Group,
  List,
  Loader,
  ScrollArea,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle,
  IconDeviceWatch,
  IconDownload,
  IconUpload,
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
import { LevelScale, fmt } from './MetabolicRisk';

const SOURCE_NAMES = {
  apple_health: 'Apple Health',
  google_fit: 'Google Fit',
  csv: 'CSV',
};
const METRICS = ['steps', 'physical_activity', 'sleep', 'resting_hr', 'weight'];
const UNIT_KEYS = {
  steps: 'units.steps',
  physical_activity: 'units.minWeek',
  resting_hr: 'units.bpm',
};
const LITERAL_UNITS = { sleep: 'h', weight: 'kg' };
const TEMPLATE =
  'Fecha;Pasos;Minutos activos;Horas de sueño;FC reposo;Peso (kg)\n' +
  '01/09/2026;8200;35;7,5;64;82,4\n' +
  '02/09/2026;5400;0;6,8;66;\n';

export function WearableSummary({ summary, locale }) {
  const { t } = useTranslation('medical');
  const r = (key, opts) => t(`metabolic.wearables.${key}`, opts);
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
      {METRICS.map(key => {
        const metric = summary.metrics?.[key];
        if (!metric || metric.value == null) return null;
        const unit = UNIT_KEYS[key] ? r(UNIT_KEYS[key]) : LITERAL_UNITS[key];
        return (
          <Card key={key} withBorder radius="md" padding="md">
            <Text size="sm" c="dimmed">
              {r(`metrics.${key}`)}
            </Text>
            <Group gap={6} align="baseline">
              <Text fw={700} size="xl">
                {fmt(metric.value, locale)}
              </Text>
              <Text size="sm" c="dimmed">
                {unit}
              </Text>
            </Group>
            {key !== 'weight' && (
              <Text size="xs" c="dimmed" mt={4}>
                {r(`hints.${key}`)}
              </Text>
            )}
            {metric.bands && (
              <LevelScale
                bands={metric.bands}
                level={metric.level}
                locale={locale}
              />
            )}
          </Card>
        );
      })}
    </SimpleGrid>
  );
}

const MetabolicWearables = () => {
  const { t, i18n } = useTranslation('medical');
  const r = (key, opts) => t(`metabolic.wearables.${key}`, opts);
  const locale = i18n.language;
  const { formatDate } = useDateFormat();
  const { patient } = usePatientWithStaticData();
  const patientId = patient?.patient?.id;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState(null);
  const [parsing, setParsing] = useState(false);
  const [preview, setPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(
    async signal => {
      if (!patientId) return;
      setLoading(true);
      try {
        const out = await metabolicApi.getWearables(
          patientId,
          { days: 90 },
          signal
        );
        if (!signal?.aborted) setData(out);
      } catch (err) {
        if (!signal?.aborted)
          logger.error('metabolic_wearables_load_failed', {
            error: err?.message,
          });
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

  const analyse = async () => {
    setParsing(true);
    setError(null);
    try {
      setPreview(await metabolicApi.parseWearables(patientId, file));
    } catch (err) {
      logger.error('metabolic_wearables_parse_failed', { error: err?.message });
      setError(r('parseError'));
    } finally {
      setParsing(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const out = await metabolicApi.importWearables(patientId, {
        source: preview.source,
        days: preview.days,
      });
      notifications.show({
        color: 'teal',
        message: `${r('imported', { count: out.days })}${
          out.score != null ? ` · ${r('newScore', { score: out.score })}` : ''
        }`,
      });
      setPreview(null);
      setFile(null);
      await load();
    } catch (err) {
      logger.error('metabolic_wearables_import_failed', {
        error: err?.message,
      });
      setError(r('importError'));
    } finally {
      setSaving(false);
    }
  };

  const apply = async () => {
    setApplying(true);
    setError(null);
    try {
      const out = await metabolicApi.applyWearables(patientId);
      notifications.show({
        color: 'teal',
        message: r('applied', {
          minutes: out.physical_activity_minutes_week ?? '–',
          hours: out.sleep_hours ?? '–',
          score: out.score ?? '–',
        }),
      });
    } catch (err) {
      logger.error('metabolic_wearables_apply_failed', { error: err?.message });
      setError(r('applyError'));
    } finally {
      setApplying(false);
    }
  };

  const downloadTemplate = () => {
    const url = URL.createObjectURL(
      new Blob([TEMPLATE], { type: 'text/csv;charset=utf-8' })
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = 'silho-wearables.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const discarded = Object.values(preview?.warnings || {}).reduce(
    (a, b) => a + b,
    0
  );
  const summary = data?.summary;
  const cell = v => (v == null ? '–' : fmt(v, locale));

  return (
    <Container size="xl" py="md">
      <PageHeader title={r('title')} icon="⌚" />
      <Text c="dimmed" mt="md">
        {r('subtitle')}
      </Text>
      <Alert color="blue" mt="md" icon={<IconDeviceWatch size={18} />}>
        {r('nativeNote')}
      </Alert>
      {!patientId && (
        <Alert color="blue" mt="md">
          {t('metabolic.selectPatient')}
        </Alert>
      )}
      {error && (
        <Alert color="red" mt="md" icon={<IconAlertTriangle size={18} />}>
          {error}
        </Alert>
      )}

      <Card withBorder radius="lg" padding="lg" mt="md">
        <Title order={4} mb="sm">
          {r('howTitle')}
        </Title>
        <Tabs defaultValue="apple">
          <Tabs.List>
            <Tabs.Tab value="apple">{r('tabApple')}</Tabs.Tab>
            <Tabs.Tab value="google">{r('tabGoogle')}</Tabs.Tab>
            <Tabs.Tab value="other">{r('tabOther')}</Tabs.Tab>
          </Tabs.List>
          {[
            ['apple', 4],
            ['google', 4],
            ['other', 2],
          ].map(([tab, n]) => (
            <Tabs.Panel key={tab} value={tab} pt="sm">
              <List type="ordered" size="sm" spacing={4}>
                {Array.from({ length: n }, (_, i) => (
                  <List.Item key={i}>{r(`${tab}${i + 1}`)}</List.Item>
                ))}
              </List>
            </Tabs.Panel>
          ))}
        </Tabs>
        <Group mt="md" gap="sm">
          <FileButton
            onChange={setFile}
            accept=".zip,.xml,.csv,.txt,application/zip,text/csv,text/xml"
          >
            {props => (
              <Button
                {...props}
                variant="default"
                leftSection={<IconUpload size={16} />}
                disabled={!patientId}
              >
                {r('upload')}
              </Button>
            )}
          </FileButton>
          <Button
            onClick={analyse}
            loading={parsing}
            disabled={!file || !patientId}
          >
            {r('analyse')}
          </Button>
          <Button
            variant="subtle"
            leftSection={<IconDownload size={16} />}
            onClick={downloadTemplate}
          >
            {r('template')}
          </Button>
        </Group>
        {file && (
          <Text size="sm" mt="xs">
            {file.name}
          </Text>
        )}
        <Text size="xs" c="dimmed" mt="sm">
          {r('privacy')}
        </Text>
      </Card>

      {preview && (
        <Card withBorder radius="lg" padding="lg" mt="md">
          <Group justify="space-between" mb="sm">
            <Title order={4}>{r('previewTitle')}</Title>
            <Badge variant="light">{SOURCE_NAMES[preview.source]}</Badge>
          </Group>
          <Text size="sm" c="dimmed" mb="sm">
            {r('range', {
              start: formatDate(preview.days[0].date),
              end: formatDate(preview.days[preview.days.length - 1].date),
              count: preview.days.length,
            })}
          </Text>
          {discarded > 0 && (
            <Alert color="yellow" mb="sm">
              {r('discarded', { count: discarded })}
            </Alert>
          )}
          <WearableSummary summary={preview.summary} locale={locale} />
          <ScrollArea h={300} mt="md" type="auto">
            <Table miw={620} stickyHeader>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{r('cols.date')}</Table.Th>
                  <Table.Th>{r('metrics.steps')}</Table.Th>
                  <Table.Th>{r('cols.exercise')}</Table.Th>
                  <Table.Th>{`${r('metrics.sleep')} (h)`}</Table.Th>
                  <Table.Th>{r('metrics.resting_hr')}</Table.Th>
                  <Table.Th>{`${r('metrics.weight')} (kg)`}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {[...preview.days].reverse().map(d => (
                  <Table.Tr key={d.date}>
                    <Table.Td>{formatDate(d.date)}</Table.Td>
                    <Table.Td>{cell(d.steps)}</Table.Td>
                    <Table.Td>{cell(d.exercise_minutes)}</Table.Td>
                    <Table.Td>{cell(d.sleep_hours)}</Table.Td>
                    <Table.Td>{cell(d.resting_hr)}</Table.Td>
                    <Table.Td>{cell(d.weight_kg)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
          <Text size="xs" c="dimmed" mt="sm">
            {r('reviewNote')} {r('weightNote')}
          </Text>
          <Group mt="md">
            <Button onClick={save} loading={saving}>
              {r('save', { count: preview.days.length })}
            </Button>
            <Button variant="default" onClick={() => setPreview(null)}>
              {r('cancel')}
            </Button>
          </Group>
        </Card>
      )}

      <Card withBorder radius="lg" padding="lg" mt="md">
        {loading && !data ? (
          <Loader size="sm" />
        ) : summary?.days_with_data ? (
          <Stack gap="md">
            <Group justify="space-between">
              <Title order={4}>
                {r('summaryTitle', { days: summary.window_days })}
              </Title>
              {data.last_import && (
                <Text size="xs" c="dimmed">
                  {r('lastImport', { date: formatDate(data.last_import) })}
                </Text>
              )}
            </Group>
            <WearableSummary summary={summary} locale={locale} />
            <Text size="xs" c="dimmed">
              {r('rangesNote')}
            </Text>
            <Group>
              <Button
                variant="light"
                onClick={apply}
                loading={applying}
                disabled={!patientId}
              >
                {r('apply')}
              </Button>
              <Text size="xs" c="dimmed" maw={520}>
                {r('applyHint')}
              </Text>
            </Group>
            <Title order={5}>{r('chartTitle')}</Title>
            <div style={{ width: '100%', height: 220 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data.days.filter(d => d.steps != null)}
                  margin={{ top: 8, right: 12, left: -8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={v => formatDate(v)}
                    fontSize={11}
                  />
                  <YAxis fontSize={11} />
                  <Tooltip
                    labelFormatter={v => formatDate(v)}
                    formatter={v => [fmt(v, locale), r('metrics.steps')]}
                  />
                  <Bar dataKey="steps" fill="#c9a227" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Stack>
        ) : (
          <Text c="dimmed">{r('noData')}</Text>
        )}
      </Card>
    </Container>
  );
};

export default MetabolicWearables;
