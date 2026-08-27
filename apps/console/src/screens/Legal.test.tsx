/**
 * The public legal route renders the real, published document — not a stub, and with no session
 * and no network call. That is the whole point of it: the one reader who most needs the Terms is
 * the one deciding whether to sign up, and he has no token to send.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Legal } from './Legal';
import docs from 'virtual:legal-docs';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="legal/:slug" element={<Legal />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Legal', () => {
  it('exposes exactly the readable documents, and none of the internal ones', () => {
    const slugs = docs.map((d) => d.slug).sort();
    expect(slugs).toEqual(
      ['cookies', 'data-subject-rights', 'privacy-policy', 'terms'].sort(),
    );
    // dpia / ropa / processing-agreement are not `public` or `accept` and must never surface here.
    expect(slugs).not.toContain('dpia');
    expect(slugs).not.toContain('ropa');
    expect(slugs).not.toContain('processing-agreement');
  });

  it('renders the real Terms text, with tokens already filled', () => {
    renderAt('/legal/terms');
    // A clause title and a sentence from its body — proof this is the actual document, not a stub.
    expect(screen.getAllByText(/الأطراف والقبول/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/تُبرَم هذه الشروط بين/).length).toBeGreaterThan(0);
    // The placeholder company name from `values:` was substituted into the clause text.
    expect(screen.getAllByText(/راجِع/).length).toBeGreaterThan(0);
    // No unfilled token leaks into what a reader sees.
    expect(document.body.textContent).not.toMatch(/\{\{[A-Z0-9_]+\}\}/);
  });

  it('renders the privacy policy from the PDPL pack, with its own clauses filled from our values', () => {
    renderAt('/legal/privacy-policy');
    // From the pack template's own clause 1 ("Controller — Name and Activity").
    expect(screen.getAllByText(/جهة التحكم — الاسم والنشاط/).length).toBeGreaterThan(0);
    // {{COMPANY_NAME}} resolved to our seed's value.
    expect(screen.getAllByText(/راجِع/).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/\{\{[A-Z0-9_]+\}\}/);
  });

  it('renders the cookies categories our seed adds beyond the template', () => {
    renderAt('/legal/cookies');
    expect(screen.getAllByText(/ضرورية/).length).toBeGreaterThan(0);
  });

  it('answers an unknown slug with a real page, not a crash', () => {
    renderAt('/legal/does-not-exist');
    expect(screen.getAllByText('الوثيقة غير موجودة').length).toBe(1);
  });
});
