/**
 * MessagePreview.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the screen itself. ur/ha/fil/bn were produced in this pass to unblock the mechanism end to end
 * — get a real operator reading his own language today rather than none at all — but they have
 * NOT been checked by a native speaker. Flagged explicitly rather than shipped silently: a wrong
 * word here is a worse failure than the Arabic fallback it replaces. Review before this reaches a
 * shop that actually has Urdu/Hausa/Filipino/Bengali-speaking staff on the floor.
 */
import { registerOperatorStrings } from '../operator-i18n';

registerOperatorStrings({
  ar: {
    'messagePreview.status.rejected': 'رفضها واتساب',
    'messagePreview.status.pendingReview': 'عند واتساب للمراجعة',
    'messagePreview.status.notSubmitted': 'لم تُرفَع بعد',
    'messagePreview.status.ready': 'جاهزة للإرسال',
    'messagePreview.status.awaitingApproval': 'بانتظار اعتماد واتساب',

    'messagePreview.tone.masculine': 'مذكر',
    'messagePreview.tone.feminine': 'مؤنث',

    'messagePreview.toneSaveError': 'تعذّر حفظ النبرة.',
    'messagePreview.saveError': 'تعذّر الحفظ.',
    'messagePreview.actionError': 'تعذّر التنفيذ.',
    'messagePreview.flowFetchError': 'تعذّر جلب شاشات الفلو.',
    'messagePreview.noFlowPermission': 'لا صلاحية لقراءة شاشات الفلو',

    'messagePreview.noPermission': 'لا يشمل دورك تحرير نصوص الرسائل.',
    'messagePreview.loadFailed': 'تعذّر عرض نصّ هذه الرسالة الآن — والخلل عندنا. حاول بعد قليل.',
    'messagePreview.empty.unread': 'تعذّرت قراءة صيغنا الآن — والخلل عندنا، لا عندك. حاول بعد قليل.',
    'messagePreview.empty.pending': 'نصّك مُرسَل إلى واتساب للمراجعة، وقد تستغرق ساعات. سنعلمك فور اعتماده.',
    'messagePreview.empty.none': 'لا توجد صيغة جاهزة لهذه الرسالة بعد — وهذا نقصٌ عندنا نعمل عليه.',

    'messagePreview.availableWordings': 'الصيغ المتاحة',
    'messagePreview.tapHint': 'اضغط الصيغة لتقرأ قالبها كما هو مكتوب، ومثالاً كما يصل عميلك.',
    'messagePreview.yourText': 'نصّك',
    'messagePreview.sendingNow': 'تُرسَل الآن',
    'messagePreview.templateAsWritten': 'القالب كما هو مكتوب',

    'messagePreview.previewOnWhatsapp': 'معاينة على واتساب',
    'messagePreview.thisIsSendingNote': 'هذه الصيغة هي ما يخرج باسمك لهذه الرسالة.',
    'messagePreview.useIt': 'استعملها',
    'messagePreview.backToOurs': 'العودة إلى صياغتنا',
    'messagePreview.makeMyTone': 'اجعلها نبرتي',
    'messagePreview.submitToWhatsapp': 'ارفعه إلى واتساب',
    'messagePreview.helpMe': 'ساعدوني',
    'messagePreview.requestReceived': 'طلبك وصلنا — نرد عليك هنا.',

    'messagePreview.footerChosen': 'نصّك هو ما يُرسَل لهذه الرسالة — والنبرة تحكم بقية رسائلك.',
    'messagePreview.footerTone': 'نبرتك تُطبَّق على كل رسائلك، لا على هذه وحدها.',

    'messagePreview.writeYourOwnPrompt': 'تبي صياغتك أنت؟ اكتبها ونرفعها لواتساب باسمك.',
    'messagePreview.writeYourText': 'اكتب نصّك',

    'messagePreview.cannotWriteNote': 'هذه الرسالة تُرسَل بصياغتنا — نصّها مرتبط بحقٍّ نظامي لعميلك.',

    'messagePreview.previewSubtitle': 'بالضبط ما يستلمه العميل — الفلو الحقيقي، لا نسخة مقلَّدة.',

    'messagePreview.savingEllipsis': 'يُحفظ…',
  },
  en: {
    'messagePreview.status.rejected': 'WhatsApp rejected it',
    'messagePreview.status.pendingReview': 'With WhatsApp for review',
    'messagePreview.status.notSubmitted': 'Not submitted yet',
    'messagePreview.status.ready': 'Ready to send',
    'messagePreview.status.awaitingApproval': 'Awaiting WhatsApp approval',

    'messagePreview.tone.masculine': 'Masculine',
    'messagePreview.tone.feminine': 'Feminine',

    'messagePreview.toneSaveError': "Couldn't save the tone.",
    'messagePreview.saveError': "Couldn't save.",
    'messagePreview.actionError': "Couldn't complete this.",
    'messagePreview.flowFetchError': "Couldn't fetch the Flow's screens.",
    'messagePreview.noFlowPermission': 'No permission to read Flow screens',

    'messagePreview.noPermission': "Your role doesn't include editing message wordings.",
    'messagePreview.loadFailed': "Couldn't display this message's text right now — the fault is ours. Try again shortly.",
    'messagePreview.empty.unread': "Couldn't read our wordings right now — the fault is ours, not yours. Try again shortly.",
    'messagePreview.empty.pending': 'Your text has been sent to WhatsApp for review, which can take hours. We\'ll let you know once it\'s approved.',
    'messagePreview.empty.none': "No ready wording exists for this message yet — a gap on our end we're working on.",

    'messagePreview.availableWordings': 'Available wordings',
    'messagePreview.tapHint': 'Tap a wording to read its template as written, and an example as your customer receives it.',
    'messagePreview.yourText': 'Your text',
    'messagePreview.sendingNow': 'Sending now',
    'messagePreview.templateAsWritten': 'The template as written',

    'messagePreview.previewOnWhatsapp': 'Preview on WhatsApp',
    'messagePreview.thisIsSendingNote': 'This is what actually goes out under your name for this message.',
    'messagePreview.useIt': 'Use it',
    'messagePreview.backToOurs': 'Back to our wording',
    'messagePreview.makeMyTone': 'Make it my tone',
    'messagePreview.submitToWhatsapp': 'Submit to WhatsApp',
    'messagePreview.helpMe': 'Help me',
    'messagePreview.requestReceived': "We've received your request — we'll reply here.",

    'messagePreview.footerChosen': 'Your text is what sends for this message — the tone governs the rest of your messages.',
    'messagePreview.footerTone': 'Your tone applies to all your messages, not this one alone.',

    'messagePreview.writeYourOwnPrompt': 'Want your own wording? Write it and we\'ll submit it to WhatsApp under your name.',
    'messagePreview.writeYourText': 'Write your text',

    'messagePreview.cannotWriteNote': "This message sends with our wording — its text is tied to a statutory right of your customer.",

    'messagePreview.previewSubtitle': 'Exactly what the customer receives — the real Flow, not an imitation.',

    'messagePreview.savingEllipsis': 'Saving…',
  },
  ur: {
    'messagePreview.status.rejected': 'واٹس ایپ نے مسترد کیا',
    'messagePreview.status.pendingReview': 'واٹس ایپ کے پاس جائزے کے لیے',
    'messagePreview.status.notSubmitted': 'ابھی جمع نہیں کیا گیا',
    'messagePreview.status.ready': 'بھیجنے کے لیے تیار',
    'messagePreview.status.awaitingApproval': 'واٹس ایپ کی منظوری کا منتظر',

    'messagePreview.tone.masculine': 'مذکر',
    'messagePreview.tone.feminine': 'مؤنث',

    'messagePreview.toneSaveError': 'لہجہ محفوظ نہیں ہو سکا۔',
    'messagePreview.saveError': 'محفوظ نہیں ہو سکا۔',
    'messagePreview.actionError': 'مکمل نہیں ہو سکا۔',
    'messagePreview.flowFetchError': 'فلو کی اسکرینیں حاصل نہیں ہو سکیں۔',
    'messagePreview.noFlowPermission': 'فلو اسکرینز پڑھنے کی اجازت نہیں',

    'messagePreview.noPermission': 'آپ کے کردار میں پیغامات کی تحریر میں ترمیم شامل نہیں۔',
    'messagePreview.loadFailed': 'اس پیغام کا متن ابھی نہیں دکھا سکے — یہ ہماری خرابی ہے۔ تھوڑی دیر بعد کوشش کریں۔',
    'messagePreview.empty.unread': 'ہماری تحریریں ابھی نہیں پڑھ سکے — یہ ہماری خرابی ہے، آپ کی نہیں۔ تھوڑی دیر بعد کوشش کریں۔',
    'messagePreview.empty.pending': 'آپ کا متن جائزے کے لیے واٹس ایپ کو بھیج دیا گیا ہے، جس میں گھنٹے لگ سکتے ہیں۔ منظوری ملتے ہی آپ کو بتائیں گے۔',
    'messagePreview.empty.none': 'اس پیغام کے لیے ابھی کوئی تیار تحریر موجود نہیں — یہ ہماری کمی ہے جس پر ہم کام کر رہے ہیں۔',

    'messagePreview.availableWordings': 'دستیاب تحریریں',
    'messagePreview.tapHint': 'اپنے قالب کو تحریر شدہ حالت میں اور گاہک تک پہنچنے والی مثال کے طور پر پڑھنے کے لیے تحریر پر دبائیں۔',
    'messagePreview.yourText': 'آپ کا متن',
    'messagePreview.sendingNow': 'ابھی بھیجا جا رہا ہے',
    'messagePreview.templateAsWritten': 'قالب جیسا لکھا گیا ہے',

    'messagePreview.previewOnWhatsapp': 'واٹس ایپ پر معائنہ',
    'messagePreview.thisIsSendingNote': 'اس پیغام کے لیے آپ کے نام سے یہی جاتا ہے۔',
    'messagePreview.useIt': 'اسے استعمال کریں',
    'messagePreview.backToOurs': 'ہماری تحریر پر واپس جائیں',
    'messagePreview.makeMyTone': 'اسے میرا لہجہ بنائیں',
    'messagePreview.submitToWhatsapp': 'واٹس ایپ کو جمع کروائیں',
    'messagePreview.helpMe': 'میری مدد کریں',
    'messagePreview.requestReceived': 'آپ کی درخواست موصول ہوئی — ہم یہاں جواب دیں گے۔',

    'messagePreview.footerChosen': 'آپ کا متن اس پیغام کے لیے بھیجا جاتا ہے — لہجہ آپ کے باقی پیغامات پر حکم کرتا ہے۔',
    'messagePreview.footerTone': 'آپ کا لہجہ آپ کے تمام پیغامات پر لاگو ہوتا ہے، صرف اس پر نہیں۔',

    'messagePreview.writeYourOwnPrompt': 'اپنی تحریر چاہتے ہیں؟ اسے لکھیں اور ہم اسے آپ کے نام سے واٹس ایپ کو جمع کروائیں گے۔',
    'messagePreview.writeYourText': 'اپنا متن لکھیں',

    'messagePreview.cannotWriteNote': 'یہ پیغام ہماری تحریر سے بھیجا جاتا ہے — اس کا متن آپ کے گاہک کے قانونی حق سے جڑا ہے۔',

    'messagePreview.previewSubtitle': 'بالکل وہی جو گاہک کو ملتا ہے — اصل فلو، کوئی نقل نہیں۔',

    'messagePreview.savingEllipsis': 'محفوظ ہو رہا ہے…',
  },
  ha: {
    'messagePreview.status.rejected': 'WhatsApp ya ƙi shi',
    'messagePreview.status.pendingReview': 'Yana wurin WhatsApp don dubawa',
    'messagePreview.status.notSubmitted': 'Ba a mika shi ba tukuna',
    'messagePreview.status.ready': 'Shirye don aikawa',
    'messagePreview.status.awaitingApproval': 'Ana jiran amincewar WhatsApp',

    'messagePreview.tone.masculine': 'Namiji',
    'messagePreview.tone.feminine': 'Mace',

    'messagePreview.toneSaveError': 'Ba a iya ajiye sautin ba.',
    'messagePreview.saveError': 'Ba a iya ajiyewa ba.',
    'messagePreview.actionError': 'Ba a iya kammalawa ba.',
    'messagePreview.flowFetchError': 'Ba a iya samun allon Flow ba.',
    'messagePreview.noFlowPermission': 'Babu izinin karanta allon Flow',

    'messagePreview.noPermission': "Matsayinka ba ya haɗa da gyara rubutun saƙonni.",
    'messagePreview.loadFailed': 'Ba a iya nuna rubutun wannan saƙon yanzu ba — laifi namu ne. Sake gwadawa bayan ɗan lokaci.',
    'messagePreview.empty.unread': 'Ba a iya karanta rubutunmu yanzu ba — laifi namu ne, ba naka ba. Sake gwadawa bayan ɗan lokaci.',
    'messagePreview.empty.pending': 'An aika rubutunka zuwa WhatsApp don dubawa, wanda zai iya ɗaukar sa\'o\'i. Za mu sanar da kai da zarar an amince.',
    'messagePreview.empty.none': 'Babu rubutu a shirye don wannan saƙon tukuna — gibi ne namu da muke aiki a kai.',

    'messagePreview.availableWordings': 'Rubuce-rubucen da ke akwai',
    'messagePreview.tapHint': 'Danna rubutu don karanta samfurinsa yadda aka rubuta, da misali yadda yake isa ga abokin cinikinka.',
    'messagePreview.yourText': 'Rubutunka',
    'messagePreview.sendingNow': 'Ana aikawa yanzu',
    'messagePreview.templateAsWritten': 'Samfurin yadda aka rubuta',

    'messagePreview.previewOnWhatsapp': 'Duba a WhatsApp',
    'messagePreview.thisIsSendingNote': 'Wannan shine abin da ke fita da sunanka don wannan saƙon.',
    'messagePreview.useIt': 'Yi amfani da shi',
    'messagePreview.backToOurs': 'Koma zuwa rubutunmu',
    'messagePreview.makeMyTone': 'Sanya shi sautina',
    'messagePreview.submitToWhatsapp': 'Mika zuwa WhatsApp',
    'messagePreview.helpMe': 'Taimaka mini',
    'messagePreview.requestReceived': 'Mun karɓi buƙatarka — za mu amsa a nan.',

    'messagePreview.footerChosen': 'Rubutunka shine ake aikawa don wannan saƙon — sautin yana mulkin sauran saƙonninka.',
    'messagePreview.footerTone': 'Sautinka yana aiki a kan duk saƙonninka, ba wannan kaɗai ba.',

    'messagePreview.writeYourOwnPrompt': 'Kana son rubutunka? Rubuta shi kuma za mu mika shi zuwa WhatsApp da sunanka.',
    'messagePreview.writeYourText': 'Rubuta rubutunka',

    'messagePreview.cannotWriteNote': 'Ana aika wannan saƙon da rubutunmu — rubutunsa yana da alaƙa da haƙƙin doka na abokin cinikinka.',

    'messagePreview.previewSubtitle': 'Ainihin abin da abokin ciniki ke karɓa — Flow na gaskiya, ba kwafi ba.',

    'messagePreview.savingEllipsis': 'Ana ajiyewa…',
  },
  fil: {
    'messagePreview.status.rejected': 'Tinanggihan ng WhatsApp',
    'messagePreview.status.pendingReview': 'Nasa WhatsApp para sa review',
    'messagePreview.status.notSubmitted': 'Hindi pa naisumite',
    'messagePreview.status.ready': 'Handa nang ipadala',
    'messagePreview.status.awaitingApproval': 'Hinihintay ang pag-apruba ng WhatsApp',

    'messagePreview.tone.masculine': 'Panlalaki',
    'messagePreview.tone.feminine': 'Pambabae',

    'messagePreview.toneSaveError': 'Hindi ma-save ang tono.',
    'messagePreview.saveError': 'Hindi ma-save.',
    'messagePreview.actionError': 'Hindi makumpleto.',
    'messagePreview.flowFetchError': 'Hindi makuha ang mga screen ng Flow.',
    'messagePreview.noFlowPermission': 'Walang pahintulot na basahin ang mga screen ng Flow',

    'messagePreview.noPermission': 'Hindi kasama sa role mo ang pag-edit ng teksto ng mensahe.',
    'messagePreview.loadFailed': "Hindi maipakita ang teksto ng mensaheng ito ngayon — kasalanan namin ito. Subukan ulit mamaya.",
    'messagePreview.empty.unread': 'Hindi mabasa ang mga wording namin ngayon — kasalanan namin ito, hindi sa iyo. Subukan ulit mamaya.',
    'messagePreview.empty.pending': 'Naipadala na ang teksto mo sa WhatsApp para sa review, na maaaring tumagal ng ilang oras. Sasabihin namin sa iyo pagka-apruba.',
    'messagePreview.empty.none': 'Wala pang handang wording para sa mensaheng ito — isang kakulangan namin na aming ginagawan ng paraan.',

    'messagePreview.availableWordings': 'Mga available na wording',
    'messagePreview.tapHint': 'Pindutin ang wording para basahin ang template nito nang nakasulat, at isang halimbawa kung paano ito matatanggap ng customer mo.',
    'messagePreview.yourText': 'Ang teksto mo',
    'messagePreview.sendingNow': 'Ipinapadala ngayon',
    'messagePreview.templateAsWritten': 'Ang template nang nakasulat',

    'messagePreview.previewOnWhatsapp': 'I-preview sa WhatsApp',
    'messagePreview.thisIsSendingNote': 'Ito ang lumalabas sa pangalan mo para sa mensaheng ito.',
    'messagePreview.useIt': 'Gamitin ito',
    'messagePreview.backToOurs': 'Bumalik sa wording namin',
    'messagePreview.makeMyTone': 'Gawin itong tono ko',
    'messagePreview.submitToWhatsapp': 'Isumite sa WhatsApp',
    'messagePreview.helpMe': 'Tulungan ako',
    'messagePreview.requestReceived': 'Natanggap namin ang request mo — sasagutin namin dito.',

    'messagePreview.footerChosen': 'Ang teksto mo ang ipinapadala para sa mensaheng ito — ang tono ang namamahala sa iba mong mensahe.',
    'messagePreview.footerTone': 'Ang tono mo ay para sa lahat ng mensahe mo, hindi lang dito.',

    'messagePreview.writeYourOwnPrompt': 'Gusto mo ng sarili mong wording? Isulat ito at isusumite namin sa WhatsApp gamit ang pangalan mo.',
    'messagePreview.writeYourText': 'Isulat ang teksto mo',

    'messagePreview.cannotWriteNote': 'Ang mensaheng ito ay ipinapadala gamit ang wording namin — ang teksto nito ay konektado sa legal na karapatan ng customer mo.',

    'messagePreview.previewSubtitle': 'Eksakto ang natatanggap ng customer — ang totoong Flow, hindi tularan.',

    'messagePreview.savingEllipsis': 'Sine-save…',
  },
  bn: {
    'messagePreview.status.rejected': 'হোয়াটসঅ্যাপ প্রত্যাখ্যান করেছে',
    'messagePreview.status.pendingReview': 'হোয়াটসঅ্যাপের কাছে পর্যালোচনার জন্য',
    'messagePreview.status.notSubmitted': 'এখনো জমা দেওয়া হয়নি',
    'messagePreview.status.ready': 'পাঠানোর জন্য প্রস্তুত',
    'messagePreview.status.awaitingApproval': 'হোয়াটসঅ্যাপের অনুমোদনের অপেক্ষায়',

    'messagePreview.tone.masculine': 'পুরুষবাচক',
    'messagePreview.tone.feminine': 'স্ত্রীবাচক',

    'messagePreview.toneSaveError': 'টোন সংরক্ষণ করা যায়নি।',
    'messagePreview.saveError': 'সংরক্ষণ করা যায়নি।',
    'messagePreview.actionError': 'সম্পন্ন করা যায়নি।',
    'messagePreview.flowFetchError': 'ফ্লোর স্ক্রিন আনা যায়নি।',
    'messagePreview.noFlowPermission': 'ফ্লো স্ক্রিন পড়ার অনুমতি নেই',

    'messagePreview.noPermission': 'আপনার ভূমিকায় বার্তার লেখা সম্পাদনা অন্তর্ভুক্ত নয়।',
    'messagePreview.loadFailed': 'এখন এই বার্তার লেখা দেখানো যায়নি — এটা আমাদের ত্রুটি। একটু পরে চেষ্টা করুন।',
    'messagePreview.empty.unread': 'আমাদের লেখাগুলো এখন পড়া যায়নি — এটা আমাদের ত্রুটি, আপনার নয়। একটু পরে চেষ্টা করুন।',
    'messagePreview.empty.pending': 'আপনার লেখা পর্যালোচনার জন্য হোয়াটসঅ্যাপে পাঠানো হয়েছে, যা কয়েক ঘণ্টা সময় নিতে পারে। অনুমোদন হলেই আপনাকে জানাব।',
    'messagePreview.empty.none': 'এই বার্তার জন্য এখনো কোনো প্রস্তুত লেখা নেই — এটা আমাদের একটি ঘাটতি যা নিয়ে আমরা কাজ করছি।',

    'messagePreview.availableWordings': 'উপলব্ধ লেখাগুলো',
    'messagePreview.tapHint': 'কোনো লেখায় ট্যাপ করুন এর টেমপ্লেট যেভাবে লেখা হয়েছে তা পড়তে, এবং আপনার গ্রাহক যেভাবে পাবে তার একটি উদাহরণ দেখতে।',
    'messagePreview.yourText': 'আপনার লেখা',
    'messagePreview.sendingNow': 'এখন পাঠানো হচ্ছে',
    'messagePreview.templateAsWritten': 'টেমপ্লেট যেমন লেখা হয়েছে',

    'messagePreview.previewOnWhatsapp': 'হোয়াটসঅ্যাপে প্রিভিউ',
    'messagePreview.thisIsSendingNote': 'এই বার্তার জন্য আপনার নামে আসলে এটাই যায়।',
    'messagePreview.useIt': 'এটি ব্যবহার করুন',
    'messagePreview.backToOurs': 'আমাদের লেখায় ফিরে যান',
    'messagePreview.makeMyTone': 'এটি আমার টোন করুন',
    'messagePreview.submitToWhatsapp': 'হোয়াটসঅ্যাপে জমা দিন',
    'messagePreview.helpMe': 'আমাকে সাহায্য করুন',
    'messagePreview.requestReceived': 'আপনার অনুরোধ পেয়েছি — আমরা এখানে উত্তর দেব।',

    'messagePreview.footerChosen': 'এই বার্তার জন্য আপনার লেখাই পাঠানো হয় — টোন আপনার বাকি বার্তাগুলো নিয়ন্ত্রণ করে।',
    'messagePreview.footerTone': 'আপনার টোন আপনার সব বার্তায় প্রযোজ্য, শুধু এতে নয়।',

    'messagePreview.writeYourOwnPrompt': 'নিজের লেখা চান? এটি লিখুন এবং আমরা আপনার নামে হোয়াটসঅ্যাপে জমা দেব।',
    'messagePreview.writeYourText': 'আপনার লেখা লিখুন',

    'messagePreview.cannotWriteNote': 'এই বার্তাটি আমাদের লেখা দিয়ে পাঠানো হয় — এর লেখা আপনার গ্রাহকের একটি আইনি অধিকারের সাথে সংযুক্ত।',

    'messagePreview.previewSubtitle': 'গ্রাহক ঠিক যা পায় — আসল ফ্লো, কোনো নকল নয়।',

    'messagePreview.savingEllipsis': 'সংরক্ষণ হচ্ছে…',
  },
});
