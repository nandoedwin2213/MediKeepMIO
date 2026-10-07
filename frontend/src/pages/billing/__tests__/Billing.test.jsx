import { vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render as rtlRender } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import render from '../../../test-utils/render';
import PaymentResponse from '../PaymentResponse';
import SubscriptionGate from '../../../components/billing/SubscriptionGate';

const { api } = vi.hoisted(() => ({
  api: { getMine: vi.fn(), confirm: vi.fn() },
}));
vi.mock('../../../services/api/billingApi', () => ({ default: api }));
vi.mock('../../../components/layout/PageHeader', () => ({
  default: ({ title }) => <h1>{title}</h1>,
}));

function renderAt(url) {
  return rtlRender(
    <MantineProvider>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/billing/response" element={<PaymentResponse />} />
        </Routes>
      </MemoryRouter>
    </MantineProvider>
  );
}

describe('SubscriptionGate', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the page when the user has access', async () => {
    api.getMine.mockResolvedValue({ has_access: true });
    render(
      <SubscriptionGate>
        <p>premium content</p>
      </SubscriptionGate>
    );
    expect(await screen.findByText('premium content')).toBeInTheDocument();
  });

  it('shows the paywall without access', async () => {
    api.getMine.mockResolvedValue({ has_access: false });
    render(
      <SubscriptionGate>
        <p>premium content</p>
      </SubscriptionGate>
    );
    expect(await screen.findByTestId('subscription-gate')).toBeInTheDocument();
    expect(screen.queryByText('premium content')).not.toBeInTheDocument();
    expect(
      screen
        .getAllByRole('link')
        .some(l => l.getAttribute('href') === '/subscription')
    ).toBe(true);
  });
});

describe('PaymentResponse', () => {
  beforeEach(() => vi.clearAllMocks());

  it('confirms the payment with PayPhone parameters', async () => {
    api.confirm.mockResolvedValue({
      subscription: { status: 'active', period_end: '2026-11-05T00:00:00' },
    });
    renderAt('/billing/response?id=123&clientTransactionId=abc');
    await waitFor(() => expect(api.confirm).toHaveBeenCalledWith('123', 'abc'));
    expect(await screen.findByTestId('payment-result')).toBeInTheDocument();
    expect(
      screen
        .getAllByRole('link')
        .some(l => l.getAttribute('href') === '/my-metabolic-health')
    ).toBe(true);
  });

  it('does not confirm a cancelled checkout', async () => {
    renderAt('/billing/response?cancelled=1');
    expect(await screen.findByTestId('payment-result')).toBeInTheDocument();
    expect(api.confirm).not.toHaveBeenCalled();
  });

  it('shows an error when confirmation fails', async () => {
    api.confirm.mockRejectedValue(new Error('boom'));
    renderAt('/billing/response?id=9&clientTransactionId=x');
    expect(await screen.findByTestId('payment-result')).toBeInTheDocument();
  });
});
