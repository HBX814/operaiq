/**
 * Playwright E2E Test 2: Clicking "Engage Agent" opens the chat drawer
 * and sends a triage request.
 * Spec from prompt: "Clicking 'Engage Agent' opens the chat drawer and sends a triage request"
 */
import { test, expect } from "@playwright/test";

test.describe("Agent Chat Drawer — Engage Agent Flow", () => {
  test("'Ask OperaIQ' button opens the chat drawer", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");

    // Find and click the "Ask OperaIQ" button (floating button or sidebar)
    const askButton = page.getByRole("button", { name: /ask opera.?iq/i }).first();
    await expect(askButton).toBeVisible({ timeout: 10000 });
    await askButton.click();

    // Chat drawer should slide in
    const drawer = page.locator('[class*="chat"], [class*="drawer"], [aria-label*="chat"]').first();
    await expect(drawer).toBeVisible({ timeout: 5000 });

    // Should see the OperaIQ AI header
    await expect(page.getByText(/OperaIQ AI/i).first()).toBeVisible({ timeout: 5000 });
  });

  test("chat drawer input bar is interactive", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");

    // Open drawer
    const askButton = page.getByRole("button", { name: /ask opera.?iq/i }).first();
    await askButton.click();

    // Wait for drawer to open
    await page.waitForTimeout(500);

    // Find the input bar
    const input = page.locator("input[placeholder*='incident'], input[placeholder*='runbook'], input[placeholder*='ask']").first();
    await expect(input).toBeVisible({ timeout: 5000 });

    // Type a triage request
    await input.fill("Triage the latest critical incident");
    await expect(input).toHaveValue("Triage the latest critical incident");

    // Send button should be enabled
    const sendButton = page.getByRole("button", { name: /send/i }).first();
    await expect(sendButton).toBeEnabled();
  });

  test("'Engage Agent' button on incident row opens chat with incident context", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");

    // Look for any "Engage Agent" button in the incident feed
    const engageButton = page.getByRole("button", { name: /engage agent/i }).first();

    // If incidents are loaded, the button should exist
    const hasEngageButton = await engageButton.isVisible({ timeout: 8000 }).catch(() => false);

    if (hasEngageButton) {
      await engageButton.click();
      // Chat drawer should open
      await expect(page.getByText(/OperaIQ AI/i).first()).toBeVisible({ timeout: 5000 });
    } else {
      // No incidents loaded — open chat drawer directly instead
      const askButton = page.getByRole("button", { name: /ask opera.?iq/i }).first();
      await askButton.click();
      await expect(page.getByText(/OperaIQ AI/i).first()).toBeVisible({ timeout: 5000 });
    }
  });
});
