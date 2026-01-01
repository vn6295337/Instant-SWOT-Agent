import { test, expect } from '@playwright/test'

test.describe('Instant SWOT Agent', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should display the home page', async ({ page }) => {
    await expect(page.getByText('Instant SWOT Agent')).toBeVisible()
    await expect(page.getByPlaceholder('Search U.S. listed companies...')).toBeVisible()
  })

  test('should show empty state message', async ({ page }) => {
    await expect(page.getByText('Enter a company name to begin')).toBeVisible()
  })

  test('should toggle between Executive and Full view modes', async ({ page }) => {
    const executiveBtn = page.getByRole('button', { name: 'Executive' })
    const fullBtn = page.getByRole('button', { name: 'Full' })

    await expect(executiveBtn).toBeVisible()
    await expect(fullBtn).toBeVisible()

    // Click Executive
    await executiveBtn.click()
    await expect(executiveBtn).toHaveClass(/bg-primary/)

    // Click Full
    await fullBtn.click()
    await expect(fullBtn).toHaveClass(/bg-primary/)
  })

  test('should toggle dark mode', async ({ page }) => {
    const darkModeBtn = page.locator('button').filter({ has: page.locator('svg') }).last()

    // Check initial state (dark mode)
    await expect(page.locator('html')).toHaveClass(/dark/)

    // Toggle to light mode
    await darkModeBtn.click()
    await expect(page.locator('html')).not.toHaveClass(/dark/)

    // Toggle back to dark mode
    await darkModeBtn.click()
    await expect(page.locator('html')).toHaveClass(/dark/)
  })

  test('should search for stocks', async ({ page }) => {
    const searchInput = page.getByPlaceholder('Search U.S. listed companies...')

    await searchInput.fill('AAPL')

    // Wait for autocomplete dropdown
    await expect(page.getByText('Apple')).toBeVisible({ timeout: 5000 })
  })

  test('should select a stock and show Generate button', async ({ page }) => {
    const searchInput = page.getByPlaceholder('Search U.S. listed companies...')

    await searchInput.fill('TSLA')

    // Wait for and click the Tesla option
    await page.getByText('Tesla').first().click()

    // Generate button should appear
    await expect(page.getByRole('button', { name: /Generate SWOT/i })).toBeVisible()
  })
})

test.describe('SWOT Analysis Workflow', () => {
  test('should complete full analysis workflow', async ({ page }) => {
    // This test requires the backend to be running
    test.skip(!!process.env.CI, 'Skipping in CI - requires backend')

    await page.goto('/')

    // Search and select a stock
    const searchInput = page.getByPlaceholder('Search U.S. listed companies...')
    await searchInput.fill('AAPL')
    await page.getByText('Apple').first().click()

    // Click Generate SWOT
    await page.getByRole('button', { name: /Generate SWOT/i }).click()

    // Wait for loading state
    await expect(page.getByText(/Analyzing/i)).toBeVisible({ timeout: 5000 })

    // Wait for results (up to 2 minutes for full analysis)
    await expect(page.getByText('Strengths')).toBeVisible({ timeout: 120000 })
    await expect(page.getByText('Weaknesses')).toBeVisible()
    await expect(page.getByText('Opportunities')).toBeVisible()
    await expect(page.getByText('Threats')).toBeVisible()
  })
})
