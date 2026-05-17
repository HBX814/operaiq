import { test, expect } from '@playwright/test';

test.describe('Remediation Approval Flow', () => {
  test('should present remediation options and handle approval', async ({ page }) => {
    // We will navigate to a specific incident where we can trigger remediation
    await page.goto('/incidents');
    
    const row = page.locator('table tbody tr').first();
    if (await row.isVisible()) {
      await row.click();
      
      const input = page.getByPlaceholder(/Type a message/i);
      await input.fill('Fix this incident');
      await input.press('Enter');
      
      // Wait for the remediation agent to ask for approval
      const approveButton = page.getByRole('button', { name: /Approve/i });
      await expect(approveButton).toBeVisible({ timeout: 15000 });
      
      await approveButton.click();
      
      // Agent should confirm execution
      await expect(page.getByText(/Action approved/i)).toBeVisible();
    }
  });
});
