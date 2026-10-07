import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { authService } from '../../services/auth/simpleAuthService';
import styles from '../../styles/pages/Login.module.css';

let configPromise = null;

export const loadClerkConfig = () => {
  if (!configPromise) {
    configPromise = authService.getClerkConfig().then(config => {
      if (config?.error) configPromise = null;
      return config || { enabled: false };
    });
  }
  return configPromise;
};

export const resetClerkConfigCache = () => {
  configPromise = null;
};

/** "Continue with Google or email" entry point, shown only when Clerk is set up. */
const ClerkEntryButton = ({ mode = 'sign-in', showDivider = true }) => {
  const { t } = useTranslation('auth');
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    let active = true;
    loadClerkConfig().then(config => {
      if (active) setEnabled(Boolean(config.enabled));
    });
    return () => {
      active = false;
    };
  }, []);

  if (!enabled) return null;

  const signUp = mode === 'sign-up';
  return (
    <div className={styles.ssoSection} data-testid="clerk-entry">
      {showDivider && (
        <div className={styles.divider}>
          <span>{t('login.or')}</span>
        </div>
      )}
      <Link
        to={signUp ? '/auth/clerk?mode=sign-up' : '/auth/clerk'}
        className={styles.ssoBtn}
        style={{
          display: 'block',
          textAlign: 'center',
          textDecoration: 'none',
        }}
      >
        {signUp ? t('clerk.signUp') : t('clerk.continue')}
      </Link>
    </div>
  );
};

export default ClerkEntryButton;
