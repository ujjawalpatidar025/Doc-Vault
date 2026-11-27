import { useState } from "react"
import { ChevronLeft, ChevronRight, Download, FileText, Files, Link2, RefreshCw, Trash2 } from "lucide-react"
import { toast } from "sonner"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatBytes, formatDate } from "@/lib/format"
import { cn } from "@/lib/utils"
import { deleteFile, downloadFile, getErrorMessage } from "@/services/api"

function deleteExplanation(file) {
  if (file.is_reference) {
    return "This removes only this copy. The other copies of the same content stay available."
  }
  if (file.reference_count > 1) {
    return "Other copies of this content keep working: the oldest one takes over the stored data."
  }
  return `This permanently deletes the file and frees ${formatBytes(file.size)} of your storage.`
}

function DuplicateBadge({ file }) {
  if (file.is_reference) {
    return (
      <Badge variant="outline" title="Shares storage with an earlier upload">
        <Link2 />
        <span className="hidden sm:inline">Duplicate</span>
      </Badge>
    )
  }
  if (file.reference_count > 1) {
    return (
      <Badge variant="secondary" title="Copies of this content (stored once)">
        <Files />
        {file.reference_count}
        <span className="hidden sm:inline">copies</span>
      </Badge>
    )
  }
  return null
}

function DeleteButton({ file, onDeleted }) {
  const [deleting, setDeleting] = useState(false)

  const confirm = async () => {
    setDeleting(true)
    try {
      await deleteFile(file.id)
      toast.success(`${file.original_filename} deleted`)
      onDeleted()
    } catch (error) {
      toast.error("Couldn't delete the file", { description: getErrorMessage(error, "Please try again.") })
    } finally {
      setDeleting(false)
    }
  }

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-destructive size-8"
          disabled={deleting}
          aria-label={`Delete ${file.original_filename}`}
        >
          <Trash2 />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete “{file.original_filename}”?</AlertDialogTitle>
          <AlertDialogDescription>{deleteExplanation(file)}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction className={buttonVariants({ variant: "destructive" })} onClick={confirm}>
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function LoadingRows() {
  return Array.from({ length: 5 }).map((_, i) => (
    <TableRow key={i}>
      <TableCell><Skeleton className="h-4 w-48" /></TableCell>
      <TableCell className="hidden md:table-cell"><Skeleton className="h-4 w-24" /></TableCell>
      <TableCell><Skeleton className="ml-auto h-4 w-14" /></TableCell>
      <TableCell className="hidden lg:table-cell"><Skeleton className="h-4 w-32" /></TableCell>
      <TableCell><Skeleton className="ml-auto h-8 w-16" /></TableCell>
    </TableRow>
  ))
}

export default function FileList({ data, loading, page, onPageChange, onRefresh, onChange, isFiltered }) {
  const files = data?.results ?? []
  const count = data?.count ?? 0

  const handleDownload = async (file) => {
    try {
      await downloadFile(file.id, file.original_filename)
    } catch (error) {
      toast.error("Download failed", { description: getErrorMessage(error, "Please try again.") })
    }
  }

  return (
    <Card className="min-w-0 gap-4">
      <CardHeader>
        <CardTitle>Your files</CardTitle>
        <CardDescription>
          {loading && !data ? "Loading…" : `${count} ${count === 1 ? "file" : "files"}${isFiltered ? " match your filters" : ""}`}
        </CardDescription>
        <CardAction>
          <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
            <RefreshCw className={cn(loading && "animate-spin")} />
            Refresh
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="px-0">
        {!loading && files.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
            <div className="bg-muted flex size-12 items-center justify-center rounded-full">
              <Files className="text-muted-foreground size-5" />
            </div>
            <div className="space-y-1">
              <p className="font-medium">{isFiltered ? "No matching files" : "No files yet"}</p>
              <p className="text-muted-foreground text-sm">
                {isFiltered ? "Try changing or clearing the filters." : "Upload a file to get started."}
              </p>
            </div>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="pl-4 sm:pl-6">Name</TableHead>
                <TableHead className="hidden md:table-cell">Type</TableHead>
                <TableHead className="text-right">Size</TableHead>
                <TableHead className="hidden lg:table-cell">Uploaded</TableHead>
                <TableHead className="pr-4 text-right sm:pr-6">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && files.length === 0 ? (
                <LoadingRows />
              ) : (
                files.map((file) => (
                  <TableRow key={file.id} className={cn(loading && "opacity-60")}>
                    <TableCell className="pl-4 sm:pl-6">
                      <div className="flex items-center gap-2">
                        <FileText className="text-muted-foreground size-4 shrink-0" />
                        <span className="max-w-[7rem] truncate font-medium sm:max-w-[16rem]" title={file.original_filename}>
                          {file.original_filename}
                        </span>
                        <DuplicateBadge file={file} />
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground hidden max-w-[10rem] truncate font-mono text-xs md:table-cell" title={file.file_type}>
                      {file.file_type || "unknown"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{formatBytes(file.size)}</TableCell>
                    <TableCell className="text-muted-foreground hidden lg:table-cell">{formatDate(file.uploaded_at)}</TableCell>
                    <TableCell className="pr-4 sm:pr-6">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-muted-foreground size-8"
                          onClick={() => handleDownload(file)}
                          aria-label={`Download ${file.original_filename}`}
                        >
                          <Download />
                        </Button>
                        <DeleteButton file={file} onDeleted={onChange} />
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        )}
      </CardContent>

      {(data?.next || data?.previous) && (
        <CardFooter className="justify-between border-t pt-4 [&.border-t]:pt-4">
          <span className="text-muted-foreground text-sm">Page {page}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={!data.previous || loading} onClick={() => onPageChange(page - 1)}>
              <ChevronLeft />
              Previous
            </Button>
            <Button variant="outline" size="sm" disabled={!data.next || loading} onClick={() => onPageChange(page + 1)}>
              Next
              <ChevronRight />
            </Button>
          </div>
        </CardFooter>
      )}
    </Card>
  )
}
