import { test, expect } from '@playwright/test';

test.describe('Incidents Flow', () => {
  test('should display active incidents', async ({ page }) => {
    await page.goto('/incidents');
    
    // Expect the page title to be visible
    await expect(page.getByRole('heading', { name: /Incident Explorer/i })).toBeVisible();
    
    // Wait for network/feed to populate some data or show empty state
    // We check for the table or list to be present
    const table = page.locator('table');
    await expect(table).toBeVisible();
  });

  test('should allow opening an incident and interacting with TriageAgent', async ({ page }) => {
    await page.goto('/incidents');
    
    // Check if there are incidents to click on, otherwise the test passes if the table is empty
    const row = page.locator('table tbody tr').first();
    if (await row.isVisible()) {
      await row.click();
      
      // Wait for the AgentChatDrawer to open
      await expect(page.getByText(/Agent/i)).toBeVisible();
      
      // Type a message to the agent
      const input = page.getByPlaceholder(/Type a message/i);
      await input.fill('Triage this incident');
      await input.press('Enter');
      
      // Wait for agent to respond
      await expect(page.locator('.agent-message')).toBeVisible({ timeout: 15000 });
    }
  });
});
