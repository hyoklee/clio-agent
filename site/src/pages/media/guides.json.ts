import type { APIRoute } from "astro";
import type { ImageMetadata } from "astro";
import { captureImage } from "../../lib/captures";
import { guideMediaSources } from "../../lib/guide-media";

const pages = import.meta.glob<string>("/src/content/docs/docs/**/*.mdx", {
  query: "?raw",
  eager: true,
  import: "default",
});
const images = import.meta.glob<ImageMetadata>(
  ["/src/assets/captures/*.{png,jpg,jpeg,webp}", "/src/assets/tutorials/**/*.{png,jpg,jpeg,webp}"],
  { eager: true, import: "default" },
);

/** Static, same-origin references to the media used by published guides. */
export const GET: APIRoute = async () => {
  const guides = [];
  const resolved = new Map<string, Awaited<ReturnType<typeof captureImage>>>();
  for (const [filename, source] of Object.entries(pages).sort(([a], [b]) =>
    a.localeCompare(b),
  )) {
    const id = filename
      .replace("/src/content/docs/", "")
      .replace(/\.mdx$/, "")
      .replace(/\/index$/, "");
    const media = [];
    for (const item of guideMediaSources(source)) {
      if (item.kind === "video") {
        media.push({ ...item, src: item.source, source: undefined });
        continue;
      }
      const asset = item.source.startsWith("tutorials/") ? item.source : `captures/${item.source}`;
      const image = images[`/src/assets/${asset}`];
      if (!image)
        throw new Error(`Guide ${id} references missing image ${item.source}`);
      let capture = resolved.get(item.source);
      if (!capture) {
        capture = await captureImage(image);
        resolved.set(item.source, capture);
      }
      media.push({
        ...item,
        src: capture.full,
        width: capture.width,
        height: capture.height,
        source: undefined,
      });
    }
    if (media.length)
      guides.push({
        id,
        title:
          source
            .match(/^title:\s*(.+)$/m)?.[1]
            ?.trim()
            .replace(/^["']|["']$/g, "") || id,
        url: `/${id}/`,
        availability: source.includes("<PreviewGuide") || source.includes('title="Development build"')
          ? "development"
          : undefined,
        media,
      });
  }
  return new Response(JSON.stringify({ version: 1, guides }), {
    headers: { "Content-Type": "application/json" },
  });
};
