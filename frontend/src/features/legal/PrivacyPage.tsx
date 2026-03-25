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
            'We collect the idea queries you submit to generate reports, locally persisted report data, and standard operational telemetry needed to keep the service running.',
          )}
        </p>

        <h2>{t('legal.privacy.useTitle', '2. How We Use Your Information')}</h2>
        <p>
          {t(
            'legal.privacy.use',
            'We use this information to generate reports, improve retrieval and report quality, and keep the service stable.',
          )}
        </p>

        <h2>{t('legal.privacy.storageTitle', '3. Data Storage & Security')}</h2>
        <p>
          {t(
            'legal.privacy.storage',
            'On the main branch, reports are stored locally using file-based persistence and local SQLite checkpoints. We recommend HTTPS for public deployments and do not require payment or account data.',
          )}
        </p>

        <h2>{t('legal.privacy.sharingTitle', '4. Data Sharing')}</h2>
        <p>
          {t(
            'legal.privacy.sharing',
            'We do not sell your personal data. Report queries may be sent to configured model and retrieval providers only to produce the report you requested.',
          )}
        </p>

        <h2>{t('legal.privacy.retentionTitle', '5. Data Retention')}</h2>
        <p>
          {t(
            'legal.privacy.retention',
            'Anonymous reports are retained according to the configured TTL for the local file cache. If you self-host the service, you control the stored files and retention policy.',
          )}
        </p>

        <h2>{t('legal.privacy.rightsTitle', '6. Your Rights')}</h2>
        <p>
          {t(
            'legal.privacy.rights',
            'If you self-host the service, you control access, export, and deletion of locally stored report data. Export is available directly from the report page.',
          )}
        </p>

        <h2>{t('legal.privacy.cookiesTitle', '7. Cookies')}</h2>
        <p>
          {t(
            'legal.privacy.cookies',
            'The personal deployment does not require login cookies. We do not use third-party advertising cookies.',
          )}
        </p>

        <h2>{t('legal.privacy.changesTitle', '8. Changes to This Policy')}</h2>
        <p>
          {t(
            'legal.privacy.changes',
            'We may update this privacy policy from time to time by changing the documentation in the repository or deployed app.',
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
