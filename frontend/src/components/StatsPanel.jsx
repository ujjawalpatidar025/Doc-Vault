import { Copy, Files, HardDrive, PiggyBank } from "lucide-react"

import { Card, CardAction, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { formatBytes } from "@/lib/format"
import { cn } from "@/lib/utils"

function StatCard({ label, value, icon: Icon, children }) {
  return (
    <Card className="gap-3 py-5">
      <CardHeader className="px-5">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl font-semibold tabular-nums">{value}</CardTitle>
        <CardAction>
          <div className="bg-muted text-muted-foreground flex size-9 items-center justify-center rounded-lg">
            <Icon className="size-4" />
          </div>
        </CardAction>
      </CardHeader>
      <CardFooter className="text-muted-foreground flex-col items-start gap-2 px-5 text-xs">
        {children}
      </CardFooter>
    </Card>
  )
}

function StatsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i} className="gap-3 py-5">
          <CardHeader className="px-5">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-2 h-7 w-16" />
          </CardHeader>
          <CardFooter className="px-5">
            <Skeleton className="h-3 w-32" />
          </CardFooter>
        </Card>
      ))}
    </div>
  )
}

export default function StatsPanel({ stats }) {
  if (!stats) return <StatsSkeleton />

  const usedPercent = stats.storage_limit
    ? Math.min(100, Math.round((stats.total_storage_used / stats.storage_limit) * 100))
    : 0

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Files" value={stats.total_files} icon={Files}>
        {stats.unique_files} unique {stats.unique_files === 1 ? "file" : "files"} stored
      </StatCard>

      <StatCard label="Duplicates detected" value={stats.duplicate_entries} icon={Copy}>
        Uploads that reuse stored content
      </StatCard>

      <StatCard label="Space saved" value={formatBytes(stats.storage_savings)} icon={PiggyBank}>
        {stats.savings_percentage}% of uploaded data deduplicated
      </StatCard>

      <StatCard label="Storage used" value={formatBytes(stats.total_storage_used)} icon={HardDrive}>
        <Progress
          value={usedPercent}
          aria-label="Storage quota used"
          indicatorClassName={cn(
            usedPercent >= 90 ? "bg-destructive" : usedPercent >= 75 ? "bg-warning" : "bg-primary"
          )}
        />
        <span>
          {usedPercent}% of {formatBytes(stats.storage_limit)} ·{" "}
          {formatBytes(stats.storage_remaining)} left
        </span>
      </StatCard>
    </div>
  )
}
