const UNITS = ["B", "KB", "MB", "GB", "TB"]

export function formatBytes(bytes) {
  if (!bytes) return "0 B"
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), UNITS.length - 1)
  const value = bytes / 1024 ** exponent
  return `${value >= 10 || exponent === 0 ? Math.round(value) : value.toFixed(1)} ${UNITS[exponent]}`
}

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
})

export function formatDate(value) {
  return dateFormatter.format(new Date(value))
}
