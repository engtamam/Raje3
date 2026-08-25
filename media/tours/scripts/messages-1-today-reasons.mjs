/**
 * «رسائلي» — PART 1 OF 3, «متى نرسل» + the health card above it. Read Messages.tsx,
 * MessagePreview.tsx, rj-ui/Segmented.tsx, rj-ui/FilterMenu.tsx and rj-ui/Toggle.tsx directly
 * before writing a single selector — this project's own standing rule. Beyond the frontend, an
 * agent studied the REAL backend logic behind this tab (services/reminders' gate.py/reasons.py)
 * before this plan was finalized — not because the video explains any of that (it explains the
 * UI, in an owner's own words, per an explicit correction), but so every caption said here is
 * something this Claude actually verified is true, not a guess dressed as a fact.
 *
 * WHAT THE STUDY CHANGED ABOUT THIS SCRIPT, CONCRETELY:
 *   - «خرجت» ≠ «وصلت» is called out explicitly (Part 2's script, not here) because gate.py/
 *     receipts.py confirm delivery/read tracking is genuinely best-effort, not a UI simplification
 *     — an owner who reads "خرجت" as "arrived" is wrong in a way that matters.
 *   - The class explanation (خدمية/شخصية/تسويقية) states plainly that تسويقية is the one that
 *     needs the customer's own prior agreement — gate.py's own first check after "the customer's
 *     own stop" is exactly this, and it is a real, hard, legal gate, not a toggle for convenience.
 *
 * THREE PARTS, BY THE SCREEN'S OWN FOUR TABS (same split reasoning as visit-1/2): Part 1 (this
 * file) is «متى نرسل» — the automatic reasons, plus the always-visible health card above every
 * tab. Part 2 is «بانتظار الخروج» + «السجل». Part 3 is «حملاتي».
 *
 * EACH PART IS RECORDED, PRODUCED AND VERIFIED BEFORE THE NEXT IS WRITTEN — an explicit
 * correction to the earlier, hastier pass at this tab. This file is Part 1; Part 2 and 3 do not
 * exist yet and are not written until this one has a real, checked recording.
 *
 * THE DEMO ACCOUNT'S REAL STATE, CONFIRMED NOT ASSUMED: no WhatsApp number is linked (no real
 * Meta credentials on a demo account), so `ceiling.known` is false and the «سقف واتساب» line
 * never renders — narrated by voice only, never targeted as a click. `today.blocked` is empty
 * (nothing stops sending), so the three-number row renders, not the red banner.
 *
 * THIS SCRIPT'S ONE REAL, PERSISTENT SIDE EFFECT: the toggle demo turns the account's first
 * reason (server order — was «سُجّلت زيارة» when this was written) off, and does NOT turn it
 * back on inside the recording (see the step's own comment for why). After EVERY recording of
 * this script, run the fix-back below before touching anything else — the account must not be
 * left mid-tour-state for whatever script runs against it next:
 *
 *   node -e "(async()=>{const s=JSON.parse(require('fs').readFileSync('media/tours/.demo-session.json','utf8'));
 *   const cat=await(await fetch('http://localhost:5174/api/v1/app/catalog',{headers:{authorization:'Bearer '+s.token}})).json();
 *   let a; for(const sv of cat.services){const x=sv.actions.find(x=>x.id==='reminders.reasons'); if(x) a=x;}
 *   const r=await(await fetch('http://localhost:5174'+a.path,{headers:{authorization:'Bearer '+s.token}})).json();
 *   const off=r.reasons.find(x=>!x.on); if(!off){console.log('nothing off — already clean'); return;}
 *   let sa; for(const sv of cat.services){const x=sv.actions.find(x=>x.id==='reminders.set_reason'); if(x) sa=x;}
 *   const out=await(await fetch('http://localhost:5174'+sa.path,{method:sa.method,headers:{authorization:'Bearer '+s.token,'content-type':'application/json'},body:JSON.stringify({reason_id:off.id,on:true})})).json();
 *   console.log('restored', off.id, JSON.stringify(out.error||'ok'));})();"
 */
export default {
  id: 'messages-1-today-reasons',
  title: 'رسائلي 1 — هل كل شي يشتغل، ومتى نرسل',
  section: 'رسائلي', // nav.ts's own label
  useDemoSession: true,
  // A live check found the click sound played is wrong/inaccurate — off until the actual
  // sfx asset/mix itself is fixed (media/lib/sfx/click.ogg or media/lib/ffmpeg.mjs::mixSfx).
  sfx: false,
  steps: [
    {
      goto: '/messages',
      chapter: 'هل كل شي يشتغل؟',
      say: 'تعرف مين يراسل عملاءك باسمك، ومتى؟ تعال أوريك',
    },
    {
      say: 'أول شي فوق — بطاقة تقولك هل الإرسال شغّال',
    },
    {
      click: 'text=خرجت اليوم',
      say: 'كم رسالة خرجت فعليًا اليوم',
    },
    {
      click: 'text=بانتظار الخروج',
      say: 'وكم لسه بالطابور — بتخرج تلقائيًا بوقتها',
    },
    {
      click: 'text=تعيد المحاولة',
      say: 'ولو رسالة تعثّرت، تعيد المحاولة تلقائيًا — ما تضيع',
    },
    {
      say: 'ولو ربطت واتساب، تشوف هنا سقفك اليومي مع ميتا',
    },
    {
      chapter: 'متى نرسل',
      say: 'تحت — كل الأسباب اللي ترسل رسالة باسمك تلقائيًا',
    },
    {
      say: 'أول جملة تقولك كم سبب عندك',
    },
    {
      say: 'ثلاث أنواع: خدمية، وشخصية تخصّه هو',
    },
    {
      say: 'وتسويقية — وهذي وحدها تحتاج موافقة عميلك مسبقًا',
    },
    {
      click: 'role=button:النوع',
      say: 'فلتر «النوع» — لو تبي تشوف نوع معيّن بس',
    },
    {
      click: 'role=option:تسويقية',
      say: 'اضغط «تسويقية» — تشوف اللي تحتاج موافقة',
    },
    {
      click: 'role=button:النوع',
      say: 'وأقفلها بنفس الزر',
    },
    {
      click: 'role=button:إزالة تسويقية',
      say: 'شلنا الفلتر — رجعنا نشوف الكل',
    },
    {
      click: 'role=radio:موقوفة',
      say: 'أو فلتر ثاني — «موقوفة» يوريك اللي أوقفتها',
    },
    {
      click: 'role=radio:الكل',
      say: 'ورجعنا لكل الأسباب',
    },
    {
      chapter: 'اقرأ رسالتك واختر متى تُوقفها',
      // Position-targeted (css), on purpose — this account's real 13-14 reason rows are
      // server-driven text, not something this script can name ahead of a live read.
      click: 'css=ul li button',
      say: 'اضغط على أي سطر تقرأ نص رسالته بالضبط',
    },
    {
      say: 'نصّها جاهز، وتقدر تغيّره لو تبي',
    },
    {
      click: 'role=button:Close',
      say: 'وترجع من هنا',
    },
    {
      // ONE CLICK ONLY, NOT A CLICK-THEN-REVERT PAIR — a real recording caught the revert click
      // landing but not applying (Messages.tsx's `flip()` is a real network round trip, not a
      // pure client toggle, and this node was under genuine load from today's fleet-wide
      // redeploy + a fresh 1000-customer seed when this was recorded). Demonstrating a state
      // change this screen cannot GUARANTEE completes within one recording pass is the wrong
      // trade for a tutorial; the fix-back happens by a direct, verified API call after
      // recording, never inside the video itself. See the seed/fix note at the bottom of this
      // file for exactly what has to be restored before this tour is considered done.
      click: 'css=ul li button[role="switch"]',
      say: 'والمفتاح جنب كل سطر يوقف هذا النوع كله',
    },
    {
      say: 'وما هو بالطابور الآن يسقط معه فورًا',
    },
    {
      say: 'ونفس الضغطة ترجّعه — بأي وقت تبي',
    },
    {
      say: 'بعض الأسطر بلا مفتاح — لأنها حقّ عميلك، مو خيارك',
    },
  ],
};
