import { expect, test } from "@playwright/test";

test("the carousel shows actual docs images and stops its hidden video", async ({
  page,
}) => {
  await page.goto("/docs/widgets/carousel/");
  const example = page.getByRole("region", {
    name: "Find and keep useful messages",
  });
  await expect(
    example.getByRole("img", { name: "Message rail preview" }),
  ).toBeVisible();
  await expect(example).toContainText("1 of 3");
  await example.getByRole("button", { name: "Next slide" }).click();
  await expect(
    example.getByRole("img", { name: "Marked messages list" }),
  ).toBeVisible();
  await expect(
    example.getByRole("img", { name: "Message rail preview" }),
  ).toHaveCount(0);
  await example.getByRole("button", { name: "Next slide" }).click();
  const video = example.locator("video");
  await expect(video).toHaveAttribute("controls", "");
  await expect
    .poll(() =>
      video.evaluate((element: HTMLVideoElement) => element.readyState),
    )
    .toBeGreaterThanOrEqual(1);
  expect(
    await video.evaluate((element: HTMLVideoElement) => element.duration),
  ).toBeGreaterThan(0);
  await example.getByRole("button", { name: "Previous slide" }).click();
  await expect(example.locator("video")).toHaveCount(0);
  await page.goto("/docs/widgets/video/");
  await expect(page.locator("video")).toHaveAttribute("controls", "");
});

test("the guide media index points to published images and videos in document order", async ({
  request,
}) => {
  const response = await request.get("/media/guides.json");
  expect(response.ok()).toBe(true);
  const index = await response.json();
  const guide = index.guides.find(
    (item: { id: string }) => item.id === "docs/sessions",
  );
  expect(guide.url).toBe("/docs/sessions/");
  expect(
    guide.media.some((item: { alt: string }) =>
      item.alt.startsWith("Marked messages"),
    ),
  ).toBe(true);
  const exports = index.guides.find(
    (item: { id: string }) => item.id === "docs/exports",
  );
  for (const media of [...guide.media, ...exports.media]) {
    expect(media.src).toMatch(/^\//);
    expect((await request.get(media.src)).ok()).toBe(true);
    expect(media.caption.length).toBeGreaterThan(0);
  }
});
