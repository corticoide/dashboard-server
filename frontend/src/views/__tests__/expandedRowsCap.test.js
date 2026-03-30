import { describe, it, expect } from 'vitest'

function applyExpand(expandedRows, expandedOrder, newId, MAX = 5) {
  expandedRows = { ...expandedRows, [newId]: true }
  expandedOrder = [...expandedOrder, newId]
  if (expandedOrder.length > MAX) {
    const evicted = expandedOrder[0]
    expandedOrder = expandedOrder.slice(1)
    expandedRows = { ...expandedRows }
    delete expandedRows[evicted]
  }
  return { expandedRows, expandedOrder }
}

function applyCollapse(expandedRows, expandedOrder, id) {
  expandedRows = { ...expandedRows }
  delete expandedRows[id]
  expandedOrder = expandedOrder.filter(i => i !== id)
  return { expandedRows, expandedOrder }
}

describe('expanded rows FIFO cap', () => {
  it('allows up to 5 rows expanded', () => {
    let rows = {}, order = []
    for (let i = 1; i <= 5; i++) {
      ;({ expandedRows: rows, expandedOrder: order } = applyExpand(rows, order, i))
    }
    expect(Object.keys(rows)).toHaveLength(5)
    expect(order).toHaveLength(5)
  })

  it('evicts the oldest row when a 6th is expanded', () => {
    let rows = {}, order = []
    for (let i = 1; i <= 6; i++) {
      ;({ expandedRows: rows, expandedOrder: order } = applyExpand(rows, order, i))
    }
    expect(Object.keys(rows)).toHaveLength(5)
    expect(rows[1]).toBeUndefined()
    expect(rows[6]).toBe(true)
  })

  it('tracks insertion order correctly after collapse', () => {
    let rows = { 1: true, 2: true, 3: true }, order = [1, 2, 3]
    ;({ expandedRows: rows, expandedOrder: order } = applyCollapse(rows, order, 2))
    expect(rows[2]).toBeUndefined()
    expect(order).toEqual([1, 3])
    ;({ expandedRows: rows, expandedOrder: order } = applyExpand(rows, order, 4))
    ;({ expandedRows: rows, expandedOrder: order } = applyExpand(rows, order, 5))
    ;({ expandedRows: rows, expandedOrder: order } = applyExpand(rows, order, 6))
    ;({ expandedRows: rows, expandedOrder: order } = applyExpand(rows, order, 7))
    expect(Object.keys(rows)).toHaveLength(5)
    expect(rows[1]).toBeUndefined()
  })

  it('does not evict on collapse', () => {
    let rows = { 1: true, 2: true }, order = [1, 2]
    ;({ expandedRows: rows, expandedOrder: order } = applyCollapse(rows, order, 1))
    expect(Object.keys(rows)).toHaveLength(1)
    expect(rows[2]).toBe(true)
  })
})
