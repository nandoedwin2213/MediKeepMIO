import { vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import render from '../../../test-utils/render';
import MetabolicRecipes from '../MetabolicRecipes';

const { api, auth } = vi.hoisted(() => ({
  api: {
    getRecipes: vi.fn(),
    getRecommendedRecipes: vi.fn(),
    createRecipe: vi.fn(),
    updateRecipe: vi.fn(),
    deleteRecipe: vi.fn(),
  },
  auth: { role: 'user' },
}));

vi.mock('../../../services/api/metabolicApi', () => ({ default: api }));
vi.mock('../../../contexts/AuthContext', async importOriginal => ({
  ...(await importOriginal()),
  useAuth: () => ({ user: { id: 1, role: auth.role } }),
}));
vi.mock('../../../hooks/useGlobalData', () => ({
  usePatientWithStaticData: () => ({
    patient: { patient: { id: 7 } },
    loading: false,
  }),
}));

const recipe = (id, slug, name, category, extra = {}) => ({
  id,
  slug,
  name,
  category,
  description: null,
  servings: 1,
  prep_minutes: 10,
  kcal: 320,
  protein_g: 20,
  carbs_g: 30,
  fat_g: 10,
  fiber_g: 8,
  diets: ['omnivore', 'vegan'],
  allergens: [],
  tags: ['high_fiber'],
  ingredients: ['1 taza de lentejas'],
  steps: ['Cocinar las lentejas'],
  image_url: null,
  image_credit: 'Autor · CC BY 2.0',
  image_source_url: 'https://example.org/photo',
  language: 'es',
  is_library: true,
  is_active: true,
  ...extra,
});

const LENTILS = recipe(1, 'menestra-lentejas', 'Menestra de lentejas', 'lunch');
const TEA = recipe(2, 'te-hierbas', 'Té de hierbas', 'drink');

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState({}, '', '/');
  auth.role = 'user';
  api.getRecipes.mockResolvedValue([LENTILS, TEA]);
  api.getRecommendedRecipes.mockResolvedValue({
    basis: 'approved_plan',
    diet_pattern: 'vegan',
    ranker_version: 'recipes-0.1.0',
    excluded: { diet: 2, allergen: 1, dislike: 0 },
    items: [
      {
        recipe: LENTILS,
        score: 5,
        reasons: ['high_fiber'],
        assigned: true,
        conflicts: [],
      },
    ],
  });
});

describe('MetabolicRecipes', () => {
  it('shows recommendations, filters the library and opens a recipe', async () => {
    render(<MetabolicRecipes />);
    const recommended = await screen.findByTestId('recipes-recommended');
    await waitFor(() =>
      expect(api.getRecommendedRecipes).toHaveBeenCalledWith(
        7,
        { limit: 6 },
        expect.anything()
      )
    );
    expect(recommended).toHaveTextContent('Menestra de lentejas');
    expect(api.getRecipes).toHaveBeenCalledWith({}, expect.anything());
    expect(await screen.findByText('Té de hierbas')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'hierbas' },
    });
    await waitFor(() =>
      expect(screen.getAllByText('Menestra de lentejas')).toHaveLength(1)
    );

    fireEvent.click(screen.getByText('Té de hierbas'));
    expect(await screen.findByText('Cocinar las lentejas')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Autor · CC BY 2.0' })
    ).toHaveAttribute('href', 'https://example.org/photo');
    expect(screen.queryByRole('button', { name: /edit|editar/i })).toBeNull();
  }, 15000);

  it('lets professionals see hidden recipes and hide library ones', async () => {
    auth.role = 'nutritionist';
    api.deleteRecipe.mockResolvedValue({ deleted: false, hidden: true });
    render(<MetabolicRecipes />);
    await waitFor(() =>
      expect(api.getRecipes).toHaveBeenCalledWith(
        { include_inactive: true },
        expect.anything()
      )
    );
    fireEvent.click(await screen.findByText('Té de hierbas'));
    fireEvent.click(
      await screen.findByRole('button', { name: /hide|ocultar|detail\.hide/i })
    );
    await waitFor(() => expect(api.deleteRecipe).toHaveBeenCalledWith(2));
  }, 15000);
});
