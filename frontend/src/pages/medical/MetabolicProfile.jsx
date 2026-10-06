import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Button,
  Card,
  Center,
  Checkbox,
  Container,
  Group,
  Loader,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { PageHeader } from '../../components';
import { usePatientWithStaticData } from '../../hooks/useGlobalData';
import metabolicApi from '../../services/api/metabolicApi';
import logger from '../../services/logger';

const HISTORY_FIELDS = [
  'has_diabetes',
  'has_prediabetes',
  'has_hypertension',
  'has_dyslipidemia',
  'has_fatty_liver',
  'has_obesity',
  'has_cardiovascular_disease',
  'family_diabetes',
];

const NUMBER_FIELDS = [
  { key: 'physical_activity_minutes_week', min: 0, max: 3000, step: 10 },
  { key: 'sitting_hours_day', min: 0, max: 24, step: 0.5, decimals: 1 },
  { key: 'sleep_hours', min: 0, max: 24, step: 0.5, decimals: 1 },
  { key: 'sugary_drinks_per_week', min: 0, max: 100, step: 1 },
  { key: 'ultraprocessed_per_week', min: 0, max: 100, step: 1 },
  { key: 'fruit_veg_servings_day', min: 0, max: 30, step: 1 },
];

const OPTIONS = {
  alcohol: ['none', 'occasional', 'weekly', 'daily'],
  smoking: ['never', 'former', 'current'],
};

const EMPTY = {
  ...Object.fromEntries(HISTORY_FIELDS.map(k => [k, false])),
  ...Object.fromEntries(NUMBER_FIELDS.map(f => [f.key, ''])),
  alcohol: null,
  smoking: null,
  musculoskeletal_limitations: '',
  pain_level: '',
  goals: '',
};

const toPayload = form => {
  const out = {};
  Object.entries(form).forEach(([k, v]) => {
    out[k] = v === '' ? null : v;
  });
  return out;
};

const MetabolicProfile = () => {
  const { t } = useTranslation('medical');
  const navigate = useNavigate();
  const { patient } = usePatientWithStaticData();
  const patientId = patient?.patient?.id;
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!patientId) return undefined;
    const controller = new AbortController();
    setLoading(true);
    metabolicApi
      .getProfile(patientId, controller.signal)
      .then(data => {
        if (controller.signal.aborted) return;
        const next = { ...EMPTY };
        Object.keys(EMPTY).forEach(k => {
          if (data?.[k] !== null && data?.[k] !== undefined) next[k] = data[k];
        });
        setForm(next);
      })
      .catch(err => {
        if (controller.signal.aborted) return;
        logger.error('metabolic_profile_load_failed', { error: err?.message });
        setError(
          t(
            'metabolic.profile.loadError',
            'Could not load the metabolic history.'
          )
        );
      })
      .finally(() => !controller.signal.aborted && setLoading(false));
    return () => controller.abort();
  }, [patientId, t]);

  const set = (key, value) => setForm(prev => ({ ...prev, [key]: value }));

  const save = async () => {
    setSaving(true);
    try {
      await metabolicApi.updateProfile(patientId, toPayload(form));
      notifications.show({
        color: 'teal',
        message: t('metabolic.profile.saved', 'Metabolic history saved'),
      });
      navigate('/metabolic-risk');
    } catch (err) {
      logger.error('metabolic_profile_save_failed', { error: err?.message });
      notifications.show({
        color: 'red',
        message: t(
          'metabolic.profile.saveError',
          'Could not save the metabolic history.'
        ),
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Container size="lg" py="md" className="silho-ir-page">
      <PageHeader
        title={t('metabolic.profile.title', 'Metabolic history')}
        icon="📋"
      />
      <Text c="dimmed" mt="md">
        {t(
          'metabolic.profile.subtitle',
          'Simple questions about your background and habits. They help calculate your metabolic risk.'
        )}
      </Text>
      {!patientId && (
        <Alert color="blue" mt="md">
          {t(
            'metabolic.selectPatient',
            'Select a patient to see their metabolic risk.'
          )}
        </Alert>
      )}
      {error && (
        <Alert color="red" mt="md">
          {error}
        </Alert>
      )}
      {loading ? (
        <Center py="xl">
          <Loader />
        </Center>
      ) : (
        patientId && (
          <Stack gap="lg" mt="md">
            <Card withBorder radius="lg" padding="lg">
              <Title order={4} mb="xs">
                {t(
                  'metabolic.profile.sections.history',
                  'Have you been told you have…?'
                )}
              </Title>
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                {HISTORY_FIELDS.map(key => (
                  <Checkbox
                    key={key}
                    label={t(`metabolic.profile.fields.${key}`, key)}
                    checked={!!form[key]}
                    onChange={e => set(key, e.currentTarget.checked)}
                  />
                ))}
              </SimpleGrid>
            </Card>

            <Card withBorder radius="lg" padding="lg">
              <Title order={4} mb="xs">
                {t('metabolic.profile.sections.habits', 'Your habits')}
              </Title>
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                {NUMBER_FIELDS.map(f => (
                  <NumberInput
                    key={f.key}
                    label={t(`metabolic.profile.fields.${f.key}`, f.key)}
                    min={f.min}
                    max={f.max}
                    step={f.step}
                    decimalScale={f.decimals || 0}
                    clampBehavior="none"
                    value={form[f.key]}
                    onChange={v => set(f.key, v)}
                    error={
                      form[f.key] !== '' &&
                      (form[f.key] < f.min || form[f.key] > f.max)
                        ? t(
                            'metabolic.profile.range',
                            'Between {{min}} and {{max}}',
                            f
                          )
                        : null
                    }
                  />
                ))}
                {Object.entries(OPTIONS).map(([key, values]) => (
                  <Select
                    key={key}
                    label={t(`metabolic.profile.fields.${key}`, key)}
                    data={values.map(v => ({
                      value: v,
                      label: t(`metabolic.profile.options.${key}.${v}`, v),
                    }))}
                    value={form[key]}
                    onChange={v => set(key, v)}
                    clearable
                  />
                ))}
              </SimpleGrid>
            </Card>

            <Card withBorder radius="lg" padding="lg">
              <Title order={4} mb="xs">
                {t(
                  'metabolic.profile.sections.limitations',
                  'Limitations and goals'
                )}
              </Title>
              <Stack gap="md">
                <Textarea
                  label={t(
                    'metabolic.profile.fields.musculoskeletal_limitations',
                    'Pain, injuries or physical limitations'
                  )}
                  autosize
                  minRows={2}
                  maxLength={2000}
                  value={form.musculoskeletal_limitations}
                  onChange={e =>
                    set('musculoskeletal_limitations', e.currentTarget.value)
                  }
                />
                <NumberInput
                  label={t(
                    'metabolic.profile.fields.pain_level',
                    'Usual pain level (0-10)'
                  )}
                  min={0}
                  max={10}
                  clampBehavior="none"
                  value={form.pain_level}
                  onChange={v => set('pain_level', v)}
                  error={
                    form.pain_level !== '' &&
                    (form.pain_level < 0 || form.pain_level > 10)
                      ? t(
                          'metabolic.profile.range',
                          'Between {{min}} and {{max}}',
                          {
                            min: 0,
                            max: 10,
                          }
                        )
                      : null
                  }
                />
                <Textarea
                  label={t(
                    'metabolic.profile.fields.goals',
                    'What would you like to achieve?'
                  )}
                  autosize
                  minRows={2}
                  maxLength={2000}
                  value={form.goals}
                  onChange={e => set('goals', e.currentTarget.value)}
                />
              </Stack>
            </Card>

            <Group justify="flex-end">
              <Button
                variant="default"
                onClick={() => navigate('/metabolic-risk')}
              >
                {t('metabolic.profile.cancel', 'Cancel')}
              </Button>
              <Button loading={saving} onClick={save}>
                {t('metabolic.profile.save', 'Save')}
              </Button>
            </Group>
          </Stack>
        )
      )}
    </Container>
  );
};

export default MetabolicProfile;
