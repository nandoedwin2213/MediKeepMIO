import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Accordion,
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Center,
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
import { IconPlus, IconTrash } from '@tabler/icons-react';
import AdminLayout from '../../components/admin/AdminLayout';
import metabolicApi from '../../services/api/metabolicApi';
import logger from '../../services/logger';
import { LEVEL_COLORS } from '../../utils/insulinResistance';

const LEVELS = ['low', 'normal', 'borderline', 'high', 'veryHigh'];
const RISK_LEVELS = ['favorable', 'initial', 'moderate', 'high'];
const OPS = ['>=', '>', '<=', '<'];
const SEXES = ['M', 'F'];

const num = v => (v === '' || v === undefined ? null : v);

function BandsEditor({ bands, onChange }) {
  const { t } = useTranslation(['admin', 'medical']);
  const update = (i, patch) =>
    onChange(bands.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  return (
    <Stack gap={6}>
      {bands.map((b, i) => (
        <Group key={i} gap="xs" wrap="nowrap" className="silho-mr-band-row">
          <Select
            w={150}
            size="xs"
            label={i === 0 ? t('metabolicSettings.level', 'Level') : undefined}
            data={LEVELS.map(l => ({
              value: l,
              label: t(`medical:insulinResistance.levels.${l}`, l),
            }))}
            value={b.level}
            onChange={v => update(i, { level: v })}
            leftSection={
              <span
                className="silho-ir-dot"
                style={{
                  background: `var(--mantine-color-${LEVEL_COLORS[b.level]}-6)`,
                }}
              />
            }
          />
          <NumberInput
            w={110}
            size="xs"
            label={
              i === 0 ? t('metabolicSettings.from', 'From (≥)') : undefined
            }
            placeholder="—"
            decimalScale={3}
            value={b.min ?? ''}
            onChange={v => update(i, { min: num(v) })}
          />
          <NumberInput
            w={110}
            size="xs"
            label={i === 0 ? t('metabolicSettings.to', 'Up to (<)') : undefined}
            placeholder="—"
            decimalScale={3}
            value={b.max ?? ''}
            onChange={v => update(i, { max: num(v) })}
          />
          <ActionIcon
            variant="subtle"
            color="red"
            aria-label={t('metabolicSettings.remove', 'Remove')}
            onClick={() => onChange(bands.filter((_, j) => j !== i))}
          >
            <IconTrash size={16} />
          </ActionIcon>
        </Group>
      ))}
      <Button
        size="xs"
        variant="subtle"
        w="fit-content"
        leftSection={<IconPlus size={14} />}
        onClick={() =>
          onChange([...bands, { level: 'normal', min: null, max: null }])
        }
      >
        {t('metabolicSettings.addBand', 'Add range')}
      </Button>
    </Stack>
  );
}

function IndicatorEditor({ indicator, onChange }) {
  const { t } = useTranslation(['admin', 'medical']);
  if (indicator.bands) {
    return (
      <BandsEditor
        bands={indicator.bands}
        onChange={bands => onChange({ ...indicator, bands })}
      />
    );
  }
  if (indicator.by_sex) {
    return (
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        {SEXES.map(sex => (
          <Stack key={sex} gap={4}>
            <Text size="sm" fw={600}>
              {t(`metabolicSettings.sex.${sex}`, sex)}
            </Text>
            <BandsEditor
              bands={indicator.by_sex[sex] || []}
              onChange={bands =>
                onChange({
                  ...indicator,
                  by_sex: { ...indicator.by_sex, [sex]: bands },
                })
              }
            />
          </Stack>
        ))}
      </SimpleGrid>
    );
  }
  return (
    <SimpleGrid cols={{ base: 1, sm: 2 }}>
      {Object.entries(indicator.map || {}).map(([option, level]) => (
        <Select
          key={option}
          size="xs"
          label={option}
          data={LEVELS.map(l => ({
            value: l,
            label: t(`medical:insulinResistance.levels.${l}`, l),
          }))}
          value={level}
          onChange={v =>
            onChange({ ...indicator, map: { ...indicator.map, [option]: v } })
          }
        />
      ))}
    </SimpleGrid>
  );
}

function ThresholdInput({ value, onChange, label }) {
  const { t } = useTranslation('admin');
  if (value && typeof value === 'object') {
    return (
      <Group gap="xs">
        {SEXES.map(sex => (
          <NumberInput
            key={sex}
            w={120}
            size="xs"
            label={`${label} · ${t(`metabolicSettings.sex.${sex}`, sex)}`}
            value={value[sex] ?? ''}
            onChange={v => onChange({ ...value, [sex]: num(v) })}
          />
        ))}
      </Group>
    );
  }
  return (
    <NumberInput
      w={140}
      size="xs"
      label={label}
      value={value ?? ''}
      onChange={v => onChange(num(v))}
    />
  );
}

const MetabolicSettings = () => {
  const { t } = useTranslation(['admin', 'medical']);
  const [meta, setMeta] = useState(null);
  const [config, setConfig] = useState(null);
  const [notes, setNotes] = useState('');
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    metabolicApi
      .getConfig(controller.signal)
      .then(data => {
        if (controller.signal.aborted) return;
        setMeta(data);
        setConfig(data.config);
      })
      .catch(err => {
        if (controller.signal.aborted) return;
        logger.error('metabolic_config_load_failed', { error: err?.message });
        setError(
          t(
            'metabolicSettings.loadError',
            'Could not load the clinical configuration.'
          )
        );
      });
    return () => controller.abort();
  }, [t]);

  const indicatorName = key => t(`medical:metabolic.indicators.${key}`, key);
  const setSection = (key, value) =>
    setConfig(prev => ({ ...prev, [key]: value }));

  const resetDefaults = async () => {
    try {
      const data = await metabolicApi.getDefaultConfig();
      setConfig(data.config);
    } catch (err) {
      logger.error('metabolic_default_config_failed', { error: err?.message });
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const data = await metabolicApi.updateConfig(config, notes || null);
      setMeta(data);
      setConfig(data.config);
      setNotes('');
      notifications.show({
        color: 'teal',
        message: t('metabolicSettings.saved', 'Saved as version {{version}}', {
          version: data.version,
        }),
      });
    } catch (err) {
      notifications.show({
        color: 'red',
        title: t(
          'metabolicSettings.saveError',
          'Could not save the configuration'
        ),
        message: err?.message,
      });
    } finally {
      setSaving(false);
    }
  };

  const syndrome = config?.metabolic_syndrome;

  return (
    <AdminLayout>
      <Stack gap="lg" p="md">
        <div>
          <Title order={2}>
            {t('metabolicSettings.title', 'Clinical configuration')}
          </Title>
          <Text c="dimmed" size="sm">
            {t(
              'metabolicSettings.subtitle',
              'Reference ranges, metabolic syndrome criteria, score weights and alert rules used by the metabolic risk engine. Each save creates a new version; previous evaluations keep the version they used.'
            )}
          </Text>
          {meta && (
            <Badge mt="xs" variant="light">
              {t('metabolicSettings.version', 'Active version: {{version}}', {
                version:
                  meta.version || t('metabolicSettings.defaults', 'defaults'),
              })}
            </Badge>
          )}
        </div>
        {error && <Alert color="red">{error}</Alert>}
        {!config && !error && (
          <Center py="xl">
            <Loader />
          </Center>
        )}
        {config && (
          <>
            <Card withBorder radius="lg">
              <Title order={4} mb="sm">
                {t('metabolicSettings.indicators', 'Reference ranges')}
              </Title>
              <Text size="xs" c="dimmed" mb="sm">
                {t(
                  'metabolicSettings.indicatorsHint',
                  'Each range includes the "from" value and goes up to, but not including, the "up to" value. Leave a field empty for no limit.'
                )}
              </Text>
              <Accordion variant="separated" multiple>
                {Object.entries(config.indicators).map(([key, indicator]) => (
                  <Accordion.Item key={key} value={key}>
                    <Accordion.Control>{indicatorName(key)}</Accordion.Control>
                    <Accordion.Panel>
                      <IndicatorEditor
                        indicator={indicator}
                        onChange={value =>
                          setSection('indicators', {
                            ...config.indicators,
                            [key]: value,
                          })
                        }
                      />
                    </Accordion.Panel>
                  </Accordion.Item>
                ))}
              </Accordion>
            </Card>

            <Card withBorder radius="lg">
              <Title order={4} mb="sm">
                {t('metabolicSettings.score', 'Metabolic score')}
              </Title>
              <Text size="sm" fw={600} mb={4}>
                {t('metabolicSettings.weights', 'Weight of each component')}
              </Text>
              <SimpleGrid cols={{ base: 2, sm: 3, md: 5 }} mb="md">
                {Object.entries(config.score_weights).map(([key, weight]) => (
                  <NumberInput
                    key={key}
                    size="xs"
                    min={0}
                    label={indicatorName(key)}
                    value={weight}
                    onChange={v =>
                      setSection('score_weights', {
                        ...config.score_weights,
                        [key]: v === '' ? 0 : v,
                      })
                    }
                  />
                ))}
              </SimpleGrid>
              <Text size="sm" fw={600} mb={4}>
                {t('metabolicSettings.points', 'Points per level (0-100)')}
              </Text>
              <SimpleGrid cols={{ base: 2, sm: 5 }} mb="md">
                {LEVELS.map(level => (
                  <NumberInput
                    key={level}
                    size="xs"
                    min={0}
                    max={100}
                    label={t(
                      `medical:insulinResistance.levels.${level}`,
                      level
                    )}
                    value={config.level_points[level]}
                    onChange={v =>
                      setSection('level_points', {
                        ...config.level_points,
                        [level]: v === '' ? 0 : v,
                      })
                    }
                  />
                ))}
              </SimpleGrid>
              <Text size="sm" fw={600} mb={4}>
                {t(
                  'metabolicSettings.riskBands',
                  'Score from which each risk level starts'
                )}
              </Text>
              <SimpleGrid cols={{ base: 2, sm: 5 }}>
                {RISK_LEVELS.map(level => {
                  const band = config.risk_bands.find(b => b.level === level);
                  return (
                    <NumberInput
                      key={level}
                      size="xs"
                      min={0}
                      max={100}
                      label={t(`medical:metabolic.risk.${level}`, level)}
                      value={band?.min ?? 0}
                      onChange={v =>
                        setSection(
                          'risk_bands',
                          config.risk_bands.map(b =>
                            b.level === level
                              ? { ...b, min: v === '' ? 0 : v }
                              : b
                          )
                        )
                      }
                    />
                  );
                })}
                <NumberInput
                  size="xs"
                  min={0}
                  max={100}
                  label={t(
                    'metabolicSettings.coverage',
                    'Minimum data coverage (%)'
                  )}
                  value={Math.round(config.score_min_coverage * 100)}
                  onChange={v =>
                    setSection('score_min_coverage', (v === '' ? 0 : v) / 100)
                  }
                />
              </SimpleGrid>
            </Card>

            <Card withBorder radius="lg">
              <Title order={4} mb="sm">
                {t('metabolicSettings.syndrome', 'Metabolic syndrome criteria')}
              </Title>
              <NumberInput
                w={220}
                size="xs"
                min={1}
                mb="sm"
                label={t('metabolicSettings.required', 'Criteria needed')}
                value={syndrome.required}
                onChange={v =>
                  setSection('metabolic_syndrome', {
                    ...syndrome,
                    required: v === '' ? 1 : v,
                  })
                }
              />
              <Stack gap="sm">
                {syndrome.criteria.map((criterion, ci) => {
                  const rules = criterion.any || [criterion];
                  const updateRule = (ri, patch) => {
                    const nextRules = rules.map((r, j) =>
                      j === ri ? { ...r, ...patch } : r
                    );
                    const next = criterion.any
                      ? { ...criterion, any: nextRules }
                      : { ...criterion, ...nextRules[0] };
                    setSection('metabolic_syndrome', {
                      ...syndrome,
                      criteria: syndrome.criteria.map((c, j) =>
                        j === ci ? next : c
                      ),
                    });
                  };
                  return (
                    <Group key={criterion.id} gap="md" align="flex-end">
                      <Text size="sm" fw={600} w={180}>
                        {t(
                          `medical:metabolic.syndrome.criteria.${criterion.id}`,
                          criterion.id
                        )}
                      </Text>
                      {rules.map((rule, ri) => (
                        <Group key={ri} gap="xs" align="flex-end">
                          <Select
                            w={80}
                            size="xs"
                            data={OPS}
                            value={rule.op}
                            onChange={v => updateRule(ri, { op: v })}
                          />
                          <ThresholdInput
                            label={indicatorName(rule.metric)}
                            value={rule.value}
                            onChange={v => updateRule(ri, { value: v })}
                          />
                        </Group>
                      ))}
                    </Group>
                  );
                })}
              </Stack>
            </Card>

            <Card withBorder radius="lg">
              <Title order={4} mb="xs">
                {t(
                  'metabolicSettings.alerts',
                  'Safety alerts ("Requires medical assessment")'
                )}
              </Title>
              <Stack gap={6}>
                {config.alerts.map((alert, i) => (
                  <Group key={i} gap="xs" align="flex-end" wrap="nowrap">
                    <Select
                      w={220}
                      size="xs"
                      data={Object.keys(config.indicators)
                        .filter(k => !config.indicators[k].map)
                        .map(k => ({ value: k, label: indicatorName(k) }))}
                      value={alert.metric}
                      onChange={v =>
                        setSection(
                          'alerts',
                          config.alerts.map((a, j) =>
                            j === i ? { ...a, metric: v } : a
                          )
                        )
                      }
                    />
                    <Select
                      w={80}
                      size="xs"
                      data={OPS}
                      value={alert.op}
                      onChange={v =>
                        setSection(
                          'alerts',
                          config.alerts.map((a, j) =>
                            j === i ? { ...a, op: v } : a
                          )
                        )
                      }
                    />
                    <NumberInput
                      w={120}
                      size="xs"
                      value={alert.value}
                      onChange={v =>
                        setSection(
                          'alerts',
                          config.alerts.map((a, j) =>
                            j === i ? { ...a, value: v === '' ? 0 : v } : a
                          )
                        )
                      }
                    />
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      aria-label={t('metabolicSettings.remove', 'Remove')}
                      onClick={() =>
                        setSection(
                          'alerts',
                          config.alerts.filter((_, j) => j !== i)
                        )
                      }
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                ))}
                <Button
                  size="xs"
                  variant="subtle"
                  w="fit-content"
                  leftSection={<IconPlus size={14} />}
                  onClick={() =>
                    setSection('alerts', [
                      ...config.alerts,
                      {
                        id: `custom_${Date.now()}`,
                        metric: 'glucose',
                        op: '>=',
                        value: 0,
                      },
                    ])
                  }
                >
                  {t('metabolicSettings.addAlert', 'Add alert')}
                </Button>
              </Stack>
            </Card>

            <Card withBorder radius="lg">
              <Textarea
                label={t(
                  'metabolicSettings.notes',
                  'Reason for the change (optional)'
                )}
                autosize
                minRows={2}
                maxLength={2000}
                value={notes}
                onChange={e => setNotes(e.currentTarget.value)}
              />
              <Group justify="space-between" mt="md">
                <Button variant="default" onClick={resetDefaults}>
                  {t('metabolicSettings.reset', 'Load default values')}
                </Button>
                <Button loading={saving} onClick={save}>
                  {t('metabolicSettings.save', 'Save new version')}
                </Button>
              </Group>
            </Card>
          </>
        )}
      </Stack>
    </AdminLayout>
  );
};

export default MetabolicSettings;
