import { Github, Globe, Terminal, Smartphone, Flame, MessageCircle, TrendingUp } from 'lucide-react'
import type { Platform } from '@/lib/types/research'

export const platformColors: Record<Platform, string> = {
  github: 'bg-chart-2/15 text-chart-2',
  tavily: 'bg-chart-3/15 text-chart-3',
  producthunt: 'bg-chart-4/15 text-chart-4',
  hackernews: 'bg-chart-5/15 text-chart-5',
  appstore: 'bg-chart-1/15 text-chart-1',
  reddit: 'bg-success/10 text-success',
  google_trends: 'bg-warning/10 text-warning',
}

export const PlatformIcon: Record<Platform, React.ElementType> = {
  github: Github,
  tavily: Globe,
  producthunt: Flame,
  hackernews: Terminal,
  appstore: Smartphone,
  reddit: MessageCircle,
  google_trends: TrendingUp,
}
