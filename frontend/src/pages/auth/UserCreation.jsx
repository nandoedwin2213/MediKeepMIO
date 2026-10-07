import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import UserRegistrationForm from '../../components/forms/UserRegistrationForm';
import PublicNav from '../../components/public/PublicNav';
import ClerkEntryButton from '../../components/auth/ClerkEntryButton';
import { buildLoginPath } from '../../utils/loginRedirect';
import { BRAND } from '../../config/brand';
import { Text, Group, ThemeIcon, List, Paper } from '@mantine/core';
import { IconShieldCheck } from '@tabler/icons-react';
import styles from '../../styles/pages/Login.module.css';

const UserCreation = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const { t } = useTranslation('auth');

  const handleSuccess = async ({ userData: _userData, formData }) => {
    // Public context success - auto-login and redirect to dashboard
    try {
      const result = await login({
        username: formData.username,
        password: formData.password,
      });

      if (result.success) {
        // Add a small delay to ensure auth state is fully saved before navigation
        await new Promise(resolve => setTimeout(resolve, 500));

        navigate('/dashboard', {
          state: {
            message: t('userCreation.welcomeMessage', {
              name: formData.firstName,
            }),
          },
        });
      } else {
        // If login result indicates failure, redirect to login page
        navigate(buildLoginPath({ reason: 'registered' }), {
          state: {
            message: t('userCreation.accountCreated'),
          },
        });
      }
    } catch (error) {
      // If auto-login fails, redirect to login page with success message
      navigate(buildLoginPath({ reason: 'registered' }), {
        state: {
          message: t('userCreation.accountCreated'),
        },
      });
    }
  };

  // Cancel and "back to login" are ordinary navigation, not a session event.
  // No reason: attaching one would tell a visitor who was never signed in that
  // they had been signed out, and would suppress a redirect that should happen.
  const handleCancel = () => {
    navigate(buildLoginPath());
  };

  return (
    <div className={styles.loginContainer}>
      <PublicNav overlay />
      <div className={`${styles.loginForm} ${styles.registerForm}`}>
        <div className={styles.loginHeader}>
          <h1>
            <img
              src={BRAND.logo}
              alt=""
              width={48}
              height={48}
              style={{
                verticalAlign: 'middle',
                marginRight: '12px',
                filter: 'drop-shadow(0 6px 16px rgba(11, 26, 51, 0.35))',
              }}
            />
            {t('userCreation.pageTitle')}
          </h1>
          <p style={{ margin: '4px 0 0', opacity: 0.8 }}>
            {t('userCreation.pageSubtitle')}
          </p>
        </div>

        <div className={styles.loginDivider}>
          <span>{t('userCreation.cardTitle')}</span>
        </div>

        <ClerkEntryButton mode="sign-up" showDivider={false} />

        <UserRegistrationForm
          onSuccess={handleSuccess}
          onCancel={handleCancel}
          isAdminContext={false}
        />

        <Paper p="md" mt="lg" radius="lg" className="silho-info-box">
          <Group align="flex-start" wrap="nowrap">
            <ThemeIcon size="md" radius="xl" className="silho-info-icon">
              <IconShieldCheck size={16} />
            </ThemeIcon>
            <div>
              <Text size="sm" fw={600}>
                {t('userCreation.whatHappensNext')}
              </Text>
              <List size="xs" c="dimmed" listStyleType="disc" mt={4}>
                <List.Item>{t('userCreation.nextSteps.autoRecord')}</List.Item>
                <List.Item>{t('userCreation.nextSteps.loggedIn')}</List.Item>
                <List.Item>
                  {t('userCreation.nextSteps.startManaging')}
                </List.Item>
                <List.Item>{t('userCreation.nextSteps.dataSecure')}</List.Item>
              </List>
            </div>
          </Group>
        </Paper>

        <div className={styles.loginActions}>
          <Link to={buildLoginPath()} className={styles.backHomeLink}>
            {t('userCreation.backToLogin')}
          </Link>
        </div>
      </div>
    </div>
  );
};

export default UserCreation;
