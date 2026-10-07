import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import PageHeader from '../layout/PageHeader';
import {
  Button,
  Card,
  Center,
  Container,
  List,
  Loader,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconCheck, IconLock } from '@tabler/icons-react';
import billingApi from '../../services/api/billingApi';
import { PLAN_FEATURES } from '../../utils/billing';

function SubscriptionGate({ children }) {
  const { t } = useTranslation('common');
  const [state, setState] = useState({ loading: true, hasAccess: true });

  useEffect(() => {
    const controller = new AbortController();
    billingApi
      .getMine(controller.signal)
      .then(data =>
        setState({ loading: false, hasAccess: data?.has_access !== false })
      )
      .catch(() => {
        if (!controller.signal.aborted) {
          setState({ loading: false, hasAccess: true });
        }
      });
    return () => controller.abort();
  }, []);

  if (state.loading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  if (state.hasAccess) return children;

  return (
    <Container size="xl" py="md">
      <PageHeader title={t('billing.title')} icon="💳" />
      <Card
        withBorder
        radius="lg"
        padding="xl"
        maw={640}
        mx="auto"
        mt="lg"
        data-testid="subscription-gate"
      >
        <Stack align="center" gap="md">
          <IconLock size={40} color="var(--silho-gold, #c9a45c)" />
          <Title order={2} ta="center">
            {t('billing.gate.title')}
          </Title>
          <Text ta="center" c="dimmed">
            {t('billing.gate.text')}
          </Text>
          <List spacing="xs" icon={<IconCheck size={16} color="#2f9e6e" />}>
            {PLAN_FEATURES.map(feature => (
              <List.Item key={feature}>
                {t(`billing.features.${feature}`)}
              </List.Item>
            ))}
          </List>
          <Button component={Link} to="/subscription" size="md" color="primary">
            {t('billing.gate.cta')}
          </Button>
        </Stack>
      </Card>
    </Container>
  );
}

export default SubscriptionGate;
