"""Static labels for the two branded Word/PDF exports (`procedure_checklist_render.py`,
`staff_performance_render.py`) — the document's OWN chrome (title, column headers, warnings),
never a shop's own data.

WHY THIS IS A SEPARATE, HAND-WRITTEN DICTIONARY FROM THE SHOP-CONTENT PIPELINE
(`core/translations.py`). That pipeline exists for text an OWNER TYPES — unbounded, per-tenant,
unknown until it happens, which is why it is hashed, queued, and translated by a worker. These
dozen-odd strings are the OPPOSITE: fixed by us, identical for every tenant, and known in full
today. Routing them through a hash/queue/worker for a value that never changes would be the same
mistake `no-placeholder-drift` warns against in reverse — real, unnecessary infrastructure for a
value a person can just write once. Translated by hand here; a new export label added later is
added to all six rows in the same edit, the same discipline `operator-i18n` coverage already
enforces on the console side.

`OperatorLocale` — SAME SIX CODES ('ar','en','ur','ha','fil','bn') AS `operator-i18n.tsx`'s own
type, deliberately, so a `locale` value that is valid in the console is valid here unchanged.
"""
from __future__ import annotations

RTL_LOCALES: frozenset[str] = frozenset({"ar", "ur"})


def is_rtl(locale: str) -> bool:
    return locale in RTL_LOCALES


_LABELS: dict[str, dict[str, str]] = {
    "ar": {
        "checklist.eyebrow": "بطاقة إجراءات الخدمة",
        "checklist.combined_note": "قائمة موحّدة لـ{n} خدمات — كل إجراء مشترك مذكور مرة واحدة فقط.",
        "checklist.empty": "لا توجد إجراءات مسجَّلة لهذه الخدمة بعد.",
        "checklist.truncated": "⚠ هذه البطاقة تعرض أعلى {n} إجراءً فقط من أصل {m}.",
        "checklist.shared_with": "↳ مشتركة مع: ",
        "checklist.critical_tag": "  ⚠ خطوة حرجة",
        "generated_at": "أُنشئ بتاريخ: ",
        "performance.title": "تقرير أداء الموظفين",
        "performance.tenant_id": "معرّف المنشأة (UUID): ",
        "performance.empty": "لا توجد بيانات أداء لهذه الفترة.",
        "performance.truncated": "⚠ هذا التقرير يعرض أعلى {n} موظفاً فقط من أصل {m} — "
                                 "رتّب حسب الفرع لتضييق النطاق.",
        "performance.col.operator": "الموظف",
        "performance.col.visits": "الزيارات",
        "performance.col.ratings": "التقييمات",
        "performance.col.avg_rating": "متوسط التقييم",
        "performance.col.no_show_rate": "نسبة عدم الحضور",
    },
    "en": {
        "checklist.eyebrow": "Service Procedure Card",
        "checklist.combined_note": "Combined list for {n} services — each shared step listed once only.",
        "checklist.empty": "No procedures recorded for this service yet.",
        "checklist.truncated": "⚠ This card shows the top {n} steps only, out of {m}.",
        "checklist.shared_with": "↳ Shared with: ",
        "checklist.critical_tag": "  ⚠ Critical step",
        "generated_at": "Generated: ",
        "performance.title": "Staff Performance Report",
        "performance.tenant_id": "Establishment ID (UUID): ",
        "performance.empty": "No performance data for this period.",
        "performance.truncated": "⚠ This report shows the top {n} staff only, out of {m} — "
                                 "filter by branch to narrow it.",
        "performance.col.operator": "Staff",
        "performance.col.visits": "Visits",
        "performance.col.ratings": "Ratings",
        "performance.col.avg_rating": "Average rating",
        "performance.col.no_show_rate": "No-show rate",
    },
    "ur": {
        "checklist.eyebrow": "سروس پروسیجر کارڈ",
        "checklist.combined_note": "{n} سروسز کی مشترکہ فہرست — ہر مشترکہ مرحلہ صرف ایک بار درج ہے۔",
        "checklist.empty": "اس سروس کے لیے ابھی تک کوئی طریقہ کار درج نہیں ہے۔",
        "checklist.truncated": "⚠ یہ کارڈ صرف {m} میں سے سب سے اوپر کے {n} مراحل دکھاتا ہے۔",
        "checklist.shared_with": "↳ مشترکہ ساتھ: ",
        "checklist.critical_tag": "  ⚠ اہم مرحلہ",
        "generated_at": "تیار کردہ: ",
        "performance.title": "عملے کی کارکردگی کی رپورٹ",
        "performance.tenant_id": "ادارے کی شناخت (UUID): ",
        "performance.empty": "اس مدت کے لیے کوئی کارکردگی کا ڈیٹا موجود نہیں۔",
        "performance.truncated": "⚠ یہ رپورٹ صرف {m} میں سے سب سے اوپر کے {n} عملے دکھاتی ہے — "
                                 "شاخ کے ذریعے فلٹر کریں۔",
        "performance.col.operator": "عملہ",
        "performance.col.visits": "وزٹس",
        "performance.col.ratings": "درجہ بندیاں",
        "performance.col.avg_rating": "اوسط درجہ بندی",
        "performance.col.no_show_rate": "غیر حاضری کی شرح",
    },
    "ha": {
        "checklist.eyebrow": "Katin Tsarin Aiki",
        "checklist.combined_note": "Jerin haɗaɗɗen sabis {n} — kowane matakin da aka raba an "
                                   "lissafa shi sau ɗaya kawai.",
        "checklist.empty": "Babu wani tsari da aka rubuta don wannan sabis tukuna.",
        "checklist.truncated": "⚠ Wannan katin yana nuna manyan matakai {n} kawai daga cikin {m}.",
        "checklist.shared_with": "↳ An raba tare da: ",
        "checklist.critical_tag": "  ⚠ Muhimmin mataki",
        "generated_at": "An ƙirƙira: ",
        "performance.title": "Rahoton Ayyukan Ma'aikata",
        "performance.tenant_id": "Lambar Kamfani (UUID): ",
        "performance.empty": "Babu bayanan aiki don wannan lokacin.",
        "performance.truncated": "⚠ Wannan rahoto yana nuna manyan ma'aikata {n} kawai daga cikin "
                                 "{m} — tace ta reshe don rage shi.",
        "performance.col.operator": "Ma'aikaci",
        "performance.col.visits": "Ziyara",
        "performance.col.ratings": "Kimantawa",
        "performance.col.avg_rating": "Matsakaicin kima",
        "performance.col.no_show_rate": "Adadin rashin zuwa",
    },
    "fil": {
        "checklist.eyebrow": "Kard ng Pamamaraan ng Serbisyo",
        "checklist.combined_note": "Pinagsamang listahan para sa {n} serbisyo — bawat sabay na "
                                   "hakbang ay nakalista nang minsan lamang.",
        "checklist.empty": "Wala pang naitalang pamamaraan para sa serbisyong ito.",
        "checklist.truncated": "⚠ Ang kard na ito ay nagpapakita lamang ng nangungunang {n} "
                               "hakbang mula sa {m}.",
        "checklist.shared_with": "↳ Kasama sa: ",
        "checklist.critical_tag": "  ⚠ Mahalagang hakbang",
        "generated_at": "Ginawa noong: ",
        "performance.title": "Ulat ng Pagganap ng Kawani",
        "performance.tenant_id": "ID ng Establisimyento (UUID): ",
        "performance.empty": "Walang datos ng pagganap para sa panahong ito.",
        "performance.truncated": "⚠ Ang ulat na ito ay nagpapakita lamang ng nangungunang {n} "
                                 "kawani mula sa {m} — i-filter ayon sa sangay.",
        "performance.col.operator": "Kawani",
        "performance.col.visits": "Mga Bisita",
        "performance.col.ratings": "Mga Rating",
        "performance.col.avg_rating": "Average na Rating",
        "performance.col.no_show_rate": "Rate ng Hindi Pagdating",
    },
    "bn": {
        "checklist.eyebrow": "সেবা পদ্ধতি কার্ড",
        "checklist.combined_note": "{n} সেবার সম্মিলিত তালিকা — প্রতিটি ভাগ করা ধাপ কেবল একবার তালিকাভুক্ত।",
        "checklist.empty": "এই সেবার জন্য এখনো কোনো পদ্ধতি রেকর্ড করা হয়নি।",
        "checklist.truncated": "⚠ এই কার্ডে {m} এর মধ্যে শুধু শীর্ষ {n}টি ধাপ দেখানো হয়েছে।",
        "checklist.shared_with": "↳ যাদের সাথে ভাগ করা: ",
        "checklist.critical_tag": "  ⚠ গুরুত্বপূর্ণ ধাপ",
        "generated_at": "তৈরি করা হয়েছে: ",
        "performance.title": "কর্মী কার্যক্ষমতা প্রতিবেদন",
        "performance.tenant_id": "প্রতিষ্ঠান আইডি (UUID): ",
        "performance.empty": "এই সময়ের জন্য কোনো কার্যক্ষমতার তথ্য নেই।",
        "performance.truncated": "⚠ এই প্রতিবেদনে {m} এর মধ্যে শুধু শীর্ষ {n} জন কর্মী দেখানো হয়েছে — "
                                 "শাখা অনুযায়ী ফিল্টার করুন।",
        "performance.col.operator": "কর্মী",
        "performance.col.visits": "ভিজিট",
        "performance.col.ratings": "রেটিং",
        "performance.col.avg_rating": "গড় রেটিং",
        "performance.col.no_show_rate": "অনুপস্থিতির হার",
    },
}


def label(locale: str, key: str, **fmt: object) -> str:
    """One export label, in `locale` — Arabic when `locale` is unknown (never a KeyError, same
    "honest fallback" posture `core/translations.py::resolve` already gives the shop's own
    content, so a bad/missing locale degrades a document, never breaks its generation)."""
    row = _LABELS.get(locale) or _LABELS["ar"]
    text = row.get(key) or _LABELS["ar"].get(key, "")
    return text.format(**fmt) if fmt else text
