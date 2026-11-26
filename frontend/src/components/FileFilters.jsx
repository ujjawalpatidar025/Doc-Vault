import { Search, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NativeSelect } from "@/components/ui/native-select"
import { Separator } from "@/components/ui/separator"

export const EMPTY_FILTERS = {
  search: "",
  mime_type: "",
  min_size_kb: "",
  max_size_kb: "",
  date_from: "",
  date_to: "",
  duplicates_only: false,
  ordering: "-uploaded_at",
}

const SORT_OPTIONS = [
  ["-uploaded_at", "Newest first"],
  ["uploaded_at", "Oldest first"],
  ["name", "Name (A–Z)"],
  ["-name", "Name (Z–A)"],
  ["-file_size", "Largest first"],
  ["file_size", "Smallest first"],
]

function Field({ id, label, children }) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

export default function FileFilters({ filters, onChange }) {
  const set = (field) => (event) => onChange({ [field]: event.target.value })
  const isFiltered = Object.keys(EMPTY_FILTERS).some(
    (key) => key !== "ordering" && filters[key] !== EMPTY_FILTERS[key]
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Search &amp; filter</CardTitle>
        <CardDescription>Filters combine; results update as you type.</CardDescription>
        <CardAction>
          <Button
            variant="ghost"
            size="sm"
            disabled={!isFiltered}
            onClick={() => onChange({ ...EMPTY_FILTERS, ordering: filters.ordering })}
          >
            <X />
            Clear
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="grid gap-4">
        <Field id="filter-search" label="File name">
          <div className="relative">
            <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2" />
            <Input
              id="filter-search"
              placeholder="Search by name…"
              className="pl-8"
              value={filters.search}
              onChange={set("search")}
            />
          </div>
        </Field>

        <Field id="filter-type" label="File type">
          <Input
            id="filter-type"
            placeholder="e.g. image or application/pdf"
            value={filters.mime_type}
            onChange={set("mime_type")}
          />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field id="filter-min" label="Min size (KB)">
            <Input id="filter-min" type="number" min="0" placeholder="0" value={filters.min_size_kb} onChange={set("min_size_kb")} />
          </Field>
          <Field id="filter-max" label="Max size (KB)">
            <Input id="filter-max" type="number" min="0" placeholder="Any" value={filters.max_size_kb} onChange={set("max_size_kb")} />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field id="filter-from" label="Uploaded from">
            <Input id="filter-from" type="date" value={filters.date_from} onChange={set("date_from")} />
          </Field>
          <Field id="filter-to" label="Uploaded to">
            <Input id="filter-to" type="date" value={filters.date_to} onChange={set("date_to")} />
          </Field>
        </div>

        <div className="flex items-center gap-2">
          <Checkbox
            id="filter-duplicates"
            checked={filters.duplicates_only}
            onCheckedChange={(checked) => onChange({ duplicates_only: checked === true })}
          />
          <Label htmlFor="filter-duplicates" className="font-normal">
            Only show duplicated content
          </Label>
        </div>

        <Separator />

        <Field id="filter-sort" label="Sort by">
          <NativeSelect id="filter-sort" value={filters.ordering} onChange={set("ordering")}>
            {SORT_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </CardContent>
    </Card>
  )
}
