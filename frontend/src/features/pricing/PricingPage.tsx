import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Check, Zap, Crown, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/lib/auth/useAuth'
import { createCheckoutSession, getSubscriptionStatus } from '@/lib/api/client'

export function PricingPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [loading, setLoading] = useState(false)
  const [currentPlan, setCurrentPlan] = useState('free')
  const [stripeConfigured, setStripeConfigured] = useState(false)

  useEffect(() => {
    if (!user) return
    getSubscriptionStatus()
      .then(status => {
        setCurrentPlan(status.plan)
        setStripeConfigured(status.stripe_configured)
      })
      .catch(() => {})
  }, [user])

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
      setLoading(false)
    }
  }

  const plans = [
    {
      name: 'Free',
      price: '$0',
      period: t('pricing.perMonth', '/month'),
      features: [
        t('pricing.freeFeature1', '5 analyses per month'),
        t('pricing.freeFeature2', 'Basic competitor reports'),
        t('pricing.freeFeature3', '6 data sources'),
        t('pricing.freeFeature4', 'Report export (Markdown)'),
      ],
      current: currentPlan === 'free',
      icon: Zap,
    },
    {
      name: 'Pro',
      price: '$19',
      period: t('pricing.perMonth', '/month'),
      features: [
        t('pricing.proFeature1', '100 analyses per month'),
        t('pricing.proFeature2', 'Advanced competitor insights'),
        t('pricing.proFeature3', '6 data sources + priority'),
        t('pricing.proFeature4', 'Report export (Markdown)'),
        t('pricing.proFeature5', 'Reports never expire'),
        t('pricing.proFeature6', 'Priority support'),
      ],
      current: currentPlan === 'pro',
      highlighted: true,
      icon: Crown,
    },
  ]

  return (
    <div className="app-shell px-4 max-w-4xl">
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors mb-8"
      >
        <ArrowLeft className="w-4 h-4" />
        {t('nav.home', 'Home')}
      </Link>

      <div className="text-center mb-12">
        <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tight mb-4">
          {t('pricing.title', 'Choose Your Plan')}
        </h1>
        <p className="text-lg text-muted-foreground font-bold max-w-xl mx-auto">
          {t('pricing.subtitle', 'Start free, upgrade when you need more power.')}
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6 md:gap-8">
        {plans.map(plan => {
          const Icon = plan.icon
          return (
            <div
              key={plan.name}
              className={`border-4 bg-card p-6 md:p-8 transition-all ${
                plan.highlighted
                  ? 'border-primary shadow-lg shadow-primary'
                  : 'border-border shadow-md'
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
                  {t('pricing.currentPlan', 'Current Plan')}
                </Button>
              ) : plan.highlighted && stripeConfigured ? (
                <Button
                  size="lg"
                  className="w-full"
                  onClick={handleUpgrade}
                  disabled={loading || !user}
                >
                  {loading ? (
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  ) : (
                    <Crown className="w-5 h-5 mr-2" />
                  )}
                  {t('pricing.upgrade', 'Upgrade to Pro')}
                </Button>
              ) : plan.highlighted && !stripeConfigured ? (
                <Button variant="outline" size="lg" className="w-full" disabled>
                  {t('pricing.comingSoon', 'Coming Soon')}
                </Button>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
