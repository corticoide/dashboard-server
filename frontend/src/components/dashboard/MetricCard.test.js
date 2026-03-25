import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import MetricCard from './MetricCard.vue'

describe('MetricCard', () => {
  it('renders label and value', () => {
    const wrapper = mount(MetricCard, { props: { label: 'CPU', value: 42.5, unit: '%', color: 'blue' } })
    expect(wrapper.text()).toContain('CPU')
    expect(wrapper.text()).toContain('42.5')
  })

  it('renders progress bar with correct width', () => {
    const wrapper = mount(MetricCard, { props: { label: 'RAM', value: 75, unit: '%', color: 'green' } })
    const bar = wrapper.find('.bar-fill')
    expect(bar.attributes('style')).toContain('75%')
  })
})
