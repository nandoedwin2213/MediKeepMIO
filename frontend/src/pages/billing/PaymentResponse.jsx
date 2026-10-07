import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PageHeader } from '../../components';
import {
  Alert,
  Button,
  Card,
  Container,
  Group,
  Loader,
  Stack,
  Title,
} from '@mantine/core';
import billingApi from '../../services/api/billingApi';
import { formatDay } from './Subscription';

const RESULT_COLORS = {
  success: 'green',
  pending: 'yellow',
  cancelled: 'gray',
  rejected: 'red',
  error: 'red',
};

function PaymentResponse() {
  const { t, i18n } = useTranslation('common');
  const [params] = useSearchParams();
  const [result, setResult] = useState(null);
  const started = useRef(false);

  const id = params.get('id');
  const clientTx = params.get('clientTransactionId');
  const cancelled = params.has('cancelled');

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (cancelled || !id || id === '0' || !clientTx) {
      setResult({ kind: 'cancelled' });
      return;
    }
    billingApi
      .confirm(id, clientTx)
      .then(data => {
        const status = data?.subscription?.status;
        if (status === 'active') {
          setResult({ kind: 'success', date: data.subscription.period_end });
        } else if (status === 'pending') {
          setResult({ kind: 'pending' });
        } else if (status === 'cancelled') {
          setResult({ kind: 'cancelled' });
        } else {
          setResult({ kind: 'rejected' });
        }
      })
      .catch(() => setResult({ kind: 'error' }));
  }, [cancelled, id, clientTx]);

  return (
    <Container size="lg" py="md">
      <PageHeader title={t('billing.title')} icon="💳" />
      <Card withBorder radius="lg" padding="xl" maw={640} mx="auto" mt="lg">
        <Stack gap="md">
          <Title order={2}>{t('billing.response.title')}</Title>
          {!result ? (
            <Group>
              <Loader size="sm" />
              {t('billing.response.confirming')}
            </Group>
          ) : (
            <Alert
              color={RESULT_COLORS[result.kind]}
              data-testid="payment-result"
            >
              {t(`billing.response.${result.kind}`, {
                date: formatDay(result.date, i18n.language),
              })}
            </Alert>
          )}
          {result && (
            <Group>
              {result.kind === 'success' ? (
                <Button
                  component={Link}
                  to="/my-metabolic-health"
                  color="primary"
                >
                  {t('billing.response.goProgram')}
                </Button>
              ) : null}
              <Button component={Link} to="/subscription" variant="default">
                {t('billing.response.backToPlans')}
              </Button>
            </Group>
          )}
        </Stack>
      </Card>
    </Container>
  );
}

export default PaymentResponse;
