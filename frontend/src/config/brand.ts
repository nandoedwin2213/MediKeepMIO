/**
 * Clinic branding for this deployment. Upstream MediKeep strings and assets
 * are swapped for these values across the UI.
 */
export const BRAND = {
  name: 'SILHO',
  fullName: 'SILHO Servicios Médicos',
  tagline: 'Plataforma de gestión de la resistencia a la insulina',
  logo: '/silho-icon.svg',
  defaultLanguage: 'es',
  // Upstream MediKeep release notes mention its GitHub contributors; not for clinic staff.
  showReleaseNotes: false,
};

/**
 * Modules outside the insulin-resistance care pathway. Their pages still
 * exist; they are only removed from navigation and the dashboard.
 */
export const HIDDEN_MODULE_PATHS = [
  '/injuries',
  '/immunizations',
  '/procedures',
  '/pharmacies',
  '/insurance',
  '/medical-equipment',
];

export const isModuleHidden = (path?: string): boolean =>
  HIDDEN_MODULE_PATHS.some(
    hidden => path === hidden || Boolean(path?.startsWith(`${hidden}/`))
  );
