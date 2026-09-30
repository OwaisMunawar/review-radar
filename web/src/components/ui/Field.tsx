import type { SelectHTMLAttributes } from 'react'
import { useId } from 'react'

import { cn } from './cn'

interface SelectFieldProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'onChange'> {
  label: string
  options: { value: string; label: string }[]
  onValueChange: (value: string) => void
  placeholder?: string
}

export function SelectField({
  label,
  options,
  onValueChange,
  placeholder = 'All',
  className,
  ...props
}: SelectFieldProps) {
  const id = useId()
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <label htmlFor={id} className="text-muted text-xs font-medium">
        {label}
      </label>
      <select
        id={id}
        className="border-line bg-surface text-ink h-9 rounded-md border px-2 text-sm"
        onChange={(event) => {
          onValueChange(event.target.value)
        }}
        {...props}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}
