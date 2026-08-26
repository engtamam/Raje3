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
      say: 'منصّتك تراسل عملاءك نيابةً عنك',
    },
    {
      say: 'بلا أن تكتب رسالة واحدة بنفسك',
    },
    {
      click: 'role=button:فتح القائمة',
      say: 'ومن «رسائلي» تتابع كل هذا التواصل بنظرة واحدة',
    },
    {
      click: 'role=link:رسائلي',
      say: 'هنا مركز التواصل الكامل مع عملائك',
    },
    {
      say: 'وأول شيء تراه فوق — بطاقة تطمئنك',
    },
    {
      say: 'هل الإرسال يعمل فعلاً',
    },
    {
      click: 'text=خرجت اليوم',
      say: 'كم رسالة خرجت فعليًا اليوم',
    },
    {
      click: 'text=بانتظار الخروج',
      say: 'وكم لا يزال بالطابور — يخرج تلقائيًا بوقته المناسب',
    },
    {
      click: 'text=تعيد المحاولة',
      say: 'ولو رسالة تعثّرت، المنصّة تعيد المحاولة تلقائيًا',
    },
    {
      say: 'فلا تضيع رسالة أبداً',
    },
    {
      say: 'ولو ربطت واتساب، ترى هنا سقفك اليومي',
    },
    {
      say: 'وهذا حدّ تفرضه شركة ميتا المالكة لواتساب نفسها',
    },
    {
      say: 'وليس حدّاً وضعته منصّتنا',
    },
    {
      chapter: 'تواصل يعمل من نفسه',
      say: 'وتحت هذي البطاقة، كل الأسباب',
    },
    {
      say: 'اللي تجعل المنصّة ترسل باسمك',
    },
    {
      say: 'تلقائيًا',
    },
    {
      say: 'أول جملة تخبرك كم سبب فعّال عندك الآن',
    },
    {
      say: 'ثلاثة أنواع مبنية بذكاء: خدمية، وشخصية تخصّ عميلك',
    },
    {
      say: 'هو نفسه',
    },
    {
      say: 'وتسويقية — وهذي وحدها تحترم موافقة عميلك',
    },
    {
      say: 'المسبقة',
    },
    {
      click: 'role=button:النوع',
      say: 'وفلتر «النوع» يمنحك تحكماً دقيقاً',
    },
    {
      say: 'ترى نوعاً معيّناً فقط',
    },
    {
      click: 'role=option:تسويقية',
      say: 'اضغط «تسويقية» ترى بالضبط',
    },
    {
      say: 'اللي يحترم هذي الموافقة',
    },
    {
      click: 'role=button:النوع',
      say: 'وأغلقها بنفس الزر',
    },
    {
      click: 'role=button:إزالة تسويقية',
      say: 'أزلنا الفلتر — ورجعنا نرى كل أسبابك',
    },
    {
      click: 'role=radio:موقوفة',
      say: 'أو فلتر ثانٍ يُظهر لك بالضبط اللي أوقفته أنت',
    },
    {
      click: 'role=radio:الكل',
      say: 'ورجعنا لكل الأسباب دفعة واحدة',
    },
    {
      chapter: 'تحكّم كامل بكل رسالة',
      // Position-targeted (css), on purpose — this account's real 13-14 reason rows are
      // server-driven text, not something this script can name ahead of a live read.
      click: 'css=ul li button',
      say: 'واضغط على أي سطر تقرأ نص رسالته الفعلي بالضبط',
    },
    {
      say: 'نصّها جاهز مسبقاً، وتقدر تخصّصه بحرية لو تريد',
    },
    {
      click: 'role=button:Close',
      say: 'وترجع من هنا',
    },
    {
      // ONE CLICK ONLY, NOT A CLICK-THEN-REVERT PAIR — see the header note on why.
      click: 'css=ul li button[role="switch"]',
      say: 'والمفتاح جنب كل سطر يمنحك إيقاف هذا النوع كله',
    },
    {
      say: 'بضغطة واحدة',
    },
    {
      say: 'وما هو بالطابور الآن يسقط معه فورًا',
    },
    {
      say: 'تحكم لحظي حقيقي',
    },
    {
      say: 'ونفس الضغطة تُرجعه — بأي وقت تريد',
    },
    {
      say: 'وبعض الأسطر بلا مفتاح — لأنها حقّ عميلك',
    },
    {
      say: 'وليست خيارك أنت',
    },
    {
      chapter: 'بانتظار الخروج',
      click: 'role=radio:بانتظار الخروج',
      say: 'ونكمل من نفس القصة — نرى الآن اللي لا يزال بالطابور',
    },
    {
      say: 'كل رسالة هنا مربوطة بشخص فعلي، لا بنوعها فقط',
    },
    {
      say: 'حتى تقدر توقف رسالة شخص معيّن بذاته، بدقة',
    },
    {
      // Cancel one scheduled row — position-targeted (css), on purpose: the row belongs to a
      // real, live customer this script cannot name ahead of a live read. Real, persistent
      // side effect — accepted per the header note, never undone inside the video.
      click: 'css=ul li button',
      say: 'اضغط «أوقفها» فتوقف رسالة هذا الشخص هو فقط',
    },
    {
      say: 'وزيارته القادمة تجدول له رسالة جديدة تلقائيًا',
    },
    {
      say: 'بلا أي تدخل منك',
    },
    {
      chapter: 'السجل — كل رسالة وسببها',
      click: 'role=radio:السجل',
      say: 'وأخيراً «السجل» — كل رسالة أرسلتها المنصّة',
    },
    {
      say: 'مع سببها بوضوح',
    },
    {
      say: 'وأي رسالة امتنعت، سببها مكتوب أمامك مباشرة',
    },
    {
      click: 'role=radio:لم تخرج',
      say: 'اضغط «لم تخرج» ترى فقط اللي لم تصل',
    },
    {
      say: 'أسباب شائعة: خارج وقت الإرسال المناسب',
    },
    {
      say: 'أو بلغ سقفه اليومي',
    },
    {
      click: 'role=radio:الكل',
      say: 'ورجعنا لكل السجل دفعة واحدة',
    },
    {
      say: 'وكل رسالة خرجت فعلاً — تجد حالتها بالضبط',
    },
    {
      say: '«خرجت» لا تعني «وصلت» — واتساب نفسه أحيانًا يتأخر',
    },
    {
      say: 'وهذا صادق معك',
    },
    {
      say: 'تواصل كامل، تلقائي، وتحت سيطرتك بأي لحظة',
    },
    {
      say: 'هذا رسائلي',
    },
  ],
};
