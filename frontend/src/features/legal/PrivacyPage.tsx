import { ArrowLeft, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'

interface LegalSection {
  id: string
  title: string
  body: string
}

export function PrivacyPage() {
  const { t, i18n } = useTranslation()
  const isChinese = (i18n.resolvedLanguage ?? i18n.language ?? 'en').startsWith('zh')

  useDocumentTitle(`${t('legal.privacyTitle', 'Privacy Policy')} | IdeaGo`)

  const pageCopy = isChinese
    ? {
        intro: '这份说明介绍了 IdeaGo 会收集哪些数据、如何使用这些数据，以及您可以如何访问、导出或删除自己的信息。',
        panelTitle: '重点关注',
        panelBody: '如果您最关心个人信息边界，建议优先查看数据共享、数据保留和您的权利这三个部分。',
        navTitle: '章节导航',
        summaryLabel: '数据范围',
        summaryValue: '账户资料、查询内容、使用行为与结算相关信息',
        noteTitle: '隐私更新通知',
        noteBody: '当本政策出现重要更新时，我们会通过页面、站内通知或邮件告知您。最新版本始终以本页为准。',
      }
    : {
        intro:
          'This policy explains what IdeaGo collects, how the information is used, and how you can access, export, or delete your data.',
        panelTitle: 'What matters most',
        panelBody:
          'If you mainly care about data boundaries, start with Data Sharing, Data Retention, and Your Rights.',
        navTitle: 'Section map',
        summaryLabel: 'Data scope',
        summaryValue: 'Account details, queries, usage events, and billing-related records',
        noteTitle: 'Privacy update notice',
        noteBody:
          'When this policy changes in a material way, we will notify you through the page, in-app notices, or email. The latest version on this page is the current policy.',
      }

  const sections: LegalSection[] = [
    {
      id: 'collect',
      title: t('legal.privacy.collectTitle', '1. Information We Collect'),
      body: t(
        'legal.privacy.collect',
        'We collect information you provide when creating an account (email, display name), your search queries for generating reports, and standard usage analytics (page views, feature usage).',
      ),
    },
    {
      id: 'use',
      title: t('legal.privacy.useTitle', '2. How We Use Your Information'),
      body: t(
        'legal.privacy.use',
        'We use your information to provide and improve the Service, process payments, send important account notifications, and aggregate anonymized analytics.',
      ),
    },
    {
      id: 'storage',
      title: t('legal.privacy.storageTitle', '3. Data Storage & Security'),
      body: t(
        'legal.privacy.storage',
        'Your data is stored securely using Supabase (PostgreSQL) with row-level security. We use HTTPS for all communications and never store payment card details - billing is handled entirely by Stripe.',
      ),
    },
    {
      id: 'sharing',
      title: t('legal.privacy.sharingTitle', '4. Data Sharing'),
      body: t(
        'legal.privacy.sharing',
        'We do not sell your personal data. We may share data with: Stripe (payment processing), Supabase (database hosting), and AI model providers (for report generation - queries only, not personal info).',
      ),
    },
    {
      id: 'retention',
      title: t('legal.privacy.retentionTitle', '5. Data Retention'),
      body: t(
        'legal.privacy.retention',
        'Your reports and account data are retained as long as your account is active. Anonymous (non-authenticated) reports are automatically deleted after the configured TTL. You can delete your account and all associated data at any time from your profile settings.',
      ),
    },
    {
      id: 'rights',
      title: t('legal.privacy.rightsTitle', '6. Your Rights'),
      body: t(
        'legal.privacy.rights',
        'You have the right to access, export, correct, and delete your personal data. You can delete your account from the Profile page, which will permanently remove all your data.',
      ),
    },
    {
      id: 'cookies',
      title: t('legal.privacy.cookiesTitle', '7. Cookies'),
      body: t(
        'legal.privacy.cookies',
        'We use essential cookies for authentication sessions. We do not use third-party advertising or tracking cookies.',
      ),
    },
    {
      id: 'changes',
      title: t('legal.privacy.changesTitle', '8. Changes to This Policy'),
      body: t(
        'legal.privacy.changes',
        'We may update this privacy policy from time to time. We will notify you of significant changes via email or in-app notification.',
      ),
    },
    {
      id: 'contact',
      title: t('legal.privacy.contactTitle', '9. Contact'),
      body: t(
        'legal.privacy.contact',
        'For privacy-related questions, please contact us through the channels listed on our website.',
      ),
    },
  ]

  return (
    <div className="relative min-h-screen overflow-hidden bg-background px-4 pb-20 text-foreground">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.05]"
        style={{
          backgroundImage:
            'radial-gradient(circle at 1px 1px, var(--foreground) 1px, transparent 0), linear-gradient(135deg, color-mix(in oklab, var(--primary) 10%, transparent), transparent 38%)',
          backgroundSize: '28px 28px, 100% 100%',
        }}
      />
      <div className="absolute right-0 top-28 h-56 w-56 -translate-x-8 border-8 border-primary/20 bg-primary/10" aria-hidden="true" />
      <div className="absolute left-8 top-64 h-20 w-20 border-4 border-border bg-card shadow-lg" aria-hidden="true" />

      <article className="app-shell relative z-10 max-w-6xl">
        <header className="border-4 border-border bg-card shadow-xl">
          <div className="grid gap-8 p-6 md:grid-cols-[minmax(0,1.4fr)_280px] md:p-10">
            <div>
              <Link
                to="/"
                className="mb-6 inline-flex min-h-[44px] items-center gap-2 text-sm font-bold uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
              >
                <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                {t('legal.backToHome', 'Back to Home')}
              </Link>

              <div className="mb-5 inline-flex items-center border-2 border-border bg-primary px-4 py-2 text-xs font-black uppercase tracking-[0.3em] text-primary-foreground shadow">
                {pageCopy.summaryLabel}
              </div>

              <h1 className="max-w-3xl text-[clamp(2.8rem,7vw,5.6rem)] leading-[0.9] text-foreground">
                {t('legal.privacyTitle', 'Privacy Policy')}
              </h1>

              <p className="mt-6 max-w-2xl border-l-8 border-primary pl-5 text-base font-medium leading-8 text-muted-foreground md:text-lg">
                {pageCopy.intro}
              </p>
            </div>

            <div className="flex flex-col gap-4 border-2 border-border bg-background p-5 shadow-md">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.28em] text-muted-foreground">
                  {t('legal.lastUpdated', 'Last updated')}
                </p>
                <p className="mt-2 text-2xl font-black text-foreground">2026-03-22</p>
              </div>

              <div className="border-t-2 border-border pt-4">
                <p className="text-xs font-black uppercase tracking-[0.28em] text-muted-foreground">
                  {pageCopy.panelTitle}
                </p>
                <p className="mt-3 text-sm leading-7 text-muted-foreground">{pageCopy.panelBody}</p>
              </div>

              <div className="border-t-2 border-border pt-4">
                <p className="text-xs font-black uppercase tracking-[0.28em] text-muted-foreground">
                  {pageCopy.summaryLabel}
                </p>
                <p className="mt-3 text-sm font-bold leading-7 text-foreground">{pageCopy.summaryValue}</p>
              </div>
            </div>
          </div>
        </header>

        <div className="mt-10 grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)] lg:items-start">
          <aside className="border-2 border-border bg-card p-5 shadow-md lg:sticky lg:top-32">
            <p className="mb-4 text-xs font-black uppercase tracking-[0.28em] text-muted-foreground">
              {pageCopy.navTitle}
            </p>
            <nav aria-label={pageCopy.navTitle} className="space-y-2">
              {sections.map(section => (
                <a
                  key={section.id}
                  href={`#${section.id}`}
                  className="group flex items-start justify-between gap-3 border-2 border-transparent px-3 py-3 text-sm font-bold leading-6 text-muted-foreground transition-all hover:border-border hover:bg-background hover:text-foreground"
                >
                  <span>{section.title}</span>
                  <ArrowRight className="mt-1 h-4 w-4 shrink-0 transition-transform group-hover:translate-x-1" aria-hidden="true" />
                </a>
              ))}
            </nav>
          </aside>

          <div className="space-y-5">
            {sections.map(section => (
              <section
                key={section.id}
                id={section.id}
                className="border-4 border-border bg-card p-6 shadow-lg transition-transform duration-200 hover:-translate-y-1 md:p-8"
              >
                <div className="mb-5 flex items-start gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center border-2 border-border bg-primary text-lg font-black text-primary-foreground shadow">
                    {section.title.split('.')[0]}
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-[clamp(1.7rem,4vw,2.8rem)] leading-[1.02] text-foreground">{section.title}</h2>
                  </div>
                </div>
                <p className="max-w-4xl text-base leading-8 text-muted-foreground md:text-lg">{section.body}</p>
              </section>
            ))}

            <section className="border-4 border-border bg-primary px-6 py-7 text-primary-foreground shadow-xl md:px-8">
              <p className="text-xs font-black uppercase tracking-[0.28em] opacity-80">{pageCopy.noteTitle}</p>
              <p className="mt-3 max-w-4xl text-base font-bold leading-8 md:text-lg">{pageCopy.noteBody}</p>
            </section>
          </div>
        </div>
      </article>
    </div>
  )
}
