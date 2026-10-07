import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Container,
  Group,
  List,
  Loader,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import {
  IconCheck,
  IconInfoCircle,
  IconShieldCheck,
} from '@tabler/icons-react';
import { PageHeader } from '../../components';
import billingApi from '../../services/api/billingApi';
import {
  formatMoney,
  monthlyEquivalent,
  PLAN_FEATURES,
  savingPercent,
} from '../../utils/billing';

export const STATUS_COLORS = {
  active: 'green',
  pending: 'yellow',
  cancelled: 'gray',
  rejected: 'red',
  error: 'red',
};

export function formatDay(value, locale) {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(
      new Date(value)
    );
  } catch {
    return value.slice(0, 10);
  }
}

function Subscription() {
  const { t, i18n } = useTranslation('common');
  const [me, setMe] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [accepted, setAccepted] = useState(false);
  const [paying, setPaying] = useState(null);
  const [error, setError] = useState('');
  const locale = i18n.language;

  const load = useCallback(
    async signal => {
      try {
        const [mine, plans] = await Promise.all([
          billingApi.getMine(signal),
          billingApi.getPlans(signal),
        ]);
        setMe(mine);
        setCatalog(plans);
      } catch {
        if (!signal?.aborted) setError(t('billing.checkoutError'));
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [t]
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const pay = async planId => {
    setError('');
    if (!accepted) {
      setError(t('billing.termsRequired'));
      return;
    }
    setPaying(planId);
    try {
      const out = await billingApi.checkout(planId);
      window.location.assign(out.redirect_url);
    } catch {
      setError(t('billing.checkoutError'));
      setPaying(null);
    }
  };

  if (loading) {
    return (
      <Container size="lg" py="xl">
        <Loader />
      </Container>
    );
  }

  const plans = catalog?.plans || [];
  const currency = catalog?.currency || 'USD';
  const active = me?.active;
  const canPay = Boolean(me?.configured) && !me?.exempt;

  return (
    <Container size="lg" py="md">
      <PageHeader title={t('billing.title')} icon="💳" />
      <Text c="dimmed" mt="md">
        {t('billing.subtitle')}
      </Text>

      <Stack mt="lg" gap="lg">
        {me?.exempt && (
          <Alert color="blue" icon={<IconInfoCircle size={18} />}>
            {t('billing.exempt')}
          </Alert>
        )}
        {!me?.configured && !me?.exempt && (
          <Alert color="primary" icon={<IconInfoCircle size={18} />}>
            {t('billing.notConfigured')}
          </Alert>
        )}

        <Card withBorder radius="md" padding="lg">
          {active ? (
            <Group justify="space-between" wrap="wrap">
              <div>
                <Title order={4}>{t('billing.activeTitle')}</Title>
                <Text mt={4}>
                  {t('billing.activeUntil', {
                    plan: t(`billing.plans.${active.plan}`, active.plan),
                    date: formatDay(active.period_end, locale),
                  })}
                </Text>
              </div>
              <Badge color="green" size="lg">
                {t('billing.status.active')}
              </Badge>
            </Group>
          ) : (
            <Text>{t('billing.noActive')}</Text>
          )}
        </Card>

        {canPay && (
          <>
            <div>
              <Title order={3}>{t('billing.choose')}</Title>
              {active && (
                <Text size="sm" c="dimmed" mt={4}>
                  {t('billing.extend')}
                </Text>
              )}
            </div>
            <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
              {plans.map(plan => {
                const saving = savingPercent(plan, plans);
                return (
                  <Card key={plan.id} withBorder radius="md" padding="lg">
                    <Stack gap="xs" h="100%">
                      <Group justify="space-between">
                        <Title order={4}>
                          {t(`billing.plans.${plan.id}`, plan.id)}
                        </Title>
                        {saving > 0 && (
                          <Badge color="teal">
                            {t('billing.saving', { percent: saving })}
                          </Badge>
                        )}
                      </Group>
                      <Text fz={30} fw={800}>
                        {formatMoney(plan.amount_cents, currency, locale)}
                      </Text>
                      <Text size="sm" c="dimmed">
                        {t(`billing.period.${plan.id}`, String(plan.months))}
                        {plan.months > 1 &&
                          ` · ${t('billing.perMonth', {
                            amount: formatMoney(
                              monthlyEquivalent(plan),
                              currency,
                              locale
                            ),
                          })}`}
                      </Text>
                      <List
                        size="sm"
                        spacing={4}
                        icon={<IconCheck size={14} color="#2f9e6e" />}
                        style={{ flex: 1 }}
                      >
                        {PLAN_FEATURES.map(feature => (
                          <List.Item key={feature}>
                            {t(`billing.features.${feature}`)}
                          </List.Item>
                        ))}
                      </List>
                      <Button
                        mt="sm"
                        color="primary"
                        loading={paying === plan.id}
                        disabled={Boolean(paying) && paying !== plan.id}
                        onClick={() => pay(plan.id)}
                      >
                        {paying === plan.id
                          ? t('billing.paying')
                          : t('billing.pay')}
                      </Button>
                    </Stack>
                  </Card>
                );
              })}
            </SimpleGrid>
            <Checkbox
              checked={accepted}
              onChange={event => setAccepted(event.currentTarget.checked)}
              label={t('billing.terms')}
            />
            <Group gap="xs">
              <IconShieldCheck size={18} color="#2f9e6e" />
              <Text size="sm" c="dimmed">
                {t('billing.secure')}
              </Text>
            </Group>
          </>
        )}

        {error && <Alert color="red">{error}</Alert>}

        <Card withBorder radius="md" padding="lg">
          <Title order={4} mb="sm">
            {t('billing.history')}
          </Title>
          {me?.history?.length ? (
            <Table.ScrollContainer minWidth={520}>
              <Table verticalSpacing="xs">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('billing.col.date')}</Table.Th>
                    <Table.Th>{t('billing.col.plan')}</Table.Th>
                    <Table.Th>{t('billing.col.amount')}</Table.Th>
                    <Table.Th>{t('billing.col.status')}</Table.Th>
                    <Table.Th>{t('billing.col.validUntil')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {me.history.map(row => (
                    <Table.Tr key={row.id}>
                      <Table.Td>{formatDay(row.created_at, locale)}</Table.Td>
                      <Table.Td>
                        {t(`billing.plans.${row.plan}`, row.plan)}
                      </Table.Td>
                      <Table.Td>
                        {formatMoney(row.amount_cents, row.currency, locale)}
                      </Table.Td>
                      <Table.Td>
                        <Badge color={STATUS_COLORS[row.status] || 'gray'}>
                          {t(`billing.status.${row.status}`, row.status)}
                        </Badge>
                      </Table.Td>
                      <Table.Td>{formatDay(row.period_end, locale)}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          ) : (
            <Text c="dimmed">{t('billing.noHistory')}</Text>
          )}
        </Card>
      </Stack>
    </Container>
  );
}

export default Subscription;
