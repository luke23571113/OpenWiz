// Setup page wording and status marks (#1105). Pure: no fetch, no effects.
// T4 (`engine`, `activate_engine`) and T5 (`remote_access`, `configure_access`)
// change only their own lines here.
import type { SetupComponent, SetupComponentId, SetupView } from './api.ts';

export function componentName(id: SetupComponentId): string {
  switch (id) {
    case 'cloudroom': return 'CloudRoom';
    case 'harness': return 'Agent harness';
    case 'personal_github': return 'Personal GitHub';
    case 'github_app': return 'OpenWiz GitHub App';
    case 'project': return 'Project';
    case 'engine': return 'Engine';
    case 'remote_access': return 'Phone access';
  }
}

/** Refused and missing need the owner; verified is settled; unknown is unproven. */
export function componentTier(state: SetupComponent['state']): 't1' | 't2' | 't5' {
  return state === 'missing' || state === 'refused' ? 't1' : state === 'verified' ? 't2' : 't5';
}

export function operationName(kind: SetupView['operations'][number]['kind']): string {
  switch (kind) {
    case 'connect_app': return 'Connect OpenWiz GitHub App';
    case 'prepare_project': return 'Prepare project';
    case 'activate_engine': return 'Activate engine';
    case 'configure_access': return 'Configure phone access';
  }
}

/** The first component that needs the owner, in setup order, or null. */
export function nextComponent(view: SetupView): SetupComponent | null {
  return view.components.find((c) => c.id !== 'engine' && c.id !== 'remote_access' && c.state !== 'verified') ?? null;
}

/** #633: the owner explicitly skipped the App, so the personal login acts. */
export function appSkipped(view: SetupView): boolean {
  return view.identity?.selected === 'personal_login' && view.identity.app_choice === 'skip';
}

/** #633: the identity line on a GitHub row, or null. The acting login comes
 * only from the owner's saved skip; an App failure never offers or implies it. */
export function identityNote(view: SetupView, id: SetupComponent['id']): { kind: 'acting' | 'chosen' | 'offer'; text: string } | null {
  const login = view.components.find((c) => c.id === 'personal_github');
  const app = view.components.find((c) => c.id === 'github_app');
  if (id === 'personal_github' && appSkipped(view) && view.identity?.acting_login) {
    return login?.state === 'verified'
      ? { kind: 'acting', text: `Acting identity: ${view.identity.acting_login}, your personal GitHub login. The App is skipped.` }
      : { kind: 'chosen', text: `Chosen identity: ${view.identity.acting_login}, your personal GitHub login, is not verified now. The App is skipped.` };
  }
  if (id === 'github_app' && !appSkipped(view) && view.identity?.selected !== 'app' && login?.state === 'verified' && app?.state !== 'verified') {
    return { kind: 'offer', text: 'Prefer not to create an App? Ask your installing agent to skip it. Your verified personal login then acts for the factory, and the App stays missing.' };
  }
  return null;
}
