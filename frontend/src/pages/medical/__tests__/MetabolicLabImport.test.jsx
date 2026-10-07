import { vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import render from '../../../test-utils/render';
import MetabolicLabImport from '../MetabolicLabImport';

const { api } = vi.hoisted(() => ({
  api: {
    getLabCatalog: vi.fn(),
    parseLabs: vi.fn(),
    importLabs: vi.fn(),
  },
}));

vi.mock('../../../services/api/metabolicApi', () => ({ default: api }));
vi.mock('../../../hooks/useGlobalData', () => ({
  usePatientWithStaticData: () => ({
    patient: { patient: { id: 7 } },
    loading: false,
  }),
}));

const row = (variable, value, unit, extra = {}) => ({
  variable,
  value,
  unit,
  loinc: variable === 'glucose' ? '2345-7' : '2571-8',
  line: `${variable} ${value}`,
  ref_min: null,
  ref_max: null,
  ref_text: null,
  warnings: [],
  selected: true,
  ...extra,
});

describe('MetabolicLabImport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getLabCatalog.mockResolvedValue([
      { variable: 'glucose', units: ['mg/dL', 'mmol/L'] },
      { variable: 'triglycerides', units: ['mg/dL', 'mmol/L'] },
    ]);
    api.parseLabs.mockResolvedValue({
      rows: [
        row('glucose', 104, 'mg/dL', { ref_min: 70, ref_max: 100 }),
        row('triglycerides', 230, 'mg/dL'),
        row('glucose', 5.8, 'mmol/L', {
          selected: false,
          warnings: ['duplicate'],
        }),
      ],
      unrecognized: 1,
      suggested_date: '2026-09-12',
      source: 'text',
    });
    api.importLabs.mockResolvedValue({
      imported: 2,
      lab_result_id: 3,
      assessment_id: 4,
      score: { value: 58 },
    });
  });

  it('parses pasted text, lets the user review and imports only selected rows', async () => {
    const { container } = render(<MetabolicLabImport />);
    const analyse = await screen.findByText(
      /labs\.analyse|Analyse/,
      {},
      { timeout: 15000 }
    );
    fireEvent.change(container.querySelector('textarea'), {
      target: { value: 'Glucosa 104 mg/dL' },
    });
    fireEvent.click(analyse);

    await waitLabRows();
    expect(api.parseLabs).toHaveBeenCalledWith(7, {
      text: 'Glucosa 104 mg/dL',
      file: null,
    });
    expect(screen.getAllByText(/LOINC 2345-7/)).toHaveLength(4);

    fireEvent.click(screen.getByText(/labs\.import$|Save 2 values/));
    await waitFor(() => expect(api.importLabs).toHaveBeenCalled());
    const [patientId, body] = api.importLabs.mock.calls[0];
    expect(patientId).toBe(7);
    expect(body.collected_on).toBe('2026-09-12');
    expect(body.rows).toEqual([
      expect.objectContaining({
        variable: 'glucose',
        value: 104,
        unit: 'mg/dL',
        ref_min: 70,
        ref_max: 100,
      }),
      expect.objectContaining({ variable: 'triglycerides', value: 230 }),
    ]);
    expect(
      await screen.findByText(/labs\.newScore|is now 58/)
    ).toBeInTheDocument();
  }, 20000);
});

async function waitLabRows() {
  await waitFor(() =>
    expect(screen.getAllByRole('checkbox').length).toBeGreaterThanOrEqual(3)
  );
}
