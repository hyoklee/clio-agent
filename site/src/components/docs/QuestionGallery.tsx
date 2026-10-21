import { ArrowLeft, ArrowRight } from 'lucide-react';
import { useState } from 'react';
import { useClientReady } from '../../lib/use-client-ready';
import Capture, { type CaptureImage } from '../overview/Capture';
import { Button } from '../ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';

interface QuestionExample {
  id: string;
  label: string;
  explanation: string;
  image: CaptureImage;
  previewHeight?: number;
  alt: string;
  caption: string;
  version?: string;
}

/** Browse real interface captures without mistaking them for answer controls. */
export default function QuestionGallery({ examples, version }: { examples: readonly QuestionExample[]; version: string }) {
  const [active, setActive] = useState(examples[0]?.id ?? '');
  const interactive = useClientReady();
  const index = examples.findIndex((example) => example.id === active);
  if (!examples.length) return null;

  return (
    <Tabs className="not-content" value={active} onValueChange={(value) => { if (typeof value === 'string') setActive(value); }}>
      <TabsList aria-label="Question types" className="group-data-horizontal/tabs:h-auto max-w-full flex-wrap justify-start gap-x-3 gap-y-3" variant="line">
        {examples.map((example) => <TabsTrigger disabled={!interactive} key={example.id} value={example.id}>{example.label}</TabsTrigger>)}
      </TabsList>
      <div className="mt-2 flex items-center justify-between gap-2 text-sm text-muted-foreground">
        <span aria-live="polite">Example {index + 1} of {examples.length}</span>
        <div className="flex gap-1">
          <Button aria-label="Previous question example" disabled={!interactive} onClick={() => setActive(examples[(index - 1 + examples.length) % examples.length].id)} size="icon-sm" variant="ghost"><ArrowLeft aria-hidden="true" /></Button>
          <Button aria-label="Next question example" disabled={!interactive} onClick={() => setActive(examples[(index + 1) % examples.length].id)} size="icon-sm" variant="ghost"><ArrowRight aria-hidden="true" /></Button>
        </div>
      </div>
      {examples.filter((example) => example.id === active).map((example) => (
        <TabsContent className="space-y-3" key={example.id} value={example.id}>
          <p className="m-0 text-base leading-relaxed">{example.explanation}</p>
          <Capture alt={example.alt} caption={example.caption} image={example.image} previewHeight={example.previewHeight} version={example.version ?? version} />
        </TabsContent>
      ))}
    </Tabs>
  );
}
