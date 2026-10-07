import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ClerkProvider,
  SignIn,
  SignUp,
  useAuth as useClerkAuth,
  useClerk,
} from '@clerk/clerk-react';
import { useAuth } from '../../contexts/AuthContext';
import { authService } from '../../services/auth/simpleAuthService';
import { getPostSSORedirectPath } from '../../components/auth/SSOCallback';
import { loadClerkConfig } from '../../components/auth/ClerkEntryButton';
import PublicNav from '../../components/public/PublicNav';
import { authErrorCopy } from '../../utils/authErrorCopy';
import { buildLoginPath } from '../../utils/loginRedirect';
import styles from '../../styles/pages/Login.module.css';

const LOCALIZATION_LOADERS = {
  de: () => import('@clerk/localizations/de-DE').then(m => m.deDE),
  el: () => import('@clerk/localizations/el-GR').then(m => m.elGR),
  en: () => import('@clerk/localizations/en-US').then(m => m.enUS),
  es: () => import('@clerk/localizations/es-ES').then(m => m.esES),
  fr: () => import('@clerk/localizations/fr-FR').then(m => m.frFR),
  it: () => import('@clerk/localizations/it-IT').then(m => m.itIT),
  nl: () => import('@clerk/localizations/nl-NL').then(m => m.nlNL),
  pl: () => import('@clerk/localizations/pl-PL').then(m => m.plPL),
  pt: () => import('@clerk/localizations/pt-BR').then(m => m.ptBR),
  ru: () => import('@clerk/localizations/ru-RU').then(m => m.ruRU),
  sv: () => import('@clerk/localizations/sv-SE').then(m => m.svSE),
  th: () => import('@clerk/localizations/th-TH').then(m => m.thTH),
  zh: () => import('@clerk/localizations/zh-CN').then(m => m.zhCN),
};

const loadLocalization = lang =>
  (LOCALIZATION_LOADERS[lang] || LOCALIZATION_LOADERS.es)().catch(
    () => undefined
  );

const SELF = '/auth/clerk';

const appearanceFor = dark => ({
  variables: dark
    ? {
        colorPrimary: '#c9a45c',
        colorTextOnPrimaryBackground: '#0b1a33',
        colorBackground: '#0f1d38',
        colorInputBackground: '#0b1a33',
        colorText: '#f6f3ec',
        colorInputText: '#f6f3ec',
        colorTextSecondary: 'rgba(246, 243, 236, 0.72)',
        borderRadius: '12px',
      }
    : {
        colorPrimary: '#0b1a33',
        colorTextOnPrimaryBackground: '#ffffff',
        colorBackground: '#ffffff',
        colorText: '#0b1a33',
        borderRadius: '12px',
      },
  elements: {
    rootBox: { width: '100%', display: 'flex', justifyContent: 'center' },
    cardBox: { boxShadow: '0 18px 48px rgba(5, 12, 28, 0.28)' },
  },
});

const ClerkExchange = ({ mode }) => {
  const { t } = useTranslation('auth');
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  const clerk = useClerk();
  const { login } = useAuth();
  const navigate = useNavigate();
  const started = useRef(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isLoaded || !isSignedIn || started.current) return;
    started.current = true;

    (async () => {
      let result;
      try {
        const token = await getToken();
        result = await authService.exchangeClerkSession(token);
      } catch (e) {
        result = { success: false, error: e.message };
      }
      // MediKeep keeps its own session; the Clerk one is no longer needed.
      await clerk.signOut().catch(() => {});

      if (!result.success) {
        setError(result);
        return;
      }
      login(result.user, {
        sso: true,
        mustChangePassword: result.mustChangePassword,
      });
      navigate(
        getPostSSORedirectPath({
          mustChangePassword: result.mustChangePassword,
          isNewUser: result.isNewUser,
          returnUrl: null,
        }),
        { replace: true }
      );
    })();
  }, [isLoaded, isSignedIn, getToken, clerk, login, navigate]);

  if (error) {
    return (
      <div className={styles.loginForm} data-testid="clerk-error">
        <div className={styles.errorMessage}>
          {error.errorCode
            ? authErrorCopy(t, error.errorCode, t('clerk.error'))
            : t('clerk.error')}
        </div>
        <div className={styles.loginActions}>
          <button
            type="button"
            className={styles.ssoBtn}
            onClick={() => {
              started.current = false;
              setError(null);
            }}
          >
            {t('clerk.retry')}
          </button>
          <Link to={buildLoginPath()} className={styles.backHomeLink}>
            {t('clerk.backToLogin')}
          </Link>
        </div>
      </div>
    );
  }

  if (!isLoaded || isSignedIn) {
    return (
      <div className={styles.loginForm} role="status">
        <p style={{ textAlign: 'center', margin: 0 }}>
          {isSignedIn ? t('clerk.signingIn') : t('clerk.loading')}
        </p>
      </div>
    );
  }

  return mode === 'sign-up' ? (
    <SignUp
      routing="hash"
      signInUrl={SELF}
      forceRedirectUrl={SELF}
      signInForceRedirectUrl={SELF}
    />
  ) : (
    <SignIn
      routing="hash"
      signUpUrl={`${SELF}?mode=sign-up`}
      forceRedirectUrl={SELF}
      signUpForceRedirectUrl={SELF}
    />
  );
};

const ClerkSignIn = () => {
  const { t, i18n } = useTranslation('auth');
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [localization, setLocalization] = useState(null);
  const mode = searchParams.get('mode') === 'sign-up' ? 'sign-up' : 'sign-in';
  const dark =
    typeof document !== 'undefined' &&
    document.documentElement.getAttribute('data-theme') === 'dark';
  const lang = (i18n.language || 'es').slice(0, 2);

  useEffect(() => {
    let active = true;
    loadClerkConfig().then(c => active && setConfig(c));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    loadLocalization(lang).then(l => active && setLocalization({ value: l }));
    return () => {
      active = false;
    };
  }, [lang]);

  let content;
  if (!config || (config.enabled && !localization)) {
    content = (
      <div className={styles.loginForm} role="status">
        <p style={{ textAlign: 'center', margin: 0 }}>{t('clerk.loading')}</p>
      </div>
    );
  } else if (!config.enabled || !config.publishable_key) {
    content = (
      <div className={styles.loginForm} data-testid="clerk-unavailable">
        <p style={{ textAlign: 'center' }}>{t('clerk.notConfigured')}</p>
        <div className={styles.loginActions}>
          <Link to={buildLoginPath()} className={styles.backHomeLink}>
            {t('clerk.backToLogin')}
          </Link>
        </div>
      </div>
    );
  } else {
    content = (
      <ClerkProvider
        publishableKey={config.publishable_key}
        localization={localization.value}
        appearance={appearanceFor(dark)}
        routerPush={to => navigate(to)}
        routerReplace={to => navigate(to, { replace: true })}
        afterSignOutUrl={SELF}
      >
        <ClerkExchange mode={mode} />
      </ClerkProvider>
    );
  }

  return (
    <div className={styles.loginContainer}>
      <PublicNav overlay />
      <div
        style={{
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 16,
          position: 'relative',
          zIndex: 1,
        }}
      >
        {content}
        {config?.enabled && (
          <Link
            to={buildLoginPath()}
            className={`${styles.backHomeLink} ${styles.onDarkLink}`}
          >
            {t('clerk.backToLogin')}
          </Link>
        )}
      </div>
    </div>
  );
};

export default ClerkSignIn;
