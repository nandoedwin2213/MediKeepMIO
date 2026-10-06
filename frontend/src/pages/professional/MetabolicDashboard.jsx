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
  ScrollArea,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { IconAlertTriangle, IconUsers } from '@tabler/icons-react';
import { PageHeader } from '../../components';
import { useAppData } from '../../contexts/AppDataContext';
import { useDateFormat } from '../../hooks/useDateFormat';
import metabolicApi from '../../services/api/metabolicApi';
import patientApi from '../../services/api/patientApi';
import logger from '../../services/logger';
import { RISK_COLORS, fmt } from '../medical/MetabolicRisk';

const LEVELS = ['favorable', 'initial', 'moderate', 'high', 'unknown'];
const ALERT_KEYS = [
  'high_risk',
  'risk_increased',
  'critical',
  'hba1c',
  'stale',
  'no_data',
];
const ALERT_COLORS = {
  high_risk: 'red',
  risk_increased: 'orange',
  critical: 'red',
  hba1c: 'red',
  stale: 'yellow',
  no_data: 'gray',
};
const levelColor = level => RISK_COLORS[level] || 'gray';

function LevelCard({ level, count, total }) {
  const { t } = useTranslation('medical');
  const pct = total ? Math.round((count / total) * 100) : 0;
  return (
    <Card withBorder radius="md" padding="md">
      <Group justify="space-between" wrap="nowrap">
        <Text size="sm" fw={600}>
          {t(`metabolic.professional.levels.${level}`)}
        </Text>
        <Badge color={levelColor(level)} variant="filled" circle size="sm">
          {' '}
        </Badge>
      </Group>
      <Text fz={32} fw={700} c={levelColor(level)}>
        {count}
      </Text>
      <Text size="xs" c="dimmed">
        {pct}%
      </Text>
    </Card>
  );
}

function AlertsCard({ alerts, staleDays }) {
  const { t } = useTranslation('medical');
  const active = ALERT_KEYS.filter(key => alerts[key] > 0);
  return (
    <Card withBorder radius="md" padding="lg">
      <Group gap="xs" mb="sm">
        <IconAlertTriangle size={20} />
        <Title order={4}>{t('metabolic.professional.alertsTitle')}</Title>
      </Group>
      {active.length === 0 ? (
        <Text c="dimmed">{t('metabolic.professional.noAlerts')}</Text>
      ) : (
        <Stack gap="xs">
          {active.map(key => (
            <Group key={key} gap="sm" wrap="nowrap">
              <Badge color={ALERT_COLORS[key]} size="lg" miw={44}>
                {alerts[key]}
              </Badge>
              <Text size="sm">
                {t(`metabolic.professional.alertText.${key}`, {
                  days: staleDays,
                })}
              </Text>
            </Group>
          ))}
        </Stack>
      )}
    </Card>
  );
}

function PatientsTable({ rows, onOpen, opening }) {
  const { t, i18n } = useTranslation('medical');
  const { formatDate } = useDateFormat();
  const locale = i18n.language;
  if (!rows.length) {
    return <Text c="dimmed">{t('metabolic.professional.empty')}</Text>;
  }
  const alertBadges = row => (
    <Group gap={4}>
      {row.alerts.map(key => (
        <Badge key={key} color={ALERT_COLORS[key]} variant="light" size="sm">
          {t(`metabolic.professional.alertBadge.${key}`)}
        </Badge>
      ))}
    </Group>
  );
  return (
    <>
      <Stack gap="sm" hiddenFrom="sm">
        {rows.map(row => (
          <Card key={row.patient_id} withBorder radius="md" padding="sm">
            <Group justify="space-between" wrap="nowrap" align="flex-start">
              <div>
                <Text fw={600}>{row.name}</Text>
                <Text size="xs" c="dimmed">
                  {t('metabolic.professional.columns.lastData')}:{' '}
                  {row.last_data_date ? formatDate(row.last_data_date) : '—'}
                </Text>
              </div>
              <Button
                size="xs"
                variant="filled"
                loading={opening === row.patient_id}
                onClick={() => onOpen(row.patient_id)}
              >
                {t('metabolic.professional.open')}
              </Button>
            </Group>
            <Group gap="xs" mt="xs">
              <Badge
                color={levelColor(row.level)}
                variant="light"
                h="auto"
                py={4}
                styles={{ label: { whiteSpace: 'normal' } }}
              >
                {row.score != null ? `${fmt(row.score, locale)} · ` : ''}
                {t(`metabolic.professional.levels.${row.level}`)}
              </Badge>
              {row.score_delta != null && (
                <Text
                  size="sm"
                  fw={600}
                  c={
                    row.score_delta > 0
                      ? 'teal'
                      : row.score_delta < 0
                        ? 'red'
                        : 'dimmed'
                  }
                >
                  {row.score_delta > 0 ? '+' : ''}
                  {fmt(row.score_delta, locale)}
                </Text>
              )}
            </Group>
            {row.alerts.length > 0 && <Box mt="xs">{alertBadges(row)}</Box>}
          </Card>
        ))}
      </Stack>
      <ScrollArea type="auto" visibleFrom="sm">
        <Table highlightOnHover verticalSpacing="sm" miw={760}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('metabolic.professional.columns.patient')}</Table.Th>
              <Table.Th>{t('metabolic.professional.columns.score')}</Table.Th>
              <Table.Th>{t('metabolic.professional.columns.change')}</Table.Th>
              <Table.Th>
                {t('metabolic.professional.columns.lastData')}
              </Table.Th>
              <Table.Th>{t('metabolic.professional.columns.alerts')}</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map(row => (
              <Table.Tr key={row.patient_id}>
                <Table.Td>
                  <Text fw={600}>{row.name}</Text>
                  {row.top_factors?.length > 0 && (
                    <Text size="xs" c="dimmed">
                      {row.top_factors
                        .map(f => t(`metabolic.indicators.${f.key}`, f.key))
                        .join(' · ')}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Badge
                    color={levelColor(row.level)}
                    variant="light"
                    size="lg"
                    h="auto"
                    py={4}
                    styles={{ label: { whiteSpace: 'normal' } }}
                  >
                    {row.score != null ? `${fmt(row.score, locale)} · ` : ''}
                    {t(`metabolic.professional.levels.${row.level}`)}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  {row.score_delta == null ? (
                    <Text c="dimmed">—</Text>
                  ) : (
                    <Text
                      fw={600}
                      c={
                        row.score_delta > 0
                          ? 'teal'
                          : row.score_delta < 0
                            ? 'red'
                            : 'dimmed'
                      }
                    >
                      {row.score_delta > 0 ? '+' : ''}
                      {fmt(row.score_delta, locale)}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  {row.last_data_date ? formatDate(row.last_data_date) : '—'}
                </Table.Td>
                <Table.Td>{alertBadges(row)}</Table.Td>
                <Table.Td>
                  <Button
                    size="xs"
                    variant="filled"
                    loading={opening === row.patient_id}
                    onClick={() => onOpen(row.patient_id)}
                  >
                    {t('metabolic.professional.open')}
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea>
    </>
  );
}

export default function MetabolicDashboard() {
  const { t } = useTranslation('medical');
  const navigate = useNavigate();
  const { setCurrentPatient } = useAppData();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [opening, setOpening] = useState(null);

  const load = useCallback(async signal => {
    setLoading(true);
    setError(false);
    try {
      const res = await metabolicApi.getProfessionalDashboard(signal);
      if (!signal?.aborted) setData(res);
    } catch (err) {
      if (signal?.aborted) return;
      logger.error('metabolic_dashboard_load_error', {
        message: 'Failed to load professional dashboard',
        error: err?.message,
      });
      setError(true);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const openPatient = async patientId => {
    setOpening(patientId);
    try {
      const patient = await patientApi.switchActivePatient(patientId);
      await setCurrentPatient(patient);
      navigate('/metabolic-risk');
    } catch (err) {
      logger.error('metabolic_dashboard_open_error', {
        message: 'Failed to switch patient',
        patientId,
        error: err?.message,
      });
      setError(true);
    } finally {
      setOpening(null);
    }
  };

  return (
    <Container size="xl" py="md" className="silho-ir-page">
      <PageHeader title={t('metabolic.professional.title')} icon="🩺" />
      <Stack gap="lg" mt="md">
        <Text c="dimmed">{t('metabolic.professional.subtitle')}</Text>
        {error && (
          <Alert color="yellow" icon={<IconAlertTriangle size={18} />}>
            <Group justify="space-between">
              <Text size="sm">{t('metabolic.professional.loadError')}</Text>
              <Button size="xs" variant="light" onClick={() => load()}>
                {t('metabolic.retry')}
              </Button>
            </Group>
          </Alert>
        )}
        {loading && !data ? (
          <Center py="xl">
            <Loader />
          </Center>
        ) : (
          data && (
            <>
              <SimpleGrid cols={{ base: 2, sm: 3, lg: 6 }}>
                <Card withBorder radius="md" padding="md">
                  <Group gap="xs">
                    <IconUsers size={18} />
                    <Text size="sm" fw={600}>
                      {t('metabolic.professional.total')}
                    </Text>
                  </Group>
                  <Text fz={32} fw={700}>
                    {data.total}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {t('metabolic.professional.followUp', {
                      count: data.needs_follow_up,
                    })}
                  </Text>
                </Card>
                {LEVELS.map(level => (
                  <LevelCard
                    key={level}
                    level={level}
                    count={data.by_level[level] || 0}
                    total={data.total}
                  />
                ))}
              </SimpleGrid>
              <AlertsCard alerts={data.alerts} staleDays={data.stale_days} />
              <Card withBorder radius="md" padding="lg">
                <Title order={4} mb="sm">
                  {t('metabolic.professional.patientsTitle')}
                </Title>
                <PatientsTable
                  rows={data.patients}
                  onOpen={openPatient}
                  opening={opening}
                />
              </Card>
              <Text size="xs" c="dimmed">
                {t('metabolic.professional.disclaimer')}
              </Text>
            </>
          )
        )}
      </Stack>
    </Container>
  );
}
