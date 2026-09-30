import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ApiError } from '../../api/client'
import { BarList, Button, EmptyState, Pagination, QueryState, Sparkline, Stat, Table } from '.'

describe('ui primitives', () => {
  it('renders a stat with its hint', () => {
    render(<Stat label="Reviews" value="400" hint="all stores" />)
    expect(screen.getByText('Reviews')).toBeInTheDocument()
    expect(screen.getByText('400')).toBeInTheDocument()
    expect(screen.getByText('all stores')).toBeInTheDocument()
  })

  it('gives sparklines an accessible name that carries the data', () => {
    render(<Sparkline values={[1, 3, 2]} label="Weekly reviews" />)
    expect(screen.getByRole('img', { name: 'Weekly reviews: 1, 3, 2' })).toBeInTheDocument()
  })

  it('draws nothing for a single point', () => {
    const { container } = render(<Sparkline values={[4]} label="x" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders table rows with a caption', () => {
    render(
      <Table
        caption="Segments"
        rows={[{ id: 'a', name: 'Crash' }]}
        rowKey={(r) => r.id}
        columns={[{ key: 'name', header: 'Name', cell: (r) => r.name }]}
      />,
    )
    expect(screen.getByRole('table', { name: 'Segments' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Crash' })).toBeInTheDocument()
  })

  it('prints bar values as text, not only as length', () => {
    render(<BarList bars={[{ key: 'crash', label: 'Crash', value: 38 }]} />)
    expect(screen.getByText('38')).toBeInTheDocument()
  })

  it('pages forward and back', async () => {
    const onChange = vi.fn()
    render(<Pagination total={45} limit={20} offset={20} onChange={onChange} />)
    expect(screen.getByText('21–40 of 45')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await userEvent.click(screen.getByRole('button', { name: 'Previous' }))
    expect(onChange.mock.calls).toEqual([[40], [0]])
  })

  it('shows API error codes in the error branch', () => {
    const error = new ApiError(404, {
      error: { code: 'not_found', message: 'no reviews for version 9.9.9', details: {} },
    })
    render(
      <QueryState query={{ data: undefined, isPending: false, error }}>
        {() => <p>never</p>}
      </QueryState>,
    )
    expect(screen.getByText('no reviews for version 9.9.9 (not_found)')).toBeInTheDocument()
  })

  it('shows a loading status while pending', () => {
    render(
      <QueryState query={{ data: undefined, isPending: true, error: null }}>
        {() => <p>never</p>}
      </QueryState>,
    )
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })

  it('renders buttons and empty states', () => {
    render(
      <>
        <Button disabled>Save</Button>
        <EmptyState title="Nothing here">Try again later</EmptyState>
      </>,
    )
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(screen.getByText('Try again later')).toBeInTheDocument()
  })
})
