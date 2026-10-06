import { vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import render from '../../../test-utils/render';
import MetabolicNutrition from '../MetabolicNutrition';

const { api, auth } = vi.hoisted(() => ({
  api: {
    getNutritionPlans: vi.fn(),
    generateNutritionPlan: vi.fn(),
    createNutritionPlan: vi.fn(),
    updateNutritionPlan: vi.fn(),
    approveNutritionPlan: vi.fn(),
    deleteNutritionPlan: vi.fn(),
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

const PLAN = {
  energy: { kcal_target: 1850, deficit_kcal: 400, tdee_kcal: 2250 },
  macros: {
    protein_g_kg_min: 1.0,
    protein_g_kg_max: 1.2,
    protein_g_min: 85,
    protein_g_max: 100,
    carbs_pct_min: 35,
    carbs_pct_max: 45,
    fat_pct_min: 30,
    fat_pct_max: 35,
    fiber_g_min: 30,
    added_sugar_g_max: 25,
    saturated_fat_pct_max: 7,
    sodium_mg_max: 1500,
  },
  meals: {
    meals_per_day: 3,
    snacks_per_day: 1,
    plate_model: true,
    protein_each_meal: true,
    regular_schedule: true,
  },
  hydration_l: 2.2,
  prioritize: ['vegetables', 'legumes'],
  limit: ['sugary_drinks'],
  avoid: ['peanut'],
  dislikes: [],
  targets: ['fruit_veg_5'],
  safety: ['professional_review'],
};

const plan = (id, status) => ({
  id,
  patient_id: 7,
  status,
  plan: PLAN,
  rationale: ['glycemic'],
  generator_version: 'nutrition-0.1.0',
  created_at: '2026-09-01T10:00:00',
  updated_at: '2026-09-01T10:00:00',
  approved_at: status === 'approved' ? '2026-09-02T10:00:00' : null,
});

beforeEach(() => {
  vi.clearAllMocks();
  auth.role = 'user';
});

describe('MetabolicNutrition', () => {
  it('shows only the approved plan to patients, without professional actions', async () => {
    api.getNutritionPlans.mockResolvedValue([
      plan(4, 'draft'),
      plan(5, 'approved'),
    ]);
    render(<MetabolicNutrition />);
    expect(await screen.findByText(/1850 kcal/)).toBeInTheDocument();
    expect(screen.getByText('peanut')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /generate|generar|plan\.generate/i })
    ).toBeNull();
    expect(
      screen.queryByRole('button', { name: /approve|aprobar|plan\.approve/i })
    ).toBeNull();
  });

  it('tells patients when there is no approved plan', async () => {
    api.getNutritionPlans.mockResolvedValue([]);
    render(<MetabolicNutrition />);
    await waitFor(() =>
      expect(api.getNutritionPlans).toHaveBeenCalledWith(7, expect.anything())
    );
    expect(screen.queryByText(/1850 kcal/)).toBeNull();
  });

  it('lets nutritionists save edits, approve and generate drafts', async () => {
    auth.role = 'nutritionist';
    api.getNutritionPlans.mockResolvedValue([plan(9, 'draft')]);
    api.updateNutritionPlan.mockResolvedValue(plan(9, 'draft'));
    api.approveNutritionPlan.mockResolvedValue(plan(9, 'approved'));
    api.generateNutritionPlan.mockResolvedValue(plan(10, 'draft'));
    render(<MetabolicNutrition />);

    const generate = await screen.findByRole('button', {
      name: /generate|generar|plan\.generate/i,
    });
    const approve = await screen.findByRole('button', {
      name: /approve|aprobar|plan\.approve/i,
    });
    fireEvent.click(approve);
    await waitFor(() =>
      expect(api.approveNutritionPlan).toHaveBeenCalledWith(7, 9)
    );
    expect(api.updateNutritionPlan).toHaveBeenCalledWith(
      7,
      9,
      expect.objectContaining({
        plan: expect.objectContaining({ macros: PLAN.macros }),
      })
    );
    fireEvent.click(generate);
    await waitFor(() =>
      expect(api.generateNutritionPlan).toHaveBeenCalledWith(7)
    );
  });
});
