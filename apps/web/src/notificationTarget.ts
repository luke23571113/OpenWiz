import { actionable, slotsOf } from './decisions.ts';
import type { Decisions, Item } from './decisions.ts';
import type { Clock, Received } from './cockpit.ts';
import { freshNow } from './cockpit.ts';

// The Decisions page's bound mode. Push notifications and their landing are
// retired (0.0.17 ER4); only this exact-identity selection stays.
type Subject = { kind: 'issue' | 'pull_request'; number: number };
export type DecisionReference = { repository: string; subject: Subject; comment_id: number; request_id: string; fingerprint: string };

export type BoundDecision = { state: 'current'; item: Item; binding: string } | { state: 'changed' | 'resolved' | 'missing' | 'ambiguous' | 'unread'; needsResolution?: boolean };

/** Select by exact identity; a displayed proposal never silently rebinds. */
export function selectBoundDecision(reference: DecisionReference, decisions: Decisions, received: Received, now: Clock, pinned?: string): BoundDecision {
  // Local ids are unique only within a repository (#2150). Compare the source's
  // verified name in the reference's lowercase form; never substitute another.
  const ours = decisions.items.filter((item) => item.subject.repository.toLowerCase() === reference.repository);
  const matches = ours.filter((item) => item.comment_id === reference.comment_id);
  if (matches.length > 1 || ours.filter((item) => item.request.id === reference.request_id).length > 1) return { state: 'ambiguous' };
  const item = matches[0];
  if (!item) return { state: 'unread', needsResolution: decisions.coverage.state === 'complete' && freshNow(decisions.freshness, decisions.snapshot_at, received, now) };
  if (item.subject.kind !== reference.subject.kind || item.subject.number !== reference.subject.number
    || item.request.id !== reference.request_id || item.request.fingerprint !== reference.fingerprint) return { state: 'changed' };
  if ('known' in item.current && !item.current.known) return { state: 'changed' };
  if (decisions.coverage.state !== 'complete') return { state: 'unread' };
  const slot = slotsOf({ ...decisions, items: [item] })[0];
  if (!slot) return { state: 'resolved' };
  const act = actionable(decisions, slot, received, now);
  if (!act.ok) return { state: 'unread' };
  // Answer progress is lifecycle, not changed proposal wording. The existing
  // card owns every question's send id and receipt; this adds no answer state.
  const proposal = Object.fromEntries(Object.entries(item.request).filter(([key]) => key !== 'status' && key !== 'answered'));
  const binding = JSON.stringify([reference, proposal, act.target]);
  if (pinned !== undefined && binding !== pinned) return { state: 'changed' };
  return { state: 'current', item, binding };
}
