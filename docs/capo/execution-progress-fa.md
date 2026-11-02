# برنامه اجرا و دفتر پیشرفت OMERTAOS

تاریخ وضعیت: ۲۰۲۶-۱۱-۰۲. این سند مرجع هماهنگی ادامه کار است؛ نتیجه تست
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
   imageهای قبلی این اصلاح را ندارند؛ پیش از پذیرش بعدی، فقط image کنسول
   با tag مستقل rebuild شود. هیچ credential واقعی برای این اصلاح خوانده نشد.
2. M4.1.3 هنوز اجرا نشده: parity زنده old-only/new-only، رفتار تعارض و درخواست
   احرازشده روی imageهای مهاجرت‌یافته نیازمند شاهد است.
3. backup و restore مستقل و پذیرش نهایی restart/fencing روی همین نسخه باز است.
4. گیتهاب هنگام push تعداد ۸۳ هشدار شاخه پیش‌فرض اعلام کرد؛ این عدد نتیجه
   audit فعلی CAPO نیست. دامنه، اعتبار و اثر هر هشدار باید بررسی شود.
5. دفتر ادعاها باید با گزارش‌های جدید از نظر سازگاری، از جمله محدودیت fencing،
   تطبیق داده شود؛ فقط در صورت وجود شاهد دقیق اصلاح شود.
6. موفقیت Linux isolation، production readiness، consensus، federation و
   scalability اثبات نشده‌اند. fail-closed stub معادل isolation موفق نیست.

## برنامه مرحله‌ای ادامه

P1 با درخواست اجرای برنامه در ۲۰۲۶-۱۱-۰۲ آغاز شد. مراحل بعدی در انتظار تأیید
جداگانه‌اند. پس از پایان هر مرحله، نتیجه و محدودیت‌ها گزارش و برای مرحله بعد
تأیید گرفته شود. کارهای پذیرفته‌شده قبلی دوباره از ابتدا اجرا نشوند، مگر تغییر
یا خطای تازه آن را لازم کند.

| شناسه | اقدام و خروجی | معیار پذیرش | وضعیت |
|---|---|---|---|
| P1 | بازبینی و انتقال تغییرات مفید checkout دیگر | چهار فایل منتقل شد؛ password از props کلاینت حذف شد؛ چهار تست Login در suite با ۳۶ تست پاس شد؛ build تولیدی موفق | تکمیل محلی؛ push نشده |
| P2 / M4.1.3 | rebuild کنسول و harness تکرارپذیر برای aliasهای پشتیبانی‌شده، login و echo واقعی | old-only/new-only موفق، تعارض fail-closed، log بدون secret؛ تفکیک env واقعی process از interpolation Compose | منتظر تأیید |
| P3 | restart، replay/fencing، persistence، backup و restore مجزا | داده fixture و audit حفظ شود؛ restore در مقصد جدا و بررسی‌شده؛ ثبت شکست‌ها | منتظر تأیید |
| P4 | بازبینی امنیت و وابستگی و اعتبارسنجی تجمیعی CAPO | دسته‌بندی هشدارها، اصلاح متمرکز، تست متناسب و smoke/authenticated flow روی نسخه نهایی | منتظر تأیید |
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

شاهد جدید از نوع E1 برای props صفحه Login و بررسی build است؛ پذیرش زنده،
cookie/session واقعی و رفع عیب در image قدیمی را اثبات نمی‌کند. P2 تا P8 در
این مرحله اجرا نشدند. source commit و tag قدیمی imageها از یکدیگر تفکیک شوند.
دستورات بازتولید در بخش P1 [گزارش پذیرش](acceptance-report.md) ثبت شده‌اند.

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

## دفتر پیشرفت

| تاریخ | اقدام | نتیجه واقعی | قدم بعد |
|---|---|---|---|
| ۲۰۲۶-۱۰-۱۷ | مقایسه checkoutها و CAPO | این شاخه جلوتر؛ پنج فایل ثبت‌نشده در checkout دیگر شناسایی شد | P1 |
| ۲۰۲۶-۱۰-۱۷ | push مجاز CAPO و بررسی SHA مقصد | `2e8b914` روی CAPO تأیید شد؛ تست تازه اجرا نشد | تهیه سند مصوب کاربر |
| ۲۰۲۶-۱۰-۱۷ | ایجاد این دفتر | مستندسازی هدف، شواهد و gateها؛ بدون اجرای مراحل P1 تا P8 | تأیید P1 |
| ۲۰۲۶-۱۰-۱۷ | تطبیق تسک `01a001e5-1aef-7b01-ab9d-c4d538dfd0c7` | کد اختصاصی باقی نمانده؛ الزامات backup، تفکیک fresh/upgrade و یافته permissions به برنامه اضافه شد | تکمیل validation مربوط به P1 و سپس P2 |
| ۲۰۲۶-۱۱-۰۲ | تکمیل P1 با درخواست اجرای برنامه | نصب locked، ۳۶ تست و build موفق؛ خطای مالکیت build رفع شد؛ کد در `dae20bf` ثبت شد | تأیید جداگانه P2 / M4.1.3 |

برای ادامه، به همین جدول سطر افزوده شود و وضعیت مرحله مرتبط فقط پس از ثبت
نتیجه تغییر کند. این سند snapshot برنامه است؛ گزارش پذیرش مرجع جزئیات آزمایش
و دفتر ادعاها مرجع حدود ادعاهای پژوهشی باقی می‌مانند.
