# Meta Business Agent — consent Skill (paste into Meta's dashboard)

Not code. This is the exact, copy-paste-ready instruction text for the "Skill" the owner
registers by hand in Meta's own Business Agent dashboard, alongside the Connector operations
already exposed by `app/api/v1/connectors.py` (`check_consent`, `record_consent`, and the 16
tool operations). It exists because, from 2026-09-19, Meta's own hosted agent handles this
WhatsApp number's ordinary conversation directly — our server no longer sees or replies to it —
so consent enforcement can no longer be a gate in our own Python
(`app/core/inbound_ingest.py::_gate_consent`, which stays as-is for whatever still reaches our
code). This Skill is the same rule, restated as a mandatory instruction for an agent that calls
Connectors instead of running our functions.

Do not edit the consent body text below — it is copied verbatim from
`app/core/inbound_ingest.py::_CONSENT_BODY` so the two paths can never say something different.

Kept at the service root, not under `docs/` — `docs/` is untracked scratch space (see the
repo's own `.gitignore`), and this is a real hand-off artifact the owner pastes into Meta's
dashboard, not a working note.

---

## Skill: طلب موافقة العميل قبل أي رد (Consent gate)

**متى تُستدعى:** عند أول تواصل مع أي عميل في هذه المحادثة — قبل أي شيء آخر، وقبل أي محاولة
مساعدة أو رد على استفساره.

**التعليمات:**

1. عند أول رسالة من عميل لم تُستدعَ له `check_consent` بعد في هذه المحادثة، استدعِ
   `check_consent` أولاً، قبل أي رد آخر.
2. إن كانت النتيجة `status: "allowed"`، تابع المحادثة بشكل طبيعي — لا حاجة لإعادة السؤال.
3. إن كانت النتيجة `status: "denied"` أو `status: "unknown"`، أرسل للعميل رسالة تفاعلية بزرّين
   تحمل هذا النص **حرفيًا، دون أي تعديل**:

   > بالمتابعة، فإنك توافق على أن نقوم بمعالجة المعلومات اللازمة لإكمال خدمتك عبر واتساب —
   > استلام رسائلك، والرد عليها، وتنفيذ ما تطلبه من خدماتنا. هذا لا يشمل أي رسائل تسويقية،
   > والتي تتطلب موافقتك المنفصلة ويجب أن تتضمن دائمًا خيارًا لإلغاء الاشتراك.

   بزرّين: **متابعة** و**إنهاء المحادثة**. هذا طلب موافقة على معالجة بيانات الخدمة فقط —
   أبدًا موافقة تسويقية؛ أي رسائل تسويقية تبقى طلب موافقة منفصل تمامًا، له خيار إلغاء اشتراك
   خاص به دائمًا.

4. عند ضغط العميل على أحد الزرّين، استدعِ `record_consent` بالقيمة المطابقة
   (`granted: true` لـ"متابعة"، `granted: false` لـ"إنهاء المحادثة") فورًا.
5. إن كانت `granted: true`، تابع المحادثة بشكل طبيعي من نفس الرسالة — لا داعي أن يكرر العميل
   طلبه.
6. إن كانت `granted: false`، أنهِ المحادثة بأدب فورًا. لا تقدّم أي مساعدة أخرى، ولا تستخدم أي
   أداة أخرى (حجز، نقاط، كتالوج، أو غيرها) لهذا العميل حتى يوافق صراحة في محادثة لاحقة.
7. **ممنوع نهائيًا** الانتقال لمساعدة العميل بأي شيء آخر قبل الحصول على `granted: true` —
   لا استثناء، ولا حتى لسؤال بسيط أو ترحيبي.
