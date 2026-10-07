import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { BRAND } from '../../config/brand';
import './PublicNav.css';

function PublicNav({ links = [], overlay = false }) {
  const { t } = useTranslation('common');
  const { pathname } = useLocation();

  return (
    <header
      className={`silho-pubnav${overlay ? ' silho-pubnav--overlay' : ''}`}
      data-testid="public-nav"
    >
      <Link to="/" className="silho-pubnav-brand" aria-label={BRAND.name}>
        <img src={BRAND.logo} alt="" width="36" height="36" />
        <span>{BRAND.name}</span>
      </Link>
      {links.length > 0 && (
        <nav className="silho-pubnav-links" aria-label={t('landing.nav.label')}>
          {links.map(link => (
            <a key={link.href} href={link.href}>
              {link.label}
            </a>
          ))}
        </nav>
      )}
      <div className="silho-pubnav-cta">
        {pathname !== '/login' && (
          <Link to="/login" className="silho-btn silho-btn-ghost">
            {t('landing.cta.login')}
          </Link>
        )}
        {pathname !== '/user-creation' && (
          <Link to="/user-creation" className="silho-btn silho-btn-gold">
            {t('landing.cta.start')}
          </Link>
        )}
      </div>
    </header>
  );
}

export default PublicNav;
