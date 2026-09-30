export function Stars({ rating }: { rating: number }) {
  return (
    <span
      className="text-warn text-sm tracking-tight"
      role="img"
      aria-label={`${rating} out of 5 stars`}
    >
      {'★'.repeat(rating)}
      <span className="text-axis">{'★'.repeat(5 - rating)}</span>
    </span>
  )
}
