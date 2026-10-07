import { vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import render from '../../../test-utils/render';
import MetabolicResearch from '../MetabolicResearch';

const { api } = vi.hoisted(() => ({
  api: { getResearchSummary: vi.fn(), exportResearch: vi.fn() },
}));

vi.mock('../../../services/api/metabolicApi', () => ({ default: api }));
vi.mock('../../../components/admin/AdminLayout', () => ({
  default: ({ children }) => <div>{children}</div>,
}));

describe('MetabolicResearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.URL.createObjectURL = vi.fn(() => 'blob:x');
    window.URL.revokeObjectURL = vi.fn();
    api.getResearchSummary.mockResolvedValue({
      patients_total: 12,
      patients_consented: 3,
      assessments: 9,
      columns: 52,
      min_group_size: 5,
      small_sample: true,
    });
    api.exportResearch.mockResolvedValue('research_id,sex\nR-1,M\n');
  });

  it('shows consent stats, small-sample warning and downloads the CSV', async () => {
    render(<MetabolicResearch />);
    expect(
      await screen.findByText('52', {}, { timeout: 15000 })
    ).toBeInTheDocument();
    expect(screen.getByText('9')).toBeInTheDocument();
    expect(
      screen.getByText(/metabolicResearch\.smallSample|Fewer than 5/)
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText(/formats\.csv|Data \(CSV\)/));
    await waitFor(() => expect(api.exportResearch).toHaveBeenCalledWith('csv'));
    expect(window.URL.createObjectURL).toHaveBeenCalled();
  }, 20000);
});
