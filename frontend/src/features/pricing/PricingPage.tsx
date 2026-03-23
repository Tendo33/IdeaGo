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
  useDocumentTitle(t('pricing.title', 'Choose Your Plan') + ' — IdeaGo')
  const { user } = useAuth()
  const [loading, setLoading] = useState(false)
  const [currentPlan, setCurrentPlan] = useState('free')
  const [stripeConfigured, setStripeConfigured] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!user) return
    getSubscriptionStatus()
      .then(status => {
        setCurrentPlan(status.plan)
        setStripeConfigured(status.stripe_configured)
      })
      .catch(err => {
        console.error('Failed to get subscription status', err)
        setError(t('pricing.loadError', 'Could not verify your current subscription status.'))
      })
  }, [user, t])

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
      toast.error(t('pricing.upgradeError', 'Failed to start checkout. Please try again.'))
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
      price: '$9',
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
    <div className="app-shell max-w-4xl pt-12 pb-16 md:pt-16 md:pb-24">
      <Link
        to="/"
        className={buttonVariants({ variant: 'secondary', size: 'sm', className: "mb-8 bg-card" })}
      >
        <ArrowLeft className="w-4 h-4 mr-2" />
        {t('nav.home', 'Home')}
      </Link>

      <div className="border-4 border-border bg-card p-8 md:p-12 mb-12 shadow-lg relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary rounded-full blur-[50px] opacity-20 group-hover:opacity-40 transition-opacity" />
        <h1 className="text-4xl md:text-6xl font-black uppercase tracking-tighter mb-4 relative z-10">
          {t('pricing.title', 'Choose Your Plan')}
        </h1>
        <p className="text-lg md:text-xl text-muted-foreground font-bold max-w-xl mb-6 relative z-10 border-l-4 border-primary pl-4">
          {t('pricing.subtitle', 'Start free, upgrade when you need more power.')}
        </p>
        {error && (
          <Alert variant="warning" className="max-w-xl text-left relative z-10">
            <span className="font-bold">{error}</span>
          </Alert>
        )}
        <div className="absolute -bottom-6 -right-6 w-24 h-24 bg-success border-4 border-border rounded-full opacity-50 rotate-12 group-hover:rotate-45 transition-transform duration-700" />
      </div>

      <div className="grid md:grid-cols-2 gap-6 md:gap-8">
        {plans.map(plan => {
          const Icon = plan.icon
          return (
            <div
              key={plan.name}
              className={`border-4 bg-card p-6 md:p-8 transition-all duration-300 hover:translate-x-[-4px] hover:translate-y-[-4px] ${
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
                  {t('pricing.currentPlan', 'Current Plan')}
                </Button>
              ) : plan.highlighted && stripeConfigured && user ? (
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
                  {t('pricing.upgrade', 'Upgrade to Pro')}
                </Button>
              ) : plan.highlighted && stripeConfigured && !user ? (
                <Link
                  to="/login"
                  className="w-full inline-flex items-center justify-center gap-2 min-h-[48px] border-2 border-border bg-primary text-primary-foreground px-6 py-3 text-base font-bold uppercase tracking-wider shadow transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none"
                >
                  <LogIn className="w-5 h-5" />
                  {t('pricing.signInToUpgrade', 'Sign in to Upgrade')}
                </Link>
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
