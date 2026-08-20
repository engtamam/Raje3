"""
Saudi Places Scraper v2 — Google Places API
"""

import requests, csv, time, math, argparse, textwrap
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# 🔑 API KEY — ضع مفتاحك هنا أو مرره كـ environment variable
# ─────────────────────────────────────────────────────────────
import os
API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "YOUR_GOOGLE_PLACES_API_KEY")

# ─────────────────────────────────────────────────────────────
# ⚙️ الإعدادات الافتراضية
# ─────────────────────────────────────────────────────────────
DEFAULT_PLACE_TYPE = "صالون نسائي"

DEFAULT_KEYWORDS = [
    "صالون نسائي",
    "مركز تجميل نسائي",
    "سبا نسائي",
    "ladies salon",
    "women beauty salon",
    "beauty center women",
]

FEMALE_INDICATORS = [
    "نسائي", "نساء", "للسيدات", "ladies", "women", "female", "femme",
    "بيوتي", "beauty", "تجميل", "صالون", "salon",
]

DEFAULT_RADIUS_KM    = 5
DEFAULT_RADIUS_SMALL = 2.5
DEFAULT_DELAY        = 0.5
MAX_RESULTS          = 60

ALL_CITIES = {
    "الرياض":          {"region": "منطقة الرياض",          "lat": 24.7136, "lng": 46.6753, "w": 100, "h": 80},
    "جدة":             {"region": "منطقة مكة المكرمة",     "lat": 21.5433, "lng": 39.1728, "w": 80,  "h": 30},
    "مكة المكرمة":     {"region": "منطقة مكة المكرمة",     "lat": 21.3891, "lng": 39.8579, "w": 50,  "h": 50},
    "المدينة المنورة": {"region": "منطقة المدينة المنورة", "lat": 24.5247, "lng": 39.5692, "w": 40,  "h": 40},
    "الدمام":          {"region": "المنطقة الشرقية",        "lat": 26.3927, "lng": 49.9777, "w": 30,  "h": 20},
    "الخبر":           {"region": "المنطقة الشرقية",        "lat": 26.2172, "lng": 50.1971, "w": 20,  "h": 15},
    "الأحساء":         {"region": "المنطقة الشرقية",        "lat": 25.3854, "lng": 49.5854, "w": 60,  "h": 60},
    "أبها":            {"region": "منطقة عسير",             "lat": 18.2164, "lng": 42.5053, "w": 25,  "h": 25},
    "تبوك":            {"region": "منطقة تبوك",             "lat": 28.3998, "lng": 36.5700, "w": 35,  "h": 35},
    "بريدة":           {"region": "منطقة القصيم",           "lat": 26.3260, "lng": 43.9750, "w": 30,  "h": 30},
}

FIELDNAMES = [
    "الاسم", "رقم_الجوال", "المدينة", "المنطقة_الإدارية",
    "رابط_جوجل_ماب", "التقييم", "عدد_التقييمات",
    "العنوان", "الحي", "ساعات_العمل", "الموقع_الإلكتروني",
    "خط_العرض", "خط_الطول", "place_id", "نوع_المكان", "تاريخ_السحب",
]

# ─────────────────────────────────────────────────────────────
# 📖 Help مفصّل
# ─────────────────────────────────────────────────────────────
HELP_TEXT = textwrap.dedent("""
╔══════════════════════════════════════════════════════════════════╗
║           Saudi Places Scraper v2 — دليل الاستخدام الكامل       ║
╚══════════════════════════════════════════════════════════════════╝

الوصف:
  يسحب بيانات الأماكن التجارية من Google Maps لـ 10 مدن سعودية
  ويحفظها في CSV جاهز للتحليل، يعمل مع أي نوع من الأماكن.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 الإعداد الأول (مرة واحدة فقط)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1) احصل على Google Places API Key:
       https://console.cloud.google.com → APIs & Services → Credentials
       فعّل: "Places API" من المكتبة

  2) ضع المفتاح بإحدى طريقتين:

     أ) داخل الملف مباشرة (السطر 13):
        API_KEY = "AIzaSy..."

     ب) كـ Environment Variable (أكثر أماناً):
        Windows:  set GOOGLE_PLACES_API_KEY=AIzaSy...
        Mac/Linux: export GOOGLE_PLACES_API_KEY=AIzaSy...

  3) ثبّت المتطلبات:
        pip install requests

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 الخيارات (Arguments)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  --type "نص"
      نوع المكان المطلوب. يُستخدم كتسمية في عمود نوع_المكان بالـ CSV.
      الافتراضي: "صالون نسائي"
      مثال:  --type "مغسلة سيارات"
             --type "صيدلية"
             --type "مطعم"

  --keywords "كلمة1,كلمة2,كلمة3"
      كلمات البحث المرسلة لـ Google، مفصولة بفاصلة.
      الـ Script يشغّل لوب على كل كلمة مستقلة لضمان أقصى تغطية.
      الافتراضي: 6 كلمات للصالونات النسائية
      مثال:  --keywords "car wash,مغسلة,غسيل سيارات,carwash"
             --keywords "pharmacy,صيدلية,دواء"
      ⚠️  لا تترك مسافة بعد الفاصلة داخل علامات التنصيص

  --radius رقم
      نصف قطر البحث بالكيلومتر لكل نقطة في الـ Grid.
      قيمة صغيرة = دقة أعلى + استعلامات أكثر
      قيمة كبيرة = سرعة أعلى + دقة أقل
      الافتراضي: 5
      مثال:  --radius 3   ← للمدن الكثيفة جداً (وسط الرياض)
             --radius 8   ← للمدن الصغيرة أو المناطق الصناعية
             --radius 10  ← للحصول على نتائج سريعة تقريبية

  --cities "مدينة1,مدينة2"
      أسماء المدن المطلوبة مفصولة بفاصلة.
      يجب أن تكون مطابقة تماماً للقائمة أدناه.
      الافتراضي: كل المدن العشر
      المدن المتاحة:
        الرياض | جدة | مكة المكرمة | المدينة المنورة | الدمام
        الخبر  | الأحساء | أبها | تبوك | بريدة
      مثال:  --cities "الرياض"
             --cities "الرياض,جدة,الدمام"

  --output "اسم_الملف.csv"
      اسم ملف الإخراج.
      الافتراضي: places_نوع_المكان_YYYYMMDD_HHMM.csv
      مثال:  --output "صالونات_الرياض_2026.csv"
             --output "D:/data/salons.csv"

  --no-filter
      يطفئ فلتر النسائي (مفعّل افتراضياً للصالونات).
      استخدمه عند سحب أماكن غير مرتبطة بالجنس.
      مثال:  --no-filter   ← لمغاسل السيارات والصيدليات والمطاعم

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 أعمدة ملف CSV الناتج (16 عمود)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  الاسم              اسم المكان كما يظهر في Google
  رقم_الجوال         رقم الهاتف المسجّل في Google
  المدينة            المدينة التي سُحبت منها البيانات
  المنطقة_الإدارية  المنطقة الإدارية (منطقة الرياض، المنطقة الشرقية...)
  رابط_جوجل_ماب     رابط مباشر لصفحة المكان في Google Maps
  التقييم            متوسط النجوم (1.0 – 5.0)
  عدد_التقييمات     عدد التقييمات — مهم لمعرفة موثوقية التقييم
  العنوان            العنوان الكامل
  الحي               اسم الحي أو الحي الفرعي
  ساعات_العمل        أوقات العمل الأسبوعية
  الموقع_الإلكتروني  الموقع إن وُجد
  خط_العرض           Latitude — للتحليل الجغرافي
  خط_الطول           Longitude — للتحليل الجغرافي
  place_id           المعرّف الفريد في Google (يُستخدم لمنع التكرار)
  نوع_المكان         قيمة --type التي أدخلتها
  تاريخ_السحب        تاريخ تشغيل السكريبت

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 كيف يعمل السكريبت — الخوارزمية
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Grid System:
     يقسّم كل مدينة لشبكة من النقاط بناءً على أبعادها الجغرافية.
     المسافة بين النقاط = radius × 1.5 (تداخل مقصود للتغطية الكاملة)

  2. Multi-Keyword Loop:
     لكل نقطة في الـ Grid، يشغّل استعلاماً مستقلاً لكل keyword.
     هذا يضمن ظهور الأماكن بغض النظر عن طريقة تسجيلها في Google.

  3. Pagination:
     Google ترجع 20 نتيجة لكل صفحة كحد أقصى (3 صفحات = 60 نتيجة).
     السكريبت يجلب كل الصفحات تلقائياً.

  4. Auto-Split:
     إذا رجعت نتيجة = 60 (الحد الأقصى) تعني أن هناك المزيد.
     السكريبت يقسّم النقطة تلقائياً لـ 4 نقاط فرعية بـ radius أصغر
     (2.5 كم) للتأكد من عدم فقدان أي مكان.

  5. Deduplication:
     كل مكان له place_id فريد من Google.
     السكريبت يتتبع كل الـ place_id المسحوبة ويتجاهل المكررات
     تلقائياً عبر كل المدن والكلمات والنقاط.

  6. Female Filter (للصالونات):
     بعد سحب النتائج، يفحص اسم كل مكان ويحتفظ فقط بالأماكن
     التي تحتوي على مؤشرات نسائية في اسمها.
     يمكن إطفاؤه بـ --no-filter للأماكن الأخرى.

  7. Place Details:
     لكل مكان جديد، يرسل طلباً إضافياً لجلب التفاصيل الكاملة
     (رقم الجوال، ساعات العمل، الموقع الإلكتروني...).

  8. حفظ تدريجي:
     يحفظ الـ CSV كل 50 مكان تلقائياً لضمان عدم فقدان البيانات
     عند الانقطاع المفاجئ.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 أمثلة عملية
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # 1. الاستخدام الافتراضي — صالونات نسائية في كل المدن
  python places_scraper_v2.py

  # 2. صالونات نسائية في الرياض وجدة فقط
  python places_scraper_v2.py --cities "الرياض,جدة"

  # 3. مغاسل سيارات — كل المدن بدون فلتر نسائي
  python places_scraper_v2.py \\
    --type "مغسلة سيارات" \\
    --keywords "car wash,مغسلة سيارات,غسيل سيارات,carwash" \\
    --no-filter

  # 4. صيدليات في المنطقة الشرقية
  python places_scraper_v2.py \\
    --type "صيدلية" \\
    --keywords "pharmacy,صيدلية,دواء" \\
    --cities "الدمام,الخبر,الأحساء" \\
    --no-filter

  # 5. مطاعم في الرياض بدقة عالية (radius صغير)
  python places_scraper_v2.py \\
    --type "مطعم" \\
    --keywords "مطعم,restaurant,food" \\
    --cities "الرياض" \\
    --radius 3 \\
    --no-filter \\
    --output "مطاعم_الرياض_2026.csv"

  # 6. كوفي شوب في جدة
  python places_scraper_v2.py \\
    --type "كوفي شوب" \\
    --keywords "coffee,كافيه,قهوة,كوفي" \\
    --cities "جدة" \\
    --no-filter

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 تقدير التكلفة والوقت
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Google Places API تكلفة:
    Nearby Search : $0.032 لكل طلب
    Place Details : $0.017 لكل طلب
    Google Credit : $200 مجاناً شهرياً

  تقدير لصالونات نسائية (10 مدن، radius=5, 6 keywords):
    ┌─────────────────┬──────────┬──────────┬──────────┐
    │ المدينة         │ Grid     │ طلبات    │ تكلفة    │
    ├─────────────────┼──────────┼──────────┼──────────┤
    │ الرياض          │ ~65 نقطة │ ~390     │ ~$13     │
    │ جدة             │ ~30 نقطة │ ~180     │ ~$6      │
    │ باقي 8 مدن      │ ~120     │ ~720     │ ~$24     │
    │ Place Details   │ ~500 مكان│ ~500     │ ~$9      │
    ├─────────────────┼──────────┼──────────┼──────────┤
    │ المجموع         │          │ ~1790    │ ~$52     │
    └─────────────────┴──────────┴──────────┴──────────┘
  → داخل الـ $200 credit المجاني ✅

  الوقت التقريبي للتشغيل الكامل: 3–5 ساعات
  (بسبب الـ delay بين الطلبات لتجنب Rate Limiting)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 حل المشاكل الشائعة
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ❌ REQUEST_DENIED
     السبب: API Key غلط أو Places API غير مفعّلة
     الحل:  تحقق من المفتاح وفعّل Places API في Google Console

  ❌ OVER_QUERY_LIMIT
     السبب: تجاوزت الحد اليومي أو المعدل الزمني
     الحل:  زد DEFAULT_DELAY في الكود من 0.5 إلى 1.0

  ❌ مدينة غير موجودة
     السبب: اسم المدينة لا يطابق القائمة تماماً
     الحل:  انسخ الاسم بالضبط من قائمة المدن في --help

  ❌ CSV فارغ
     السبب: الفلتر النسائي يحذف كل النتائج
     الحل:  جرب --no-filter أو عدّل keywords لتكون أوضح

  ❌ نتائج قليلة جداً
     السبب: radius كبير أو keywords قليلة
     الحل:  قلّل --radius أو أضف كلمات بحث أكثر

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

# ─────────────────────────────────────────────────────────────
# 🔍 فلتر نسائي
# ─────────────────────────────────────────────────────────────
def is_female_place(name, apply_filter):
    if not apply_filter:
        return True
    return any(ind in name.lower() for ind in FEMALE_INDICATORS)

# ─────────────────────────────────────────────────────────────
# 📐 Grid Generator
# ─────────────────────────────────────────────────────────────
def generate_grid(lat, lng, w_km, h_km, step_km):
    points = []
    lat_step  = step_km / 111.0
    lng_step  = step_km / (111.0 * math.cos(math.radians(lat)))
    lat_range = h_km / 111.0
    lng_range = w_km / (111.0 * math.cos(math.radians(lat)))
    cur_lat = lat - lat_range / 2
    while cur_lat <= lat + lat_range / 2:
        cur_lng = lng - lng_range / 2
        while cur_lng <= lng + lng_range / 2:
            points.append((round(cur_lat, 6), round(cur_lng, 6)))
            cur_lng += lng_step
        cur_lat += lat_step
    return points

# ─────────────────────────────────────────────────────────────
# 🌐 API Calls
# ─────────────────────────────────────────────────────────────
def search_places(lat, lng, radius_m, keyword, page_token=None):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {"location": f"{lat},{lng}", "radius": radius_m,
              "keyword": keyword, "key": API_KEY, "language": "ar"}
    if page_token:
        params["pagetoken"] = page_token
    try:
        return requests.get(url, params=params, timeout=10).json()
    except Exception as e:
        print(f"  ❌ {e}")
        return None

def get_place_details(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,formatted_phone_number,formatted_address,"
                  "opening_hours,website,url,rating,user_ratings_total,"
                  "vicinity,address_components",
        "key": API_KEY, "language": "ar",
    }
    try:
        return requests.get(url, params=params, timeout=10).json().get("result", {})
    except:
        return {}

# ─────────────────────────────────────────────────────────────
# 🔄 Fetch + Pagination + Auto-split
# ─────────────────────────────────────────────────────────────
def fetch_all_for_point(lat, lng, radius_km, keyword):
    results, page_token = [], None
    while True:
        data = search_places(lat, lng, radius_km * 1000, keyword, page_token)
        if not data or data.get("status") not in ["OK", "ZERO_RESULTS"]:
            break
        results.extend(data.get("results", []))
        page_token = data.get("next_page_token")
        if not page_token:
            break
        time.sleep(2)
    return results

def fetch_with_autosplit(lat, lng, radius_km, keyword, seen_ids, apply_filter):
    new_places = []
    results = fetch_all_for_point(lat, lng, radius_km, keyword)
    if len(results) >= MAX_RESULTS and radius_km > DEFAULT_RADIUS_SMALL:
        print(f"      ⚡ Auto-split ({len(results)} نتيجة) → {DEFAULT_RADIUS_SMALL}كم")
        offset = radius_km * 0.4 / 111.0
        for slat, slng in [(lat+offset,lng+offset),(lat+offset,lng-offset),
                           (lat-offset,lng+offset),(lat-offset,lng-offset)]:
            for p in fetch_all_for_point(slat, slng, DEFAULT_RADIUS_SMALL, keyword):
                pid = p.get("place_id")
                if pid and pid not in seen_ids and is_female_place(p.get("name",""), apply_filter):
                    seen_ids.add(pid); new_places.append(p)
            time.sleep(DEFAULT_DELAY)
    else:
        for p in results:
            pid = p.get("place_id")
            if pid and pid not in seen_ids and is_female_place(p.get("name",""), apply_filter):
                seen_ids.add(pid); new_places.append(p)
    return new_places

# ─────────────────────────────────────────────────────────────
# 📊 بناء صف CSV
# ─────────────────────────────────────────────────────────────
def extract_neighborhood(components):
    for c in components:
        if "sublocality" in c.get("types",[]) or "neighborhood" in c.get("types",[]):
            return c.get("long_name","")
    return ""

def build_row(place, city_name, city_info, place_type):
    place_id = place.get("place_id","")
    d = get_place_details(place_id)
    time.sleep(DEFAULT_DELAY)
    wt = d.get("opening_hours",{}).get("weekday_text",[])
    return {
        "الاسم":             d.get("name") or place.get("name",""),
        "رقم_الجوال":        d.get("formatted_phone_number",""),
        "المدينة":           city_name,
        "المنطقة_الإدارية": city_info["region"],
        "رابط_جوجل_ماب":    d.get("url") or f"https://www.google.com/maps/place/?q=place_id:{place_id}",
        "التقييم":           d.get("rating") or place.get("rating",""),
        "عدد_التقييمات":    d.get("user_ratings_total") or place.get("user_ratings_total",""),
        "العنوان":           d.get("formatted_address") or place.get("vicinity",""),
        "الحي":              extract_neighborhood(d.get("address_components",[])),
        "ساعات_العمل":       " | ".join(wt) if wt else "",
        "الموقع_الإلكتروني":d.get("website",""),
        "خط_العرض":          place.get("geometry",{}).get("location",{}).get("lat",""),
        "خط_الطول":          place.get("geometry",{}).get("location",{}).get("lng",""),
        "place_id":          place_id,
        "نوع_المكان":        place_type,
        "تاريخ_السحب":       datetime.now().strftime("%Y-%m-%d"),
    }

def save_csv(rows, filename):
    if not rows: return
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader(); writer.writerows(rows)

# ─────────────────────────────────────────────────────────────
# 🚀 Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="places_scraper_v2.py",
        description="Saudi Places Scraper v2 — سحب بيانات الأماكن من Google Maps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=HELP_TEXT,
        add_help=False,  # نعطّل الـ help الافتراضي ونبنيه نحن
    )
    parser.add_argument("-h", "--help", action="store_true",
                        help="عرض هذا الدليل الكامل والخروج")
    parser.add_argument("--type",      default=DEFAULT_PLACE_TYPE,
                        metavar='"نص"',
                        help="نوع المكان (الافتراضي: صالون نسائي)")
    parser.add_argument("--keywords",  default=",".join(DEFAULT_KEYWORDS),
                        metavar='"ك1,ك2,ك3"',
                        help="كلمات البحث مفصولة بفاصلة")
    parser.add_argument("--radius",    default=DEFAULT_RADIUS_KM, type=float,
                        metavar="رقم",
                        help="نصف القطر بالكيلومتر (الافتراضي: 5)")
    parser.add_argument("--cities",    default=",".join(ALL_CITIES.keys()),
                        metavar='"م1,م2"',
                        help="المدن مفصولة بفاصلة (الافتراضي: كل المدن)")
    parser.add_argument("--output",    default="",
                        metavar='"ملف.csv"',
                        help="اسم ملف الإخراج (الافتراضي: تلقائي)")
    parser.add_argument("--no-filter", action="store_true",
                        help="أطفئ فلتر النسائي (للأماكن العامة)")

    args = parser.parse_args()

    if args.help:
        print(HELP_TEXT)
        return

    place_type   = args.type
    keywords     = [k.strip() for k in args.keywords.split(",")]
    radius_km    = args.radius
    cities       = [c.strip() for c in args.cities.split(",")]
    apply_filter = not args.no_filter
    timestamp    = datetime.now().strftime("%Y%m%d_%H%M")
    output       = args.output or f"places_{place_type.replace(' ','_')}_{timestamp}.csv"

    print(f"\n🚀 Saudi Places Scraper v2")
    print(f"{'─'*50}")
    print(f"📍 نوع المكان  : {place_type}")
    print(f"🔑 كلمات البحث : {len(keywords)}")
    for kw in keywords: print(f"   • {kw}")
    print(f"📐 نصف القطر  : {radius_km} كم")
    print(f"🏙️  المدن       : {', '.join(cities)}")
    print(f"🔍 فلتر نسائي  : {'✅ مفعّل' if apply_filter else '❌ مطفأ'}")
    print(f"💾 الإخراج     : {output}")
    print(f"{'─'*50}\n")

    seen_ids, all_rows = set(), []

    for city_name in cities:
        city = ALL_CITIES.get(city_name)
        if not city:
            print(f"⚠️  مدينة غير موجودة: '{city_name}'")
            print(f"   المدن المتاحة: {', '.join(ALL_CITIES.keys())}")
            continue

        print(f"\n{'═'*50}")
        print(f"🏙️  {city_name} — {city['region']}")
        print(f"{'═'*50}")
        grid = generate_grid(city["lat"], city["lng"], city["w"], city["h"], step_km=radius_km*1.5)
        print(f"📐 نقاط Grid: {len(grid)} | keywords: {len(keywords)}")

        city_places = []
        for i, (lat, lng) in enumerate(grid):
            for kw in keywords:
                places = fetch_with_autosplit(lat, lng, radius_km, kw, seen_ids, apply_filter)
                city_places.extend(places)
                time.sleep(DEFAULT_DELAY)
            if (i+1) % 5 == 0 or (i+1) == len(grid):
                print(f"  📍 {i+1:2d}/{len(grid)} | المدينة: {len(city_places):3d} | الإجمالي: {len(seen_ids):4d}")

        print(f"\n  📋 جلب تفاصيل {len(city_places)} مكان...")
        for place in city_places:
            all_rows.append(build_row(place, city_name, city, place_type))
            if len(all_rows) % 50 == 0:
                save_csv(all_rows, output)
                print(f"  💾 حفظ تدريجي: {len(all_rows)}")
        print(f"  ✅ {city_name}: {len(city_places)} مكان فريد")

    save_csv(all_rows, output)
    print(f"\n{'═'*50}")
    print(f"✅ اكتمل! إجمالي الأماكن الفريدة: {len(all_rows)}")
    print(f"💾 الملف: {output}")
    print(f"{'═'*50}")

if __name__ == "__main__":
    main()
