import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  Alert,
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Checkbox,
  Container,
  Group,
  List,
  Loader,
  MultiSelect,
  NumberInput,
  Progress,
  SimpleGrid,
  Stack,
  TagsInput,
  Text,
  Textarea,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle,
  IconBan,
  IconCheck,
  IconCopy,
  IconDeviceFloppy,
  IconDroplet,
  IconFlame,
  IconSalad,
  IconSparkles,
  IconTarget,
  IconChefHat,
  IconToolsKitchen2,
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

const OPTIONS = {
  prioritize: [
    'vegetables',
    'legumes',
    'whole_grains',
    'fruit_whole',
    'oily_fish',
    'fish',
    'poultry',
    'eggs',
    'low_fat_dairy',
    'legumes_protein',
    'tofu_tempeh',
    'nuts_seeds',
    'olive_oil',
    'water',
  ],
  limit: [
    'sugary_drinks',
    'ultraprocessed',
    'refined_flours',
    'fried_foods',
    'processed_meat',
    'fruit_juice',
    'sweets',
    'alcohol',
    'saturated_fats',
    'added_salt',
    'salty_snacks',
    'fructose_drinks',
    'organ_meats',
  ],
  targets: [
    'sugary_drinks_zero',
    'fruit_veg_5',
    'ultraprocessed_down',
    'weight_5pct',
    'waist_down',
    'water_daily',
  ],
  safety: [
    'professional_review',
    'no_extreme_diets',
    'diabetes_meds',
    'renal_review',
    'allergy_check',
    'b12_review',
  ],
};

const STATUS_COLORS = { draft: 'yellow', approved: 'teal', archived: 'gray' };

function useNutritionT() {
  const { t } = useTranslation('medical');
  const n = (key, opts) => t(`metabolic.nutrition.${key}`, opts);
  const opt = (group, value) =>
    t(`metabolic.nutrition.options.${group}.${value}`, value);
  return { t, n, opt };
}

function macroGrams(macros, kcal) {
  if (!kcal) return null;
  const range = (lo, hi, perGram) => [
    Math.round((kcal * lo) / 100 / perGram),
    Math.round((kcal * hi) / 100 / perGram),
  ];
  return {
    carbs: range(macros.carbs_pct_min, macros.carbs_pct_max, 4),
    fat: range(macros.fat_pct_min, macros.fat_pct_max, 9),
  };
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

function Chips({ group, values, color, free }) {
  const { opt } = useNutritionT();
  if (!values?.length) return null;
  return (
    <Group gap={6}>
      {values.map(v => (
        <Badge key={v} variant="light" color={color} tt="none">
          {free ? v : opt(group, v)}
        </Badge>
      ))}
    </Group>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700}>{value}</Text>
    </div>
  );
}

function PlateModel() {
  const { n } = useNutritionT();
  return (
    <Box>
      <Progress.Root size={22} radius="xl">
        <Progress.Section value={50} color="teal">
          <Progress.Label>{n('plate.vegetables')}</Progress.Label>
        </Progress.Section>
        <Progress.Section value={25} color="orange">
          <Progress.Label>{n('plate.protein')}</Progress.Label>
        </Progress.Section>
        <Progress.Section value={25} color="yellow">
          <Progress.Label>{n('plate.carbs')}</Progress.Label>
        </Progress.Section>
      </Progress.Root>
      <Text size="xs" c="dimmed" mt={4}>
        {n('plate.help')}
      </Text>
    </Box>
  );
}

function Rationale({ keys }) {
  const { n } = useNutritionT();
  if (!keys?.length) return null;
  return (
    <Card withBorder radius="md" padding="md">
      <Group gap="xs" mb="xs">
        <IconSparkles size={16} />
        <Text fw={600} size="sm">
          {n('plan.why')}
        </Text>
      </Group>
      <List size="sm" spacing={2}>
        {keys.map(key => (
          <List.Item key={key}>{n(`rationale.${key}`)}</List.Item>
        ))}
      </List>
    </Card>
  );
}

function useRecipeOptions(enabled) {
  const [recipes, setRecipes] = useState([]);
  useEffect(() => {
    if (!enabled) return undefined;
    const controller = new AbortController();
    metabolicApi
      .getRecipes({}, controller.signal)
      .then(res => setRecipes(res || []))
      .catch(err => {
        if (!controller.signal.aborted) {
          logger.error('nutrition_recipes_load_failed', {
            error: err?.message,
          });
        }
      });
    return () => controller.abort();
  }, [enabled]);
  return recipes;
}

function AssignedRecipes({ ids }) {
  const { n } = useNutritionT();
  const recipes = useRecipeOptions(ids.length > 0);
  const assigned = recipes.filter(r => ids.includes(r.id));
  if (!assigned.length) return null;
  return (
    <SectionCard icon={IconChefHat} color="grape" title={n('sections.recipes')}>
      <List size="sm" spacing={4}>
        {assigned.map(r => (
          <List.Item key={r.id}>
            <Anchor component={Link} to={`/metabolic-recipes?recipe=${r.id}`}>
              {r.name}
            </Anchor>
          </List.Item>
        ))}
      </List>
    </SectionCard>
  );
}

function PlanView({ plan, rationale }) {
  const { n, opt } = useNutritionT();
  const { energy = {}, macros = {}, meals = {} } = plan;
  const grams = macroGrams(macros, energy.kcal_target);
  return (
    <Stack gap="md">
      {plan.safety?.length > 0 && (
        <Alert color="orange" icon={<IconAlertTriangle size={18} />}>
          <List size="sm" spacing={2}>
            {plan.safety.map(s => (
              <List.Item key={s}>{opt('safety', s)}</List.Item>
            ))}
          </List>
        </Alert>
      )}
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <SectionCard icon={IconFlame} color="red" title={n('sections.energy')}>
          {energy.kcal_target ? (
            <>
              <Text fz={28} fw={800} lh={1.1}>
                {`${energy.kcal_target} kcal`}
                <Text span size="sm" c="dimmed" fw={400}>
                  {' '}
                  {n('fields.perDay')}
                </Text>
              </Text>
              <Group gap="lg" mt="xs">
                {energy.deficit_kcal > 0 && (
                  <Stat
                    label={n('fields.deficit')}
                    value={`−${energy.deficit_kcal} kcal`}
                  />
                )}
                {energy.tdee_kcal && (
                  <Stat
                    label={n('fields.tdee')}
                    value={`${energy.tdee_kcal} kcal`}
                  />
                )}
              </Group>
            </>
          ) : (
            <Text size="sm" c="dimmed">
              {n('fields.noEnergy')}
            </Text>
          )}
          {energy.notes && (
            <Text size="sm" mt="xs">
              {energy.notes}
            </Text>
          )}
        </SectionCard>
        <SectionCard icon={IconSalad} color="teal" title={n('sections.macros')}>
          <SimpleGrid cols={2} spacing="xs">
            <Stat
              label={n('fields.protein')}
              value={
                macros.protein_g_min
                  ? `${macros.protein_g_min}–${macros.protein_g_max} g`
                  : `${macros.protein_g_kg_min}–${macros.protein_g_kg_max} g/kg`
              }
            />
            <Stat
              label={n('fields.carbs')}
              value={`${macros.carbs_pct_min}–${macros.carbs_pct_max}%${
                grams ? ` · ${grams.carbs[0]}–${grams.carbs[1]} g` : ''
              }`}
            />
            <Stat
              label={n('fields.fat')}
              value={`${macros.fat_pct_min}–${macros.fat_pct_max}%${
                grams ? ` · ${grams.fat[0]}–${grams.fat[1]} g` : ''
              }`}
            />
            <Stat
              label={n('fields.fiber')}
              value={`≥ ${macros.fiber_g_min} g`}
            />
            <Stat
              label={n('fields.sugar')}
              value={`≤ ${macros.added_sugar_g_max} g`}
            />
            <Stat
              label={n('fields.saturated')}
              value={`< ${macros.saturated_fat_pct_max}%`}
            />
            <Stat
              label={n('fields.sodium')}
              value={`≤ ${macros.sodium_mg_max} mg`}
            />
            {plan.hydration_l != null && (
              <Stat
                label={n('fields.hydration')}
                value={`${plan.hydration_l} L`}
              />
            )}
          </SimpleGrid>
          {macros.notes && (
            <Text size="sm" mt="xs">
              {macros.notes}
            </Text>
          )}
        </SectionCard>
      </SimpleGrid>
      <SectionCard
        icon={IconToolsKitchen2}
        color="orange"
        title={n('sections.meals')}
      >
        <Text size="sm">
          {n('fields.mealsSummary', {
            meals: meals.meals_per_day,
            snacks: meals.snacks_per_day,
          })}
        </Text>
        <List size="sm" spacing={2} mt="xs">
          {meals.protein_each_meal && (
            <List.Item>{n('fields.protein_each_meal')}</List.Item>
          )}
          {meals.regular_schedule && (
            <List.Item>{n('fields.regular_schedule')}</List.Item>
          )}
        </List>
        {meals.plate_model && (
          <Box mt="sm">
            <PlateModel />
          </Box>
        )}
        {meals.notes && (
          <Text size="sm" mt="xs">
            {meals.notes}
          </Text>
        )}
      </SectionCard>
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <SectionCard
          icon={IconCheck}
          color="teal"
          title={n('sections.prioritize')}
        >
          <Chips group="prioritize" values={plan.prioritize} color="teal" />
        </SectionCard>
        <SectionCard icon={IconBan} color="red" title={n('sections.limit')}>
          <Chips group="limit" values={plan.limit} color="red" />
        </SectionCard>
      </SimpleGrid>
      {(plan.avoid?.length > 0 || plan.dislikes?.length > 0) && (
        <SectionCard
          icon={IconAlertTriangle}
          color="grape"
          title={n('sections.avoid')}
        >
          <Chips values={plan.avoid} color="grape" free />
          {plan.dislikes?.length > 0 && (
            <>
              <Text size="xs" c="dimmed" mt="sm" mb={4}>
                {n('fields.dislikes')}
              </Text>
              <Chips values={plan.dislikes} color="gray" free />
            </>
          )}
        </SectionCard>
      )}
      {plan.targets?.length > 0 && (
        <SectionCard
          icon={IconTarget}
          color="blue"
          title={n('sections.targets')}
        >
          <List size="sm" spacing={2}>
            {plan.targets.map(v => (
              <List.Item key={v}>{opt('targets', v)}</List.Item>
            ))}
          </List>
        </SectionCard>
      )}
      <AssignedRecipes ids={plan.recipe_ids || []} />
      <Rationale keys={rationale} />
    </Stack>
  );
}

function Num({ label, value, onChange, min = 0, max, decimals = 0, step }) {
  return (
    <NumberInput
      label={label}
      value={value ?? ''}
      min={min}
      max={max}
      step={step}
      decimalScale={decimals}
      allowDecimal={decimals > 0}
      onChange={v => onChange(v === '' ? null : Number(v))}
    />
  );
}

function OptionSelect({ label, group, value, onChange }) {
  const { opt } = useNutritionT();
  const known = OPTIONS[group];
  const data = [...known, ...value.filter(v => !known.includes(v))].map(v => ({
    value: v,
    label: opt(group, v),
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

function PlanEditor({ value, onChange }) {
  const { n } = useNutritionT();
  const recipes = useRecipeOptions(true);
  const set = (section, key, v) =>
    onChange({ ...value, [section]: { ...value[section], [key]: v } });
  const setTop = (key, v) => onChange({ ...value, [key]: v });
  const { energy, macros, meals } = value;
  return (
    <Stack gap="md">
      <SectionCard icon={IconFlame} color="red" title={n('sections.energy')}>
        <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm">
          <Num
            label={n('fields.kcal')}
            value={energy.kcal_target}
            min={800}
            max={5000}
            step={50}
            onChange={v => set('energy', 'kcal_target', v)}
          />
          <Num
            label={n('fields.deficit')}
            value={energy.deficit_kcal}
            max={1500}
            step={50}
            onChange={v => set('energy', 'deficit_kcal', v ?? 0)}
          />
          <Num
            label={n('fields.hydration')}
            value={value.hydration_l}
            max={6}
            step={0.1}
            decimals={1}
            onChange={v => setTop('hydration_l', v)}
          />
        </SimpleGrid>
      </SectionCard>
      <SectionCard icon={IconSalad} color="teal" title={n('sections.macros')}>
        <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
          <Num
            label={n('fields.proteinKgMin')}
            value={macros.protein_g_kg_min}
            min={0.5}
            max={2.5}
            step={0.1}
            decimals={1}
            onChange={v => set('macros', 'protein_g_kg_min', v)}
          />
          <Num
            label={n('fields.proteinKgMax')}
            value={macros.protein_g_kg_max}
            min={0.5}
            max={2.5}
            step={0.1}
            decimals={1}
            onChange={v => set('macros', 'protein_g_kg_max', v)}
          />
          <Num
            label={n('fields.proteinGMin')}
            value={macros.protein_g_min}
            max={400}
            onChange={v => set('macros', 'protein_g_min', v)}
          />
          <Num
            label={n('fields.proteinGMax')}
            value={macros.protein_g_max}
            max={400}
            onChange={v => set('macros', 'protein_g_max', v)}
          />
          <Num
            label={n('fields.carbsMin')}
            value={macros.carbs_pct_min}
            min={10}
            max={70}
            onChange={v => set('macros', 'carbs_pct_min', v)}
          />
          <Num
            label={n('fields.carbsMax')}
            value={macros.carbs_pct_max}
            min={10}
            max={70}
            onChange={v => set('macros', 'carbs_pct_max', v)}
          />
          <Num
            label={n('fields.fatMin')}
            value={macros.fat_pct_min}
            min={15}
            max={50}
            onChange={v => set('macros', 'fat_pct_min', v)}
          />
          <Num
            label={n('fields.fatMax')}
            value={macros.fat_pct_max}
            min={15}
            max={50}
            onChange={v => set('macros', 'fat_pct_max', v)}
          />
          <Num
            label={n('fields.fiber')}
            value={macros.fiber_g_min}
            min={10}
            max={80}
            onChange={v => set('macros', 'fiber_g_min', v)}
          />
          <Num
            label={n('fields.sugar')}
            value={macros.added_sugar_g_max}
            max={100}
            onChange={v => set('macros', 'added_sugar_g_max', v)}
          />
          <Num
            label={n('fields.saturated')}
            value={macros.saturated_fat_pct_max}
            min={3}
            max={15}
            onChange={v => set('macros', 'saturated_fat_pct_max', v)}
          />
          <Num
            label={n('fields.sodium')}
            value={macros.sodium_mg_max}
            min={500}
            max={5000}
            step={100}
            onChange={v => set('macros', 'sodium_mg_max', v)}
          />
        </SimpleGrid>
      </SectionCard>
      <SectionCard
        icon={IconToolsKitchen2}
        color="orange"
        title={n('sections.meals')}
      >
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
          <Num
            label={n('fields.meals_per_day')}
            value={meals.meals_per_day}
            min={1}
            max={8}
            onChange={v => set('meals', 'meals_per_day', v ?? 3)}
          />
          <Num
            label={n('fields.snacks_per_day')}
            value={meals.snacks_per_day}
            max={4}
            onChange={v => set('meals', 'snacks_per_day', v ?? 0)}
          />
        </SimpleGrid>
        <Group gap="lg" mt="sm">
          {['plate_model', 'protein_each_meal', 'regular_schedule'].map(k => (
            <Checkbox
              key={k}
              label={n(`fields.${k}`)}
              checked={!!meals[k]}
              onChange={e => set('meals', k, e.currentTarget.checked)}
            />
          ))}
        </Group>
      </SectionCard>
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <OptionSelect
          label={n('sections.prioritize')}
          group="prioritize"
          value={value.prioritize}
          onChange={v => setTop('prioritize', v)}
        />
        <OptionSelect
          label={n('sections.limit')}
          group="limit"
          value={value.limit}
          onChange={v => setTop('limit', v)}
        />
        <TagsInput
          label={n('sections.avoid')}
          description={n('fields.avoidHelp')}
          value={value.avoid}
          onChange={v => setTop('avoid', v)}
          maxTags={30}
          clearable
        />
        <TagsInput
          label={n('fields.dislikes')}
          value={value.dislikes}
          onChange={v => setTop('dislikes', v)}
          maxTags={30}
          clearable
        />
        <OptionSelect
          label={n('sections.targets')}
          group="targets"
          value={value.targets}
          onChange={v => setTop('targets', v)}
        />
        <OptionSelect
          label={n('sections.safety')}
          group="safety"
          value={value.safety}
          onChange={v => setTop('safety', v)}
        />
        <MultiSelect
          label={n('sections.recipes')}
          description={n('fields.recipesHelp')}
          data={recipes.map(r => ({ value: String(r.id), label: r.name }))}
          value={(value.recipe_ids || []).map(String)}
          onChange={v => setTop('recipe_ids', v.map(Number))}
          searchable
          clearable
          maxValues={40}
        />
      </SimpleGrid>
    </Stack>
  );
}

function ProfessionalPlans({ patientId, formatDate }) {
  const { n } = useNutritionT();
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
          (await metabolicApi.getNutritionPlans(patientId, signal)) || [];
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
        logger.error('nutrition_plans_load_failed', { error: err?.message });
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
      notifications.show({ color: 'teal', message: n(successKey) });
      await load(undefined, res?.id ?? selectedId);
    } catch (err) {
      logger.error('nutrition_plan_action_failed', {
        action: name,
        error: err?.message,
      });
      notifications.show({ color: 'red', message: n('error') });
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
          <ThemeIcon variant="light" size="lg" radius="md" color="teal">
            <IconSalad size={20} />
          </ThemeIcon>
          <div>
            <Title order={3}>{n('plan.title')}</Title>
            <Text size="sm" c="dimmed">
              {n('plan.subtitlePro')}
            </Text>
          </div>
        </Group>
        <Button
          leftSection={<IconSparkles size={16} />}
          loading={busy === 'generate'}
          onClick={() =>
            run(
              'generate',
              () => metabolicApi.generateNutritionPlan(patientId),
              'plan.generated'
            )
          }
        >
          {n('plan.generate')}
        </Button>
      </Group>

      {loading ? (
        <Center py="lg">
          <Loader />
        </Center>
      ) : error ? (
        <Alert color="red" mt="md">
          {n('loadError')}
        </Alert>
      ) : !plans.length ? (
        <Text c="dimmed" mt="md">
          {n('plan.noneProfessional')}
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
                    {n(`plan.status.${p.status}`)}
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
                  {n('plan.approvedOn', {
                    date: formatDate(selected.approved_at),
                  })}
                </Text>
              )}
              {selected.status === 'draft' ? (
                <>
                  <Alert color="yellow" mb="md">
                    {n('plan.draftNotice')}
                  </Alert>
                  <Box mb="md">
                    <Rationale keys={selected.rationale} />
                  </Box>
                  <PlanEditor value={draft} onChange={setDraft} />
                  <Textarea
                    mt="md"
                    label={n('plan.notes')}
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
                            metabolicApi.deleteNutritionPlan(
                              patientId,
                              selected.id
                            ),
                          'plan.deleted'
                        )
                      }
                    >
                      {n('plan.delete')}
                    </Button>
                    <Button
                      variant="default"
                      leftSection={<IconDeviceFloppy size={16} />}
                      loading={busy === 'save'}
                      onClick={() =>
                        run(
                          'save',
                          () =>
                            metabolicApi.updateNutritionPlan(
                              patientId,
                              selected.id,
                              body
                            ),
                          'plan.saved'
                        )
                      }
                    >
                      {n('plan.save')}
                    </Button>
                    <Button
                      color="teal"
                      leftSection={<IconCheck size={16} />}
                      loading={busy === 'approve'}
                      onClick={() =>
                        run(
                          'approve',
                          async () => {
                            await metabolicApi.updateNutritionPlan(
                              patientId,
                              selected.id,
                              body
                            );
                            return metabolicApi.approveNutritionPlan(
                              patientId,
                              selected.id
                            );
                          },
                          'plan.approved'
                        )
                      }
                    >
                      {n('plan.approve')}
                    </Button>
                  </Group>
                </>
              ) : (
                <>
                  <PlanView
                    plan={selected.plan}
                    rationale={selected.rationale}
                  />
                  {selected.notes && (
                    <Text size="sm" mt="sm" style={{ whiteSpace: 'pre-wrap' }}>
                      {selected.notes}
                    </Text>
                  )}
                  <Group justify="flex-end" mt="md">
                    <Button
                      variant="default"
                      leftSection={<IconCopy size={16} />}
                      loading={busy === 'copy'}
                      onClick={() =>
                        run(
                          'copy',
                          () =>
                            metabolicApi.createNutritionPlan(patientId, {
                              plan: selected.plan,
                              notes: selected.notes,
                            }),
                          'plan.copied'
                        )
                      }
                    >
                      {n('plan.newVersion')}
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
  const { n } = useNutritionT();
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(false);
    metabolicApi
      .getNutritionPlans(patientId, controller.signal)
      .then(res =>
        setPlan((res || []).find(p => p.status === 'approved') || null)
      )
      .catch(err => {
        if (controller.signal.aborted) return;
        logger.error('nutrition_plan_load_failed', { error: err?.message });
        setError(true);
      })
      .finally(() => !controller.signal.aborted && setLoading(false));
    return () => controller.abort();
  }, [patientId]);

  return (
    <Card withBorder radius="lg" padding="lg">
      <Group gap="sm" mb="md">
        <ThemeIcon variant="light" size="lg" radius="md" color="teal">
          <IconSalad size={20} />
        </ThemeIcon>
        <div>
          <Title order={3}>{n('plan.titlePatient')}</Title>
          {plan?.approved_at && (
            <Text size="sm" c="dimmed">
              {n('plan.approvedOn', { date: formatDate(plan.approved_at) })}
            </Text>
          )}
        </div>
      </Group>
      {loading ? (
        <Center py="lg">
          <Loader />
        </Center>
      ) : error ? (
        <Alert color="red">{n('loadError')}</Alert>
      ) : !plan ? (
        <Text c="dimmed">{n('plan.none')}</Text>
      ) : (
        <>
          <PlanView plan={plan.plan} />
          {plan.notes && (
            <Text size="sm" mt="sm" style={{ whiteSpace: 'pre-wrap' }}>
              {plan.notes}
            </Text>
          )}
        </>
      )}
    </Card>
  );
}

export default function MetabolicNutrition() {
  const { n, t } = useNutritionT();
  const { patient } = usePatientWithStaticData();
  const { user } = useAuth();
  const { formatDate } = useDateFormat();
  const patientId = patient?.patient?.id;
  const professional = PRO_ROLES.includes(user?.role);

  return (
    <Container size="xl" py="md" className="silho-ir-page">
      <PageHeader title={n('title')} icon="🥗" />
      <Text c="dimmed" mt="md">
        {n('subtitle')}
      </Text>
      <Alert
        color="blue"
        variant="light"
        mt="md"
        icon={<IconDroplet size={18} />}
      >
        {n('disclaimer')}
      </Alert>
      {!patientId ? (
        <Alert color="blue" mt="md">
          {t('metabolic.selectPatient')}
        </Alert>
      ) : (
        <Stack gap="lg" mt="lg">
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
