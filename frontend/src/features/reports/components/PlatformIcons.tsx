import { Github, Globe, Terminal, Smartphone, Flame, MessageCircle } from 'lucide-react'

export const platformColors: Record<string, string> = {
  github: 'bg-chart-2/15 text-chart-2',
  tavily: 'bg-chart-3/15 text-chart-3',
  producthunt: 'bg-chart-4/15 text-chart-4',
  hackernews: 'bg-chart-5/15 text-chart-5',
  appstore: 'bg-chart-1/15 text-chart-1',
  reddit: 'bg-orange-500/15 text-orange-500',
}

export const PlatformIcon: Record<string, React.ElementType> = {
  github: Github,
  tavily: Globe,
  producthunt: Flame,
  hackernews: Terminal,
  appstore: Smartphone,
  reddit: MessageCircle,
}
