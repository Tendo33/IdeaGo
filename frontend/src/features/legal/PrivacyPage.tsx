import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

export function PrivacyPage() {
  const { t } = useTranslation()

  return (
    <div className="min-h-screen px-4 py-12 bg-background text-foreground">
      <article className="app-shell max-w-3xl prose prose-neutral dark:prose-invert">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm font-bold uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors no-underline mb-8"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('legal.backToHome', 'Back to Home')}
        </Link>

        <h1 className="text-4xl font-black uppercase tracking-tight border-b-4 border-border pb-4 mb-8">
          {t('legal.privacyTitle', 'Privacy Policy')}
        </h1>

        <p className="text-sm text-muted-foreground mb-8">
          {t('legal.lastUpdated', 'Last updated')}: 2026-03-22
        </p>

        <h2>{t('legal.privacy.collectTitle', '1. Information We Collect')}</h2>
        <p>
          {t(
            'legal.privacy.collect',
            'We collect information you provide when creating an account (email, display name), your search queries for generating reports, and standard usage analytics (page views, feature usage).',
          )}
        </p>

        <h2>{t('legal.privacy.useTitle', '2. How We Use Your Information')}</h2>
        <p>
          {t(
            'legal.privacy.use',
            'We use your information to provide and improve the Service, process payments, send important account notifications, and aggregate anonymized analytics.',
          )}
        </p>

        <h2>{t('legal.privacy.storageTitle', '3. Data Storage & Security')}</h2>
        <p>
          {t(
            'legal.privacy.storage',
            'Your data is stored securely using Supabase (PostgreSQL) with row-level security. We use HTTPS for all communications and never store payment card details — billing is handled entirely by Stripe.',
          )}
        </p>

        <h2>{t('legal.privacy.sharingTitle', '4. Data Sharing')}</h2>
        <p>
          {t(
            'legal.privacy.sharing',
            'We do not sell your personal data. We may share data with: Stripe (payment processing), Supabase (database hosting), and AI model providers (for report generation — queries only, not personal info).',
          )}
        </p>

        <h2>{t('legal.privacy.retentionTitle', '5. Data Retention')}</h2>
        <p>
          {t(
            'legal.privacy.retention',
            'Your reports and account data are retained as long as your account is active. Anonymous (non-authenticated) reports are automatically deleted after the configured TTL. You can delete your account and all associated data at any time from your profile settings.',
          )}
        </p>

        <h2>{t('legal.privacy.rightsTitle', '6. Your Rights')}</h2>
        <p>
          {t(
            'legal.privacy.rights',
            'You have the right to access, export, correct, and delete your personal data. You can delete your account from the Profile page, which will permanently remove all your data.',
          )}
        </p>

        <h2>{t('legal.privacy.cookiesTitle', '7. Cookies')}</h2>
        <p>
          {t(
            'legal.privacy.cookies',
            'We use essential cookies for authentication sessions. We do not use third-party advertising or tracking cookies.',
          )}
        </p>

        <h2>{t('legal.privacy.changesTitle', '8. Changes to This Policy')}</h2>
        <p>
          {t(
            'legal.privacy.changes',
            'We may update this privacy policy from time to time. We will notify you of significant changes via email or in-app notification.',
          )}
        </p>

        <h2>{t('legal.privacy.contactTitle', '9. Contact')}</h2>
        <p>
          {t(
            'legal.privacy.contact',
            'For privacy-related questions, please contact us through the channels listed on our website.',
          )}
        </p>
      </article>
    </div>
  )
}
