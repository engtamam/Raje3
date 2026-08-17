/**
 * The one blank in his own text that he does not choose, cannot move, and cannot delete.
 *
 * TAMAM'S DECISION, AND WHY IT LANDS ON THE SCREEN. He writes his own wording, Meta approves it
 * under HIS shop's name, and the fine for a promotional message with no way to stop it lands on
 * HIM. So the stop link may not be a field he can leave empty — the server appends it — and the
 * screen's whole job is to make sure he KNOWS it is there.
 *
 * SHOWN LOCKED, NOT HIDDEN. An owner who does not see it in his text believes it is not in his
 * text. The first he would learn otherwise is a customer's reply, or a letter.
 *
 * Source-shape assertions rather than a rendered DOM, for the reason gates.test.ts gives: what is
 * pinned is that the branch exists and is fed by the right field. The Arabic itself comes from the
 * server (`reasons.MANDATORY_NOTE`), so asserting the words here would assert a copy of them.
 */
import { describe, expect, it } from 'vitest';

import editorSrc from './screens/TextEditor.tsx?raw';
import previewSrc from './screens/MessagePreview.tsx?raw';

describe('the address a message owes, on the screen that writes it', () => {
  it('the editor is TOLD which address it is, and never works it out', () => {
    // THE RULE HAS ONE OWNER: `reasons.mandatory_tail`, read by the library generator and by the
    // draft path. A screen that decided for itself whether this message owes a stop link or an
    // invitation would be a fourth reader of a rule this codebase has already watched drift.
    expect(editorSrc).toContain('mandatory?: Mandatory');
    expect(editorSrc).not.toMatch(/cls\s*===\s*'marketing'/);
    expect(editorSrc).not.toContain("'stop_link'");
  });

  it('it is rendered, and rendered as locked rather than as a chip he may add', () => {
    // NOT IN THE PALETTE. The palette is what he inserts at the caret; offering this one there
    // would let him drop a second copy mid-sentence, which the save then refuses — a palette whose
    // choices can be refused is a palette that teaches by error.
    expect(editorSrc).toMatch(/mandatory\s*\?\s*\(/);
    expect(editorSrc).toContain('Lock');
    expect(editorSrc).toContain('mandatory.note');
    // The palette still maps `slots`, and the mandatory one is not among them — the server strips
    // it from that list (`reasons.public`), so this asserts the two are separate renderings.
    expect(editorSrc).toMatch(/slots\.map\(/);
  });

  it('the preview shows what ARRIVES, not what he typed', () => {
    // «كما تصل عميلك» is the one line on this screen that may not be approximately true: the
    // server appends the address at save, so a preview stopping at his last word would show him a
    // shorter message than the one his customer reads.
    expect(editorSrc).toContain('mandatory.sample');
  });

  it('the screen that owns the reason fetches it and hands it down', () => {
    // A prop nothing ever passes is the defect family this file's neighbours were written for:
    // declared for a purpose, and nobody read it.
    expect(previewSrc).toContain('mandatory?: Mandatory');
    expect(previewSrc).toContain('setMandatory(x.reason?.mandatory)');
    expect(previewSrc).toContain('mandatory={mandatory}');
  });
});
