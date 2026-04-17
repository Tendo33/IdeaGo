import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Check, Zap, Crown, Loader2, LogIn } from 'lucide-react'
import { Button, buttonVariants } from '@/components/ui/Button'
import { toast } from 'sonner'
import { useAuth } from '@/lib/auth/useAuth'
import { createCheckoutSession, getSubscriptionStatus } from '@/lib/api/client'

import { Alert } from '@/components/ui/Alert'

import { useDocumentTitle } from '@/hooks/useDocumentTitle'

export function PricingPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('pricing.title') + ' — IdeaGo')
  const { user } = useAuth()
  const [loading, setLoading] = useState(false)
  const [currentPlan, setCurrentPlan] = useState<string | null>(null)
  const [stripeConfigured, setStripeConfigured] = useState<boolean | null>(null)
  const [statusReloadToken, setStatusReloadToken] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const resolvedCurrentPlan = user ? currentPlan : 'free'

  useEffect(() => {
    if (!user) return
    let cancelled = false

    async function loadStatus() {
      setError(null)
      setCurrentPlan(null)
      setStripeConfigured(null)
      try {
        const status = await getSubscriptionStatus()
        if (cancelled) return
        setCurrentPlan(status.plan)
        setStripeConfigured(status.stripe_configured)
      } catch {
        if (cancelled) return
        setError(t('pricing.loadError'))
      }
    }

    void loadStatus()
    return () => {
      cancelled = true
    }
  }, [user, t, statusReloadToken])

  const handleUpgrade = async () => {
    if (!user) return
    setLoading(true)
    try {
      const url = await createCheckoutSession(
        `${window.location.origin}/profile?checkout=success`,
        `${window.location.origin}/pricing`,
      )
      window.location.href = url
    } catch {
      toast.error(t('pricing.upgradeError'))
      setLoading(false)
    }
  }

  const plans = [
    {
      name: t('admin.values.plans.free'),
      price: '$0',
      period: t('pricing.perMonth'),
      features: [
        t('pricing.freeFeature1'),
        t('pricing.freeFeature2'),
        t('pricing.freeFeature3'),
        t('pricing.freeFeature4'),
      ],
      current: resolvedCurrentPlan === 'free',
      icon: Zap,
    },
    {
      name: t('admin.values.plans.pro'),
      price: '$9',
      period: t('pricing.perMonth'),
      features: [
        t('pricing.proFeature1'),
        t('pricing.proFeature2'),
        t('pricing.proFeature3'),
        t('pricing.proFeature4'),
        t('pricing.proFeature5'),
        t('pricing.proFeature6'),
      ],
      current: resolvedCurrentPlan === 'pro',
      highlighted: true,
      icon: Crown,
    },
  ]

  return (
    <div className="app-shell max-w-4xl pt-12 pb-16 md:pt-16 md:pb-24">
      <Link
        to="/"
        className="topbar-action mb-8"
      >
        <ArrowLeft className="w-4 h-4 mr-2" />
        {t('nav.home')}
      </Link>

      <div className="border-4 border-border bg-card p-8 md:p-12 mb-12 shadow-lg relative group">
        <div className="absolute top-0 right-0 h-8 w-20 bg-primary/20 border-l-4 border-b-4 border-border" />
        <h1 className="text-4xl md:text-6xl font-black uppercase tracking-tighter mb-4 relative z-10">
          {t('pricing.title')}
        </h1>
        <p className="text-lg md:text-xl text-muted-foreground font-bold max-w-xl mb-6 relative z-10 border-l-4 border-primary pl-4">
          {t('pricing.subtitle')}
        </p>
        {user && error && (
          <Alert variant="warning" className="max-w-xl text-left relative z-10">
            <span className="font-bold">{error}</span>
          </Alert>
        )}
        <div className="absolute -bottom-4 -right-4 h-7 w-16 bg-success/25 border-4 border-border transition-colors group-hover:bg-success/35" />
      </div>

      <div className="grid md:grid-cols-2 gap-6 md:gap-8">
        {plans.map(plan => {
          const Icon = plan.icon
          return (
            <div
              key={plan.name}
              className={`border-4 bg-card p-6 md:p-8 transition-all duration-150 ease-brutal hover:translate-x-[-2px] hover:translate-y-[-2px] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none ${
                plan.highlighted
                  ? 'border-primary shadow-xl shadow-primary hover:shadow-2xl'
                  : 'border-border shadow-md hover:shadow-xl'
              }`}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className={`p-2 border-2 ${plan.highlighted ? 'border-primary bg-primary/10' : 'border-border bg-muted'}`}>
                  <Icon className={`w-5 h-5 ${plan.highlighted ? 'text-primary' : 'text-muted-foreground'}`} />
                </div>
                <h2 className="text-2xl font-black uppercase tracking-tight">{plan.name}</h2>
              </div>

              <div className="mb-6">
                <span className="text-4xl font-black">{plan.price}</span>
                <span className="text-muted-foreground font-bold ml-1">{plan.period}</span>
              </div>

              <ul className="space-y-3 mb-8">
                {plan.features.map(feature => (
                  <li key={feature} className="flex items-start gap-2">
                    <Check className={`w-4 h-4 mt-0.5 shrink-0 ${plan.highlighted ? 'text-primary' : 'text-muted-foreground'}`} />
                    <span className="text-sm font-bold">{feature}</span>
                  </li>
                ))}
              </ul>

              {plan.current ? (
                <Button variant="outline" size="lg" className="w-full" disabled>
                  {t('pricing.currentPlan')}
                </Button>
              ) : plan.highlighted && !user ? (
                <Link
                  to="/login"
                  className={buttonVariants({ size: 'lg', className: 'w-full gap-2' })}
                >
                  <LogIn className="w-5 h-5" />
                  {t('pricing.signInToUpgrade')}
                </Link>
              ) : plan.highlighted && user && error && stripeConfigured === null ? (
                <Button
                  variant="outline"
                  size="lg"
                  className="w-full"
                  onClick={() => setStatusReloadToken(previous => previous + 1)}
                >
                  {t('report.failed.retryShort')}
                </Button>
              ) : plan.highlighted && user && stripeConfigured === false ? (
                <Button variant="outline" size="lg" className="w-full" disabled>
                  {t('pricing.comingSoon')}
                </Button>
              ) : plan.highlighted && user && stripeConfigured === null ? (
                <Button variant="outline" size="lg" className="w-full" disabled>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  {t('loading.page')}
                </Button>
              ) : plan.highlighted && user ? (
                <Button
                  size="lg"
                  className="w-full"
                  onClick={handleUpgrade}
                  disabled={loading}
                >
                  {loading ? (
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  ) : (
                    <Crown className="w-5 h-5 mr-2" />
                  )}
                  {t('pricing.upgrade')}
                </Button>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
