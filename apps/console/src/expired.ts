/**
 * One announcement, heard once: this token is no longer good.
 *
 * WHY AN EVENT AND NOT A RETURN VALUE. A 401 arrives inside whichever screen happened to be
 * fetching — the recent-customers strip, the catalogue, the legal gate — and every one of those
 * call sites would otherwise have to know how to end a session. They did not, so the screens
 * logged the refusal to the console and kept showing a spinner: the person was signed out on the
 * server and still looking at an application on his phone.
 *
 * ONLY 401. A 403 is a capability this person does not hold, which is a normal answer for a real
 * session — signing him out for it would throw an operator to the door for opening a manager's
 * section.
 */
export const SESSION_EXPIRED = 'raje3:session-expired';

export function announceExpiry(): void {
  window.dispatchEvent(new Event(SESSION_EXPIRED));
}
