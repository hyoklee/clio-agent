import { useSyncExternalStore } from 'react';

const subscribe = () => () => {};
const ready = () => true;
const serverReady = () => false;

/** Enable interactive controls only after their browser handlers are mounted. */
export function useClientReady(): boolean {
  return useSyncExternalStore(subscribe, ready, serverReady);
}
