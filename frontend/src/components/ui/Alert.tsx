import { forwardRef, type ReactNode } from 'react'
import { AlertCircle, AlertTriangle, CheckCircle, Info } from 'lucide-react'

export interface AlertProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  variant?: 'default' | 'destructive' | 'warning' | 'success'
  title?: ReactNode
  icon?: ReactNode
}

export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className = '', variant = 'default', title, children, icon, ...props }, ref) => {
    const baseClasses = "flex items-start gap-3 p-4 border-2"

    const variantConfig = {
      default: {
        classes: "bg-card border-border shadow text-foreground",
        icon: <Info className="h-5 w-5 shrink-0 mt-0.5 text-muted-foreground" />,
        titleClasses: "text-foreground",
        descClasses: "text-muted-foreground"
      },
      destructive: {
        classes: "bg-destructive/10 border-destructive shadow shadow-destructive text-destructive",
        icon: <AlertCircle className="h-5 w-5 shrink-0 mt-0.5 text-destructive" />,
        titleClasses: "text-destructive",
        descClasses: "text-destructive/90"
      },
      warning: {
        classes: "bg-warning/20 border-warning shadow shadow-warning text-warning",
        icon: <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5 text-warning" />,
        titleClasses: "text-warning",
        descClasses: "text-warning/90"
      },
      success: {
        classes: "bg-success/10 border-success shadow shadow-success text-success",
        icon: <CheckCircle className="h-5 w-5 shrink-0 mt-0.5 text-success" />,
        titleClasses: "text-success",
        descClasses: "text-success/90"
      },
    }

    const config = variantConfig[variant]
    const defaultIcon = icon ?? config.icon

    const combinedClasses = `${baseClasses} ${config.classes} ${className}`.trim().replace(/\s+/g, ' ')

    return (
      <div ref={ref} role="alert" className={combinedClasses} {...props}>
        {defaultIcon}
        <div className="min-w-0 flex-1">
          {title && (
            <h5 className={`text-sm font-bold uppercase tracking-wider mb-1 leading-tight break-words ${config.titleClasses}`}>
              {title}
            </h5>
          )}
          <div className={`text-sm leading-relaxed break-words ${config.descClasses}`}>
            {children}
          </div>
        </div>
      </div>
    )
  }
)

Alert.displayName = 'Alert'
