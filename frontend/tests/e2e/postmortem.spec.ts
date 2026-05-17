import { test, expect } from '@playwright/test';

test.describe('Post-Mortem Review Flow', () => {
  test('should display post-mortems and allow editing', async ({ page }) => {
    await page.goto('/postmortems');
    
    await expect(page.getByRole('heading', { name: /Post-Mortems/i })).toBeVisible();
    
    // Click on a post-mortem to open it
    const postMortemCard = page.locator('.post-mortem-card').first();
    if (await postMortemCard.isVisible()) {
      await postMortemCard.click();
      
      // Check if the editor is visible
      await expect(page.locator('.ProseMirror')).toBeVisible();
      
      // Type in the editor
      await page.locator('.ProseMirror').type('Adding some notes to the post-mortem.');
      
      // Interact with the PostMortemAgent
      const chatInput = page.getByPlaceholder(/Type a message/i);
      await chatInput.fill('Score this post-mortem');
      await chatInput.press('Enter');
      
      await expect(page.getByText(/QUALITY SCORE/i)).toBeVisible({ timeout: 15000 });
    }
  });
});
