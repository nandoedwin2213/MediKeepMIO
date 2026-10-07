import { vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import render from '../../../test-utils/render';
import MetabolicWeek, { adherenceColor } from '../MetabolicWeek';

const { api } = vi.hoisted(() => ({
  api: {
    getWeek: vi.fn(),
    logAdherence: vi.fn(),
    getAdherenceHistory: vi.fn(),
  },
}));

vi.mock('../../../services/api/metabolicApi', () => ({ default: api }));
vi.mock('../../../hooks/useGlobalData', () => ({
  usePatientWithStaticData: () => ({
    patient: { patient: { id: 7 } },
    loading: false,
  }),
}));

const day = (i, extra = {}) => ({
  date: `2026-10-0${5 + i}`,
  weekday: i,
  is_today: i === 1,
  is_future: i > 1,
  meals: {},
  aerobic: null,
  strength: null,
  mobility: null,
  balance: null,
  steps_target: 7000,
  walk_after_meals: true,
  items: [{ item: 'walk', done: false }],
  ...extra,
});

const WEEK = {
  start: '2026-10-05',
  end: '2026-10-11',
  is_current: true,
  plans: { exercise: { id: 1 }, nutrition: { id: 2 } },
  weekly: [
    { item: 'weight', done: true, source: 'vitals' },
    { item: 'waist', done: false, source: null },
  ],
  adherence: { done: 3, expected: 4, planned: 20, percent: 75 },
  days: [
    day(0, {
      aerobic: { minutes: 30, intensity: 'moderate', type: 'brisk_walking' },
      meals: {
        breakfast: {
          id: 11,
          name: 'Avena con frutos rojos',
          category: 'breakfast',
        },
      },
      items: [
        { item: 'exercise', done: true },
        { item: 'walk', done: true },
      ],
    }),
    day(1),
    ...[2, 3, 4].map(i => day(i)),
  ],
};

describe('MetabolicWeek', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getWeek.mockResolvedValue(WEEK);
    api.getAdherenceHistory.mockResolvedValue({ weeks: [] });
    api.logAdherence.mockResolvedValue({});
  });

  it('shows the adherence score, days and recipe links', async () => {
    render(<MetabolicWeek />);
    expect(
      await screen.findByText(/75%/, {}, { timeout: 15000 })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Avena con frutos rojos').closest('a')
    ).toHaveAttribute('href', '/metabolic-recipes?recipe=11');
    expect(
      screen.getByText(/fromVitals|Recorded in vital signs/)
    ).toBeInTheDocument();
  }, 20000);

  it('logs a checklist item and blocks future days', async () => {
    render(<MetabolicWeek />);
    const today = await screen.findByTestId(
      'day-2026-10-06',
      {},
      { timeout: 15000 }
    );
    const checkbox = today.querySelector('input[type="checkbox"]');
    fireEvent.click(checkbox);
    await waitFor(() =>
      expect(api.logAdherence).toHaveBeenCalledWith(7, {
        log_date: '2026-10-06',
        item: 'walk',
        done: true,
      })
    );
    const future = screen.getByTestId('day-2026-10-07');
    expect(future.querySelector('input[type="checkbox"]')).toBeDisabled();
  }, 20000);

  it('explains when there are no approved plans', async () => {
    api.getWeek.mockResolvedValue({
      ...WEEK,
      plans: { exercise: null, nutrition: null },
      weekly: [],
    });
    render(<MetabolicWeek />);
    expect(
      await screen.findByText(
        /noPlans|once your professional approves/,
        {},
        { timeout: 15000 }
      )
    ).toBeInTheDocument();
  }, 20000);

  it('maps adherence to traffic-light colours', () => {
    expect(adherenceColor(85)).toBe('green');
    expect(adherenceColor(65)).toBe('yellow');
    expect(adherenceColor(45)).toBe('orange');
    expect(adherenceColor(10)).toBe('red');
    expect(adherenceColor(null)).toBe('gray');
  });
});
