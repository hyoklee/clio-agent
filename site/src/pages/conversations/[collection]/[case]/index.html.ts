import type { APIRoute, GetStaticPaths } from 'astro';
import { ndpConversations, readNdpConversation } from '../../../../lib/ndp-conversations';

export const getStaticPaths: GetStaticPaths = () =>
  ndpConversations.map((asset) => ({ params: { case: asset.slug }, props: { asset } }));

/** Serve the exact self-contained native viewer as a static HTML page. */
export const GET: APIRoute = async ({ props }) => {
  const content = await readNdpConversation(props.asset);
  return new Response(content as Uint8Array<ArrayBuffer>, {
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });
};
