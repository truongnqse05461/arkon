import { expect, test } from "@playwright/test";

test("mindmap page supports generate, view, and delete flows", async ({ page }) => {
  const apiBase = "http://localhost:5055";
  const globalMindmapId = "11111111-1111-1111-1111-111111111111";
  const sourceId = "22222222-2222-2222-2222-222222222222";
  const departmentId = "33333333-3333-3333-3333-333333333333";
  const projectId = "44444444-4444-4444-4444-444444444444";

  let mindmaps: Array<Record<string, unknown>> = [];

  await page.addInitScript(() => {
    window.localStorage.setItem("arkon_token", "e2e-token");
  });

  await page.route(`${apiBase}/api/auth/me`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "55555555-5555-5555-5555-555555555555",
        name: "E2E User",
        email: "e2e@example.com",
        role: "employee",
        department_ids: [departmentId],
        department_names: ["Engineering"],
        permissions: [
          "wiki:read:own_dept",
          "doc:read:own_dept",
        ],
        workspace_memberships: [],
      }),
    });
  });

  await page.route(`${apiBase}/api/projects*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { id: projectId, name: "Phoenix" },
      ]),
    });
  });

  await page.route(`${apiBase}/api/departments*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { id: departmentId, name: "Engineering" },
      ]),
    });
  });

  await page.route(`${apiBase}/api/sources*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { id: sourceId, title: "Architecture RFC", source_type: "file" },
      ]),
    });
  });

  await page.route(`${apiBase}/api/mindmaps`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mindmaps),
    });
  });

  await page.route(`${apiBase}/api/mindmap?*`, async (route) => {
    const url = new URL(route.request().url());
    const scopeType = url.searchParams.get("scope_type");
    const scopeId = url.searchParams.get("scope_id");
    const target = mindmaps.find(
      (mindmap) =>
        mindmap.scope_type === scopeType &&
        (mindmap.scope_id ?? null) === (scopeId ?? null),
    );

    await route.fulfill({
      status: target ? 200 : 404,
      contentType: "application/json",
      body: JSON.stringify(
        target
          ? {
              ...target,
              tree_json: {
                name: "Source overview map",
                children: [{ name: "Architecture RFC", children: [] }],
              },
            }
          : { detail: "Not found" },
      ),
    });
  });

  await page.route(`${apiBase}/api/mindmap/generate`, async (route) => {
    const body = route.request().postDataJSON() as {
      scope_type: string;
      scope_id?: string | null;
      source_type: string;
      source_ids?: string[];
      instruction?: string;
    };

    const generated = {
      id: globalMindmapId,
      scope_type: body.scope_type,
      scope_id: body.scope_id ?? null,
      title: "Source overview map",
      source_type: body.source_type,
      wiki_page_count: body.source_ids?.length ?? 1,
      generated_at: "2026-07-09T10:00:00Z",
      tree_json: {
        name: "Source overview map",
        children: [{ name: "Architecture RFC", children: [] }],
      },
    };

    mindmaps = [
      {
        id: generated.id,
        scope_type: generated.scope_type,
        scope_id: generated.scope_id,
        title: generated.title,
        source_type: generated.source_type,
        wiki_page_count: generated.wiki_page_count,
        generated_at: generated.generated_at,
      },
    ];

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(generated),
    });
  });

  await page.route(new RegExp(`${apiBase}/api/mindmap/.+`), async (route) => {
    if (route.request().method() !== "DELETE") {
      await route.fallback();
      return;
    }

    mindmaps = [];
    await route.fulfill({ status: 204, body: "" });
  });

  await page.goto("/mindmap");

  await expect(page.getByRole("heading", { name: "Mindmaps" })).toBeVisible();
  await expect(page.getByText("No mindmaps yet")).toBeVisible();

  await page.getByRole("button", { name: "Generate" }).first().click();
  await expect(page.getByRole("heading", { name: "Generate Mindmap" })).toBeVisible();

  await page.getByLabel("Source *").selectOption("source_docs");
  await expect(page.getByText("Architecture RFC")).toBeVisible();
  await expect(page.getByRole("button", { name: "Generate" }).last()).toBeDisabled();

  await page.getByLabel("Select Documents *").locator("..").getByRole("checkbox").check();
  await page.getByLabel("Instruction (optional)").fill("Focus on architecture");
  await page.getByRole("button", { name: "Generate" }).last().click();

  await expect(page.getByRole("heading", { name: "Generate Mindmap" })).toBeHidden();
  await expect(page.getByText("Source Doc")).toBeVisible();
  await expect(page.getByRole("cell", { name: "1" })).toBeVisible();

  await page.locator('button[title="View"]').click();
  await expect(page.getByText("Source overview map")).toBeVisible();
  await expect(page.locator('button[title="Back to list"]')).toBeVisible();

  await page.locator('button[title="Back to list"]').click();
  await page.locator('button[title="Delete"]').click();
  await expect(page.getByText("Delete Mindmap")).toBeVisible();
  await page.getByRole("button", { name: "Delete" }).last().click();

  await expect(page.getByText("No mindmaps yet")).toBeVisible();
});
