import { vi } from 'vitest';
import { screen } from '@testing-library/react';
import render from '../../../test-utils/render';
import Landing from '../Landing';

const { api } = vi.hoisted(() => ({ api: { getPlans: vi.fn() } }));
vi.mock('../../../services/api/billingApi', () => ({ default: api }));

describe('Landing', () => {
  it('shows the value proposition, sign-in links and plans', async () => {
    api.getPlans.mockResolvedValue({
      currency: 'USD',
      configured: true,
      plans: [
        { id: 'monthly', months: 1, amount_cents: 1999 },
        { id: 'quarterly', months: 3, amount_cents: 4999 },
      ],
    });
    render(<Landing />);

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    const loginLinks = screen
      .getAllByRole('link')
      .filter(link => link.getAttribute('href') === '/login');
    expect(loginLinks.length).toBeGreaterThan(0);
    const signupLinks = screen
      .getAllByRole('link')
      .filter(link => link.getAttribute('href') === '/user-creation');
    expect(signupLinks.length).toBeGreaterThan(1);

    expect(await screen.findByText(/19[.,]99/)).toBeInTheDocument();
    expect(screen.getByText(/49[.,]99/)).toBeInTheDocument();
  });

  it('still renders when plans cannot be loaded', async () => {
    api.getPlans.mockRejectedValue(new Error('offline'));
    render(<Landing />);
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });
});
