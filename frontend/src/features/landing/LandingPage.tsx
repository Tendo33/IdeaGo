import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/Button'
import {
  ArrowRight,
  Search,
  Zap,
  FileText,
  Github,
  Globe,
  Smartphone,
  Rocket,
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
  { icon: Github, label: 'GitHub', color: 'var(--foreground)' },
  { icon: Globe, label: 'Web', color: 'var(--primary)' },
  { icon: HackerNewsIcon, label: 'Hacker News', color: 'oklch(0.7 0.15 60)' },
  { icon: Smartphone, label: 'App Store', color: 'oklch(0.6 0.2 260)' },
  { icon: Rocket, label: 'Product Hunt', color: 'oklch(0.6 0.2 25)' },
] as const

export function LandingPage() {
  const { t, i18n } = useTranslation()
  const currentLang = i18n.resolvedLanguage ?? i18n.language ?? 'en'
  const isChinese = currentLang.startsWith('zh')

  return (
    <div className="min-h-screen bg-background text-foreground overflow-hidden">
      {/* ─── TOP BAR ─── */}
      <nav className="fixed left-0 right-0 top-0 z-50 border-b-4 border-border bg-background/95 backdrop-blur-sm px-4 py-4 md:px-8 flex items-center justify-between">
        <span className="inline-block px-4 py-2 border-2 border-border font-bold uppercase tracking-widest bg-primary text-primary-foreground shadow-[4px_4px_0px_0px_var(--border)]">
          {t('app.title')} {t('app.titleHighlight')}
        </span>
        <div className="flex items-center gap-2 sm:gap-3">
          <button
            onClick={() => i18n.changeLanguage(isChinese ? 'en' : 'zh')}
            className="topbar-action min-w-[44px] px-2 sm:px-4 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            aria-label={isChinese ? 'Switch to English' : '切换到中文'}
          >
            {isChinese ? 'EN' : 'ZH'}
          </button>
          <Link
            to="/login"
            className="topbar-action bg-primary text-primary-foreground min-w-[44px] px-3 sm:px-4 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          >
            <LogIn className="w-5 h-5 shrink-0" />
            <span className="hidden sm:inline">{t('auth.signIn', 'Sign In')}</span>
          </Link>
        </div>
      </nav>

      {/* ─── HERO ─── */}
      <section className="relative px-4 pt-28 sm:pt-36 pb-24 sm:pb-32">
        <div className="app-shell">
          <div className="grid lg:grid-cols-[1.2fr_1fr] gap-12 lg:gap-20 items-start">
            {/* Left: headline */}
            <div className="animate-fade-in">
              <p className="text-sm font-black uppercase tracking-[0.25em] text-primary mb-6 border-l-4 border-primary pl-4">
                {t('landing.badge')}
              </p>
              <h1 className="font-heading uppercase tracking-tighter leading-[0.85] text-[clamp(3rem,8vw,7rem)] mb-8">
                {t('landing.heroLine1')}
                <br />
                <span className="text-primary">{t('landing.heroLine2')}</span>
              </h1>
              <p className="max-w-lg text-lg sm:text-xl font-bold text-muted-foreground leading-relaxed mb-10">
                {t('landing.heroDesc')}
              </p>
              <div className="flex flex-wrap gap-4 items-center">
                <Link to="/login">
                  <Button size="lg" className="text-base px-8 py-4">
                    {t('landing.cta')}
                    <ArrowRight className="w-5 h-5 ml-2" />
                  </Button>
                </Link>
                <a
                  href="#how-it-works"
                  className="inline-flex items-center gap-2 text-sm font-black uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t('landing.learnMore')}
                  <ChevronDown className="w-4 h-4" />
                </a>
              </div>
            </div>

            {/* Right: mock report card */}
            <div className="animate-fade-in [animation-delay:200ms] hidden lg:block">
              <div className="border-4 border-border bg-card p-8 shadow-[12px_12px_0px_0px_var(--border)] rotate-1 hover:rotate-0 transition-transform duration-500">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-3 h-3 bg-success border-2 border-border" />
                  <span className="text-xs font-black uppercase tracking-widest text-muted-foreground">
                    {t('landing.mockLabel')}
                  </span>
                </div>
                <p className="text-lg font-bold text-foreground mb-6 border-l-4 border-primary pl-4">
                  &ldquo;{t('landing.mockQuery')}&rdquo;
                </p>
                <div className="grid grid-cols-2 gap-4 mb-6">
                  {[
                    { val: '12', label: t('landing.mockCompetitors') },
                    { val: '87%', label: t('landing.mockRelevance') },
                    { val: '5', label: t('landing.mockSources') },
                    { val: '4m', label: t('landing.mockTime') },
                  ].map(stat => (
                    <div key={stat.label} className="border-2 border-border p-3 bg-background">
                      <span className="block text-2xl font-black text-primary leading-none">{stat.val}</span>
                      <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mt-1 block">
                        {stat.label}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-2 px-3 py-2 bg-success/10 border-2 border-success">
                  <Zap className="w-4 h-4 text-success" />
                  <span className="text-sm font-black uppercase tracking-wider text-success">
                    {t('landing.mockVerdict')}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Decorative grid lines */}
        <div
          className="absolute inset-0 -z-10 opacity-[0.03]"
          style={{
            backgroundImage: `
              linear-gradient(var(--foreground) 1px, transparent 1px),
              linear-gradient(90deg, var(--foreground) 1px, transparent 1px)
            `,
            backgroundSize: '60px 60px',
          }}
        />
      </section>

      {/* ─── DATA SOURCES STRIP ─── */}
      <section className="border-y-4 border-border py-8 bg-card overflow-hidden">
        <div className="app-shell">
          <p className="text-center text-xs font-black uppercase tracking-[0.3em] text-muted-foreground mb-6">
            {t('landing.sourcesLabel')}
          </p>
          <div className="flex flex-wrap justify-center gap-6 sm:gap-10">
            {DATA_SOURCES.map(({ icon: Icon, label, color }, i) => (
              <StaggerReveal key={label} delay={i * 80} className="flex items-center gap-3">
                <Icon className="w-6 h-6 shrink-0" style={{ color }} />
                <span className="text-sm sm:text-base font-black uppercase tracking-wider">{label}</span>
              </StaggerReveal>
            ))}
          </div>
        </div>
      </section>

      {/* ─── HOW IT WORKS ─── */}
      <section id="how-it-works" className="px-4 py-24 sm:py-32">
        <div className="app-shell">
          <StaggerReveal>
            <h2 className="text-center mb-4">
              {t('landing.howTitle')}
            </h2>
            <p className="text-center text-lg font-bold text-muted-foreground max-w-xl mx-auto mb-16">
              {t('landing.howSubtitle')}
            </p>
          </StaggerReveal>

          <div className="grid md:grid-cols-3 gap-0">
            {([
              { icon: Search, step: '01', titleKey: 'landing.step1Title', descKey: 'landing.step1Desc' },
              { icon: Zap, step: '02', titleKey: 'landing.step2Title', descKey: 'landing.step2Desc' },
              { icon: FileText, step: '03', titleKey: 'landing.step3Title', descKey: 'landing.step3Desc' },
            ] as const).map(({ icon: Icon, step, titleKey, descKey }, i) => (
              <StaggerReveal key={step} delay={i * 120}>
                <div className={`
                  p-8 sm:p-10 border-2 border-border bg-background
                  ${i === 1 ? 'md:border-x-0 md:bg-card md:shadow-[8px_8px_0px_0px_var(--border)] md:scale-105 md:z-10 relative' : ''}
                `}>
                  <div className="flex items-start gap-4 mb-6">
                    <span className="text-5xl font-black text-muted-foreground/15 leading-none select-none">{step}</span>
                    <div className="w-12 h-12 border-2 border-border bg-primary text-primary-foreground flex items-center justify-center shrink-0 shadow-[3px_3px_0px_0px_var(--border)]">
                      <Icon className="w-6 h-6" />
                    </div>
                  </div>
                  <h3 className="text-xl sm:text-2xl mb-3">{t(titleKey)}</h3>
                  <p className="text-base font-medium text-muted-foreground leading-relaxed">
                    {t(descKey)}
                  </p>
                </div>
              </StaggerReveal>
            ))}
          </div>
        </div>
      </section>

      {/* ─── FEATURE HIGHLIGHTS ─── */}
      <section className="px-4 py-24 sm:py-32 bg-card border-y-4 border-border">
        <div className="app-shell">
          <StaggerReveal>
            <h2 className="mb-16 max-w-3xl">
              {t('landing.featuresTitle')}
            </h2>
          </StaggerReveal>

          <div className="grid sm:grid-cols-2 gap-6">
            {([
              { titleKey: 'landing.feat1Title', descKey: 'landing.feat1Desc', accent: 'var(--primary)' },
              { titleKey: 'landing.feat2Title', descKey: 'landing.feat2Desc', accent: 'var(--success)' },
              { titleKey: 'landing.feat3Title', descKey: 'landing.feat3Desc', accent: 'var(--destructive)' },
              { titleKey: 'landing.feat4Title', descKey: 'landing.feat4Desc', accent: 'oklch(0.7 0.15 60)' },
            ] as const).map(({ titleKey, descKey, accent }, i) => (
              <StaggerReveal key={titleKey} delay={i * 100}>
                <div className="p-6 sm:p-8 border-2 border-border bg-background shadow-[4px_4px_0px_0px_var(--border)] h-full">
                  <div
                    className="w-full h-1 mb-6"
                    style={{ backgroundColor: accent }}
                  />
                  <h3 className="text-lg sm:text-xl mb-3">{t(titleKey)}</h3>
                  <p className="text-base font-medium text-muted-foreground leading-relaxed">
                    {t(descKey)}
                  </p>
                </div>
              </StaggerReveal>
            ))}
          </div>
        </div>
      </section>

      {/* ─── FINAL CTA ─── */}
      <section className="px-4 py-24 sm:py-32">
        <div className="app-shell">
          <StaggerReveal>
            <div className="border-4 border-border p-10 sm:p-16 bg-background shadow-[12px_12px_0px_0px_var(--border)] text-center max-w-3xl mx-auto">
              <h2 className="mb-6">{t('landing.ctaTitle')}</h2>
              <p className="text-lg font-bold text-muted-foreground max-w-md mx-auto mb-10">
                {t('landing.ctaDesc')}
              </p>
              <Link to="/login">
                <Button size="lg" className="text-base px-10 py-5">
                  {t('landing.ctaButton')}
                  <ArrowRight className="w-5 h-5 ml-2" />
                </Button>
              </Link>
            </div>
          </StaggerReveal>
        </div>
      </section>

      {/* ─── FOOTER ─── */}
      <footer className="border-t-4 border-border px-4 py-8">
        <div className="app-shell flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="text-sm font-bold text-muted-foreground">
            &copy; {new Date().getFullYear()} IdeaGo
          </span>
          <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground/60">
            {t('landing.footerTagline')}
          </span>
        </div>
      </footer>
    </div>
  )
}
