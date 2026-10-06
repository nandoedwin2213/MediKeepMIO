import { vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import render from '../../../test-utils/render';
import MetabolicMovement from '../MetabolicMovement';

const { api, auth } = vi.hoisted(() => ({
  api: {
    getFunctional: vi.fn(),
    createFunctional: vi.fn(),
    deleteFunctional: vi.fn(),
    getExercisePlans: vi.fn(),
    generateExercisePlan: vi.fn(),
    createExercisePlan: vi.fn(),
    updateExercisePlan: vi.fn(),
    approveExercisePlan: vi.fn(),
    deleteExercisePlan: vi.fn(),
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
  aerobic: {
    days_per_week: 3,
    minutes: 15,
    intensity: 'light_moderate',
    rpe_min: 3,
    rpe_max: 4,
    types: ['aquatic'],
  },
  strength: {
    days_per_week: 2,
    sets_min: 1,
    sets_max: 2,
    reps_min: 12,
    reps_max: 15,
    rpe_min: 5,
    rpe_max: 6,
    muscle_groups: ['lower_limbs'],
    exercises: ['sit_to_stand'],
  },
  mobility: { days_per_week: 5, minutes: 10, focus: ['hips'] },
  balance: { days_per_week: 2, minutes: 10, exercises: ['tandem_walk'] },
  daily: {
    steps_start: 5000,
    steps_target: 7000,
    walk_after_meals: true,
    break_sitting: false,
  },
  progression: ['aerobic_build'],
  safety: ['stop_symptoms'],
};

const plan = (id, status) => ({
  id,
  patient_id: 7,
  status,
  plan: PLAN,
  rationale: ['start_gradually'],
  generator_version: 'movement-0.1.0',
  created_at: '2026-09-01T10:00:00',
  updated_at: '2026-09-01T10:00:00',
  approved_at: status === 'approved' ? '2026-09-02T10:00:00' : null,
});

beforeEach(() => {
  vi.clearAllMocks();
  auth.role = 'user';
  api.getFunctional.mockResolvedValue({
    items: [
      {
        id: 1,
        assessed_at: '2026-09-01T12:00:00',
        sit_to_stand_30s: 9,
        indicators: {
          sit_to_stand: {
            value: 9,
            unit: 'reps',
            level: 'low',
            bands: [
              { level: 'low', min: null, max: 12 },
              { level: 'adequate', min: 12, max: null },
            ],
          },
        },
      },
    ],
  });
});

describe('MetabolicMovement', () => {
  it('shows functional results and only the approved plan to patients', async () => {
    api.getExercisePlans.mockResolvedValue([plan(5, 'approved')]);
    render(<MetabolicMovement />);
    expect(await screen.findAllByText('9', { exact: false })).not.toHaveLength(
      0
    );
    await waitFor(() =>
      expect(api.getExercisePlans).toHaveBeenCalledWith(7, expect.anything())
    );
    expect(api.generateExercisePlan).not.toHaveBeenCalled();
    expect(
      screen.queryByRole('button', { name: /generate|generar|plan\.generate/i })
    ).toBeNull();
  });

  it('lets professionals generate and approve a draft', async () => {
    auth.role = 'physio';
    api.getExercisePlans.mockResolvedValue([plan(9, 'draft')]);
    api.updateExercisePlan.mockResolvedValue(plan(9, 'draft'));
    api.approveExercisePlan.mockResolvedValue(plan(9, 'approved'));
    api.generateExercisePlan.mockResolvedValue(plan(10, 'draft'));
    render(<MetabolicMovement />);

    const generate = await screen.findByRole('button', {
      name: /generate|generar|plan\.generate/i,
    });
    const approve = await screen.findByRole('button', {
      name: /approve|aprobar|plan\.approve/i,
    });
    fireEvent.click(approve);
    await waitFor(() =>
      expect(api.approveExercisePlan).toHaveBeenCalledWith(7, 9)
    );
    expect(api.updateExercisePlan).toHaveBeenCalledWith(
      7,
      9,
      expect.objectContaining({
        plan: expect.objectContaining({ aerobic: PLAN.aerobic }),
      })
    );
    fireEvent.click(generate);
    await waitFor(() =>
      expect(api.generateExercisePlan).toHaveBeenCalledWith(7)
    );
  });
});
