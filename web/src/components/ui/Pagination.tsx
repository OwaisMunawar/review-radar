import { Button } from './Button'

interface PaginationProps {
  total: number
  limit: number
  offset: number
  onChange: (offset: number) => void
}

export function Pagination({ total, limit, offset, onChange }: PaginationProps) {
  if (total <= limit) return null
  const end = Math.min(offset + limit, total)
  return (
    <nav aria-label="Pagination" className="mt-4 flex items-center justify-between text-sm">
      <p className="text-muted">
        {offset + 1}–{end} of {total}
      </p>
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={offset === 0}
          onClick={() => {
            onChange(Math.max(0, offset - limit))
          }}
        >
          Previous
        </Button>
        <Button
          size="sm"
          disabled={end >= total}
          onClick={() => {
            onChange(offset + limit)
          }}
        >
          Next
        </Button>
      </div>
    </nav>
  )
}
