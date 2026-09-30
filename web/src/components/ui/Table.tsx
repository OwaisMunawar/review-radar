import type { ReactNode } from 'react'

import { cn } from './cn'

export interface Column<T> {
  key: string
  header: ReactNode
  cell: (row: T) => ReactNode
  align?: 'left' | 'right'
  className?: string
}

interface TableProps<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  caption: string
  rowClassName?: (row: T) => string | undefined
}

/** A plain, accessible data table; the caption is read by screen readers only. */
export function Table<T>({ columns, rows, rowKey, caption, rowClassName }: TableProps<T>) {
  return (
    <div className="-mx-5 overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-line text-muted border-b text-left text-xs">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn(
                  'px-5 py-2 font-medium',
                  column.align === 'right' && 'text-right',
                  column.className,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={cn('border-line border-b last:border-0', rowClassName?.(row))}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn(
                    'text-ink px-5 py-2.5 align-top',
                    column.align === 'right' && 'tabular text-right',
                    column.className,
                  )}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
