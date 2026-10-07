import { vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import render from '../../../test-utils/render';
import MetabolicWearables from '../MetabolicWearables';

const { api } = vi.hoisted(() => ({
  api: {
    getWearables: vi.fn(),
    parseWearables: vi.fn(),
    importWearables: vi.fn(),
    applyWearables: vi.fn(),
  },
}));

vi.mock('../../../services/api/metabolicApi', () => ({ default: api }));
vi.mock('../../../hooks/useGlobalData', () => ({
  usePatientWithStaticData: () => ({
    patient: { patient: { id: 7 } },
    loading: false,
  }),
}));

const summary = {
  window_days: 28,
  days_with_data: 2,
  metrics: {
    steps: {
      value: 6650,
      unit: 'steps',
      level: 'borderline',
      bands: [
        { level: 'high', min: null, max: 5000 },
        { level: 'borderline', min: 5000, max: 7500 },
        { level: 'normal', min: 7500, max: null },
      ],
    },
    sleep: { value: 7.5, unit: 'h', level: 'normal', bands: null },
    weight: { value: 81.5, unit: 'kg', bands: null, level: null },
  },
};
const days = [
  { date: '2026-09-01', steps: 9100, exercise_minutes: 42, weight_kg: 81.5 },
  { date: '2026-09-02', steps: 4200, sleep_hours: 7.5 },
];

describe('MetabolicWearables', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getWearables.mockResolvedValue({
      days: [],
      summary: { window_days: 28, days_with_data: 0, metrics: {} },
      last_import: null,
    });
  });

  it('parses an export, shows the review and saves it', async () => {
    api.parseWearables.mockResolvedValue({
      source: 'google_fit',
      days,
      warnings: { future: 1 },
      summary,
    });
    api.importWearables.mockResolvedValue({ days: 2, score: 48 });
    render(<MetabolicWearables />);
    await waitFor(() => expect(api.getWearables).toHaveBeenCalled());

    const input = document.querySelector('input[type="file"]');
    fireEvent.change(input, {
      target: { files: [new File(['x'], 'daily.csv', { type: 'text/csv' })] },
    });
    fireEvent.click(screen.getByText('metabolic.wearables.analyse'));

    expect(await screen.findByText('Google Fit')).toBeInTheDocument();
    expect(
      screen.getByText('metabolic.wearables.discarded')
    ).toBeInTheDocument();
    expect(screen.getByText('9,100')).toBeInTheDocument();
    fireEvent.click(screen.getByText('metabolic.wearables.save'));
    await waitFor(() =>
      expect(api.importWearables).toHaveBeenCalledWith(7, {
        source: 'google_fit',
        days,
      })
    );
    await waitFor(() => expect(api.getWearables).toHaveBeenCalledTimes(2));
  });

  it('shows saved averages with ranges and applies them to the profile', async () => {
    api.getWearables.mockResolvedValue({
      days,
      summary,
      last_import: '2026-09-03T10:00:00',
    });
    api.applyWearables.mockResolvedValue({
      physical_activity_minutes_week: 120,
      sleep_hours: 7.5,
      score: 50,
    });
    render(<MetabolicWearables />);
    expect(await screen.findByText('81.5')).toBeInTheDocument();
    expect(screen.getByText('6,650')).toBeInTheDocument();
    expect(
      screen.getByText('metabolic.wearables.hints.steps')
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText('metabolic.wearables.apply'));
    await waitFor(() => expect(api.applyWearables).toHaveBeenCalledWith(7));
  });
});
