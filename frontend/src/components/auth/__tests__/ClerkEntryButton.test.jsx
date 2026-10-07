import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: key => key }),
}));

vi.mock('../../../services/auth/simpleAuthService', () => ({
  authService: { getClerkConfig: vi.fn() },
}));

import { authService } from '../../../services/auth/simpleAuthService';
import ClerkEntryButton, { resetClerkConfigCache } from '../ClerkEntryButton';

const renderButton = props =>
  render(
    <MemoryRouter>
      <ClerkEntryButton {...props} />
    </MemoryRouter>
  );

describe('ClerkEntryButton', () => {
  beforeEach(() => {
    resetClerkConfigCache();
    authService.getClerkConfig.mockReset();
  });

  it('renders nothing when Clerk is not configured', async () => {
    authService.getClerkConfig.mockResolvedValue({ enabled: false });
    renderButton();
    await waitFor(() => expect(authService.getClerkConfig).toHaveBeenCalled());
    expect(screen.queryByTestId('clerk-entry')).toBeNull();
  });

  it('links to the Clerk sign-in page when enabled', async () => {
    authService.getClerkConfig.mockResolvedValue({ enabled: true });
    renderButton();
    const link = await screen.findByRole('link', { name: 'clerk.continue' });
    expect(link.getAttribute('href')).toBe('/auth/clerk');
  });

  it('links to the sign-up mode from registration', async () => {
    authService.getClerkConfig.mockResolvedValue({ enabled: true });
    renderButton({ mode: 'sign-up', showDivider: false });
    const link = await screen.findByRole('link', { name: 'clerk.signUp' });
    expect(link.getAttribute('href')).toBe('/auth/clerk?mode=sign-up');
    expect(screen.queryByText('login.or')).toBeNull();
  });

  it('retries the config fetch after a failure', async () => {
    authService.getClerkConfig
      .mockResolvedValueOnce({ enabled: false, error: true })
      .mockResolvedValueOnce({ enabled: true });
    const { unmount } = renderButton();
    await waitFor(() =>
      expect(authService.getClerkConfig).toHaveBeenCalledTimes(1)
    );
    unmount();
    renderButton();
    expect(await screen.findByTestId('clerk-entry')).toBeTruthy();
  });
});
