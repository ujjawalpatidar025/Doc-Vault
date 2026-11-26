import { useRef, useState } from "react"
import { LoaderCircle, Upload } from "lucide-react"
import { toast } from "sonner"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { getErrorMessage, uploadFile } from "@/services/api"

export default function FileUpload({ onUpload }) {
  const inputRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)

  const uploadAll = async (fileList) => {
    const files = Array.from(fileList || [])
    if (!files.length || uploading) return

    setUploading(true)
    let uploadedAny = false
    // One at a time: each upload counts against the per-user rate limit and quota.
    for (const file of files) {
      try {
        const result = await uploadFile(file)
        uploadedAny = true
        if (result.is_duplicate) {
          toast.info(`${file.name}: duplicate detected`, {
            description: "Saved as a reference to the existing copy. No extra storage used.",
          })
        } else {
          toast.success(`${file.name} uploaded`)
        }
      } catch (error) {
        toast.error(`${file.name} wasn't uploaded`, {
          description: getErrorMessage(error, "Something went wrong. Please try again."),
        })
      }
    }
    setUploading(false)
    if (inputRef.current) inputRef.current.value = ""
    if (uploadedAny && onUpload) onUpload()
  }

  const onDrop = (event) => {
    event.preventDefault()
    setDragging(false)
    uploadAll(event.dataTransfer.files)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload files</CardTitle>
        <CardDescription>Duplicate content is detected and stored only once.</CardDescription>
      </CardHeader>
      <CardContent>
        <label
          htmlFor="file-input"
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "border-input hover:bg-muted/50 flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors",
            dragging && "border-primary bg-muted/60",
            uploading && "pointer-events-none opacity-70"
          )}
        >
          <div className="bg-muted flex size-11 items-center justify-center rounded-full">
            {uploading ? (
              <LoaderCircle className="text-muted-foreground size-5 animate-spin" />
            ) : (
              <Upload className="text-muted-foreground size-5" />
            )}
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium">
              {uploading ? "Uploading…" : dragging ? "Drop to upload" : "Drop files here or click to browse"}
            </p>
            <p className="text-muted-foreground text-xs">Any file type · counts toward your storage quota</p>
          </div>
          <input
            ref={inputRef}
            id="file-input"
            type="file"
            multiple
            className="sr-only"
            disabled={uploading}
            onChange={(event) => uploadAll(event.target.files)}
          />
        </label>
      </CardContent>
    </Card>
  )
}
