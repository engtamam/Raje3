/**
 * Three screens that answered a question nobody asked (م · قواطع).
 *
 * These are source-shape assertions rather than rendered-DOM ones, and that is deliberate: each
 * defect is a MISSING BRANCH, and a test that renders the happy path cannot see a branch that was
 * never written. What is pinned here is that the branch exists and is reached by the right state.
 */
import { describe, expect, it } from 'vitest';

// THE SOURCE AS A STRING, through Vite rather than `node:fs` — this app's tsconfig has no node
// types, and adding them so a test can read a file would be the tail wagging the build.
import customerSrc from './screens/Customer.tsx?raw';
import doorSrc from './screens/Door.tsx?raw';
import editorSrc from './screens/TextEditor.tsx?raw';
import localSrc from './screens/Shop.tsx?raw';
import previewSrc from './screens/MessagePreview.tsx?raw';
import pointsSrc from './screens/Points.tsx?raw';
import { DENIED, isReady } from './loading';
import { owns } from './apps';
import { visibleSections } from './nav';

describe('the grey box on «نقاطي» that never resolved', () => {
  it('a role that cannot ask about billing is not left loading for ever', () => {
    // THE DEFECT. A manager holding `loyalty.manage` and not `billing.self` never triggers the
    // entitlement read, so the state stayed at its initial value and `AppGate` drew a skeleton
    // for ever: no programme, no lock, and no sentence.
    expect(owns(DENIED, 'feature.loyalty')).toBe(true);
  });

  it('and it still refuses to claim «not bought» while the answer is unknown', () => {
    // The other direction is the expensive one: telling a paying shop it has not paid.
    expect(owns(undefined, 'feature.loyalty')).toBe(null);
    expect(owns(null, 'feature.loyalty')).toBe(null);
    expect(owns({ checked: false, message: '', keys: [], apps: [] }, 'feature.loyalty'))
      .toBe(null);
  });

  it('a real answer is still answered', () => {
    const owned = { checked: true, message: '', keys: ['feature.loyalty'], apps: [] };
    expect(isReady(owned)).toBe(true);
    expect(owns(owned, 'feature.loyalty')).toBe(true);
    expect(owns(owned, 'feature.campaigns')).toBe(false);
  });
});

describe('«نقاطي»: a failed settings read must not draw rules as facts', () => {
  it('the earning tab renders nothing editable until the settings arrived', () => {
    // Every control on that tab defaults to `earn?.…?.points ?? 0`, so a failed read presented the
    // whole tree as ZERO — and the first touch on any field WRITES it. The owner corrects a number
    // he was never shown correctly, and the shop starts granting what the screen made up.
    const points = pointsSrc;
    expect(points).toContain('!isReady(earn) ?');
    expect(points).toContain("t('points.settingsFailed.title')");
  });
});

describe('the door: «أكّد رقمك» on a screen with no code field', () => {
  it('both panes answer an unverified refusal with the code step', () => {
    // Opening a shop ends by signing in. When the server answered `unverified`, the new-shop pane
    // printed the sentence on a form with no code field anywhere on it — the account exists, his
    // number is taken, and there is no way forward from that screen.
    const door = doorSrc;
    expect(door.match(/needsProof\(err\)/g)?.length).toBe(2);
    expect(door.match(/<ProveNumber/g)?.length).toBe(2);
  });

  it('the rule itself is written once', () => {
    // Two copies of «what counts as unverified» is one copy that goes stale the day it changes.
    const door = doorSrc;
    expect(door.match(/reason === 'unverified'/g)?.length).toBe(1);
  });
});

describe('م · النمط 3: declared for a purpose, and nobody read it', () => {
  it('a section whose service is down stays in the rail, named', () => {
    // `catalog.unreachable` was declared with the reason written beside it — «a section missing
    // because a service is down must be distinguishable from a section missing because this
    // person may not have it» — and its only reader fired when EVERY service was down. So loyalty
    // falling over alone deleted «نقاطي» silently, and the owner who pays for it phoned support
    // about his permissions.
    const catalog = {
      services: [{ service: 'operations', actions: [{ id: 'operations.record_visit' } as never] }],
      unreachable: ['loyalty'],
    } as never;
    const rows = visibleSections(catalog);

    const points = rows.find((r) => r.id === 'points');
    expect(points, 'the row must survive its service').toBeTruthy();
    expect(points?.unavailable).toBe(true);
  });

  it('and a section he simply may not have is still absent', () => {
    // The other half: this is a permission answer, and drawing a row for it would offer him a
    // section his role does not include — a lock where there is nothing to unlock.
    const catalog = { services: [], unreachable: [] } as never;
    expect(visibleSections(catalog).find((r) => r.id === 'points')).toBeUndefined();
  });

  it('a healthy section is not marked unavailable', () => {
    const catalog = {
      services: [{ service: 'loyalty', actions: [{ id: 'loyalty.rewards.update' } as never] }],
      unreachable: [],
    } as never;
    expect(visibleSections(catalog).find((r) => r.id === 'points')?.unavailable).toBe(false);
  });

  it('«محلّي» shows the 402 sentence instead of dropping the section', () => {
    // `locked` was declared in Local.tsx with a paragraph explaining exactly this, and nothing
    // ever called `setLocked` — so every 402 was swallowed into `null` and the section vanished.
    // A capability nobody can see is a capability nobody can buy.
    expect(localSrc).toContain('setLocked((was)');
    expect(localSrc).toContain('locked.associations');
    expect(localSrc).toContain('locked.bundles');
  });

  it('the editor opens on what he wrote', () => {
    // His saved text sat one component away in `Mine.body`, unpassed, while `draft` was declared
    // for it and never set — so «عدّل نصّي» meant typing the whole message again.
    //
    // ASSERTED AS A PROPERTY, NOT AS A SPELLING. This used to pin the exact expression
    // `toHtml(body ?? '', slots)`, and it broke the day the saved body started being stripped of
    // its mandatory tail before loading — a change that leaves the property completely intact. A
    // guard that fails on a rewrite of the line it watches teaches whoever hits it to edit the
    // guard, which is how a real defect eventually walks past one.
    expect(editorSrc).toMatch(/toHtml\(.*\bbody\b.*\bslots\b/);
    expect(previewSrc).toContain('body={(isReady(mine) ? mine : [])');
  });
});

describe('أ-9 · what the operator typed, shown to the person who asked for it', () => {
  it('the visit list renders the meter reading and the note', () => {
    // Both doors accept `meter` and `note`, the visit row stores them, `public()` emits them —
    // and no screen in the product ever showed them. That is daily typing on the one screen
    // whose whole budget is five seconds, thrown away.
    expect(customerSrc).toContain('العدّاد:');
    expect(customerSrc).toContain('{v.note}');
  });
});
