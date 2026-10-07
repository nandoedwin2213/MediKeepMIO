import { vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import render from '../../../test-utils/render';
import MetabolicAI from '../MetabolicAI';

const { api, auth } = vi.hoisted(() => ({
  api: {
    getInsights: vi.fn(),
    generateInsight: vi.fn(),
    updateInsight: vi.fn(),
    approveInsight: vi.fn(),
    deleteInsight: vi.fn(),
    simulate: vi.fn(),
  },
  auth: { role: 'user' },
}));

vi.mock('../../../services/api/metabolicApi', () => ({ default: api }));
vi.mock('../../../hooks/useGlobalData', () => ({
  usePatientWithStaticData: () => ({
    patient: { patient: { id: 7 } },
    loading: false,
  }),
}));
vi.mock('../../../contexts/AuthContext', async importOriginal => ({
  ...(await importOriginal()),
  useAuth: () => ({ user: { role: auth.role } }),
}));

const insight = (status, extra = {}) => ({
  id: status === 'draft' ? 2 : 1,
  patient_id: 7,
  status,
  note: status === 'approved' ? 'Control en 3 meses' : null,
  approved_at: status === 'approved' ? '2026-10-05T10:00:00' : null,
  content: {
    pattern: 'combination',
    needs_review: false,
    concerns: [{ key: 'waist', level: 'high', value: 104, unit: 'cm' }],
    strengths: [{ key: 'hba1c', level: 'normal', value: 5.3, unit: '%' }],
    priorities: [
      { code: 'reduce_waist', because: ['waist'] },
      { code: 'repeat_labs', because: [] },
    ],
    change: {
      score_delta: 6,
      drivers: [
        { key: 'waist', direction: 'improved', from: 109, to: 104, unit: 'cm' },
      ],
    },
  },
  ...extra,
});

describe('MetabolicAI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth.role = 'user';
    api.getInsights.mockResolvedValue([insight('approved')]);
    api.simulate.mockResolvedValue({
      educational: true,
      applied: { waist: { delta: -10, from: 104, missing: false } },
      before: { value: 58, level: 'moderate' },
      after: { value: 71, level: 'initial' },
      score_delta: 13,
      changes: [
        {
          key: 'waist',
          from: 104,
          to: 94,
          unit: 'cm',
          from_level: 'high',
          to_level: 'borderline',
          direction: 'improved',
          level_changed: true,
        },
      ],
    });
  });

  it('shows the approved explanation to the patient without editing tools', async () => {
    render(<MetabolicAI />);
    expect(
      await screen.findByText('Control en 3 meses', {}, { timeout: 15000 })
    ).toBeInTheDocument();
    expect(screen.getByText(/109 → 104 cm/)).toBeInTheDocument();
    expect(
      screen.getAllByText(/priorities\.reduce_waist|Reduce waist/).length
    ).toBeGreaterThan(0);
    expect(
      screen.queryByText(/explain\.approve|Approve and publish/)
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/explain\.generate|explain\.regenerate/)
    ).not.toBeInTheDocument();
  }, 20000);

  it('tells the patient when nothing is approved yet', async () => {
    api.getInsights.mockResolvedValue([]);
    render(<MetabolicAI />);
    expect(
      await screen.findByText(
        /explain\.pending|not reviewed/,
        {},
        { timeout: 15000 }
      )
    ).toBeInTheDocument();
  }, 20000);

  it('lets a professional approve a draft', async () => {
    auth.role = 'doctor';
    api.getInsights.mockResolvedValue([insight('draft')]);
    api.updateInsight.mockResolvedValue({});
    api.approveInsight.mockResolvedValue({});
    render(<MetabolicAI />);
    const approve = await screen.findByText(
      /explain\.approve|Approve and publish/,
      {},
      { timeout: 15000 }
    );
    fireEvent.click(approve);
    await waitFor(() => expect(api.approveInsight).toHaveBeenCalledWith(7, 2));
    expect(api.updateInsight).toHaveBeenCalledWith(7, 2, {
      note: null,
      priorities: ['reduce_waist', 'repeat_labs'],
    });
  }, 20000);

  it('runs the educational simulator', async () => {
    render(<MetabolicAI />);
    const run = await screen.findByText(
      /sim\.run|Simulate/,
      {},
      { timeout: 15000 }
    );
    fireEvent.click(run);
    await waitFor(() => expect(api.simulate).toHaveBeenCalledWith(7, {}));
    expect(await screen.findByText('71')).toBeInTheDocument();
    expect(screen.getByText(/104 → 94 cm/)).toBeInTheDocument();
  }, 20000);
});
