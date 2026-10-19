/** Media references already authored beside a documentation section. */
export interface GuideMediaSource {
  kind: "image" | "video";
  source: string;
  alt: string;
  caption: string;
  section?: string;
  version?: string;
}

/** Read static Capture/WidgetRecording props without executing the document. */
export function guideMediaSources(source: string): GuideMediaSource[] {
  const imports = new Map<string, string>();
  for (const match of source.matchAll(
    /import\s+(\w+)\s+from\s+['"][^'"]*\/assets\/(captures|tutorials)\/([^'"]+)['"]/g,
  )) {
    imports.set(match[1]!, match[2] === "captures" ? match[3]! : `tutorials/${match[3]}`);
  }
  const media: GuideMediaSource[] = [];
  for (const match of source.matchAll(
    /<(Capture|WidgetRecording)\b([\s\S]*?)\/>/g,
  )) {
    const props = Object.fromEntries(
      [
        ...match[2]!.matchAll(
          /\b(alt|caption|title|name|version)\s*=\s*(["'])(.*?)\2/gs,
        ),
      ].map((item) => [item[1]!, item[3]!]),
    );
    const section = [
      ...source.slice(0, match.index).matchAll(/^#{2,3}\s+(.+)$/gm),
    ]
      .at(-1)?.[1]
      ?.trim();
    if (match[1] === "WidgetRecording" && props.name) {
      media.push({
        kind: "video",
        source: `/media/${props.name}.mp4`,
        alt: props.title || props.name,
        caption: props.caption || "",
        section,
      });
      continue;
    }
    const variable = match[2]!.match(
      /image=\{await\s+captureImage\((\w+)\)\}/,
    )?.[1];
    const image = variable && imports.get(variable);
    if (image)
      media.push({
        kind: "image",
        source: image,
        alt: props.alt || "",
        caption: props.caption || "",
        section,
        version: props.version,
      });
  }
  return media;
}
