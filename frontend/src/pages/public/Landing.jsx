import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  IconActivity,
  IconArrowRight,
  IconBrain,
  IconCalendarWeek,
  IconChartLine,
  IconCheck,
  IconDeviceWatch,
  IconFlask,
  IconHeartbeat,
  IconLock,
  IconRun,
  IconSalad,
  IconShieldCheck,
  IconStethoscope,
  IconTargetArrow,
  IconUsers,
} from '@tabler/icons-react';
import { BRAND } from '../../config/brand';
import billingApi from '../../services/api/billingApi';
import {
  formatMoney,
  monthlyEquivalent,
  PLAN_FEATURES,
  savingPercent,
} from '../../utils/billing';
import './Landing.css';

const STEPS = [
  { key: 'measure', icon: IconActivity },
  { key: 'interpret', icon: IconChartLine },
  { key: 'intervene', icon: IconTargetArrow },
  { key: 'follow', icon: IconHeartbeat },
];

const MODULES = [
  { key: 'labs', icon: IconFlask, image: '/landing/laboratorio.jpg' },
  { key: 'exercise', icon: IconRun, image: '/landing/ejercicio.jpg' },
  { key: 'nutrition', icon: IconSalad, image: '/landing/nutricion.jpg' },
  { key: 'wearables', icon: IconDeviceWatch, image: '/landing/wearable.jpg' },
];

const TOOLS = [
  { key: 'assistant', icon: IconBrain },
  { key: 'week', icon: IconCalendarWeek },
  { key: 'team', icon: IconUsers },
  { key: 'privacy', icon: IconLock },
];

const FAQ = ['what', 'who', 'doctor', 'data', 'cancel'];

const SCORE_LEVELS = ['favorable', 'initial', 'moderate', 'high'];

function Landing() {
  const { t, i18n } = useTranslation('common');
  const [billing, setBilling] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    billingApi
      .getPlans(controller.signal)
      .then(setBilling)
      .catch(() => setBilling(null));
    return () => controller.abort();
  }, []);

  const plans = billing?.plans || [];
  const currency = billing?.currency || 'USD';

  return (
    <div className="lp">
      <header className="lp-nav">
        <Link to="/" className="lp-brand" aria-label={BRAND.name}>
          <img src={BRAND.logo} alt="" width="36" height="36" />
          <span>{BRAND.name}</span>
        </Link>
        <nav className="lp-nav-links" aria-label={t('landing.nav.label')}>
          <a href="#como-funciona">{t('landing.nav.how')}</a>
          <a href="#programa">{t('landing.nav.program')}</a>
          <a href="#planes">{t('landing.nav.plans')}</a>
          <a href="#preguntas">{t('landing.nav.faq')}</a>
        </nav>
        <div className="lp-nav-cta">
          <Link to="/login" className="lp-btn lp-btn-ghost">
            {t('landing.cta.login')}
          </Link>
          <Link to="/user-creation" className="lp-btn lp-btn-gold">
            {t('landing.cta.start')}
          </Link>
        </div>
      </header>

      <section className="lp-hero">
        <div className="lp-hero-text">
          <span className="lp-eyebrow">{t('landing.hero.eyebrow')}</span>
          <h1>{t('landing.hero.title')}</h1>
          <p className="lp-lead">{t('landing.hero.subtitle')}</p>
          <div className="lp-hero-cta">
            <Link to="/user-creation" className="lp-btn lp-btn-gold lp-btn-lg">
              {t('landing.cta.start')} <IconArrowRight size={18} />
            </Link>
            <Link to="/login" className="lp-btn lp-btn-outline lp-btn-lg">
              {t('landing.cta.haveAccount')}
            </Link>
          </div>
          <ul className="lp-trust">
            <li>
              <IconShieldCheck size={18} /> {t('landing.hero.trust1')}
            </li>
            <li>
              <IconStethoscope size={18} /> {t('landing.hero.trust2')}
            </li>
            <li>
              <IconLock size={18} /> {t('landing.hero.trust3')}
            </li>
          </ul>
        </div>
        <div className="lp-hero-visual">
          <img
            src="/landing/consulta.jpg"
            alt={t('landing.hero.imageAlt')}
            className="lp-hero-img"
          />
          <div className="lp-score-card" aria-hidden="true">
            <div className="lp-score-head">
              <span>
                {t('landing.score.label', { brand: BRAND.metabolicScoreBrand })}
              </span>
              <strong>72</strong>
            </div>
            <div className="lp-score-bar">
              {SCORE_LEVELS.map(level => (
                <span
                  key={level}
                  className={`lp-level lp-level-${level}${level === 'initial' ? ' is-current' : ''}`}
                >
                  {t(`landing.score.${level}`)}
                </span>
              ))}
            </div>
            <p>{t('landing.score.change')}</p>
          </div>
        </div>
      </section>

      <section className="lp-section" id="como-funciona">
        <div className="lp-section-head">
          <span className="lp-eyebrow">{t('landing.steps.eyebrow')}</span>
          <h2>{t('landing.steps.title')}</h2>
          <p>{t('landing.steps.subtitle')}</p>
        </div>
        <ol className="lp-steps">
          {STEPS.map(({ key, icon: Icon }, index) => (
            <li key={key} className="lp-step">
              <span className="lp-step-num">{index + 1}</span>
              <Icon size={30} stroke={1.6} />
              <h3>{t(`landing.steps.${key}.title`)}</h3>
              <p>{t(`landing.steps.${key}.text`)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="lp-section lp-section-alt" id="programa">
        <div className="lp-section-head">
          <span className="lp-eyebrow">{t('landing.modules.eyebrow')}</span>
          <h2>{t('landing.modules.title')}</h2>
        </div>
        <div className="lp-modules">
          {MODULES.map(({ key, icon: Icon, image }, index) => (
            <article
              key={key}
              className={`lp-module${index % 2 ? ' is-reversed' : ''}`}
            >
              <img
                src={image}
                alt={t(`landing.modules.${key}.alt`)}
                loading="lazy"
              />
              <div className="lp-module-text">
                <span className="lp-module-icon">
                  <Icon size={22} />
                </span>
                <h3>{t(`landing.modules.${key}.title`)}</h3>
                <p>{t(`landing.modules.${key}.text`)}</p>
                <ul>
                  {[1, 2, 3].map(n => (
                    <li key={n}>
                      <IconCheck size={16} />{' '}
                      {t(`landing.modules.${key}.point${n}`)}
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          ))}
        </div>
        <div className="lp-tools">
          {TOOLS.map(({ key, icon: Icon }) => (
            <div key={key} className="lp-tool">
              <Icon size={26} stroke={1.6} />
              <h3>{t(`landing.tools.${key}.title`)}</h3>
              <p>{t(`landing.tools.${key}.text`)}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="lp-section lp-plans-section" id="planes">
        <div className="lp-section-head">
          <span className="lp-eyebrow">{t('landing.plans.eyebrow')}</span>
          <h2>{t('landing.plans.title')}</h2>
          <p>{t('landing.plans.subtitle')}</p>
        </div>
        <div className="lp-plans">
          {plans.map(plan => {
            const saving = savingPercent(plan, plans);
            const featured = plan.months === 3;
            return (
              <article
                key={plan.id}
                className={`lp-plan${featured ? ' is-featured' : ''}`}
              >
                {featured && (
                  <span className="lp-plan-badge">
                    {t('landing.plans.popular')}
                  </span>
                )}
                <h3>{t(`billing.plans.${plan.id}`, plan.id)}</h3>
                <p className="lp-plan-price">
                  {formatMoney(plan.amount_cents, currency, i18n.language)}
                </p>
                <p className="lp-plan-period">
                  {t(`billing.period.${plan.id}`, String(plan.months))}
                  {plan.months > 1 &&
                    ` · ${t('billing.perMonth', {
                      amount: formatMoney(
                        monthlyEquivalent(plan),
                        currency,
                        i18n.language
                      ),
                    })}`}
                </p>
                {saving > 0 && (
                  <p className="lp-plan-saving">
                    {t('billing.saving', { percent: saving })}
                  </p>
                )}
                <ul>
                  {PLAN_FEATURES.map(feature => (
                    <li key={feature}>
                      <IconCheck size={16} /> {t(`billing.features.${feature}`)}
                    </li>
                  ))}
                </ul>
                <Link
                  to="/user-creation"
                  className={`lp-btn ${featured ? 'lp-btn-gold' : 'lp-btn-dark'}`}
                >
                  {t('landing.plans.cta')}
                </Link>
              </article>
            );
          })}
        </div>
        <p className="lp-plans-note">{t('landing.plans.note')}</p>
      </section>

      <section className="lp-section lp-section-alt" id="preguntas">
        <div className="lp-section-head">
          <h2>{t('landing.faq.title')}</h2>
        </div>
        <div className="lp-faq">
          {FAQ.map(key => (
            <details key={key}>
              <summary>{t(`landing.faq.${key}.q`)}</summary>
              <p>{t(`landing.faq.${key}.a`)}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="lp-final">
        <h2>{t('landing.final.title')}</h2>
        <p>{t('landing.final.text')}</p>
        <div className="lp-hero-cta">
          <Link to="/user-creation" className="lp-btn lp-btn-gold lp-btn-lg">
            {t('landing.cta.start')} <IconArrowRight size={18} />
          </Link>
          <Link to="/login" className="lp-btn lp-btn-outline lp-btn-lg">
            {t('landing.cta.login')}
          </Link>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="lp-brand">
          <img src={BRAND.logo} alt="" width="28" height="28" />
          <span>{BRAND.fullName}</span>
        </div>
        <p>{t('landing.footer.disclaimer')}</p>
        <p className="lp-credits">{t('landing.footer.credits')}</p>
      </footer>
    </div>
  );
}

export default Landing;
