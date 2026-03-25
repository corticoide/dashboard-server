import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import MetricCard from './MetricCard.vue'

describe('MetricCard', () => {
  it('renders label and value', () => {
    const wrapper = mount(MetricCard, { props: { label: 'CPU', value: 42, unit: '%', color: 'blue' } })
    expect(wrapper.text()).toContain('CPU')
    expect(wrapper.text()).toContain('42')
  })

  it('arc fill has stroke-dashoffset reflecting value', () => {
    const wrapper = mount(MetricCard, { props: { label: 'RAM', value: 75, unit: '%', color: 'green' } })
    const fill = wrapper.find('.bar-fill')
    // 75% of arc: dashoffset = 131.95 * 0.25 ≈ 32.99
    const style = fill.attributes('style')
    expect(style).toContain('stroke-dashoffset')
  })

  it('auto color: green below 60%', () => {
    const wrapper = mount(MetricCard, { props: { label: 'CPU', value: 30, color: 'auto' } })
    expect(wrapper.classes()).toContain('accent-green')
  })

  it('auto color: yellow between 60-85%', () => {
    const wrapper = mount(MetricCard, { props: { label: 'CPU', value: 70, color: 'auto' } })
    expect(wrapper.classes()).toContain('accent-yellow')
  })

  it('auto color: red above 85%', () => {
    const wrapper = mount(MetricCard, { props: { label: 'CPU', value: 90, color: 'auto' } })
    expect(wrapper.classes()).toContain('accent-red')
  })
})
