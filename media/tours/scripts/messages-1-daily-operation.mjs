/**
 * «رسائلي» — MERGED 1 OF 2: understanding + daily operation. Was three separate clips
 * (messages-1-today-reasons, messages-2-queue-log, each its own recording/verification pass);
 * merged into one continuous journey per the same decision already made for تسجيل الزيارة and
 * خدماتي ومنتجاتي — one story from health check → why a message goes out at all → what's still
 * queued → what already happened, not three disconnected marketing beats. messages-1/2's own
 * files are deleted; every real fact and selector below is carried over from them unchanged,
 * only the voice and the connective tissue between beats are new.
 *
 * Read Messages.tsx, MessagePreview.tsx, rj-ui/Segmented.tsx, rj-ui/FilterMenu.tsx and
 * rj-ui/Toggle.tsx directly before writing a single selector — this project's own standing rule.
 * Beyond the frontend, the real backend logic behind this tab (services/reminders'
 * gate.py/reasons.py) was studied before either original script was written — not because the
 * video explains any of that, but so every caption said here is something verified true.
 *
 * THE DEMO ACCOUNT'S REAL STATE, CONFIRMED NOT ASSUMED: no WhatsApp number is linked (no real
 * Meta credentials on a demo account), so `ceiling.known` is false and the «سقف واتساب» line
 * never renders — narrated by voice only, never targeted as a click. `today.blocked` is empty,
 * so the three-number row renders, not the red banner. A live read of `reminders.list_schedule`
 * on this account showed 200 pending rows — every seeded visit schedules a real follow-up behind
 * it, so this account genuinely has rows to show, never an empty state.
 *
 * TWO REAL, PERSISTENT SIDE EFFECTS, BOTH ACCEPTED, NEITHER UNDONE INSIDE THE VIDEO:
 *   (1) the toggle demo turns the account's first reason off and does not turn it back on inside
 *       the recording — Messages.tsx's `flip()` is a real network round trip, not a pure client
 *       toggle, so a click-then-revert pair risked the revert landing but not applying under
 *       load. Fixed back by the verified API call below, run after every recording.
 *   (2) the cancel-one-row demo in «بانتظار الخروج» has no "undo" action of its own on this
 *       platform (cancel stops the message, not the rule — nothing recreates the exact row). This
 *       costs one queued message out of ~200 on a demo account, never a real customer, and a full
 *       reseed naturally repopulates the queue anyway. No action required for this one.
 *
 * FIX-BACK FOR (1), RUN AFTER EVERY RECORDING OF THIS SCRIPT:
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
  id: 'messages-1-daily-operation',
  title: 'رسائلي — تواصل تلقائي وذكي مع عملائك',
  section: 'رسائلي', // nav.ts's own label
  useDemoSession: true,
  preload: true,
  // A live check found the click sound played is wrong/inaccurate — off until the actual
  // sfx asset/mix itself is fixed (media/lib/sfx/click.ogg or media/lib/ffmpeg.mjs::mixSfx).
  sfx: false,
  steps: [
    {
      goto: '/',
      chapter: 'من يراسل عملاءك، ومتى؟',
      say: 'منصّتك تراسل عملاءك نيابةً عنك — بدون ما تكتب رسالة وحدة',
    },
    {
      click: 'role=button:فتح القائمة',
      say: 'من «رسائلي» تتابع كل هذا التواصل بنظرة وحدة',
    },
    {
      click: 'role=link:رسائلي',
      say: 'هنا مركز التواصل الكامل مع عملائك',
    },
    {
      say: 'أول شي فوق — بطاقة تطمئنك: هل الإرسال شغّال فعلاً',
    },
    {
      click: 'text=خرجت اليوم',
      say: 'كم رسالة خرجت فعليًا اليوم',
    },
    {
      click: 'text=بانتظار الخروج',
      say: 'وكم لسه بالطابور — بتخرج تلقائيًا بوقتها المناسب',
    },
    {
      click: 'text=تعيد المحاولة',
      say: 'ولو رسالة تعثّرت، المنصّة تعيد المحاولة تلقائيًا — ما تضيع رسالة',
    },
    {
      say: 'ولو ربطت واتساب، تشوف هنا سقفك اليومي مع ميتا لحظة بلحظة',
    },
    {
      chapter: 'تواصل يشتغل من نفسه',
      say: 'تحت — كل الأسباب اللي تخلي المنصّة ترسل باسمك تلقائيًا',
    },
    {
      say: 'أول جملة تقولك كم سبب فعّال عندك الآن',
    },
    {
      say: 'ثلاث أنواع مبنية بذكاء: خدمية، وشخصية تخصّ عميلك هو',
    },
    {
      say: 'وتسويقية — وهذي وحدها تحترم موافقة عميلك المسبقة',
    },
    {
      click: 'role=button:النوع',
      say: 'فلتر «النوع» يعطيك تحكماً دقيقاً — تشوف نوع معيّن بس',
    },
    {
      click: 'role=option:تسويقية',
      say: 'اضغط «تسويقية» تشوف بالضبط اللي يحترم هذي الموافقة',
    },
    {
      click: 'role=button:النوع',
      say: 'وأقفلها بنفس الزر',
    },
    {
      click: 'role=button:إزالة تسويقية',
      say: 'شلنا الفلتر — رجعنا نشوف كل أسبابك',
    },
    {
      click: 'role=radio:موقوفة',
      say: 'أو فلتر ثاني يوريك بالضبط اللي أوقفته أنت',
    },
    {
      click: 'role=radio:الكل',
      say: 'ورجعنا لكل الأسباب دفعة وحدة',
    },
    {
      chapter: 'تحكّم كامل بكل رسالة',
      // Position-targeted (css), on purpose — this account's real 13-14 reason rows are
      // server-driven text, not something this script can name ahead of a live read.
      click: 'css=ul li button',
      say: 'اضغط على أي سطر تقرأ نص رسالته الفعلي بالضبط',
    },
    {
      say: 'نصّها جاهز مسبقاً، وتقدر تخصّصه براحتك لو تبي',
    },
    {
      click: 'role=button:Close',
      say: 'وترجع من هنا',
    },
    {
      // ONE CLICK ONLY, NOT A CLICK-THEN-REVERT PAIR — see the header note on why.
      click: 'css=ul li button[role="switch"]',
      say: 'والمفتاح جنب كل سطر يمنحك إيقاف هذا النوع كله بضغطة وحدة',
    },
    {
      say: 'وما هو بالطابور الآن يسقط معه فورًا — تحكم لحظي حقيقي',
    },
    {
      say: 'ونفس الضغطة ترجّعه — بأي وقت تبي',
    },
    {
      say: 'وبعض الأسطر بلا مفتاح — لأنها حقّ عميلك، مو خيارك أنت',
    },
    {
      chapter: 'بانتظار الخروج',
      click: 'role=radio:بانتظار الخروج',
      say: 'نكمل من نفس القصة — نشوف الآن اللي لسه بالطابور',
    },
    {
      say: 'كل رسالة هنا مربوطة بشخص فعلي، لا بنوعها بس',
    },
    {
      say: 'عشان تقدر توقف رسالة شخص معيّن بذاته، بدقة',
    },
    {
      // Cancel one scheduled row — position-targeted (css), on purpose: the row belongs to a
      // real, live customer this script cannot name ahead of a live read. Real, persistent
      // side effect — accepted per the header note, never undone inside the video.
      click: 'css=ul li button',
      say: 'اضغط «أوقفها» يوقف رسالة هذا الشخص هو فقط',
    },
    {
      say: 'وزيارته الجاية تجدول له رسالة جديدة تلقائيًا — بلا أي تدخل منك',
    },
    {
      chapter: 'السجل — كل رسالة وسببها',
      click: 'role=radio:السجل',
      say: 'وأخيراً «السجل» — كل رسالة أرسلتها المنصّة، مع سببها بوضوح',
    },
    {
      say: 'أي رسالة امتنعت، سببها مكتوب أمامك مباشرة',
    },
    {
      click: 'role=radio:لم تخرج',
      say: 'اضغط «لم تخرج» تشوف بس اللي ما وصلت',
    },
    {
      say: 'أسباب شائعة: خارج وقت الإرسال المناسب، أو بلغ سقفه اليومي',
    },
    {
      click: 'role=radio:الكل',
      say: 'ورجعنا لكل السجل دفعة وحدة',
    },
    {
      say: 'وكل رسالة خرجت فعلاً — تلقى حالتها بالضبط',
    },
    {
      say: '«خرجت» لا تعني «وصلت» — واتساب نفسه أحيانًا يتأخر، وهذا صادق معك',
    },
    {
      say: 'تواصل كامل، تلقائي، وتحت سيطرتك بأي لحظة — هذا رسائلي',
    },
  ],
};
