import { useCallback, useEffect, useState } from "react"
import { ShieldCheck, User } from "lucide-react"
import { toast } from "sonner"

import FileFilters, { EMPTY_FILTERS } from "@/components/FileFilters.jsx"
import FileList from "@/components/FileList.jsx"
import FileUpload from "@/components/FileUpload.jsx"
import StatsPanel from "@/components/StatsPanel.jsx"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Toaster } from "@/components/ui/sonner"
import { getErrorMessage, getFiles, getStats, getUserId, setUserId } from "@/services/api"

const FILTER_DEBOUNCE_MS = 400
const USER_ID_PATTERN = /^[\w.@+-]{1,255}$/

// UI filter state -> API query parameters (sizes are entered in KB, the API takes bytes).
function toQuery(filters, page) {
  const kb = (value) => (value === "" ? "" : Math.round(Number(value) * 1024))
  return {
    search: filters.search.trim(),
    mime_type: filters.mime_type.trim(),
    min_size: kb(filters.min_size_kb),
    max_size: kb(filters.max_size_kb),
    date_from: filters.date_from,
    date_to: filters.date_to,
    duplicates_only: filters.duplicates_only,
    ordering: filters.ordering,
    page: page > 1 ? page : "",
  }
}

function UserSwitcher({ userId, onSwitch }) {
  const [draft, setDraft] = useState(userId)
  const valid = USER_ID_PATTERN.test(draft.trim())

  const submit = (event) => {
    event.preventDefault()
    const next = draft.trim()
    if (!valid || next === userId) return
    onSwitch(next)
  }

  return (
    <form onSubmit={submit} className="flex items-center gap-2">
      <Label htmlFor="user-id" className="sr-only">
        User ID
      </Label>
      <div className="relative">
        <User className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2" />
        <Input
          id="user-id"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          aria-invalid={!valid}
          className="h-8 w-32 pl-8 sm:w-44"
          title="Letters, digits, or . @ + - _"
        />
      </div>
      <Button type="submit" size="sm" variant="outline" disabled={!valid || draft.trim() === userId}>
        Switch<span className="hidden sm:inline"> user</span>
      </Button>
    </form>
  )
}

export default function App() {
  const [userId, setCurrentUserId] = useState(getUserId)
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadFiles = useCallback(async () => {
    setLoading(true)
    try {
      const response = await getFiles(toQuery(filters, page))
      setData(Array.isArray(response) ? { count: response.length, results: response } : response)
    } catch (error) {
      toast.error("Couldn't load files", {
        description: getErrorMessage(error, "Make sure the backend is running."),
      })
    } finally {
      setLoading(false)
    }
  }, [filters, page])

  const loadStats = useCallback(async () => {
    try {
      setStats(await getStats())
    } catch {
      // The file list already reports connection problems.
    }
  }, [])

  // Debounced so typing in a filter doesn't fire a request per keystroke
  // (the API allows 2 calls per second per user).
  useEffect(() => {
    const timer = setTimeout(() => {
      loadFiles()
      loadStats()
    }, FILTER_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [loadFiles, loadStats, userId])

  const refreshAll = () => {
    loadFiles()
    loadStats()
  }

  const handleFilterChange = (changes) => {
    setFilters((previous) => ({ ...previous, ...changes }))
    setPage(1)
  }

  const handleUserSwitch = (next) => {
    setUserId(next)
    setCurrentUserId(next)
    setData(null)
    setStats(null)
    setPage(1)
    toast(`Switched to ${next}`, { description: "You only see this user's files." })
  }

  const isFiltered = Object.keys(EMPTY_FILTERS).some(
    (key) => key !== "ordering" && filters[key] !== EMPTY_FILTERS[key]
  )

  return (
    <div className="bg-muted/40 min-h-screen">
      <header className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-40 border-b backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 md:px-6">
          <div className="flex items-center gap-3">
            <div className="bg-primary text-primary-foreground flex size-9 items-center justify-center rounded-lg">
              <ShieldCheck className="size-5" />
            </div>
            <div className="leading-tight">
              <h1 className="font-semibold tracking-tight">Abnormal File Vault</h1>
              <p className="text-muted-foreground hidden text-xs sm:block">
                Secure file hosting with intelligent deduplication
              </p>
            </div>
          </div>
          <UserSwitcher key={userId} userId={userId} onSwitch={handleUserSwitch} />
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 md:px-6">
        <StatsPanel stats={stats} />

        <div className="grid items-start gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <aside className="space-y-6">
            <FileUpload onUpload={refreshAll} />
            <FileFilters filters={filters} onChange={handleFilterChange} />
          </aside>

          <FileList
            data={data}
            loading={loading}
            page={page}
            onPageChange={setPage}
            onRefresh={refreshAll}
            onChange={refreshAll}
            isFiltered={isFiltered}
          />
        </div>
      </main>

      <Toaster position="top-right" richColors closeButton />
    </div>
  )
}
