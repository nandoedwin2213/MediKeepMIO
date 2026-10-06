import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import {
  Alert,
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Checkbox,
  Chip,
  Container,
  Group,
  Image,
  List,
  Loader,
  Modal,
  MultiSelect,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconClock,
  IconEdit,
  IconEyeOff,
  IconFlame,
  IconPlus,
  IconSearch,
  IconSparkles,
  IconToolsKitchen2,
  IconTrash,
  IconUserCheck,
} from '@tabler/icons-react';
import { PageHeader } from '../../components';
import { useAuth } from '../../contexts/AuthContext';
import { usePatientWithStaticData } from '../../hooks/useGlobalData';
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
const CATEGORIES = ['breakfast', 'lunch', 'dinner', 'snack', 'drink'];
const CATEGORY_COLORS = {
  breakfast: 'yellow',
  lunch: 'teal',
  dinner: 'indigo',
  snack: 'orange',
  drink: 'cyan',
};
const DIETS = ['omnivore', 'pescatarian', 'vegetarian', 'vegan', 'other'];
const ALLERGENS = [
  'gluten',
  'lactose',
  'egg',
  'fish',
  'shellfish',
  'nuts',
  'peanut',
  'soy',
  'sesame',
];
const TAGS = [
  'high_fiber',
  'high_protein',
  'low_gi',
  'omega3',
  'low_sodium',
  'no_added_sugar',
  'low_fat',
  'quick',
];
const EMPTY = {
  name: '',
  category: 'lunch',
  description: '',
  servings: 1,
  prep_minutes: null,
  kcal: null,
  protein_g: null,
  carbs_g: null,
  fat_g: null,
  fiber_g: null,
  diets: ['omnivore', 'other'],
  allergens: [],
  tags: [],
  ingredients: [],
  steps: [],
  image_url: '',
  image_credit: '',
  image_source_url: '',
  is_active: true,
};

function useRecipesT() {
  const { t, i18n } = useTranslation('medical');
  const r = (key, opts) => t(`metabolic.recipes.${key}`, opts);
  return { t, r, lang: i18n.language };
}

const round = v => (v == null ? '–' : Math.round(v));

function RecipeImage({ recipe, h }) {
  if (!recipe.image_url) {
    return (
      <Center
        h={h}
        bg={`var(--mantine-color-${CATEGORY_COLORS[recipe.category] || 'gray'}-light)`}
      >
        <IconToolsKitchen2 size={40} opacity={0.6} />
      </Center>
    );
  }
  return <Image src={recipe.image_url} h={h} fit="cover" alt={recipe.name} />;
}

function Macros({ recipe }) {
  const { r } = useRecipesT();
  const items = [
    ['protein', recipe.protein_g],
    ['carbs', recipe.carbs_g],
    ['fat', recipe.fat_g],
    ['fiber', recipe.fiber_g],
  ];
  return (
    <Group gap={6} wrap="wrap">
      {items.map(([key, v]) => (
        <Badge key={key} variant="light" color="gray" size="sm" radius="sm">
          {`${r(`macros.${key}`)} ${round(v)} g`}
        </Badge>
      ))}
    </Group>
  );
}

function RecipeCard({ recipe, rec, onOpen }) {
  const { r } = useRecipesT();
  return (
    <Card
      withBorder
      radius="lg"
      padding={0}
      onClick={() => onOpen(recipe)}
      style={{ cursor: 'pointer' }}
      data-testid={`recipe-card-${recipe.slug}`}
    >
      <RecipeImage recipe={recipe} h={150} />
      <Box p="md" pt="sm">
        <Group gap={6} wrap="wrap">
          <Badge
            color={CATEGORY_COLORS[recipe.category] || 'gray'}
            variant="light"
            size="sm"
          >
            {r(`categories.${recipe.category}`)}
          </Badge>
          {rec?.assigned && (
            <Badge
              color="grape"
              size="sm"
              leftSection={<IconUserCheck size={12} />}
            >
              {r('recommended.assigned')}
            </Badge>
          )}
          {!recipe.is_active && (
            <Badge
              color="gray"
              size="sm"
              leftSection={<IconEyeOff size={12} />}
            >
              {r('library.hiddenBadge')}
            </Badge>
          )}
        </Group>
        <Text fw={700} mt={6} lineClamp={2}>
          {recipe.name}
        </Text>
        <Group gap="md" mt={4} c="dimmed">
          <Group gap={4}>
            <IconFlame size={14} />
            <Text size="sm">
              {r('card.kcal', { kcal: round(recipe.kcal) })}
            </Text>
          </Group>
          {recipe.prep_minutes != null && (
            <Group gap={4}>
              <IconClock size={14} />
              <Text size="sm">
                {r('card.minutes', { minutes: recipe.prep_minutes })}
              </Text>
            </Group>
          )}
        </Group>
        <Box mt="xs">
          <Macros recipe={recipe} />
        </Box>
        {rec?.reasons?.length > 0 && (
          <Group gap={4} mt="xs" wrap="wrap">
            {rec.reasons.slice(0, 3).map(tag => (
              <Badge key={tag} color="teal" variant="dot" size="sm">
                {r(`tags.${tag}`)}
              </Badge>
            ))}
          </Group>
        )}
        {rec?.conflicts?.length > 0 && (
          <Text size="xs" c="orange" mt="xs">
            {r('recommended.conflict', {
              items: rec.conflicts
                .map(c =>
                  ALLERGENS.includes(c)
                    ? r(`allergens.${c}`)
                    : r(`recommended.conflicts.${c}`)
                )
                .join(', '),
            })}
          </Text>
        )}
      </Box>
    </Card>
  );
}

function RecipeDetail({ recipe, professional, onClose, onEdit, onRemove }) {
  const { r } = useRecipesT();
  if (!recipe) return null;
  const stats = [
    ['kcal', `${round(recipe.kcal)} kcal`],
    ['protein', `${round(recipe.protein_g)} g`],
    ['carbs', `${round(recipe.carbs_g)} g`],
    ['fat', `${round(recipe.fat_g)} g`],
    ['fiber', `${round(recipe.fiber_g)} g`],
  ];
  return (
    <Modal
      opened
      onClose={onClose}
      size="lg"
      radius="lg"
      title={<Text fw={700}>{recipe.name}</Text>}
    >
      <Stack gap="md">
        <Box style={{ borderRadius: 12, overflow: 'hidden' }}>
          <RecipeImage recipe={recipe} h={240} />
        </Box>
        {recipe.image_credit && (
          <Text size="xs" c="dimmed" mt={-8}>
            {r('detail.photo')}{' '}
            {recipe.image_source_url ? (
              <Anchor
                href={recipe.image_source_url}
                target="_blank"
                rel="noopener noreferrer"
                size="xs"
              >
                {recipe.image_credit}
              </Anchor>
            ) : (
              recipe.image_credit
            )}
          </Text>
        )}
        {recipe.description && <Text>{recipe.description}</Text>}
        <div>
          <Text size="sm" c="dimmed" mb={4}>
            {r('detail.perServing', { servings: recipe.servings })}
          </Text>
          <SimpleGrid cols={{ base: 3, sm: 5 }} spacing="xs">
            {stats.map(([key, v]) => (
              <Card key={key} withBorder radius="md" padding="xs">
                <Text size="xs" c="dimmed">
                  {r(`macros.${key}`)}
                </Text>
                <Text fw={700}>{v}</Text>
              </Card>
            ))}
          </SimpleGrid>
        </div>
        <Group gap={6} wrap="wrap">
          {recipe.prep_minutes != null && (
            <Badge variant="light" leftSection={<IconClock size={12} />}>
              {r('card.minutes', { minutes: recipe.prep_minutes })}
            </Badge>
          )}
          {recipe.tags.map(tag => (
            <Badge key={tag} color="teal" variant="light">
              {r(`tags.${tag}`)}
            </Badge>
          ))}
        </Group>
        <Text size="sm">
          <Text span fw={600}>
            {r('detail.suitable')}
          </Text>{' '}
          {recipe.diets
            .filter(d => d !== 'other')
            .map(d => r(`diets.${d}`))
            .join(', ')}
        </Text>
        {recipe.allergens.length > 0 && (
          <Group gap={6}>
            <Text size="sm" fw={600}>
              {r('detail.contains')}
            </Text>
            {recipe.allergens.map(a => (
              <Badge key={a} color="orange" variant="light">
                {r(`allergens.${a}`)}
              </Badge>
            ))}
          </Group>
        )}
        <div>
          <Title order={5} mb={6}>
            {r('detail.ingredients')}
          </Title>
          <List size="sm" spacing={4}>
            {recipe.ingredients.map((line, i) => (
              <List.Item key={i}>{line}</List.Item>
            ))}
          </List>
        </div>
        <div>
          <Title order={5} mb={6}>
            {r('detail.steps')}
          </Title>
          <List type="ordered" size="sm" spacing={6}>
            {recipe.steps.map((line, i) => (
              <List.Item key={i}>{line}</List.Item>
            ))}
          </List>
        </div>
        {professional && (
          <Group justify="flex-end" gap="sm">
            <Button
              variant="light"
              color="red"
              leftSection={
                recipe.is_library ? (
                  <IconEyeOff size={16} />
                ) : (
                  <IconTrash size={16} />
                )
              }
              onClick={() => onRemove(recipe)}
            >
              {recipe.is_library ? r('detail.hide') : r('detail.delete')}
            </Button>
            <Button
              leftSection={<IconEdit size={16} />}
              onClick={() => onEdit(recipe)}
            >
              {r('detail.edit')}
            </Button>
          </Group>
        )}
      </Stack>
    </Modal>
  );
}

function RecipeEditor({ initial, onClose, onSaved }) {
  const { r } = useRecipesT();
  const [form, setForm] = useState(() => ({
    ...EMPTY,
    ...(initial || {}),
    ingredientsText: (initial?.ingredients || []).join('\n'),
    stepsText: (initial?.steps || []).join('\n'),
  }));
  const [saving, setSaving] = useState(false);
  const set = (key, value) => setForm(f => ({ ...f, [key]: value }));
  const lines = text =>
    text
      .split('\n')
      .map(s => s.trim())
      .filter(Boolean);
  const options = (values, group) =>
    values.map(v => ({ value: v, label: r(`${group}.${v}`) }));
  const num = (key, label, max, decimals = 0) => (
    <NumberInput
      label={label}
      value={form[key] ?? ''}
      onChange={v => set(key, v === '' ? null : Number(v))}
      min={0}
      max={max}
      decimalScale={decimals}
      clampBehavior="none"
    />
  );

  const save = async () => {
    setSaving(true);
    const body = {
      name: form.name.trim(),
      category: form.category,
      description: form.description?.trim() || null,
      servings: form.servings || 1,
      prep_minutes: form.prep_minutes,
      kcal: form.kcal,
      protein_g: form.protein_g,
      carbs_g: form.carbs_g,
      fat_g: form.fat_g,
      fiber_g: form.fiber_g,
      diets: form.diets,
      allergens: form.allergens,
      tags: form.tags,
      ingredients: lines(form.ingredientsText),
      steps: lines(form.stepsText),
      image_url: form.image_url?.trim() || null,
      image_credit: form.image_credit?.trim() || null,
      image_source_url: form.image_source_url?.trim() || null,
      is_active: form.is_active,
    };
    try {
      const res = initial?.id
        ? await metabolicApi.updateRecipe(initial.id, body)
        : await metabolicApi.createRecipe(body);
      notifications.show({ color: 'teal', message: r('saved') });
      onSaved(res);
    } catch (err) {
      logger.error('recipe_save_failed', { error: err?.message });
      notifications.show({ color: 'red', message: r('error') });
    } finally {
      setSaving(false);
    }
  };

  const valid =
    form.name.trim().length >= 2 &&
    lines(form.ingredientsText).length > 0 &&
    lines(form.stepsText).length > 0;

  return (
    <Modal
      opened
      onClose={onClose}
      size="xl"
      radius="lg"
      title={
        <Text fw={700}>
          {initial?.id ? r('editor.editTitle') : r('editor.newTitle')}
        </Text>
      }
    >
      <Stack gap="sm">
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
          <TextInput
            label={r('editor.name')}
            value={form.name}
            onChange={e => set('name', e.currentTarget.value)}
            maxLength={150}
            required
          />
          <Select
            label={r('editor.category')}
            data={options(CATEGORIES, 'categories')}
            value={form.category}
            onChange={v => v && set('category', v)}
            allowDeselect={false}
          />
        </SimpleGrid>
        <Textarea
          label={r('editor.description')}
          value={form.description || ''}
          onChange={e => set('description', e.currentTarget.value)}
          autosize
          minRows={2}
          maxLength={1000}
        />
        <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
          {num('servings', r('editor.servings'), 20)}
          {num('prep_minutes', r('editor.prepMinutes'), 600)}
          {num('kcal', r('macros.kcal'), 3000)}
          {num('protein_g', `${r('macros.protein')} (g)`, 300, 1)}
          {num('carbs_g', `${r('macros.carbs')} (g)`, 500, 1)}
          {num('fat_g', `${r('macros.fat')} (g)`, 300, 1)}
          {num('fiber_g', `${r('macros.fiber')} (g)`, 100, 1)}
        </SimpleGrid>
        <Text size="xs" c="dimmed">
          {r('editor.perServingHelp')}
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm">
          <MultiSelect
            label={r('editor.diets')}
            data={options(DIETS, 'diets')}
            value={form.diets}
            onChange={v => set('diets', v)}
          />
          <MultiSelect
            label={r('editor.allergens')}
            data={options(ALLERGENS, 'allergens')}
            value={form.allergens}
            onChange={v => set('allergens', v)}
          />
          <MultiSelect
            label={r('editor.tags')}
            data={options(TAGS, 'tags')}
            value={form.tags}
            onChange={v => set('tags', v)}
          />
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
          <Textarea
            label={r('editor.ingredients')}
            value={form.ingredientsText}
            onChange={e => set('ingredientsText', e.currentTarget.value)}
            autosize
            minRows={5}
            required
          />
          <Textarea
            label={r('editor.steps')}
            value={form.stepsText}
            onChange={e => set('stepsText', e.currentTarget.value)}
            autosize
            minRows={5}
            required
          />
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm">
          <TextInput
            label={r('editor.imageUrl')}
            placeholder="https://"
            value={form.image_url || ''}
            onChange={e => set('image_url', e.currentTarget.value)}
          />
          <TextInput
            label={r('editor.imageCredit')}
            value={form.image_credit || ''}
            onChange={e => set('image_credit', e.currentTarget.value)}
          />
          <TextInput
            label={r('editor.imageSource')}
            placeholder="https://"
            value={form.image_source_url || ''}
            onChange={e => set('image_source_url', e.currentTarget.value)}
          />
        </SimpleGrid>
        <Checkbox
          label={r('editor.active')}
          checked={form.is_active}
          onChange={e => set('is_active', e.currentTarget.checked)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {r('editor.cancel')}
          </Button>
          <Button onClick={save} loading={saving} disabled={!valid}>
            {r('editor.save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function Recommended({ patientId, refreshKey, onOpen }) {
  const { r } = useRecipesT();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(false);
    metabolicApi
      .getRecommendedRecipes(patientId, { limit: 6 }, controller.signal)
      .then(setData)
      .catch(err => {
        if (controller.signal.aborted) return;
        logger.error('recipes_recommended_failed', { error: err?.message });
        setError(true);
      })
      .finally(() => !controller.signal.aborted && setLoading(false));
    return () => controller.abort();
  }, [patientId, refreshKey]);

  const excluded = data
    ? Object.values(data.excluded || {}).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <Card withBorder radius="lg" padding="lg" data-testid="recipes-recommended">
      <Group gap="sm" mb="xs">
        <ThemeIcon variant="light" size="lg" radius="md" color="grape">
          <IconSparkles size={20} />
        </ThemeIcon>
        <div>
          <Title order={3}>{r('recommended.title')}</Title>
          {data && (
            <Text size="sm" c="dimmed">
              {r(`recommended.basis.${data.basis}`)}
            </Text>
          )}
        </div>
      </Group>
      {loading ? (
        <Center py="lg">
          <Loader />
        </Center>
      ) : error ? (
        <Alert color="red">{r('loadError')}</Alert>
      ) : !data?.items?.length ? (
        <Text c="dimmed">{r('recommended.none')}</Text>
      ) : (
        <>
          <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }} spacing="md" mt="sm">
            {data.items.map(item => (
              <RecipeCard
                key={item.recipe.id}
                recipe={item.recipe}
                rec={item}
                onOpen={onOpen}
              />
            ))}
          </SimpleGrid>
          {excluded > 0 && (
            <Text size="sm" c="dimmed" mt="sm">
              {r('recommended.excluded', { count: excluded })}
            </Text>
          )}
        </>
      )}
    </Card>
  );
}

export default function MetabolicRecipes() {
  const { r, t, lang } = useRecipesT();
  const { patient } = usePatientWithStaticData();
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const patientId = patient?.patient?.id;
  const professional = PRO_ROLES.includes(user?.role);
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [category, setCategory] = useState('all');
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const load = useCallback(
    async signal => {
      setLoading(true);
      setError(false);
      try {
        const res = await metabolicApi.getRecipes(
          professional ? { include_inactive: true } : {},
          signal
        );
        setRecipes(res || []);
      } catch (err) {
        if (signal?.aborted) return;
        logger.error('recipes_load_failed', { error: err?.message });
        setError(true);
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [professional]
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const openId = Number(searchParams.get('recipe')) || null;
  const opened = recipes.find(x => x.id === openId) || null;
  const open = recipe => setSearchParams({ recipe: String(recipe.id) });
  const close = () => setSearchParams({});

  const visible = useMemo(() => {
    const q = query
      .trim()
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '');
    return recipes.filter(x => {
      if (category !== 'all' && x.category !== category) return false;
      if (!q) return true;
      const hay = [x.name, ...(x.ingredients || [])]
        .join(' ')
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '');
      return hay.includes(q);
    });
  }, [recipes, category, query]);

  const saved = async res => {
    setEditing(null);
    await load();
    setRefreshKey(k => k + 1);
    if (res?.id) setSearchParams({ recipe: String(res.id) });
  };

  const remove = async recipe => {
    try {
      const res = await metabolicApi.deleteRecipe(recipe.id);
      notifications.show({
        color: 'teal',
        message: res?.hidden ? r('hidden') : r('deleted'),
      });
      close();
      await load();
      setRefreshKey(k => k + 1);
    } catch (err) {
      logger.error('recipe_delete_failed', { error: err?.message });
      notifications.show({ color: 'red', message: r('error') });
    }
  };

  return (
    <Container size="lg" py="md" className="silho-ir-page">
      <PageHeader title={r('title')} icon="🍲" />
      <Text c="dimmed" mt="md">
        {r('subtitle')}
      </Text>
      <Stack gap="lg" mt="lg">
        {patientId ? (
          <Recommended
            patientId={patientId}
            refreshKey={refreshKey}
            onOpen={open}
          />
        ) : (
          <Alert color="blue">{t('metabolic.selectPatient')}</Alert>
        )}
        <Card withBorder radius="lg" padding="lg">
          <Group justify="space-between" wrap="wrap" gap="sm" mb="sm">
            <Group gap="sm">
              <ThemeIcon variant="light" size="lg" radius="md" color="teal">
                <IconToolsKitchen2 size={20} />
              </ThemeIcon>
              <Title order={3}>{r('library.title')}</Title>
            </Group>
            {professional && (
              <Button
                leftSection={<IconPlus size={16} />}
                onClick={() => setEditing({})}
              >
                {r('editor.newTitle')}
              </Button>
            )}
          </Group>
          {!lang?.startsWith('es') && (
            <Text size="sm" c="dimmed" mb="sm">
              {r('library.languageNote')}
            </Text>
          )}
          <Stack gap="sm">
            <TextInput
              leftSection={<IconSearch size={16} />}
              placeholder={r('library.search')}
              value={query}
              onChange={e => setQuery(e.currentTarget.value)}
            />
            <Chip.Group value={category} onChange={setCategory}>
              <Group gap={6} wrap="wrap">
                {['all', ...CATEGORIES].map(c => (
                  <Chip key={c} value={c} size="sm">
                    {c === 'all' ? r('library.all') : r(`categories.${c}`)}
                  </Chip>
                ))}
              </Group>
            </Chip.Group>
          </Stack>
          {loading ? (
            <Center py="lg">
              <Loader />
            </Center>
          ) : error ? (
            <Alert color="red" mt="md">
              {r('loadError')}
            </Alert>
          ) : visible.length === 0 ? (
            <Text c="dimmed" mt="md">
              {r('library.empty')}
            </Text>
          ) : (
            <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }} spacing="md" mt="md">
              {visible.map(recipe => (
                <RecipeCard key={recipe.id} recipe={recipe} onOpen={open} />
              ))}
            </SimpleGrid>
          )}
        </Card>
        <Text size="xs" c="dimmed">
          {r('disclaimer')}
        </Text>
      </Stack>
      {opened && !editing && (
        <RecipeDetail
          recipe={opened}
          professional={professional}
          onClose={close}
          onEdit={setEditing}
          onRemove={remove}
        />
      )}
      {editing && (
        <RecipeEditor
          initial={editing.id ? editing : null}
          onClose={() => setEditing(null)}
          onSaved={saved}
        />
      )}
    </Container>
  );
}
