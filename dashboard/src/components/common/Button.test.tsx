import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Button from './Button'

describe('Button', () => {
	it('renders children correctly', () => {
		render(<Button>Click me</Button>)
		expect(screen.getByText('Click me')).toBeInTheDocument()
	})

	it('handles click events', () => {
		const handleClick = vi.fn()
		render(<Button onClick={handleClick}>Click me</Button>)

		fireEvent.click(screen.getByText('Click me'))
		expect(handleClick).toHaveBeenCalledTimes(1)
	})

	it('is disabled when disabled prop is true', () => {
		render(<Button disabled>Disabled</Button>)
		expect(screen.getByText('Disabled')).toBeDisabled()
	})

	it('applies variant styles', () => {
		const { rerender } = render(<Button variant="primary">Primary</Button>)
		const button = screen.getByText('Primary')
		expect(button).toHaveClass('bg-accent-teal')

		rerender(<Button variant="danger">Danger</Button>)
		expect(screen.getByText('Danger')).toHaveClass('bg-accent-red')
	})

	it('applies size styles', () => {
		const { rerender } = render(<Button size="sm">Small</Button>)
		expect(screen.getByText('Small')).toHaveClass('text-xs')

		rerender(<Button size="lg">Large</Button>)
		expect(screen.getByText('Large')).toHaveClass('text-base')
	})

	it('applies toggle variant with active state', () => {
		const { rerender } = render(
			<Button variant="toggle" active={false}>Toggle</Button>
		)
		expect(screen.getByText('Toggle')).toHaveClass('bg-surface-3')

		rerender(<Button variant="toggle" active={true}>Toggle</Button>)
		expect(screen.getByText('Toggle')).toHaveClass('bg-accent-teal/15')
	})
})
