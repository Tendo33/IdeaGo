/* eslint-disable react-refresh/only-export-components */
import { forwardRef, type ButtonHTMLAttributes } from 'react'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'destructive' | 'warning' | 'outline' | 'ghost'
  size?: 'sm' | 'md' | 'lg' | 'icon'
}

export function buttonVariants({ variant = 'primary', size = 'md', className = '' }: { variant?: ButtonProps['variant'], size?: ButtonProps['size'], className?: string } = {}) {
  const baseClasses = "inline-flex items-center justify-center font-bold uppercase tracking-widest transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-x-0 disabled:hover:translate-y-0 disabled:hover:shadow-none shrink-0 cursor-pointer"

  const sizeClasses = {
    sm: "px-4 py-2 text-xs",
    md: "px-6 py-3 text-sm",
    lg: "px-8 py-4 text-lg",
    icon: "min-h-[44px] min-w-[44px] p-2",
  }[size]

  const variantClasses = {
    primary: "bg-primary text-primary-foreground border-2 border-border shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none focus-visible:ring-primary",
    secondary: "bg-background text-foreground border-2 border-border shadow-[4px_4px_0px_0px_var(--border)] hover:bg-muted hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none focus-visible:ring-primary",
    destructive: "bg-destructive text-destructive-foreground border-2 border-destructive shadow-[4px_4px_0px_0px_var(--destructive)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--destructive)] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none focus-visible:ring-destructive",
    warning: "bg-transparent border border-warning text-warning hover:bg-warning/10 hover:-translate-y-0.5 focus-visible:ring-warning",
    outline: "bg-transparent text-foreground border-2 border-border hover:bg-muted/50 focus-visible:ring-primary shadow-none",
    ghost: "bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-primary shadow-none",
  }[variant]

  return `${baseClasses} ${sizeClasses} ${variantClasses} ${className}`.trim().replace(/\s+/g, ' ')
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = '', variant = 'primary', size = 'md', ...props }, ref) => {
    return (
      <button ref={ref} className={buttonVariants({ variant, size, className })} {...props} />
    )
  }
)

Button.displayName = 'Button'
