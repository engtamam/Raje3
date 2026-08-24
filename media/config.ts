/**
 * ثوابت كل مقاطعنا — مكانٌ واحد يُغيَّر فيه الشكل والإيقاع، فتتغيّر المكتبة كلها.
 *
 * لماذا ملفٌّ لا اتفاقٌ شفهي: بعد عشرين مقطعاً تصير المقدّمة ثانيتين هنا وثلاثاً هناك،
 * والخط مختلفاً في مقطعٍ صُوّر متأخراً — والقناة تبدو مجموعةَ أشخاص لا منتَجاً واحداً.
 *
 * والمدّة ليست رقماً ثابتاً هنا، وهذا مقصود: المقطع ينتهي حين ينتهي الموقف. الأرقام
 * أدناه سقوفٌ تُنذر، لا أهدافٌ تُملأ — مقطعٌ من 18 ثانية يشرح موقفاً كاملاً ناجحٌ تماماً.
 */

export const VIDEO = {
  width: 1920,
  height: 1080,
  fps: 30,
  // الجوال هو الشاشة الحقيقية لعميلنا، فنصوّر عرضاً يقارب جهازه ثم نضعه داخل إطار.
  deviceWidth: 430,
  deviceHeight: 932,
} as const;

export const PACE = {
  /** قبل أول نقرة: يقرأ المشاهد الشاشة أولاً. */
  settleMs: 900,
  /** بين خطوةٍ وأخرى — لا نسابق إصبعه. */
  betweenStepsMs: 700,
  /** بعد فعلٍ يغيّر الشاشة، ليرى النتيجة قبل أن ننتقل. */
  afterActionMs: 1200,
  /** بطء الكتابة في الحقول: أسرع من إنسان، أبطأ من آلة. */
  typeDelayMs: 60,
} as const;

export const LENGTH = {
  /** موقفٌ واحد بسيط — نقرة أو نقرتان. */
  shortSeconds: 30,
  /** موقفٌ يعبر شاشتين أو فيه قرار. */
  mediumSeconds: 60,
  /**
   * السقف. ما تجاوزه ليس مقطعاً طويلاً — هو مقطعان لم نفصلهما بعد، وهذا ما يجعل
   * المشاهد يسحب الشريط بحثاً عن حاجته بدل أن يجدها.
   */
  maxSeconds: 90,
} as const;

export const BRAND = {
  introSeconds: 2,
  outroSeconds: 3,
  /** ذهبنا نفسه، من متغيّرات الواجهة — لا لونٌ منسوخ باليد. */
  accent: '#B08A3E',
  ink: '#1B2A3A',
  paper: '#F5F1E9',
  fontFamily: 'IBM Plex Sans Arabic',
} as const;

export const CAPTION = {
  /** يُقرأ ولا يُلاحَق: سطران على الأكثر. */
  maxLines: 2,
  // NO maxCharsPerLine HERE. It was a character-count guess calibrated against the ad's
  // landscape frame (1920px) and produced five lines instead of two the first time a real tour
  // ran at the portrait tour frame's actual width (430px) -- 40 Arabic characters don't fit 82%
  // of that at any legible size. tours/lib/overlay.mjs's say() measures the caption bar's real
  // rendered width in the browser itself instead, so it stays correct at whatever frame width
  // either VIDEO.deviceWidth or VIDEO.width ends up being.
  /** أقل زمنٍ يبقى فيه السطر مهما قصر. */
  minMs: 1200,
  /** زمن القراءة: نحو 14 حرفاً في الثانية للعربية. */
  charsPerSecond: 14,
  positionFromBottom: 0.12,
} as const;

export const VOICE = {
  /** يُفعَّل يوم يصل المفتاح — والنصّ مكتوبٌ في الرحلات من اليوم. */
  enabled: false,
  provider: 'azure',
  name: 'ar-SA-ZariyahNeural',
  /** أبطأ قليلاً من الافتراضي: شرحٌ لا نشرة أخبار. */
  rate: '-6%',
} as const;
