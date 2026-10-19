import { createHash } from 'node:crypto';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readNdpConversation } from './ndp-conversations';

const content = Buffer.from('<!doctype html><title>Recorded conversation</title>');
const asset = { file: 'test-session.html', bytes: content.length,
  sha256: createHash('sha256').update(content).digest('hex') };
let cacheDirectory: string;
beforeEach(async () => { cacheDirectory = await mkdtemp(join(tmpdir(), 'clio-conversation-')); });
afterEach(async () => { await rm(cacheDirectory, { recursive: true, force: true }); });

describe('published conversation integrity', () => {
  it('downloads and caches the exact native HTML, then reuses verified bytes', async () => {
    const fetchAsset = vi.fn<typeof fetch>().mockResolvedValue(new Response(content));
    expect(await readNdpConversation(asset, { cacheDirectory, fetchAsset })).toEqual(new Uint8Array(content));
    expect(await readFile(join(cacheDirectory, asset.file))).toEqual(content);
    await readNdpConversation(asset, { cacheDirectory, fetchAsset });
    expect(fetchAsset).toHaveBeenCalledTimes(1);
  });

  it('replaces a corrupt cache only with a verified download', async () => {
    await writeFile(join(cacheDirectory, asset.file), 'partial');
    const fetchAsset = vi.fn<typeof fetch>().mockResolvedValue(new Response(content));
    await readNdpConversation(asset, { cacheDirectory, fetchAsset });
    expect(await readFile(join(cacheDirectory, asset.file))).toEqual(content);
  });

  it.each([Buffer.from('partial'), Buffer.alloc(content.length)])('refuses truncated or altered exports', async (body) => {
    const fetchAsset = vi.fn<typeof fetch>().mockResolvedValue(new Response(body));
    await expect(readNdpConversation(asset, { cacheDirectory, fetchAsset })).rejects.toThrow('integrity check failed');
    await expect(readFile(join(cacheDirectory, asset.file))).rejects.toMatchObject({ code: 'ENOENT' });
  });

  it('fails the build when the public asset is unavailable', async () => {
    const fetchAsset = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 404 }));
    await expect(readNdpConversation(asset, { cacheDirectory, fetchAsset })).rejects.toThrow('HTTP 404');
  });

  it('rejects filenames outside the cache before fetching', async () => {
    const fetchAsset = vi.fn<typeof fetch>();
    await expect(readNdpConversation({ ...asset, file: '../outside.html' }, { cacheDirectory, fetchAsset }))
      .rejects.toThrow('Invalid conversation filename');
    expect(fetchAsset).not.toHaveBeenCalled();
  });
});
