import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Button,
  Card,
  Center,
  Group,
  List,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle,
  IconDownload,
  IconShieldLock,
} from '@tabler/icons-react';
import AdminLayout from '../../components/admin/AdminLayout';
import metabolicApi from '../../services/api/metabolicApi';
import logger from '../../services/logger';

const STATS = [
  'patients_total',
  'patients_consented',
  'assessments',
  'columns',
];
const MEASURES = ['consent', 'pseudonym', 'age', 'dates', 'freeText', 'loinc'];
const FORMATS = [
  { format: 'csv', ext: 'csv', type: 'text/csv' },
  { format: 'json', ext: 'json', type: 'application/json' },
  { format: 'dictionary', ext: 'csv', type: 'text/csv' },
];

function save(content, filename, type) {
  const body =
    typeof content === 'string' ? content : JSON.stringify(content, null, 2);
  const url = window.URL.createObjectURL(new Blob([body], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

const MetabolicResearch = () => {
  const { t } = useTranslation('admin');
  const r = (key, opts) => t(`metabolicResearch.${key}`, opts);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    metabolicApi
      .getResearchSummary(controller.signal)
      .then(data => !controller.signal.aborted && setSummary(data))
      .catch(err => {
        if (controller.signal.aborted) return;
        logger.error('metabolic_research_summary_failed', {
          error: err?.message,
        });
        setError(r('loadError'));
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const download = async ({ format, ext, type }) => {
    setBusy(format);
    try {
      const content = await metabolicApi.exportResearch(format);
      const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      const base =
        format === 'dictionary'
          ? 'silho-research-dictionary'
          : 'silho-research';
      save(content, `${base}-${stamp}.${ext}`, type);
    } catch (err) {
      logger.error('metabolic_research_export_failed', { error: err?.message });
      notifications.show({ color: 'red', message: r('exportError') });
    } finally {
      setBusy(null);
    }
  };

  return (
    <AdminLayout>
      <Stack gap="lg" p="md">
        <div>
          <Title order={2}>{r('title')}</Title>
          <Text c="dimmed">{r('subtitle')}</Text>
        </div>
        {error && <Alert color="red">{error}</Alert>}
        {!summary && !error ? (
          <Center py="xl">
            <Loader />
          </Center>
        ) : (
          summary && (
            <>
              <SimpleGrid cols={{ base: 2, sm: 4 }}>
                {STATS.map(key => (
                  <Card key={key} withBorder radius="lg" padding="md">
                    <Text size="sm" c="dimmed">
                      {r(`stats.${key}`)}
                    </Text>
                    <Text fz={28} fw={700}>
                      {summary[key]}
                    </Text>
                  </Card>
                ))}
              </SimpleGrid>
              {summary.small_sample && (
                <Alert
                  color="yellow"
                  icon={<IconAlertTriangle size={18} />}
                  title={r('smallTitle')}
                >
                  {r('smallSample', { count: summary.min_group_size })}
                </Alert>
              )}
              <Card withBorder radius="lg" padding="lg">
                <Group gap="sm" mb="sm">
                  <IconShieldLock size={20} />
                  <Title order={4}>{r('howTitle')}</Title>
                </Group>
                <List spacing="xs" size="sm">
                  {MEASURES.map(m => (
                    <List.Item key={m}>{r(`measures.${m}`)}</List.Item>
                  ))}
                </List>
                <Text size="xs" c="dimmed" mt="md">
                  {r('ethics')}
                </Text>
              </Card>
              <Card withBorder radius="lg" padding="lg">
                <Title order={4} mb="sm">
                  {r('downloadTitle')}
                </Title>
                <Group gap="sm">
                  {FORMATS.map(f => (
                    <Button
                      key={f.format}
                      variant={f.format === 'csv' ? 'filled' : 'light'}
                      leftSection={<IconDownload size={16} />}
                      loading={busy === f.format}
                      disabled={
                        f.format !== 'dictionary' && !summary.assessments
                      }
                      onClick={() => download(f)}
                    >
                      {r(`formats.${f.format}`)}
                    </Button>
                  ))}
                </Group>
                <Text size="xs" c="dimmed" mt="sm">
                  {r('audit')}
                </Text>
              </Card>
            </>
          )
        )}
      </Stack>
    </AdminLayout>
  );
};

export default MetabolicResearch;
