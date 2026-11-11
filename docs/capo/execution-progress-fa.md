# برنامه اجرا و دفتر پیشرفت OMERTAOS

تاریخ وضعیت: ۲۰۲۶-۱۱-۱۱. این سند مرجع هماهنگی ادامه کار است؛ نتیجه تست
یا مجوز اجرای مرحله بعد را جایگزین نمی‌کند. وضعیت هر مرحله فقط با شواهد واقعی
به‌روزرسانی می‌شود.

## هدف و مبنا

هدف، پیشبرد نمونه پژوهشی OMERTAOS به زیرساخت Runtime قابل بازتولید برای
مقاله FGCS، با حفظ مرز تصمیم‌گیری Control و اجرای Runtime است.

مسیر canonical:

```text
Console -> Gateway -> Control -> Runtime Daemon
```

تقسیم موردنظر شاخه‌ها: `AION` شاخه جامع، `CAPO` نسخه Console/terminal و
Docker، و `WARLOCK` مسیر آینده native/نصب از فلش و GUI است. این تقسیم هدف
محصول است؛ وجود همه قابلیت‌ها یا آمادگی نصب را اثبات نمی‌کند.

- مبنای شروع P1: `2e8b9142b1da68c119720452d7ff8608c5a5bdbc`.
- اصلاح کد P1: `dae20bf5e867f86e82197779bbd61cb642654cde`، محلی و هنوز push نشده.
- اصلاح correlation در P2: `9689b8a`؛ harness پذیرش: `d02a54b`؛ هر دو محلی‌اند.
- ابزار و تست بازیابی محدود P3: `9769808`؛ محلی و push نشده.
- backup رمزگذاری‌شده و restore مجزا: `3415359`؛ حفظ exportهای هر restore: `76a5477`؛ محلی و push نشده.
- ارتقای clone داده واقعی R6: `614b2ef`؛ گیت‌های محدود P3 تکمیل محلی شدند و push نشده‌اند.
- شاخه کاری: `Radin/omerta-env-namespace`؛ توسعه مستقیم روی CAPO انجام نشود.
- CAPO گیتهاب از `c79a3e0` تا همین مبنا، با ۵۱ کامیت و push معمولی همگام شد.
- این همگام‌سازی، تست جدید یا پذیرش production نبود.
- checkout دیگر: `/home/omerta/projects/OMERTAOS` روی
  `Radin/capo-r6-validation` در `3d60d75`؛ هنگام تطبیق نهایی چهار فایل
  تغییر ثبت‌نشده داشت. تغییرات اصل checkout حفظ شدند.
- کامیت طرح مهاجرت آن شاخه از نظر patch معادل کامیتی در شاخه فعلی است؛
  انتقال دوباره آن لازم نیست. تغییرات باقی‌مانده به شاخه کاری فعلی منتقل شدند.

## شواهد مرجع

- [گزارش پذیرش و فرمان‌ها](acceptance-report.md)
- [دفتر ادعاها و تعریف E0/E1/E2/E3](../research/evidence-and-claims.md)
- [بازتولید](../research/reproducibility.md)
- [قرارداد مهاجرت متغیرها](../migration/aion-env-prefix-to-omerta.md)
- [قرارداد مالکیت معماری](../adr/0001-canonical-aion-ownership.md)

نتایج جدول کارهای انجام‌شده از گزارش‌های قبلی هستند؛ اجرای تازه P1 در بخش
«نتیجه اجرای P1» جدا ثبت شده است.
E1 یعنی بررسی اجرایی مخزن، E2 یعنی نمونه پیاده‌شده با پذیرش محدود، E3 هدف
طراحی و E0 ادعای فاقد شاهد کافی. موفقیت محلی سطح جدیدی به این طبقه‌بندی اضافه
نمی‌کند و به‌تنهایی دلیل scalability یا امنیت production نیست.

## کارهای انجام‌شده

| مرحله | کار ثبت‌شده | شاهد و محدودیت |
|---|---|---|
| R5 و R6.9 | اجرای احرازشده echo از مسیر canonical و انتقال context | گزارش پذیرش؛ فقط مسیر allowlist و محیط محدود |
| R6.10 و R6.11 | lifecycle محلی و پذیرش محدود دو worker | `ac39d51` و `cd43d8f`؛ نه membership توزیع‌شده |
| R6.12 و اصلاحات | audit پایدار، مرز tenant/admin و احراز headerهای داخلی | `c5a9246`، `78b02b1`، `b0181ee`، `db32030` |
| R6.13 تا R6.15 | رزرو اتمیک ظرفیت، lease/fencing و secret فایل‌محور | `076db60`، `edde9b0`، `1d9183b`؛ دامنه دقیق هر پذیرش در گزارش |
| M0 تا M3.2 | inventory، resolver، preflight، مهاجرت reader/writer به OMERTA و قرنطینه catalog قدیمی | قرارداد مهاجرت و تست‌های مرتبط؛ aliasها هنوز لازم‌اند |
| ابزارها | هماهنگی Node/npm/pnpm، محیط validation پایتون و تعمیر bootstrap کنسول | `d994c52`، `6469f44`، `073e63c` |
| M4 | health، smoke و ماندگاری Qdrant در Docker محدود | `1d1ed05`؛ پذیرش کامل مهاجرت هنوز باز |
| M4.1.1 | اصلاح وابستگی Fastify/fast-uri و تست regression | `62fdfed`؛ ۲۶ تست Gateway، build و audit آن زمان موفق |
| M4.1.2 | pin digest، چهار build ترتیبی، readiness و shutdown | `2e8b914`؛ ۱۷ تست متمرکز و ۱۳ smoke موفق، شش volume حفظ شد |
| همگام‌سازی | انتقال کامیت‌های ثبت‌شده به CAPO | SHA گیتهاب پس از push با مبنا برابر بود |

در آخرین بررسی، پروژه Docker آزمایشی `omerta-m4-validation` کانتینر روشن
نداشت. وضعیت سرویس‌ها و حافظه پیش از هر اجرای جدید دوباره بررسی شود.

## ایرادها و شکاف‌های باز

1. اصلاح حذف نمایش password و تغییرات نمایشی به سورس فعلی منتقل شده‌اند.
   image کنسول `m413-1ac6890` اکنون آن را دارد و در stack آزمایشی بررسی شد؛
   imageهای قدیمی و پروژه‌های دیگر خودکار به‌روزرسانی نشده‌اند.
2. M4.1.3 محدود با یک Runtime تکمیل شد. ۵۲ مورد تنظیم در پنج نقش سرویس
   به نام‌های canonical و legacy تبدیل شدند؛ ۲۸ alias واقعاً warning مصرف
   تولید کردند. این نتیجه رفتار همه متغیرهای inventory را اثبات نمی‌کند.
3. restart/fencing، نصب تازه و ماندگاری چهار ذخیره‌ساز روی نسخه فعلی پاس شدند؛
   backup رمزگذاری‌شده و restore شش volume در مقصد جدا نیز پاس شدند.
   ارتقای clone واقعی R6 نیز پاس شد. restore منطقی/خارج میزبان و سازگاری همه نسخه‌ها اثبات نشده‌اند.
4. گیتهاب هنگام push تعداد ۸۳ هشدار شاخه پیش‌فرض اعلام کرد؛ این عدد نتیجه
   audit فعلی CAPO نیست. دامنه، اعتبار و اثر هر هشدار باید بررسی شود.
5. دفتر ادعاها باید با گزارش‌های جدید از نظر سازگاری، از جمله محدودیت fencing،
   تطبیق داده شود؛ فقط در صورت وجود شاهد دقیق اصلاح شود.
6. موفقیت Linux isolation، production readiness، consensus، federation و
   scalability اثبات نشده‌اند. fail-closed stub معادل isolation موفق نیست.

## برنامه مرحله‌ای ادامه

P1، P2 و گیت‌های محدود P3 با درخواست و تأیید جداگانه کاربر در ۲۰۲۶-۱۱-۰۲ اجرا شدند.
P4 با مجوز کاربر آغاز شده و هنوز بسته نیست. پس از پایان هر مرحله، نتیجه و محدودیت‌ها گزارش و برای مرحله بعد
تأیید گرفته شود. کارهای پذیرفته‌شده قبلی دوباره از ابتدا اجرا نشوند، مگر تغییر
یا خطای تازه آن را لازم کند.

| شناسه | اقدام و خروجی | معیار پذیرش | وضعیت |
|---|---|---|---|
| P1 | بازبینی و انتقال تغییرات مفید checkout دیگر | چهار فایل منتقل شد؛ password از props کلاینت حذف شد؛ چهار تست Login در suite با ۳۶ تست پاس شد؛ build تولیدی موفق | تکمیل محلی؛ push نشده |
| P2 / M4.1.3 | rebuild کنسول و Control، harness تکرارپذیر و رفع correlation زمان‌بندی | هر دو variant، ورود واقعی، echo و replay و context سه رویداد audit موفق؛ بررسی مقادیر حساس منتخب لاگ موفق؛ stack متوقف و شش volume حفظ شد | تکمیل محلی؛ push نشده |
| P3 | restart، replay/fencing، persistence، backup و restore مجزا | نصب تازه، restart، backup/restore رمزگذاری‌شده و ارتقای clone داده واقعی R6 پاس؛ حدود شواهد در گزارش پذیرش | تکمیل محدود محلی؛ push نشده |
| P4 | بازبینی امنیت و وابستگی و اعتبارسنجی تجمیعی CAPO | دسته‌بندی هشدارها، اصلاح متمرکز، تست متناسب و smoke/authenticated flow روی نسخه نهایی | majorهای منتخب و npm مصوب بررسی شدند؛ audit سه برنامه اصلی پاک و سپس Desktop/Bridge UI هم اصلاح و audit شدند؛ اسکن imageها مردود، export Console، Python و پذیرش Docker نسخه جدید باز |
| P5 | checkpoint، تطبیق شواهد و آماده‌سازی تغییرات برای GitHub | diff و commitهای قابل مرور، گزارش pass/fail/blocked؛ push/merge فقط با مجوز مربوط | منتظر تأیید |
| P6 / M5 | تصمیم درباره بازنشستگی aliasها | نبود مصرف فعال با scan/telemetry و عبور gateهای مهاجرت؛ rollback روشن | منتظر تأیید |
| P7 | طرح native/WARLOCK و بررسی static اسکریپت‌ها | plan برگشت‌پذیر user/env/systemd/update/rollback/backup/restore؛ sudo و نصب سرویس مجوز جدا می‌خواهد | منتظر تأیید |
| P8 | طرح benchmark سبک و سپس اجرای مصوب | raw artifact و provenance؛ یک سناریو در هر زمان و بدون تعمیم به ۴/۸ worker | منتظر تأیید |

P7 و P8 مسیرهای مستقل‌اند و لزوماً نیازمند حذف alias در P6 نیستند. ترتیب اجرا
با تأیید کاربر مشخص می‌شود. پیش از توسعه بیشتر scheduler، کد موجود registry،
heartbeat، eligibility و lease بررسی شود تا قابلیت موجود دوباره پیاده نشود.
هر توسعه جدید باید قرارداد، DB، امنیت، تست، rollback و اثر حافظه را مشخص کند.
federation، consensus، leader election، multi-region و Kubernetes operator
خارج از milestone محدود فعلی‌اند.

طرح benchmark: B0 مسیر client/mock، B1 مسیر Gateway/Control/Runtime/mock و
B2 مسیر دارای Policy و Trace؛ مسیرهای واقعاً پیاده‌شده پیش از اجرا احراز شوند.
ماتریس اولیه concurrency برابر ۱،۴،۸،۱۶؛ worker برابر ۱،۲؛ tenant برابر
۱،۵،۱۰؛ latency قطعی mock برابر ۱۰،۵۰،۲۵۰ میلی‌ثانیه؛ حداقل پنج تکرار پس از
warm-up. latency صدکی، throughput، خطا، queue، overhead، CPU/RAM، utilization
و recovery در صورت کاربرد ثبت شود. CSV/JSON خام، metadata محیط، SHA، plotting
و confidence interval جزو خروجی‌اند؛ فعلاً هیچ benchmark تازه‌ای اجرا نشده است.

## قواعد اجرا و ثبت پیشرفت

### نتیجه اجرای P1 — ۲۰۲۶-۱۱-۰۲

مجوز: درخواست اجرای برنامه توسط کاربر، با حفظ تأیید جداگانه مرحله بعد.
checkpoint شروع: `checkpoint/p1-start-2e8b914`. مالکیت پوشه خالی
`console/node_modules` و خروجی تولیدی `console/.next` از root به کاربر همان
checkout، یعنی `1000:1000`، اصلاح شد. هیچ permission مربوط به credential،
فایل سورس checkout دیگر یا volume تغییر نکرد.

| gate | نتیجه واقعی |
|---|---|
| نصب frozen-lockfile با pnpm پین‌شده 11.13.1 | exit 0؛ ۳۰٫۰ ثانیه؛ حداقل RAM available نمونه‌برداری‌شده ۲۳۶۰ MiB |
| suite کنسول، یک worker | ۱۵ فایل و ۳۶ تست passed، صفر failed/skipped؛ زمان runner برابر ۴۴٫۴۳ ثانیه و wrapper برابر ۴۸٫۱ ثانیه؛ حداقل RAM برابر ۲۲۳۹ MiB |
| regression صفحه Login | چهار سناریو داخل همان اجرای suite: عدم ارسال password به کلاینت، hint بدون ایمیل، redirect setup و redirect session فعال |
| Prisma generate مستقیم | exit 0؛ ۱۶٫۰ ثانیه؛ بدون اتصال DB و بدون فعال‌کردن checksum-ignore |
| اولین build تولیدی | exit 1؛ ۱۰٫۰ ثانیه؛ `EACCES` روی `.next/trace` با مالک root؛ خطای محیطی |
| build پس از اصلاح مالکیت خروجی | exit 0؛ ۴۳۰٫۸ ثانیه؛ یک build worker، heap حداکثر ۱۵۳۶ MiB؛ حداقل RAM برابر ۱۹۸۳ MiB |
| بررسی diff و فایل‌های dependency | whitespace موفق؛ manifest، lockfile و تنظیمات TypeScript تغییر نکردند |

هشدارها: داده قدیمی `baseline-browser-mapping` در تست و تشخیص workspace root
بر مبنای lockfile بیرون مخزن در build اول. ابزار global `pnpm` همچنان نسخه
9.15.9 است؛ فرمان‌های این مرحله با Corepack و نسخه قراردادی 11.13.1 اجرا شدند.
پس از نصب locked، مانع قبلی `vitest not found` رفع شد. suite موفق تکرار نشد؛
فقط build ناموفق پس از اصلاح محیط دوباره اجرا شد. محافظ حافظه زیر ۱ GiB و
timeout فعال بود و در اجراهای موفق trigger نشد. هیچ skip، تضعیف gate یا تغییر
security control برای پاس شدن انجام نشد.

شاهد P1 از نوع E1 برای props صفحه Login و بررسی build است؛ به‌تنهایی پذیرش زنده،
cookie/session واقعی و رفع عیب در image قدیمی را اثبات نمی‌کند. P2 تا P8 در
P1 اجرا نشدند؛ P2 در بخش بعدی جدا ثبت شده است. source commit و tag قدیمی imageها از یکدیگر تفکیک شوند.
دستورات بازتولید در بخش P1 [گزارش پذیرش](acceptance-report.md) ثبت شده‌اند.

### نتیجه اجرای P2 / M4.1.3 — ۲۰۲۶-۱۱-۰۲

checkpoint شروع: `checkpoint/m413-start-1ac6890`. Docker Compose نسخه 5.6.0؛
یک Runtime و پروژه ثابت `omerta-m4-validation`؛ پورت‌های برنامه فقط روی loopback.
تنظیمات renderشده و cookieهای session فقط در حافظه بودند. فایل env و secretها
تغییر نکردند. پروژه‌های دیگر Docker دست‌نخورده ماندند.

دو نقص تشخیص و رفع شد: escaping دوباره `$` در harness دستور healthِ Qdrant
را خراب می‌کرد؛ پس از اصلاح decode/encode، regression و رفت‌وبرگشت واقعی Compose
پاس شدند. سپس اجرای واقعی نشان داد `runtime.schedule` correlation را ثبت
نمی‌کند؛ خواندن مستقل و فقط‌خواندنی PostgreSQL این فقدان را تأیید کرد.
`SchedulingRequest` اکنون request_id اختیاری را از dispatcher و route به ستون
موجود audit منتقل می‌کند؛ schema، API payload و مجوزها تغییر نکردند. رویدادهای
تاریخی بازنویسی نشدند و assert همه رویدادها حفظ شد.

| gate | نتیجه واقعی |
|---|---|
| تست harness | اجرای اولیه ۸ passed؛ پس از رفع escaping و افزودن تست RAM/timeout، ۱۱ passed در ۲٫۱۶۱ ثانیه |
| تست‌های مرتبط Control | ۴۰ passed، صفر failed/skipped و پنج warning در ۱۸٫۷۲ ثانیه |
| Ruff فایل‌های متأثر | exit 0؛ بدون یافته |
| build کنسول | exit 0؛ ۱۲۰۵٫۶۴ ثانیه؛ فقط یک بار |
| build Control پس از تعمیر | exit 0؛ ۱۴٫۸۱ ثانیه؛ فقط یک بار |
| config و conflict preflight | هر دو config exit 0؛ رد تعارض ۴۵ جفت نام برای ۴۴ نام canonical |
| probe واقعی Runtime با aliasهای bind متعارض | exit 1 مورد انتظار؛ diagnostic فقط نام کلیدها را داشت |
| readiness نهایی | canonical برابر ۸۵٫۶۵ و legacy برابر ۹۲٫۸۱ ثانیه، هر دو exit 0 |
| درخواست احرازشده و replay | هر دو variant موفق؛ خروجی echo برابر و task ID replay ثابت |
| audit | سه رویداد schedule/start/success در هر variant با tenant/correlation/trace صحیح |
| deprecation | صفر alias مشاهده‌شده در canonical، ۲۸ alias متمایز در legacy |
| log scan | مقادیر حساس پیکربندی‌شده منتخب و کلید فایل lease در logهای برنامه پیدا نشدند؛ بررسی جامع forensic نیست |
| shutdown | هر دو exit 0؛ هیچ کانتینر آزمایشی روشن نماند؛ شش volume موجود حفظ شدند |

کمترین RAM available نمونه‌برداری‌شده در build/پذیرش‌ها ۲۵۲۶ MiB و در پذیرش
نهایی ۳۷۶۹ MiB بود؛ محافظ ۱ GiB فعال نشد. Gateway و Runtime rebuild نشدند،
چون کدشان تغییر نکرد. دو اجرای ناموفق با گزارش جدا حفظ شدند؛ نصب و suiteهای
نامرتبط دوباره اجرا نشدند. گزارش‌ها در `artifacts/m413/` محلی و ignored هستند؛
جزئیات، هشدارها و فرمان‌ها در [گزارش پذیرش](acceptance-report.md) ثبت شده‌اند.

این پذیرش محدود E2 است: مقایسه محیط واقعی سرویس‌ها، نه صرفاً interpolation
میزبان. کلید/فایل lease و profile بدون alias canonical باقی ماندند؛ همه متغیرها
به‌طور رفتاری مصرف نشدند. نصب تازه، upgrade روی clone داده قدیمی، backup/restore،
آزمون مستقل restart fencing، systemd، vulnerability scan و benchmark در P2
انجام نشدند و همچنان gateهای مراحل بعدی‌اند. aliasها حذف نشده‌اند.

### نتیجه بخشی از P3 — ۲۰۲۶-۱۱-۰۲

مبنای شروع `849d3d0` و checkpoint پیش از ویرایش
`checkpoint/p3-start-849d3d0` بود؛ کد ابزار در `9769808` ثبت شد.
نصب تازه در `omerta-p3-fresh-retry2` و reapply روی داده موجود
`omerta-m4-validation` به‌ترتیب و با یک Runtime بررسی شدند. ورود واقعی، echo
و context مسیر canonical، ماندگاری PostgreSQL/MongoDB/MinIO/Qdrant، حفظ admin
و migration و audit، و رد lease تکراریِ هنوز معتبر پس از restart پاس شدند.
Gateway نتیجه را از Redis replay کرد؛ بررسی مستقل gRPC نشان داد Control
پس از restart نتیجه durable ندارد و با `RUNTIME_RESULT_REPLAY_UNAVAILABLE`
بدون dispatch دوباره fail-closed می‌شود. این دو رفتار با هم یکی نیستند.

دو تلاش اول به‌خاطر فرض غلط ابزار درباره متن خطای عمومی lease و مسیر replay
شکست خوردند؛ گزارش‌ها حفظ و regression اضافه شد. تست نهایی image اعتبارسنجی:
۲۱ تست و ۱۰ subtest پاس، صفر fail/skip، ۳٫۶۶ ثانیه؛ Ruff موفق.
گزارش نهایی ۱۳۵ gate دارد و عمداً exit برابر ۲ و `partial-blocked` می‌دهد.
RAM available حداقل ۳۶۶۹ MiB؛ چهار پروژه آزمایشی متوقف، ۲۴ volume و ۴۴
container حفظ شدند؛ پروژه worker دیگر تغییر نکرد. سه artifact در برابر پنج
مقدار حساس منتخب بررسی شدند و تطبیق نداشتند؛ بررسی جامع secret/log ادعا نمی‌شود.

هنوز کلید عمومی یا fingerprint گیرنده مورد اعتماد backup ارائه نشده است.
هیچ export حساس بدون رمزگذاری و هیچ secret عملیاتی جدید ساخته نشد.
گام بعد همین P3 است: تعیین گیرنده رمزگذاری، اصلاح/تکمیل مسیر Docker backup،
backup قابل بررسی و restore روی مقصد جدا، سپس upgrade واقعی روی clone نسخه
قدیمی. اسکریپت Docker قدیمی فقط پوشه‌ها را آرشیو می‌کند و شاهد این gate نیست.
reapply داده فعلی نباید upgrade تاریخی نامیده شود. P4 آغاز نشده است.
فرمان بازتولید و شکست‌ها در گزارش پذیرش ثبت شده‌اند؛ هیچ push/merge انجام نشد.

### ادامه P3 با مجوز ساخت کلید — ۲۰۲۶-۱۱-۰۲

کاربر ساخت و استفاده از کلید را صریحاً مجاز کرد؛ مانع کلیدِ بخش قبلی رفع شد.
مبنا `9622774`، checkpoint پیش از ویرایش
`checkpoint/p3-encrypted-backup-start-9622774` و کد `3415359` و `76a5477` است.
کلید اختصاصی امضا/رمزگذاری با private key محافظت‌شده و passphrase تصادفی ساخته
شد؛ کلیدها و backup خارج Git، پوشه 0700 و فایل‌ها 0600 هستند. مقدارها در گزارش
ثبت نشدند. رمز اشتباه و ciphertext دستکاری‌شده رد شدند؛ کلید export‌شده در
keyring جدا import و امضا، checksum و صحت رمزگذاری هر ۹ فایل اصلی تأیید شد.

backup سردِ شش volume به‌همراه config، env و کلید lease روی volumeهای جدید
`omerta-p3-restore-20261102a` بازیابی شد. inventory محتوا/مالکیت/permission هر
شش volume پیش از startup مطابق بود. ورود مدیر، داده‌های قبلی PostgreSQL،
MongoDB، MinIO و Qdrant و echo مسیر canonical پاس شدند؛ منبع بعداً دوباره
بررسی و تغییرنکردن محتوای آن احراز شد. stack بازیابی متوقف و شش volume آن حفظ شد.
exportهای منطقی PostgreSQL/MongoDB هم رمزگذاری و امضا شدند؛ restore منطقی
جدا اجرا نشد. MinIO/Qdrant از backup سرد بازیابی شدند، نه export/snapshot API.

نتیجه نهایی: ۳۶ تست و ۲۱ subtest پاس، صفر fail/skip، ۷٫۰۴ ثانیه؛ regression
مسیر اجرای مجدد جداگانه پاس شد؛ Ruff موفق. خطای واقعی fail-closed در بررسی
مسیر بدون permission رفع شد و بررسی آرشیوهای بزرگ با خواندن ۱ MiB chunk
در همان فایل‌های امضاشده دوباره پاس شد. cache دو agent اختصاصی GPG پاک شد.
حداقل RAM available برابر ۳۴۰۶ MiB بود. هیچ rebuild، نصب سیستمی، تغییر
systemd، حذف volume، push یا merge انجام نشد. گزارش و فرمان‌ها در acceptance-report است.

P3 هنوز کامل نیست: ارتقای تاریخی نیازمند baseline واقعی نسخه قدیمی و clone
جداست. داده فعلی به‌عنوان داده تاریخی معرفی نمی‌شود. نگهداری خارج میزبان کلید
و backup، restore منطقی و بازیابی پس از خرابی کامل میزبان هم اثبات نشده‌اند.
ابزار فعلی acceptance محدود با imageهای یکسان است، نه ابزار کامل DR سازمانی.
گام بعد بستن همین gate ارتقاست؛ P4 هنوز آغاز نشده است.

### بستن گیت ارتقای تاریخی P3 — ۲۰۲۶-۱۱-۰۲

در بررسی فعلی، پروژه تک‌ورکری `omertaos-r6-fixed` با ده container متوقف‌شده
از ۳۰ اوت پیدا شد؛ داده فعلی یا fixture جدید به‌جای داده تاریخی معرفی نشد.
منبع روشن نشد. سه volume نام‌دار، Redis و Mongo configdb ناشناس و داده
Qdrant داخل لایه container رمزگذاری شدند و روی clone جدا بازیابی شدند.
inventory هر شش بخش مطابق بود. دو volume جدید fencing هم ایجاد شدند چون
نسخه قدیمی اساساً state پایدار lease نداشته است؛ چیزی جعل یا reset نشد.

دیتابیس قبل از ارتقا هشت جدول داشت: یک مدیر، دو node ثبت‌شده، شش attempt و
شش تصمیم زمان‌بندی. دو node ثبت‌شده به معنی دو worker روشن نیست؛ فقط یک Runtime
آزمایشی اجرا شد. migration عادی سه جدول audit/resource/execution lease را
افزود و hash چندمجموعه‌ای همه ردیف‌ها/ستون‌های قدیمی پیش از فعال‌شدن Control
حفظ شد. پس از startup، حساب و hash رمز، attemptها و تصمیم‌های قبلی همچنان
حفظ شدند؛ metadata عملیاتی nodeها طبق heartbeat می‌تواند تغییر کند.
ورود با همان credential قدیمی و مسیر canonical با نسخه فعلی موفق بود.

کد `614b2ef`؛ مبنا `6f69b3b`؛ checkpoint شروع
`checkpoint/p3-historical-upgrade-start-6f69b3b`. تست نهایی: ۴۲ تست و ۲۱
subtest پاس، صفر fail/skip، ۶٫۳۶ ثانیه؛ Ruff موفق. گزارش ۱۰۹ gate و exit 0
دارد. حداقل RAM available برابر ۳۴۸۱ MiB بود و حدود ۲۴ GiB دیسک باقی ماند.
clone متوقف و هشت volume آن حفظ شد؛ منبع و پروژه worker دیگر تغییر نکردند.

با این شاهد و نتایج قبلی، P3 در دامنه محدود مصوب بسته شد. پذیرش همه نسخه‌ها،
rollback اجرایی روی کد قدیمی، پروفایل‌های رمزگذاری‌شده پرشده، restore منطقی،
خرابی کامل میزبان و native/benchmark ادعا نمی‌شود. P4 آغاز نشده و تأیید جدا
لازم دارد. هیچ push/merge انجام نشد؛ فرمان‌ها و حدود آزمون در گزارش پذیرش‌اند.

### تطبیق تسک قبلی و الزامات بازیابی

تسک `01a001e5-1aef-7b01-ab9d-c4d538dfd0c7` در checkout اصلی بررسی شد.
آخرین checkpoint آن `3d60d75` است؛ `git cherry` معادل patch آن را در
تاریخچه این شاخه تأیید کرد. کد اختصاصی ثبت‌شده‌ای برای انتقال باقی نمانده و
چهار فایل ثبت‌نشده فعلی همان تغییرات منتقل‌شده در P1 هستند. ادعای تاریخی
«R6.15 منتظر AION_RUNTIME_LEASE_HMAC_KEY» وضعیت فعلی مهاجرت نیست؛ قرارداد
کنونی secret و شواهد جدید گزارش پذیرش ملاک‌اند.

دو gate نصب و ارتقا جدا ثبت شوند: نصب تازه در پروژه/volume مجزا، و سپس
upgrade compatibility روی clone یا backup قابل بازیابی از داده قدیمی.
موفقیت یکی جای دیگری را نمی‌گیرد. شواهد M4 فعلی نباید به پذیرش کامل هر دو
تعمیم داده شود. اجرای هر دو زیر برنامه P2/P3 با یک worker انجام شود.

پیش از P3، backup inventory فعلی دوباره احراز شود: Git و checkpointها،
تغییرات ثبت‌نشده، env و secretها، PostgreSQL logical dump، MongoDB dump،
MinIO objects، Qdrant snapshot، Runtime fencing state و lease secret.
backupهای حساس باید رمزگذاری‌شده و خارج Git باشند؛ state و کلید lease با
هم و طبق قرارداد بازیابی شوند. وجود backup بدون restore موفق کافی نیست.
گزارش قدیمی نبود volume Qdrant را توصیف می‌کرد؛ برای پروژه آزمایشی جدید،
ماندگاری Qdrant بعداً اصلاح و تست شده است. topology هر پروژه جدا احراز شود.

بررسی فقط metadata در ۲۰۲۶-۱۰-۱۷ هنوز permission برابر `664` برای
`/home/omerta/projects/OMERTAOS/.env` و `777` برای
`/home/omerta/projects/OMERTAOS/.aion/secrets` نشان داد. مالکیت، کاربران
مصرف‌کننده و نیاز mount پیش از محدودسازی بررسی شوند؛ این یافته در P4
پیگیری شود. در این تطبیق محتوای secret خوانده نشد و permission تغییر نکرد.

- میزبان ۸ گیگابایت: build و suiteها ترتیبی، شروع با یک Runtime و حداکثر دو
  worker در پذیرش اولیه؛ توقف workload زیر ۱ GiB حافظه available.
- ابتدا config Compose، سپس build فقط برای سرویس متأثر؛ rendering و image
  build معادل پذیرش stack زنده نیستند.
- پروژه آزمایشی از پروژه workerهای دیگر جدا بماند. volume موجود حذف یا rename
  نشود؛ `down -v` و prune حجم‌ها ممنوع است.
- secret موجود با مجوز و بدون نمایش استفاده شود؛ هیچ مقدار واقعی در سند یا
  artifact ثبت نشود. کنترل امنیت برای کاهش مصرف منابع غیرفعال نشود.
- پیش از ویرایش checkpoint؛ تغییرات کاربر حفظ و در صورت dirty بودن برای review
  توقف شود. تغییر شاخه، نصب سیستم و تغییر systemd تابع مجوز مربوط‌اند.
- یک بررسی اولیه تجمیعی، اصلاحات مرتبط به‌صورت دسته‌ای، سپس یک validation
  متناسب؛ تکرار فقط برای failure یا تغییر تازه. خروجی‌ها کوتاه و sanitized باشند.
- برای هر gate: فرمان دقیق، SHA، زمان، exit code، counts، warning و
  passed/failed/skipped/blocked ثبت شود. نتیجه تاریخی به‌عنوان اجرای تازه نقل نشود.
- پس از تعمیر منطقی، diff بررسی و commit متمرکز با مجوز موجود ثبت شود؛ merge
  یا انتشار بدون تأیید انجام نشود. rollback با commit برگشتی/تنظیم و image قبلی،
  با حفظ volumeها انجام شود؛ history rewrite ممنوع است.

### اجرای P4 — ۲۰۲۶-۱۱-۰۳

با مجوز «مرحله بعد را مجوز شروع داری»، بررسی تجمیعی انجام شد. دسترسی فایل
تنظیمات checkout اصلی از ۶۶۴ به ۶۰۰ و پوشه secret خالی آن از ۷۷۷ به ۷۰۰
محدود شد؛ پوشه خالی همین worktree هم از ۷۷۵ به ۷۰۰ رسید. محتوا، مالکیت،
کلیدها، aliasها و mountهای پروژه فعال worker دیگر تغییر نکردند.

کد ذخیره secret در `20988f8` اصلاح شد: نوشتن اتمیک با permission خصوصی،
رد symlink و مسیر ناامن و خطای صریح به‌جای نادیده‌گرفتن شکست permission.
کل Control با ۱۱۷ پاس و یک skip دیتابیس اختصاصی concurrency تأیید شد.
اصلاحات سازگار وابستگی و lockها در `089127b` ثبت شد؛ ۲۶ تست Gateway،
۳۶ تست Console و ۲۳ تست Runtime پاس شدند. Cargo audit پس از patch Tokio
هشداری ندارد. موجودی namespace قدیمی نیز با generator اصلی تازه شد.

audit Console از ۳۹ به چهار هشدار و Gateway از ۲۵ به ۱۵ بسته آسیب‌پذیر
کاهش یافت؛ این دو شمارش از دو ابزار متفاوت‌اند و نباید با هم جمع شوند.
هشدار critical در این دو audit باقی نماند، اما هشدارهای major همچنان بازند.
Bandit پنج یافته low دارد؛ waiver تازه‌ای اضافه نشده. Trivy vulnerability
به‌علت دسترسی دیتابیس و ابزار audit Python به‌علت DNS مسدودند. اسکن مستقل
secret روی snapshot فایل‌های Git موفق بود و جای آن دو gate مسدود را نمی‌گیرد.

در `38c6702` انتخاب صریح imageهای Runtime/Gateway و پذیرش فقط در محیط تازه
به CLI موجود اضافه شد؛ ۲۳ تست و ۱۳ subtest پاس، guard و assertionها حفظ شدند.
هر چهار image جدید ترتیبی ساخته شدند. تلاش اول Console پس از موفقیت build
تولید در export به deadline بیست‌دقیقه‌ای خورد؛ retry با مهلت بیشتر و ۲۷ مرحله
cache در ۱۰۱٫۸۲ ثانیه پاس شد و compile دوباره اجرا نشد.

پذیرش تازه با یک Runtime و ۶۸ gate، صفر failure، موفق شد: ورود و مسیر
canonical، contextهای audit، persistence چهار store و fencing بعد از restart.
replay داخلی Control همچنان fail-closed است و بازیابی durable نتیجه ادعا نشد.
stack متوقف و یازده container و شش volume نام‌دار حفظ شدند. حداقل RAM موجود
۳۲۳۸ MiB در build و ۴۰۱۸ MiB در پذیرش زنده بود؛ پروژه فعال worker دیگر دست‌نخورده
و healthy ماند. اسکن ۹ مقدار حساس انتخاب‌شده در log/diff/artifact نیز پاس شد.

P4 کامل اعلام نمی‌شود؛ برای majorها سؤال جدا مطرح شده و ورود به P5/push/merge
مجاز نیست. lock کامل transitive پایتون سرویس و scanهای مسدود هنوز کار دارند.
جزئیات failureها، انحراف کوتاه ترتیب validation، رفع و فرمان‌ها در گزارش پذیرش‌اند.
تست نهایی ابزارهای مشترک/قراردادها: ۵۲ پاس و ۲۴ subtest، صفر fail/skip،
۹٫۱۰ ثانیه. checkpoint محلی: `checkpoint/p4-compatible-repairs-2026-11-03`.

### پیگیری P4 و اصلاحات سازگار — ۲۰۲۶-۱۱-۱۰

تصمیم کاربر: ابتدا اصلاحات سازگار و checkpoint؛ majorها با تأیید جداگانه.
مبنای شروع `e8b15d5` و checkpoint پیش از ویرایش
`checkpoint/p4-open-gates-start-e8b15d5` است. شاخه تغییر نکرد.

اسکن‌های حفظ‌شده با timestamp واقعی ۲۰۲۶-۱۱-۰۲ نشان می‌دهند Trivy با
دیتابیس رسمی Aqua در ECR از انسداد خارج شده، اما هر چهار image مردودند:
Control چهار، Runtime چهار، Gateway دو و Console سه critical دارند.
این اعداد وقوع package/advisory هستند، نه شمارش CVE یکتا یا اثبات exploit.
«صفر critical» قبلی فقط به audit برنامه‌های npm/pnpm مربوط بود.
جزئیات بسته‌ها، نسخه‌ها و applicability مورد zlib در گزارش پذیرش آمده‌اند؛
هیچ ignore جدید یا ادعای امنیت کامل اضافه نشده است.

pin مربوط به Requests در Docker با lock هش‌دار validation روی ۲.۳۴.۲
هماهنگ شد. ده dependency زمان اجرای Bridge در همان majorهای موجود patch/minor
شدند؛ proxy-addr آسیب‌پذیر از ۲.۰.۷ به ۲.۰.۸ رسید. تست جلوگیری از drift و
نسخه‌های پیش از اصلاح برای Requests و کف امنیتی ده بسته Bridge اضافه شد.
ابزارهای توسعه Bridge نیز patch شدند: Vitest روی ۴.۱.۱۲ و peer پشتیبانی‌شده
Vite روی ۷.۳.۷، همان الگوی Gateway. این تغییر از peer قبلی ۸.۲.۱ صریحاً ثبت
شده و API اجرایی نیست؛ تست قرارداد peer و چهار کف امنیتی توسعه نیز اضافه شد.
تست نهایی: ۲۵ تست Python و سه تست Bridge، build و Ruff پاس؛ صفر fail/skip.
شکست Arborist در اصلاح خودکار و timeout نصب Axios صریحاً ثبت شدند؛ update
هدفمند و retry محدود نصب بدون force یا غیرفعال‌سازی peer validation پاس شدند.
audit نهایی Bridge فقط یک high مربوط به Zod دارد و هنوز exit 1 است.

اسکن تازه سورس با DB رسمی به‌روز ۲۰۲۶-۱۱-۱۰، صفر critical و دو high و سه
medium گزارش کرد؛ پنج وقوع مربوط به سه advisory در lockهای Console هستند.
Bridge در دامنه اسکن فایل findings ندارد، ولی npm همچنان Zod را رد می‌کند.
secret شناسایی‌شده صفر بود؛ ۹۷۱ فایل tracked بررسی شد و دو symlink تاریخی
شکسته دنبال نشدند. اسکن فایل، جای اسکن image یا وابستگی Python را نمی‌گیرد.

بازبینی DNS در ۲۰۲۶-۱۱-۱۰ همچنان خطای میزبان wheelهای Python را نشان داد.
pip-audit و rebuild معتبر Control هنوز مسدودند؛ image قدیمی اصلاح نشده است.
PyPI metadata برای ۳۴ بسته، پنج بسته آسیب‌پذیر و ۱۲ advisory یکتا پس از
حذف alias نشان داد؛ این روش جای pip-audit را نمی‌گیرد.
اصلاح base OS، بسته‌های باندل npm/Go، lock کامل Python و یافته‌های Bandit
هنوز باقی‌اند. P4 بسته نیست و P5/push/merge مجاز نشده است. majorهای Zod،
Minimatch/Glob و DeepmergeTS تا تأیید جداگانه دست‌نخورده می‌مانند.
این بسته migration داده ندارد؛ containerها و volumeها تغییر نکردند.
checkpoint محلی این بسته: `checkpoint/p4-compatible-deps-2026-11-10`؛
commit اصلاحات dependency و تست: `1eae3e7`، محلی و push نشده.
وضعیت «همه اصلاحات سازگار تمام شده» یا پذیرش نهایی امنیت اعلام نمی‌شود.

### اصلاح payload مدل Control در P4 — ۲۰۲۶-۱۱-۱۰

پس از checkpoint قبلی، نقصی مستقل روی image موجود بازتولید شد: import مدل
به‌علت نبود `integrations` شکست می‌خورد. Dockerfile فقط پوشه provider موردنیاز
را کپی می‌کند؛ مالکیت ماژول و مرزهای معماری تغییر نکردند. تست جدید، import
از payload جدا از checkout و رفتار fail-closed مدل غیرفعال را بررسی می‌کند.
۲۱ تست مرتبط و Ruff پاس؛ صفر fail/skip/warning. این تست جای build کامل image
را نمی‌گیرد و image قبلی هنوز این اصلاح را ندارد.

دو probe محدود DNS-over-HTTPS نیز ناموفق بودند؛ تنظیم DNS/TLS، dependencyها
یا سرویس‌های فعال تغییر نکردند. gate ساخت Control و pip-audit باز مانده‌اند.
مبنای شروع `867d782`؛ checkpoint قبل ویرایش
`checkpoint/p4-control-provider-start-867d782` و checkpoint پایان بسته
`checkpoint/p4-control-provider-payload-2026-11-10` است. P4 همچنان باز است؛
نه majorها اجرا شدند و نه push/merge. شرح خطا و فرمان‌ها در گزارش پذیرش است.

### تازه‌سازی pin پایه‌های Docker در P4 — ۲۰۲۶-۱۱-۱۰

Registry قابل دسترسی بود؛ سه پایه رسمی با digest دریافت و ترتیبی اسکن شدند.
چهار Dockerfile به baseline جدید اشاره می‌کنند: Python همچنان در خط ۳.۱۲،
Node و npm همان ۲۲.۲۳.۲ و ۱۰.۹.۸، Alpine برابر ۳.۲۴.۲ و Perl پایه Runtime
برابر `5.36.0-7+deb12u4` است. Rust builder و pnpm تغییر نکردند.
تست pinها baseline جدید و یکسان‌بودن Node در همه stageها را بررسی می‌کند.
۲۵ تست مرتبط، Ruff و رندر Compose پاس شدند؛ build برنامه یا پذیرش زنده نیستند.

اسکن پایه‌ها هنوز exit 1 دارد: Python صفر critical ولی ۴۹ high، Debian یک
critical مربوط به zlib و Node یک critical مربوط به tar باندل npm دارند.
شمارش کامل، محدودیت applicability و نسخه‌های دقیق در گزارش پذیرش ثبت شدند.
هیچ بسته یا finding برای پاس شدن حذف نشد. image برنامه‌های قبلی تغییر نکردند.

probe داخل پایه تازه Python نیز metadata با پاسخ ۲۰۰ و شکست DNS میزبان
wheelها را نشان داد. rebuild Control و pip-audit همچنان مسدودند؛ rebuild
سایر برنامه‌ها تا batch یکپارچه بعدی به تعویق افتاده، نه این‌که مردود یا پاس
اعلام شوند. مجوز majorها و P5/push/merge هنوز داده نشده است.
مبنا `c57dfc9`، checkpoint پیش از ویرایش
`checkpoint/p4-base-refresh-start-c57dfc9` و checkpoint پایان بسته
`checkpoint/p4-base-refresh-2026-11-10` است. volume و سرویس فعال تغییر نکردند.

### مهاجرت مصوب majorهای وابستگی در P4 — ۲۰۲۶-۱۱-۱۰

کاربر پس از checkpoint سازگار، بررسی و اجرای Zod، DeepmergeTS و
Minimatch/Glob را جداگانه تأیید کرد. این مجوز جایگزین عبارت‌های تاریخی
«majorها منتظر تأییدند» در بخش‌های قبلی است؛ P5، push و merge مجاز نشدند.
مبنا `ec76802`، tag پیش از ویرایش `checkpoint/p4-major-start-ec76802`
و کامیت اصلاحات `f47c8ad` است؛ شاخه تغییر نکرد.

سه برنامه Zod 4.6.7 دارند؛ recordها با قرارداد جدید سازگار و کد خطای enum
در Gateway حفظ شد. Console برای سازگاری تایپ به TypeScript 5.9.3 ارتقا یافت،
اما Node/npm/pnpm ثابت ماندند. DeepmergeTS 8.0.2 با مصرف‌کننده واقعی Prisma
تست شد؛ Prisma 6.18.0 و schema تغییر نکردند. matcherهای مدرن Minimatch
11.0.5 و Glob 14.0.4 دارند؛ API قدیمی ESLint/rimraf عمداً محفوظ است.

یک خطای واقعی brace-expansion و باقی‌ماندن Glob قدیمی در lock ثانویه شناسایی
و با override محدود به مالک رفع شد. استثنای سن انتشار که pnpm خودکار پیشنهاد
کرده بود پیش از استفاده در نصب حذف شد؛ نسخه بالغ و حالت strict انتخاب شدند.
هیچ finding، تست یا کنترل امنیتی برای پاس شدن حذف یا خاموش نشد.

نصب locked و buildهای Gateway، Bridge و Console پاس شدند. تست‌ها: Gateway
۳۱، Bridge چهار، Console یک suite کامل ۴۰تایی، سپس سه تست تقویت‌شده Policy
و typecheck نهایی، و ۲۶ تست مرتبط معماری. اجرای کامل ۴۲تایی ادعا نمی‌شود.
audit سه برنامه و lock ثانویه npm صفر advisory دادند؛ Trivy سورس ۹۷۲ فایل
نیز صفر finding/secret گزارش کرد. این اسکن Python و imageهای برنامه را پوشش
نمی‌دهد. کمترین RAM available در batch اصلی ۲۵۵۹ MiB بود؛ اجراها ترتیبی بودند.

هشدار Next درباره انتخاب ریشه `/home/omerta` با lockfile بیرونی باز است؛
فایل بیرونی دست‌نخورده ماند و اصلاح tracing root/rebuild باید در batch بعد
انجام شود. هشدارهای deprecated ابزار قدیمی نیز حذف نشده‌اند. DNS wheelهای
Python، rebuild Control، pip-audit و یافته‌های قبلی OS/binary باز هستند.
image جدید، stack زنده، native و benchmark در این batch اجرا نشدند؛ پذیرش
قدیمی Docker شاهد این majorهای جدید نیست. volume و سرویس فعال تغییر نکردند.

جزئیات فرمان، زمان، نتیجه و rollback اتمیک manifest/lock/source در گزارش
پذیرش ثبت است؛ شواهد فقط E1 منتخب را تقویت می‌کنند. checkpoint پایان:
`checkpoint/p4-major-migration-2026-11-10`؛ هیچ push یا merge انجام نشد.

### اصلاح ریشه tracing کنسول در P4 — ۲۰۲۶-۱۱-۱۰

مبنای شروع `48314cd`، checkpoint پیش از ویرایش
`checkpoint/p4-tracing-root-start-48314cd` و کامیت اصلاح `79fe192` است.
Next با وجود lockfile بیرون مخزن، ریشه را `/home/omerta` می‌گرفت؛ خروجی
قبلی حتی یک ارجاع به باینری Node بیرون checkout داشت. ریشه اکنون از محل
خود config به ریشه مخزن تعیین می‌شود؛ فایل بیرونی و مرزهای امنیتی تغییر نکردند.

اجرای اول، ۴۲ پاس و یک شکست در fixture تازه داشت؛ مشکل URL مرورگر در
jsdom با resolver واقعی Node رفع شد و شکست در گزارش حفظ شد. سپس suite
کامل ۴۳ تست، build تولیدی بدون هشدار قبلی و بررسی ۹۶ manifest با ۸۵۸۰
ارجاع پاس شدند؛ هیچ فایل گمشده یا مسیر بیرون مخزن، حتی پس از realpath، نبود.
کمترین RAM available برابر ۲۷۶۳ MiB بود؛ اجراها ترتیبی بودند.

این نتیجه جایگزین بند باز tracing root در بخش قبلی است، نه شواهد تازه برای
Docker یا امنیت imageها. rebuild برنامه‌ها، پذیرش زنده نسخه جدید، DNS wheelها
و audit کامل Python همچنان بازند. هیچ سرویس، image tag یا volume تغییر نکرد.
checkpoint پایان `checkpoint/p4-console-tracing-root-2026-11-10` است؛
P4 بسته نشده و هیچ push/merge انجام نشد.

### تعمیر build و هم‌راستایی مصوب npm در P4 — ۲۰۲۶-۱۱-۱۰ و ۱۱

مبنای این بسته `46d36c5` بود. توقف واقعی `apk add curl` با timeout مستقل
endpoint رسمی CDN بررسی شد؛ دو mirror موجود در فهرست رسمی Alpine پاسخ
TLS معتبر دادند. در `20eb56f` فقط انتخاب محدود `cdn/kernel` افزوده شد؛
پیش‌فرض، نسخه مخزن و کلیدهای امضا حفظ شدند و مقدار ناشناخته واقعاً در Docker
رد شد. هیچ DNS، TLS یا کنترل امنیتی برای پاس شدن تغییر نکرد.

Gateway ساخته شد، ولی اسکن آن یک critical مربوط به tar همراه npm داشت.
Console در دریافت وابستگی با reset/timeout متوقف شد؛ `5e7c9da` تنظیمات
انتقال را محدود کرد. نصب frozen و تولید Prisma در retry پاس شدند؛ آن build
پس از تأیید ارتقای npm عمداً لغو شد تا image قدیمی دوباره تولید نشود.

با مجوز جدا، `882b7ed` قرارداد npm را در پنج manifest/lock، شش stage داکر
و دو job دارای Node در CI به ۱۰.۹.۱۰ برد. archive با integrity ناشر تطبیق
داشت؛ npm/npx فعال میزبان و tar واقعی همراه آن اکنون ۱۰.۹.۱۰ و ۷.۵.۲۲ هستند.
prefix کاربری backup شد؛ `/usr` تغییر نکرد. Node و Corepack pnpm ثابت‌اند.
گراف و integrity هیچ وابستگی برنامه‌ای در lockها تغییر نکرد.

۳۰ تست قرارداد، Gateway با ۳۱ تست، Bridge با چهار تست، build وب Desktop
و Bridge UI و در نهایت هر ۴۳ تست Console پاس شدند. دو تست قدیمی اصلاح و
سه تست منفی اضافه شدند؛ timeout اولیه Prisma مستقل بررسی و fixtureهای
Node در محیط Node اجرا شدند. timeout و assertion حذف یا افزایش نیافتند؛
اجرای محلی نهایی Console یک‌worker بود. شکست‌های قبلی در گزارش حفظ شدند.

image جدید Gateway ساخته شد و probe آن npm برابر ۱۰.۹.۱۰ و tar برابر
۷.۵.۲۲ را تأیید کرد. اسکن تازه آن صفر critical، سیزده high، سیزده medium
و یک low داشت؛ finding مربوط به tar رفع شده ولی اسکن همچنان مردود است.
در Console نصب frozen، Prisma، build تولیدی Next و کامپایل bootstrap پاس
شدند؛ export با رسیدن دیسک به ۲٫۹۸۶ GiB توسط محافظ ۳ GiB لغو شد: exit 130،
نه build موفق. تگ باقی‌مانده مستقلاً شناسایی شد؛ probe اول timeout شد و
تکرار عین همان probe پس از دسترسی اولیه به image پاس شد: ۹۶ manifest،
۸۵۸۰ reference و صفر مسیر مفقود، npm برابر ۱۰.۹.۱۰ و tar برابر ۷.۵.۲۲.
اسکن آن دو critical مربوط به Go داخل esbuild و ۶۳ high دارد؛ build و
پذیرش زنده همچنان تأیید نشده‌اند. حداقل RAM batch ساخت برابر ۳۰۱۹ MiB بود.
هیچ stack جدید، native یا benchmark اجرا نشده است. امنیت imageها، Python
و پذیرش نهایی P4 همچنان بازند؛ محافظ‌ها کاهش نیافتند و هیچ cache، image یا
volume برای عبور از gate حذف نشد. هیچ push/merge انجام نشد.

نصب‌های میزبان با `--no-audit` اجرا شده بودند و به‌تنهایی شاهد audit نیستند؛
ممیزی مستقل هر پنج lock npm و lock اصلی pnpm انجام شد. Gateway، Console
و Bridge server صفر finding داشتند؛ Desktop و Bridge UI هرکدام سه high و
یک moderate در Vite، Browserslist، source-map-js و baseline-browser-mapping
دارند. این وابستگی‌ها با patch ابزار تغییر نکردند؛ اصلاحشان هنوز باقی است.
شکست اولیه probe و هر دو audit مردود حفظ شدند. checkpoint محلی:
`checkpoint/p4-npm-alignment-2026-11-11`؛ مرحله P4 بسته نشده است.

### اصلاح سازگار وابستگی‌های دو UI در P4 — ۲۰۲۶-۱۱-۱۱

با checkpoint شروع `checkpoint/p4-ui-patches-start-411f4e1` و در همان شاخه،
`402428d` چهار وابستگی آسیب‌پذیر Desktop و Bridge UI را اصلاح کرد:
Vite برابر ۶٫۴٫۶، baseline-browser-mapping برابر ۲٫۱۱٫۳۴، Browserslist برابر
۴٫۲۹٫۵ و source-map-js برابر ۱٫۲٫۲ در lockها ثبت شدند. Vite در major شش
ماند؛ Node/npm/pnpm، React و مرزهای احراز هویت و Runtime تغییر نکردند.
diff قفل‌ها فقط بسته‌های هدف و داده‌ها/ابزارهای وابسته به Browserslist را دارد.

۳۲ تست قرارداد و Ruff پاس شدند؛ نصب قفل‌شده، build وب و typecheck هر دو UI
پاس شدند و audit مستقل هر دو از سه high و یک moderate به صفر رسید.
حداقل RAM برابر ۳۹۸۶ MiB و دیسک برابر ۳٫۸۶۱ GiB بود. هشدار قبلی Tailwind
درباره content در Desktop حفظ شد؛ مرورگر، native و Tauri آزمایش نشدند.
هیچ build داکر، stack، cleanup یا push/merge اجرا نشد. این نتیجه اسکن‌های
مردود image، کمبود دیسک export Console، Python یا پذیرش زنده را نمی‌بندد.
checkpoint محلی: `checkpoint/p4-ui-dependency-patches-2026-11-11`؛ P4 باز است.

### ابزار tsx و کنترل checksum در P4 — ۲۰۲۶-۱۱-۱۱

از checkpoint `checkpoint/p4-console-tooling-start-7f95781`، زنجیره واقعی
tsx/esbuild بررسی شد. اسکن مستقل باینری قدیمی، Go 1.23.12 و CVE بحرانی
قبلی را بازتولید کرد. `1b3f314`، tsx را در همان major چهار به ۴٫۲۳٫۱۵ برد؛
pnpm، esbuild برابر ۰٫۲۸٫۱ و lock ثانویه npm برابر ۰٫۲۸٫۲ دارد. این ارتقا
به معنی رفع CVE نیست: ناشر جدید metadata ساخت Go را حذف کرده و Trivy آن
را تحلیل نمی‌کند. خروج صفرِ بدون تحلیل رد شد؛ گیت امنیتی همچنان ناموفق است.
برای طرح بازسازی قابل ممیزی با Go پین‌شده و metadata/SBOM تصمیم جدا خواسته شد؛
هیچ compiler یا linker سفارشی اجرا یا نصب نشد.

نقص مستقل دیگری هم بازتولید شد: wrapper تولید Prisma خودکار ignore-checksum
را فعال می‌کرد. `52bc6e5` این رفتار ضمنی را حذف کرد. تولید واقعی Prisma،
۳۳ تست قرارداد، ۴۵ تست suite کنسول، کامپایل bootstrap، دو audit و build
تولیدی پاس شدند. سه regression جدید ابتدا به‌علت پسوند فایل جمع نمی‌شدند؛
پس از اصلاح پسوند مطابق الگوی موجود، هر سه جداگانه پاس شدند. اجرای کامل
۴۸تستی ادعا نمی‌شود. ۹۶ manifest و ۸۵۸۰ reference بدون مسیر مفقود یا خروج
از مخزن بررسی شدند. حداقل RAM برابر ۳۴۳۹ MiB و دیسک برابر ۳٫۷۲۷ GiB بود.

خطای گزینه نامعتبر دستور lock، اسکن فاقد پوشش و شکاف کشف تست‌ها ثبت شدند؛
هیچ assertion یا گیت امنیتی برای سبزشدن حذف نشد. نتیجه کلی به‌علت اسکن
نامعتبر هنوز failed است. imageها، stackها، secretها و volumeها دست‌نخورده‌اند؛
Python، اسکن image و پذیرش زنده همچنان بازند. checkpoint محلی:
`checkpoint/p4-console-tooling-2026-11-11`؛ نه P5 و نه push/merge.

## دفتر پیشرفت

| تاریخ | اقدام | نتیجه واقعی | قدم بعد |
|---|---|---|---|
| ۲۰۲۶-۱۰-۱۷ | مقایسه checkoutها و CAPO | این شاخه جلوتر؛ پنج فایل ثبت‌نشده در checkout دیگر شناسایی شد | P1 |
| ۲۰۲۶-۱۰-۱۷ | push مجاز CAPO و بررسی SHA مقصد | `2e8b914` روی CAPO تأیید شد؛ تست تازه اجرا نشد | تهیه سند مصوب کاربر |
| ۲۰۲۶-۱۰-۱۷ | ایجاد این دفتر | مستندسازی هدف، شواهد و gateها؛ بدون اجرای مراحل P1 تا P8 | تأیید P1 |
| ۲۰۲۶-۱۰-۱۷ | تطبیق تسک `01a001e5-1aef-7b01-ab9d-c4d538dfd0c7` | کد اختصاصی باقی نمانده؛ الزامات backup، تفکیک fresh/upgrade و یافته permissions به برنامه اضافه شد | تکمیل validation مربوط به P1 و سپس P2 |
| ۲۰۲۶-۱۱-۰۲ | تکمیل P1 با درخواست اجرای برنامه | نصب locked، ۳۶ تست و build موفق؛ خطای مالکیت build رفع شد؛ کد در `dae20bf` ثبت شد | تأیید جداگانه P2 / M4.1.3 |
| ۲۰۲۶-۱۱-۰۲ | اجرای مصوب P2 / M4.1.3 | دو نقص رفع شد؛ ۱۱ تست harness و ۴۰ تست Control و هر دو variant زنده موفق؛ stack متوقف، volumeها حفظ و نتایج محلی ثبت شدند | تأیید جداگانه P3؛ بازیابی و fresh/upgrade |
| ۲۰۲۶-۱۱-۰۲ | اجرای مرحله بعد، P3 | نصب تازه، restart/fencing و چهار store روی دو محیط پاس؛ ۲۱ تست؛ شکست‌های ابزار ثبت و رفع؛ backup/restore هنوز مسدود | گیرنده رمزگذاری مورد اعتماد برای ادامه همین P3؛ نه شروع P4 |
| ۲۰۲۶-۱۱-۰۲ | مجوز ساخت کلید و ادامه P3 | کلید محافظت‌شده ساخته شد؛ backup امضاشده/رمزگذاری‌شده و restore شش volume و مسیر live پاس؛ ۳۶ تست و checkpoint محلی | baseline نسخه قدیمی و آزمون upgrade روی clone؛ نه P4 |
| ۲۰۲۶-۱۱-۰۲ | بستن ارتقای تاریخی P3 | داده واقعی R6 بدون تغییر منبع clone و ارتقا یافت؛ credential و ردیف‌های قدیمی حفظ؛ ۴۲ تست و مسیر canonical پاس | تأیید جداگانه P4 برای بررسی و اصلاح تجمیعی امنیت/permission |
| ۲۰۲۶-۱۱-۰۳ | checkpoint اصلاحات سازگار P4 | secret store و permissionها اصلاح؛ چهار image جدید و ۶۸ gate پذیرش تازه/restart پاس؛ شکست export با cache رفع؛ هشدارهای major و scanهای مسدود صریح ثبت | تصمیم majorها و تکمیل gateهای باز همین P4؛ نه P5 یا push |
| ۲۰۲۶-۱۱-۱۰ | مهاجرت majorهای منتخب با مجوز جدا | `f47c8ad`؛ locked install/build و تست‌های مرتبط پاس، audit lockها و اسکن سورس بدون finding؛ خطاهای override رفع و کنترل سن انتشار سخت‌تر شد | رفع tracing root، دسترسی wheelها و gateهای image/security/live در همین P4؛ نه P5 یا push |
| ۲۰۲۶-۱۱-۱۰ | رفع ریشه tracing کنسول | `79fe192`؛ ۴۳ تست و build و ۹۶ manifest پاس؛ fixture ناموفق ثبت و رفع؛ هشدار ریشه میزبان بسته شد | batch ترتیبی imageها، گیت‌های امنیتی و دسترسی wheelها در همین P4؛ نه P5 یا push |
| ۲۰۲۶-۱۱-۱۱ | تعمیر انتقال build و ارتقای مصوب npm | `20eb56f`، `5e7c9da`، `882b7ed`؛ npm/npx میزبان ۱۰.۹.۱۰، lockها و تست‌ها پاس؛ Gateway ساخته شد؛ export Console با محافظ دیسک لغو ولی probe یکسان تگ باقی‌مانده در retry پاس شد؛ tar در هر دو artifact finding ندارد، اسکن‌ها همچنان مردود | ظرفیت دیسک بدون حذف خودکار، export موفق Console و هشدارهای باقی‌مانده، Python و پذیرش زنده در همین P4؛ نه P5 یا push |
| ۲۰۲۶-۱۱-۱۱ | بستن auditهای دو UI بدون تغییر major | `402428d`؛ ۳۲ تست، نصب‌های locked، build و typecheck پاس؛ audit Desktop و Bridge UI اکنون صفر finding؛ هشدار قدیمی Tailwind ثبت شد | هشدارهای image/Go/esbuild، ظرفیت دیسک، Python و پذیرش زنده در همین P4؛ نه P5 یا push |
| ۲۰۲۶-۱۱-۱۱ | اصلاح checksum و بررسی زنجیره tsx | `52bc6e5` و `1b3f314`؛ تولید Prisma، ۳۳ قرارداد، ۴۵ تست suite و سه تست جدا، build و trace پاس؛ پوشش اسکن Go نامعتبر و نتیجه کلی failed باقی ماند | تصمیم درباره طرح بازسازی ممیزی‌پذیر، ظرفیت دیسک، Python و پذیرش زنده؛ نه P5 یا push |

برای ادامه، به همین جدول سطر افزوده شود و وضعیت مرحله مرتبط فقط پس از ثبت
نتیجه تغییر کند. این سند snapshot برنامه است؛ گزارش پذیرش مرجع جزئیات آزمایش
و دفتر ادعاها مرجع حدود ادعاهای پژوهشی باقی می‌مانند.
