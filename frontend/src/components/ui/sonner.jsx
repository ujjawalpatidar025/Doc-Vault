import { Toaster as Sonner } from "sonner"

// shadcn's Toaster, without next-themes (this app has a single light theme).
const Toaster = ({ ...props }) => {
  return (
    <Sonner
      theme="light"
      className="toaster group"
      style={{
        "--normal-bg": "var(--popover)",
        "--normal-text": "var(--popover-foreground)",
        "--normal-border": "var(--border)",
      }}
      {...props}
    />
  )
}

export { Toaster }
