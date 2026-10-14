import { expect, test } from "vitest";
import { guideMediaSources } from "./guide-media";

test("guide media retain document order, matching captions and section names", () => {
  const media =
    guideMediaSources(`import preview from '../../../assets/captures/docs-message-preview.png';
## Find a message
<Capture client:visible image={await captureImage(preview)} alt="Message preview" caption="Open the source message." version="UI abc123" />
## Save a review
<WidgetRecording name="docs-session-export" title="Export the conversation" caption="Open the saved review." />`);
  expect(media).toEqual([
    {
      kind: "image",
      source: "docs-message-preview.png",
      alt: "Message preview",
      caption: "Open the source message.",
      section: "Find a message",
      version: "UI abc123",
    },
    {
      kind: "video",
      source: "/media/docs-session-export.mp4",
      alt: "Export the conversation",
      caption: "Open the saved review.",
      section: "Save a review",
    },
  ]);
});

test("unresolved expressions do not invent media references", () => {
  expect(
    guideMediaSources(
      '<Capture image={await captureImage(missing)} caption="Missing" />',
    ),
  ).toEqual([]);
  expect(guideMediaSources("<WidgetRecording name={unknown} />")).toEqual([]);
});
