import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { buttonVariants } from '@/components/ui/Button'
import { ThemeModeMenu, type ThemeMode } from '@/app/ThemeModeMenu'
import { PRICING_ENABLED } from '@/lib/featureFlags'
import {
  ArrowRight,
  Search,
  Zap,
  FileText,
  Github,
  Globe,
  Smartphone,
  Rocket,
  MessageCircle,
  ChevronDown,
  LogIn,
} from 'lucide-react'

function HackerNewsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M0 0v24h24V0H0zm12.8 13.8V20h-1.6v-6.2L7.2 5.8h1.8l3 5.8 3-5.8h1.8l-4 8z" />
    </svg>
  )
}

function useInView(threshold = 0.15) {
  const ref = useRef<HTMLElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true) },
      { threshold },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [threshold])

  return { ref, visible }
}

function StaggerReveal({ children, delay = 0, className = '' }: {
  children: React.ReactNode
  delay?: number
  className?: string
}) {
  const { ref, visible } = useInView()
  return (
    <div
      ref={ref as React.RefObject<HTMLDivElement>}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(24px)',
        transition: `opacity 600ms ease-out ${delay}ms, transform 600ms ease-out ${delay}ms`,
      }}
    >
      {children}
    </div>
  )
}

const DATA_SOURCES = [
  { icon: Github, labelKey: 'landing.sourceNames.github', color: 'var(--foreground)' },
  { icon: Globe, labelKey: 'landing.sourceNames.tavily', color: 'var(--primary)' },
  { icon: HackerNewsIcon, labelKey: 'landing.sourceNames.hackernews', color: 'var(--warning)' },
  { icon: Smartphone, labelKey: 'landing.sourceNames.appstore', color: 'var(--primary)' },
  { icon: Rocket, labelKey: 'landing.sourceNames.producthunt', color: 'var(--destructive)' },
  { icon: MessageCircle, labelKey: 'landing.sourceNames.reddit', color: 'var(--foreground)' },
] as const

import { useDocumentTitle } from '@/hooks/useDocumentTitle'

function resolveLanguageCode(language: string | undefined): string {
  if (!language) return 'en'
  const [normalized] = language.split('-')
  return normalized || 'en'
}

function getLanguageDisplayName(language: string, uiLanguage: string): string {
  const normalizedLanguage = resolveLanguageCode(language)
  const normalizedUiLanguage = resolveLanguageCode(uiLanguage)

  try {
    const displayNames = new Intl.DisplayNames([normalizedUiLanguage], { type: 'language' })
    return displayNames.of(normalizedLanguage) ?? normalizedLanguage.toUpperCase()
  } catch {
    return normalizedLanguage.toUpperCase()
  }
}

export function LandingPage({
  themeMode,
  onSelectThemeMode,
}: {
  themeMode: ThemeMode
  onSelectThemeMode: (mode: ThemeMode) => void
}) {
  const { t, i18n } = useTranslation()
  useDocumentTitle(`${t('app.title')} — ${t('app.titleHighlight')}`)

  const currentLang = i18n.resolvedLanguage ?? i18n.language ?? 'en'
  const isChinese = currentLang.startsWith('zh')
  const nextLanguage = isChinese ? 'en' : 'zh'
  const languageToggleLabel = getLanguageDisplayName(nextLanguage, currentLang)

  return (
    <div className="min-h-screen bg-background text-foreground overflow-x-hidden">
      {/* ─── TOP BAR ─── */}
      <nav className="fixed left-0 right-0 top-0 z-50 border-b-4 border-border bg-background/95 backdrop-blur-sm px-4 py-4 md:px-8 flex items-center justify-between min-w-0">
        <Link to="/" className="inline-flex min-h-[44px] items-center px-2 sm:px-4 py-1.5 sm:py-2 border-2 border-border font-bold uppercase tracking-widest bg-primary text-primary-foreground shadow-sm truncate max-w-[50vw] sm:max-w-none text-xs sm:text-base hover:bg-foreground transition-colors">
          {t('app.title')} {t('app.titleHighlight')}
        </Link>
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
          <ThemeModeMenu themeMode={themeMode} onSelectThemeMode={onSelectThemeMode} />
          <button
            onClick={() => i18n.changeLanguage(nextLanguage)}
            className="topbar-action min-w-[44px] px-2 sm:px-4 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            aria-label={t('app.switchToLanguage', { language: languageToggleLabel })}
          >
            {isChinese ? 'EN' : 'ZH'}
          </button>
          {PRICING_ENABLED && (
            <Link
              to="/pricing"
              className="topbar-action bg-secondary text-secondary-foreground min-w-[44px] px-3 sm:px-4 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            >
              <span>{t('pricing.title', 'Pricing')}</span>
            </Link>
          )}
          <Link
            to="/login"
            className="topbar-action bg-primary text-primary-foreground min-w-[44px] px-3 sm:px-4 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          >
            <LogIn className="w-5 h-5 shrink-0" aria-hidden="true" />
            <span className="hidden sm:inline">{t('auth.signIn')}</span>
          </Link>
        </div>
      </nav>

      {/* ─── HERO ─── */}
      <section className="relative px-4 pt-32 sm:pt-48 pb-32 sm:pb-40 border-b-8 border-border">
        <div className="app-shell">
          <div className="grid lg:grid-cols-[1.3fr_1fr] gap-12 lg:gap-24 items-center">
            {/* Left: headline */}
            <div className="animate-fade-in relative z-10">
              <div className="inline-block border-4 border-border bg-primary text-primary-foreground px-6 py-2 mb-8 shadow-md transform -rotate-2">
                <p className="text-sm font-black uppercase tracking-[0.3em]">
                  {t('landing.badge')}
                </p>
              </div>
              <h1 className="font-heading uppercase tracking-tighter leading-[0.8] text-[clamp(2.5rem,10vw,8.5rem)] mb-10 drop-shadow">
                {t('landing.heroLine1')}
                <br />
                <span className="text-primary inline-block transform hover:scale-105 transition-transform cursor-default">{t('landing.heroLine2')}</span>
              </h1>
              <p className="max-w-xl text-xl sm:text-2xl font-bold text-muted-foreground leading-snug mb-12 min-w-0 break-words border-l-8 border-primary pl-6">
                {t('landing.heroDesc')}
              </p>
              <div className="flex flex-wrap gap-6 items-center">
                <Link
                  to="/login"
                  className={buttonVariants({
                    size: 'lg',
                    className: 'text-xl px-12 py-6 border-4 shadow-lg hover:translate-y-[-4px] hover:translate-x-[-4px] hover:shadow-xl transition-all',
                  })}
                >
                  {t('landing.cta')}
                  <ArrowRight className="w-6 h-6 ml-3" aria-hidden="true" />
                </Link>
                <a
                  href="#how-it-works"
                  className="inline-flex min-h-[44px] items-center gap-3 text-base font-black uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors group"
                >
                  {t('landing.learnMore')}
                  <ChevronDown className="w-5 h-5 group-hover:translate-y-1 transition-transform" aria-hidden="true" />
                </a>
              </div>
            </div>

            {/* Right: mock report card */}
            <div className="animate-fade-in [animation-delay:200ms] mt-12 lg:mt-0 relative w-full max-w-lg mx-auto lg:max-w-none">
              <div className="absolute inset-0 bg-primary translate-x-4 translate-y-4 border-4 border-border" />
              <div className="relative border-4 border-border bg-card p-10 shadow-2xl rotate-2 hover:rotate-0 transition-transform duration-500 hover:scale-105 z-10">
                <div className="flex items-center gap-4 mb-8">
                  <div className="w-4 h-4 bg-success border-4 border-border shrink-0 animate-pulse" />
                  <span className="text-sm font-black uppercase tracking-widest text-muted-foreground truncate" title={t('landing.mockLabel')}>
                    {t('landing.mockLabel')}
                  </span>
                </div>
                <p className="text-2xl font-black text-foreground mb-8 border-l-8 border-primary pl-6 line-clamp-3 leading-tight" title={t('landing.mockQuery')}>
                  &ldquo;{t('landing.mockQuery')}&rdquo;
                </p>
                <div className="flex flex-wrap border-t-4 border-border/20 pt-6 gap-y-6 mb-8">
                  {[
                    { val: '12', label: t('landing.mockCompetitors') },
                    { val: '87%', label: t('landing.mockRelevance') },
                    { val: '6', label: t('landing.mockSources') },
                    { val: '4m', label: t('landing.mockTime') },
                  ].map(stat => (
                    <div key={stat.label} className="w-1/2 flex flex-col pr-4 group cursor-default">
                      <span className="block text-4xl font-black text-primary leading-none truncate mb-2 group-hover:scale-105 transition-transform origin-left" title={stat.val}>{stat.val}</span>
                      <span className="text-xs font-black uppercase tracking-widest text-muted-foreground block truncate" title={stat.label}>
                        {stat.label}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-3 px-4 py-3 bg-success border-4 border-border mt-auto shadow transform -rotate-1">
                  <Zap className="w-6 h-6 text-success-foreground shrink-0" />
                  <span className="text-base font-black uppercase tracking-widest text-success-foreground truncate" title={t('landing.mockVerdict')}>
                    {t('landing.mockVerdict')}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Decorative grid lines */}
        <div
          className="absolute inset-0 -z-10 opacity-[0.05]"
          style={{
            backgroundImage: `
              linear-gradient(var(--foreground) 2px, transparent 2px),
              linear-gradient(90deg, var(--foreground) 2px, transparent 2px)
            `,
            backgroundSize: '100px 100px',
          }}
        />
      </section>

      {/* ─── DATA SOURCES STRIP ─── */}
      <section className="border-y-8 border-border py-12 bg-card overflow-hidden w-full min-w-0 relative">
        <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,rgba(0,0,0,0.02)_50%,transparent_75%,transparent_100%)] bg-[length:20px_20px] dark:bg-[linear-gradient(45deg,transparent_25%,rgba(255,255,255,0.02)_50%,transparent_75%,transparent_100%)] pointer-events-none" />
        <div className="app-shell relative z-10">
          <p className="text-center text-sm font-black uppercase tracking-[0.4em] text-muted-foreground mb-10">
            {t('landing.sourcesLabel')}
          </p>
          <div className="flex flex-wrap justify-center gap-8 sm:gap-16 py-4">
            {DATA_SOURCES.map(({ icon: Icon, labelKey, color }, i) => {
              const label = t(labelKey)
              return (
                <StaggerReveal key={labelKey} delay={i * 80} className="flex items-center gap-4 min-w-0 group cursor-default">
                  <div className="p-3 border-4 border-border bg-background shadow group-hover:-translate-y-2 group-hover:shadow-lg transition-all duration-300" style={{ color }}>
                    <Icon className="w-8 h-8 shrink-0" aria-hidden="true" />
                  </div>
                  <span className="text-lg sm:text-xl font-black uppercase tracking-widest truncate group-hover:text-primary transition-colors">{label}</span>
                </StaggerReveal>
              )
            })}
          </div>
        </div>
      </section>

      {/* ─── HOW IT WORKS ─── */}
      <section id="how-it-works" className="px-4 py-24 sm:py-32">
        <div className="app-shell">
          <StaggerReveal>
            <h2 className="text-center mb-4 text-[clamp(2.5rem,5vw,4.5rem)]">
              {t('landing.howTitle')}
            </h2>
            <p className="text-center text-lg font-bold text-muted-foreground max-w-xl mx-auto mb-20 min-w-0 break-words">
              {t('landing.howSubtitle')}
            </p>
          </StaggerReveal>

          <div className="flex flex-col md:flex-row gap-8 lg:gap-12 min-w-0">
            {([
              { icon: Search, step: '01', titleKey: 'landing.step1Title', descKey: 'landing.step1Desc', mt: 'mt-0' },
              { icon: Zap, step: '02', titleKey: 'landing.step2Title', descKey: 'landing.step2Desc', mt: 'md:mt-24' },
              { icon: FileText, step: '03', titleKey: 'landing.step3Title', descKey: 'landing.step3Desc', mt: 'md:mt-48' },
            ] as const).map(({ icon: Icon, step, titleKey, descKey, mt }, i) => (
              <StaggerReveal key={step} delay={i * 150} className={`flex-1 min-w-0 ${mt}`}>
                <div className="p-8 sm:p-10 border-4 border-border bg-background shadow-xl relative transition-transform duration-300 hover:-translate-y-4 hover:shadow-3xl flex flex-col min-w-0 group">
                  <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                    <Icon className="w-32 h-32" />
                  </div>
                  <div className="flex items-start gap-4 mb-8 relative z-10">
                    <span aria-hidden="true" className="text-7xl font-black text-muted-foreground/20 leading-none select-none tracking-tighter">{step}</span>
                    <div className="w-14 h-14 border-4 border-border bg-primary text-primary-foreground flex items-center justify-center shrink-0 shadow group-hover:scale-110 transition-transform">
                      <Icon className="w-7 h-7" />
                    </div>
                  </div>
                  <h3 className="text-2xl sm:text-3xl mb-4 truncate relative z-10" title={t(titleKey)}>{t(titleKey)}</h3>
                  <p className="text-lg font-medium text-muted-foreground leading-relaxed flex-1 line-clamp-4 relative z-10">
                    {t(descKey)}
                  </p>
                </div>
              </StaggerReveal>
            ))}
          </div>
        </div>
      </section>

      {/* ─── FEATURE HIGHLIGHTS ─── */}
      <section className="px-4 py-32 sm:py-48 bg-muted border-y-8 border-border relative">
        <div className="absolute inset-0 bg-[radial-gradient(var(--border)_2px,transparent_2px)] [background-size:32px_32px] opacity-10" />
        <div className="app-shell relative z-10">
          <StaggerReveal>
            <h2 className="mb-20 max-w-4xl text-[clamp(2.5rem,5vw,4.5rem)] leading-none">
              {t('landing.featuresTitle')}
            </h2>
          </StaggerReveal>

          <div className="grid sm:grid-cols-12 gap-8 lg:gap-12 relative z-10">
            {/* Massive Hero Highlight Card */}
            <StaggerReveal className="sm:col-span-12 lg:col-span-12 mb-8">
              <div className="p-12 sm:p-16 border-8 border-border bg-card shadow-4xl relative group hover:-translate-y-2 hover:shadow-5xl transition-all duration-500">
                <div className="absolute top-0 right-0 w-64 h-64 bg-primary rounded-full blur-[100px] opacity-20 group-hover:opacity-40 transition-opacity" />
                <h3 className="text-[clamp(3rem,6vw,5rem)] leading-[0.9] mb-8 max-w-3xl relative z-10">
                  {t('landing.feat1Title')}
                </h3>
                <p className="text-xl sm:text-2xl font-bold text-muted-foreground leading-relaxed max-w-2xl relative z-10">
                  {t('landing.feat1Desc')}
                </p>
                <div className="absolute bottom-8 right-8 w-24 h-24 border-8 border-primary rounded-full animate-[spin_10s_linear_infinite] opacity-50" />
              </div>
            </StaggerReveal>

            {/* Smaller Secondary Cards */}
            {([
              { titleKey: 'landing.feat2Title', descKey: 'landing.feat2Desc', accent: 'var(--success)', colSpan: 'sm:col-span-12 lg:col-span-6', rotation: '-rotate-1', shape: 'rounded-none' },
              { titleKey: 'landing.feat3Title', descKey: 'landing.feat3Desc', accent: 'var(--destructive)', colSpan: 'sm:col-span-12 lg:col-span-6', rotation: 'rotate-1', shape: 'rounded-full' },
            ] as const).map(({ titleKey, descKey, accent, colSpan, rotation, shape }, i) => (
              <StaggerReveal key={titleKey} delay={i * 150} className={colSpan}>
                <div className={`p-8 sm:p-12 border-4 border-border bg-background shadow-xl h-full flex flex-col min-w-0 group hover:bg-card transition-colors duration-300 transform ${rotation} hover:rotate-0`}>
                  <div className="flex items-center gap-6 mb-8">
                    <div
                      className={`w-16 h-16 border-4 border-border shrink-0 ${shape} group-hover:scale-110 transition-transform shadow`}
                      style={{ backgroundColor: accent }}
                    />
                    <h3 className="text-2xl sm:text-3xl truncate group-hover:text-primary transition-colors" title={t(titleKey)}>{t(titleKey)}</h3>
                  </div>
                  <p className="text-lg sm:text-xl font-medium text-muted-foreground leading-relaxed flex-1 line-clamp-4">
                    {t(descKey)}
                  </p>
                </div>
              </StaggerReveal>
            ))}
          </div>
        </div>
      </section>

      {/* ─── FINAL CTA ─── */}
      <section className="px-4 py-32 sm:py-48 relative overflow-hidden">
        {/* Wild background shapes */}
        <div className="absolute top-1/2 left-0 w-96 h-96 bg-primary/20 rounded-full blur-3xl -translate-y-1/2 -translate-x-1/2 pointer-events-none" />
        <div className="absolute top-1/2 right-0 w-96 h-96 bg-destructive/20 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none" />

        <div className="app-shell relative z-10">
          <StaggerReveal>
            <div className="border-8 border-border p-12 sm:p-24 bg-card shadow-4xl text-center max-w-4xl mx-auto transform hover:-translate-y-2 hover:shadow-5xl transition-all duration-500 relative">
              <div className="absolute -top-6 -right-6 w-12 h-12 bg-warning border-4 border-border rotate-12" />
              <div className="absolute -bottom-6 -left-6 w-16 h-16 bg-success border-4 border-border rounded-full -rotate-12" />

              <h2 className="mb-8 text-[clamp(2.5rem,6vw,5rem)] leading-none">{t('landing.ctaTitle')}</h2>
              <p className="text-xl sm:text-2xl font-bold text-muted-foreground max-w-2xl mx-auto mb-12 line-clamp-3 min-w-0 break-words leading-relaxed">
                {t('landing.ctaDesc')}
              </p>
              <Link
                to="/login"
                className={buttonVariants({
                  size: 'lg',
                  className: 'text-2xl px-16 py-8 border-4 shadow-lg hover:translate-y-[-4px] hover:translate-x-[-4px] hover:shadow-2xl transition-all group',
                })}
              >
                {t('landing.ctaButton')}
                <ArrowRight className="w-8 h-8 ml-4 group-hover:translate-x-2 transition-transform" aria-hidden="true" />
              </Link>
            </div>
          </StaggerReveal>
        </div>
      </section>

      {/* ─── FOOTER ─── */}
      <footer className="border-t-4 border-border px-4 py-8">
        <div className="app-shell flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="text-sm font-bold text-muted-foreground truncate">
            &copy; {new Date().getFullYear()} IdeaGo
          </span>
          <div className="flex items-center gap-4">
            <Link to="/terms" className="text-xs font-bold uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors">
              {t('legal.termsTitle', 'Terms')}
            </Link>
            <Link to="/privacy" className="text-xs font-bold uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors">
              {t('legal.privacyTitle', 'Privacy')}
            </Link>
          </div>
          <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground truncate" title={t('landing.footerTagline')}>
            {t('landing.footerTagline')}
          </span>
        </div>
      </footer>
    </div>
  )
}
