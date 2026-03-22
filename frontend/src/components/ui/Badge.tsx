import { forwardRef, type HTMLAttributes } from 'react'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'primary' | 'secondary' | 'outline' | 'accent'
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className = '', variant = 'default', ...props }, ref) => {
    const baseClasses = "inline-flex items-center gap-1.5 px-2 py-1 text-xs font-bold uppercase tracking-wider rounded-none shrink-0"

    const variantClasses = {
      default: "bg-secondary/50 text-muted-foreground border border-transparent",
      primary: "bg-primary text-primary-foreground border-2 border-border shadow-sm font-black",
      secondary: "bg-background text-muted-foreground border border-border",
      outline: "bg-transparent text-foreground border border-border",
      accent: "bg-primary/10 text-primary border border-border font-black",
    }[variant]

    const combinedClasses = `${baseClasses} ${variantClasses} ${className}`.trim().replace(/\s+/g, ' ')

    return (
      <span ref={ref} className={combinedClasses} {...props} />
    )
  }
)

Badge.displayName = 'Badge'
