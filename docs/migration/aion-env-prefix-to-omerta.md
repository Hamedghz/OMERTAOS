# برنامه مهاجرت namespace تنظیمات از AION به OMERTA

**وضعیت:** M0 تا M3 و زیرمرحله M3.1 تکمیل و به‌صورت static/کانتینری ولیدیت
شدند؛ catalog قدیمی در M3.2 قرنطینه شد. پذیرش محدود Docker در M4 با یک Runtime،
smoke موفق و ماندگاری Qdrant پس از recreate انجام شد؛ پذیرش کامل old-only/new-only
و restore مستقل هنوز باز است. جزئیات در [گزارش پذیرش M4](../capo/acceptance-report.md)
ثبت شده و حذف aliasهای قدیمی هنوز مجاز نیست.
**مبنای M2:** branch `Radin/omerta-env-namespace`، checkpoint
`4e1b89e3c36770dc7d06919b1f401ce526e1345c`
**تاریخ inventory:** 2026-09-04

## تصمیم نام‌گذاری

هویت پایه محصول و runtime، `OMERTA` است. نام‌هایی مانند AION، CAPO و WARLOCK
edition/branch هستند و نباید namespace عمومی تنظیمات runtime را مالک باشند.
بنابراین مقصد تنظیمات اختصاصی محصول `OMERTA_*` است، نه `AION_*`.

این تغییر باید migration سازگار باشد، نه جایگزینی سراسری متن. baseline قابل
بازتولید M2 با کنار گذاشتن شواهد تاریخی `docs/migration/evidence/**` شامل 840
رخداد، 164 token متمایز و 82 فایل درگیر است. جزئیات owner، نوع، default policy،
secret classification و مسیرهای شواهد در
[`aion-env-inventory.json`](./aion-env-inventory.json) ثبت شده و با
`scripts/audit_environment_namespace.py` بازتولید می‌شود.

## مرز تغییر

### در محدوده این migration

- متغیرهای محیطی اختصاصی محصول با پیشوند `AION_`؛
- interpolationهای Compose و shell/PowerShell؛
- env templateها، contractها و validatorها؛
- خواندن تنظیمات در Python، TypeScript و Rust؛
- secret classification، URL/port/loopback classification و redaction؛
- تست‌ها، smoke scripts، CI wrappers و مستندات فعال.

### خارج از rename خودکار

موارد زیر ممکن است در آینده rebrand شوند، اما قرارداد مستقل دارند و نباید با
replace عمومی `AION -> OMERTA` تغییر کنند:

| مورد | خطر تغییر مستقیم | تصمیم این migration |
|---|---|---|
| `AION_RUNTIME_LEASE_V1` | domain separator امضای HMAC است | در R6.15 پیش از provisioning پذیرفته‌شده مستقیماً به `OMERTA_RUNTIME_LEASE_V1` منتقل شد؛ alias ندارد |
| headerهای `x-aion-*` | قرارداد wire بین Console، Gateway، Control و Runtime است | فعلاً ثابت؛ مهاجرت جداگانه با dual-read |
| package و RPCهای `aion.v1` | تغییر breaking برای protobuf/gRPC و generated clients | ثابت تا schema migration مستقل |
| مسیرهای `.aion/*` | rename ناگهانی state و secretهای موجود را orphan می‌کند | فقط با copy/verify/rollback مستقل |
| localStorageهای `aion-*` | تنظیمات UI کاربران reset می‌شود | dual-read و one-time browser migration مستقل |
| volume، network، container و systemd unitهای `aion-*` | داده یا service موجود ظاهراً گم می‌شود | rename عملیاتی مستقل، بدون حذف volume |
| package/image/chart names | روی lockfile، registry و deployment identity اثر دارد | خارج از این مرحله |
| DB user، database، bucket و hostnameهای دارای `aion` | ممکن است شناسه persistent یا credential باشند | بدون migration داده تغییر نکنند |
| `docs/migration/evidence/**` | شواهد تاریخی باید immutable بماند | تغییر نکند |
| استانداردهایی مثل `DATABASE_URL`, `NEXTAUTH_*`, `VAULT_*`, `HTTP_PROXY` | متعلق به ecosystem خارجی هستند | تغییر نکنند |

سه استثنای نگاشت در M0 صریح شده‌اند:

- `AION_PROFILE` به `OMERTA_GATEWAY_PROFILE` می‌رود؛ `OMERTA_PROFILE` از قبل
  profile مربوط به Runtime با مقادیر `lite/full/enterprise` است.
- aliasهای `AION_VAULT_*` در صورت وجود معادل استاندارد به `VAULT_*` می‌روند و
  نباید به `OMERTA_VAULT_*` تکثیر شوند.
- `AION_GATEWAY_ADMIN_TOKEN` و `AION_ADMIN_TOKEN` یک compatibility group برای
  `OMERTA_GATEWAY_ADMIN_TOKEN` هستند. `OMERTA_ADMIN_TOKEN` موجود در Windows
  Bridge به‌دلیل تفاوت header و semantics احراز هویت، مقصد خودکار این migration
  نیست.

## نقاط پرخطر فعلی

خانواده‌های بزرگ inventory شامل حدود 30 کلید `AION_CONTROL_*`، 22 کلید
`AION_RUNTIME_*`، 10 کلید `AION_VAULT_*`، 10 کلید `AION_TLS_*`، 9 کلید
`AION_GATEWAY_*` و مجموعه‌های DB، Console، Docker، backup و telemetry هستند.

| سطح | مسیرهای اصلی برای بازبینی | شکست محتمل |
|---|---|---|
| Console | `console/lib/serverConfig.ts`, `gatewayConfig.ts`, `gatewayClient.ts`, `prisma.ts`, `console/app/api/system/**` | قطع Gateway، auth داخلی، Prisma یا health |
| Gateway | `gateway/src/config.ts`, `auth/index.ts`, `redis.ts`, `telemetry.ts`, `protoPath.ts`, `server/**` | bypass یا fail auth، CORS/TLS اشتباه، قطع Control/Redis |
| Control | `control/config.py`, `app/network/**`, `app/service_auth.py`, `app/serve.py`, `scheduling/**`, `orchestration/runtime_dispatch.py` | DSN اشتباه، از دست رفتن secret، scheduler یا lease fail |
| Runtime | `runtime-daemon/src/config.rs`, `lib.rs`, `cluster/resource_report.rs`, `security/lease.rs` | bind/health اشتباه، node mismatch، رد همه executionها |
| Docker | `deploy/docker/compose/{quickstart,local,full,catalog}*.yml`, `deploy/docker/scripts/**` | مقدار host وارد container نشود یا default ناامن فعال شود |
| Native/systemd | `deploy/native/env/**`, `deploy/native/systemd/**`, `deploy/CAPO/**` | EnvironmentFile معتبر باشد ولی unit کلید قدیمی بخواند |
| Kubernetes | `deploy/kubernetes/**` | Secret/ConfigMap و Deployment نام متفاوت بخوانند |
| CI و ابزار توسعه | `.codex/scripts/**`, `Makefile`, workflowها و test runners | CI سبز محلی ولی قرمز در runner دیگر |
| Test contracts | `tests/architecture/**`, `tests/native/**`, `tests/control/**`, تست‌های Gateway/Console/Runtime | alias یا conflict policy بدون پوشش بماند |

کلید R6.15 پیش از provisioning پذیرفته‌شده مستقیماً به
`OMERTA_RUNTIME_LEASE_HMAC_KEY` مهاجرت کرده و مطابق ADR 0002 alias قدیمی ندارد.
برای admin tokenها، JWT/TLS، Vault credentials، DSNهای credentialدار و کلید
رمزگذاری Control، rolloutهای بعدی باید conflict را بدون چاپ مقدار fail-closed
کنند.

## قرارداد سازگاری

برای هر تنظیم، یک resolver مرکزی در owner همان زبان ایجاد شود:

1. فقط `OMERTA_*` وجود دارد: مقدار canonical استفاده شود.
2. فقط `AION_*` وجود دارد: موقتاً پذیرفته شود و warning فقط نام کلید را ثبت کند.
3. هر دو وجود دارند و برابرند: مقدار `OMERTA_*` استفاده شود؛ مقدار log نشود.
4. هر دو وجود دارند و متفاوتند: startup یا همان operation به‌صورت fail-closed
   متوقف شود. برای secret، endpoint، auth، TLS، DSN و lease هیچ precedence خاموش
   مجاز نیست.
5. هیچ‌کدام وجود ندارد: همان required/default contract فعلی اعمال شود؛ rename
   نباید default امنیتی را ضعیف کند.

نمونه Compose باید host compatibility را در لایه interpolation حل کند و داخل
container فقط نام canonical را صادر کند:

```yaml
environment:
  OMERTA_RUNTIME_LEASE_TTL_SECONDS: >-
    ${OMERTA_RUNTIME_LEASE_TTL_SECONDS:-${AION_RUNTIME_LEASE_TTL_SECONDS:-45}}
```

این الگو فقط پس از تست رفتار Compose در حالت unset، blank، old-only، new-only و
both-conflicting پذیرفته شود. برای blank باید تصمیم هر کلید صریح باشد؛ `${VAR:-x}`
و `${VAR-x}` رفتار یکسان ندارند.

## ترتیب اجرای بدون flag day

### M0 ـ تثبیت inventory و policy

- [x] فهرست machine-readable از 164 token baseline تولید شد.
- [x] owner، نوع، required/default policy، secret بودن و محل مصرف ثبت شد.
- [x] موارد غیر-env و evidence تاریخی از rename list جدا شدند.
- [x] تست معماری و allowlist بازبینی‌شده، مصرف مستقیم جدید `AION_*` را خارج از
  compatibility module ممنوع می‌کند.

### M1 ـ resolverهای dual-read

- [x] helper typed برای Python، Gateway/Console TypeScript و Runtime Rust ساخته شد.
- [x] `OMERTA_*` canonical و `AION_*` alias deprecated با warning نام‌محور است.
- [x] ماتریس old-only، new-only، equal، conflict، unset، blank، malformed و
  redaction پیش از تغییر templateها اضافه شد.
- [x] lease TTL/max TTL/state به helperهای typed منتقل شد؛ HMAC key و domain
  پذیرفته‌شده R6.15 canonical-only باقی ماندند.
- [x] `AION_PROFILE` با معنای درست به `OMERTA_GATEWAY_PROFILE` و
  `AION_GATEWAY_URL` به `OMERTA_GATEWAY_URL` متصل شد.

پیاده‌سازی‌های M1 در `shared/config/environment.py`،
`gateway/src/config/environment.ts`، `console/lib/environment.ts` و
`runtime-daemon/src/environment.rs` قرار دارند. M1 خود resolverها و مصرف‌های بذر
را اضافه کرد؛ writerهای deployment و مصرف‌کنندگان لازم برای مسیر canonical در
M2 مهاجرت داده شدند.

### M2 ـ deployment writers

- [x] `.env.example`، `dev.env`، installerها و bundle envها نام canonical را
  منتشر می‌کنند. Compose ورودی canonical/قدیمی host را می‌پذیرد و برای readerهای
  باقیمانده تا M3 همان نام قدیمی process را bridge می‌کند.
- [x] `deploy/native/env/contract.json` و `.env.schema` با schema version جدید و
  نگاشت deprecated alias منتشر شدند.
- [x] systemd، Kubernetes، CAPO و CI wrapperهای درگیر با rollout دو نام هماهنگ
  شدند؛ هیچ شناسه persistent، volume، database، bucket، wire header یا RPC
  rename نشد.
- [x] preflight و migrator اتمیک، conflict را fail-closed و فقط با نام کلید گزارش
  می‌کنند؛ secret قدیمی بدون مقدار canonical برابر، خودکار کپی یا بازنویسی نمی‌شود.
- [x] مصرف‌کنندگان لازم در Console، Gateway، Control و Runtime dual-read شدند تا
  writerهای canonical باعث قطع مسیر اصلی نشوند. خواننده‌های باقیمانده برای M3
  در allowlist بازبینی‌شده نگه داشته شده‌اند.
- [x] dependency HTTP مربوط به تست و اجرای Control در image به‌طور صریح قفل شد.
- [x] تست‌های معماری، Python، Gateway، Console و Runtime و render سه Compose
  پیکربندی به‌صورت sequential اجرا شدند.
- [ ] imageهای برنامه rebuild و stack زنده اجرا نشده‌اند؛ این‌ها gateهای M4 هستند.

PowerShell روی host فعلی در دسترس نبود. قرارداد فایل‌های PowerShell با تست‌های
static مخزن بررسی شد، اما اجرای مستقیم `pwsh` به‌عنوان gate unavailable ثبت می‌شود.
Compose فقط render شده است و این نتیجه شواهد پذیرش زنده Docker نیست.

#### شواهد اجرایی M2

- audit نهایی: 164 token، 840 رخداد در 82 فایل و 154 direct reader قدیمی در
  allowlist بازبینی‌شده؛ gate بدون drift پاس شد.
- preflight: حالت canonical-only، old-only و equal پاس شدند؛ conflict با exit
  code برابر 1 و diagnostic فقط شامل نام کلیدها رد شد.
- Python: معماری 97 passed و یک completion gate عمدی deselected؛ Control برابر
  103 passed و 1 skipped؛ native برابر 75 passed؛ resolver مشترک 6 passed.
- Gateway: build و lint پاس؛ 7 فایل تست و 21 تست پاس.
- Console: 12 فایل تست و 28 تست پاس؛ production build کامل پاس.
- Runtime: `cargo fmt --check` پاس و 21 تست `--all-targets --locked` پاس.
- Compose: پیکربندی quickstart یک worker، override دو worker، full و local فقط
  با `config --quiet` render شدند.
- lint رسمی Python با `ruff 0.15.20` پاس شد. اجرای مستقیم PowerShell unavailable
  بود و هیچ image یا stack زنده‌ای در M2 ساخته یا اجرا نشد.

### M3 ـ مصرف‌کنندگان canonical-only در داخل process

- [x] چهار Compose canonical و templateهای فعال فقط `OMERTA_*` را به process
  تزریق یا منتشر می‌کنند؛ fallback میزبان قدیمی در مرز Compose حفظ شده است.
- [x] alias قدیمی در readerهای اجرایی فقط از resolver مشترک خوانده می‌شود و
  scan مستقیم Python/TypeScript/Rust صفر است.
- [x] warning و conflict فقط نام کلید canonical/legacy را ثبت می‌کنند و value
  در diagnostic ظاهر نمی‌شود.
- [x] preflightهای canonical-only، old-only، equal، conflict و malformed در
  validation image اجرا شدند؛ اجرای زنده old-only/new-only جزو M4 است.

#### M3.1 ـ محیط validation کانتینری

- [x] Python `3.11.14`، dependencyهای Python و ابزارهای `pytest`، `ruff`،
  `mypy` و `bandit` با hash در `control/requirements.validation.lock` قفل شدند.
- [x] validation image مستقل، non-root و شامل `git`، `curl` و `jq` است؛ image
  تولیدی Control با ابزارهای توسعه مخلوط نشد.
- [x] تولید lock، build، تست و lint از Makefile و بدون نصب ابزار روی host قابل
  اجرا هستند.
- [x] fake module موقت Qdrant حذف شد و تست با `qdrant-client` واقعی اجرا شد.
- [x] ترتیب smoke طوری اصلاح شد که port نامعتبر پیش از dependency check رد شود.

در شروع M3.1 سه workaround قبلی ثبت شد: نصب موقت و غیرقفل‌شده pytest در
کانتینر موجود، نبودن `qdrant-client` و جعل ماژول آن در تست، و اجرای دستی
`prisma:generate` خارج از پروتکل reproducibility. هر سه تعمیر شدند: ابزار Python
از lock/image رسمی می‌آید، Qdrant واقعی import می‌شود، و مرحله Prisma در سند و
CI صریح است. نصب اولیه lock با `pip-compile` در backtracking طولانی متوقف شد و
اولین اجرای Make target نیز به‌علت timeout شبکه exit 2 داشت؛ retry با timeout
صریح پاس شد.

#### شواهد اجرایی M3

- inventory: تعداد ثابت 164 token، برابر 527 رخداد در 80 فایل و 93 fallback
  قدیمی که همگی به مرزهای Compose بازبینی‌شده محدود شده‌اند.
- چهار render canonical شامل quickstart یک Runtime، override دو Runtime، full و
  local با exit 0 پاس شدند؛ بررسی JSON مؤثر نیز صفر کلید process با `AION_*`
  نشان داد. این نتیجه پذیرش زنده نیست.
- Python کامل در validation image: `297 passed`، `3 skipped` و 9 warning؛ تست
  concurrency PostgreSQL که در suite عمومی به DSN وابسته است جداگانه روی
  PostgreSQL موقت و بدون volume اجرا شد و `1 passed` بود.
- دو skip باقیمانده مربوط به Agent Catalog و stream service قدیمی و از قبل
  رسماً قرنطینه هستند؛ بازیابی آن namespaceها جزو این migration نیست.
- Ruff کامل exit 0 و Bandit production exit 0 بدون finding پاس شدند.
- Gateway: 25 تست در 8 فایل، build و lint پاس؛ `npm ci` دو advisory حل‌نشده
  شامل یک moderate و یک high گزارش کرد و هیچ `audit fix` خودکاری اجرا نشد.
- Console: 30 تست در 13 فایل و production build پس از Prisma generate پاس شد.
- Runtime: format پاس و 23 تست شامل 19 unit و 4 integration پاس شد؛ این نتیجه
  اثبات موفقیت isolation لینوکس نیست.

### M3.2 ـ catalog قدیمی

`deploy/docker/compose/catalog.yml` همچنان به دو Dockerfile حذف‌شده اشاره دارد و
سه قرارداد قدیمی اختصاصی دارد. این فایل از مجموعه Compose canonical جدا و در
M0 قرنطینه شده است؛ تا تعیین مالکیت worker و topology جدید، render/build آن یک
gate پاس‌شده محسوب نمی‌شود و نباید برای ادعای «تمام Composeها سالم‌اند» استفاده
شود.

### M4 ـ پذیرش و deprecation gate

- Quickstart با یک Runtime و volumeهای موجود stop/start شود؛ `down -v` ممنوع.
- canonical request path، lease fencing/restart، persistence، backup و smoke
  دوباره اجرا شوند.
- native plan فقط به‌صورت static بررسی شود تا مجوز جداگانه‌ی systemd/sudo صادر
  شود.
- حذف alias قدیمی تنها زمانی مجاز است که telemetry/scan هیچ مصرف فعال نشان ندهد.

### M5 ـ حذف کنترل‌شده alias

- در checkpoint جداگانه، aliasهای `AION_*` حذف شوند.
- architecture gate وجود هر مصرف runtime جدید را رد کند.
- evidence تاریخی، wire identifiers، state paths و service identities همچنان
  خارج از حذف باقی بمانند مگر migration مستقل آن‌ها تأیید شده باشد.

## ماتریس تست اجباری برای هر کلید

| سناریو | نتیجه مورد انتظار |
|---|---|
| old-only | کارکرد سازگار + warning بدون value |
| new-only | کارکرد canonical بدون warning deprecated |
| هر دو برابر | موفق، بدون افشای مقدار |
| هر دو متفاوت | fail-closed با ذکر نام دو کلید، بدون value |
| unset | default یا خطای required دقیقاً مطابق contract |
| blank | رفتار صریح و تست‌شده؛ معادل unset فرض نشود |
| مقدار malformed | رد شدن قبل از side effect |
| secret در repr/log/error | هیچ value یا مشتق قابل بازیابی دیده نشود |

## validation gates

ترتیب زیر باید sequential و روی host محدود فعلی اجرا شود:

```bash
git grep -nE '\bAION_[A-Z0-9_]+' -- ':!docs/migration/evidence/**'
python3 scripts/audit_environment_namespace.py --check
python -m pytest tests/architecture -q -k 'not test_structure_migration_gate'
python -m pytest tests/control tests/native -q
npm run build --prefix gateway
pnpm --dir console test --config vitest.config.mts
pnpm --dir console build
cargo fmt --manifest-path runtime-daemon/Cargo.toml --check
cargo test --manifest-path runtime-daemon/Cargo.toml --all-targets --locked
docker compose -p compose --project-directory . \
  -f deploy/docker/compose/quickstart.yml config --quiet
```

سپس با یک Runtime و بعد از کنترل RAM/disk:

- build ترتیبی Control و Runtime؛
- Quickstart smoke؛
- Console -> Gateway -> Control -> Runtime؛
- negative auth و forged headers؛
- lease با old-only، new-only و conflict؛
- restart Runtime و اثبات حفظ fence؛
- restart PostgreSQL/Control و اثبات persistence؛
- shutdown بدون `down -v`.

## چک‌لیست بازبینی دستی

- [x] هیچ `os.getenv`, `process.env` یا `std::env::var` مستقیم خارج از resolver
  مجاز باقی نمانده است.
- [x] هر secret قدیمی دقیقاً یک mapping جدید دارد و value در log/diff نیست.
- [x] templateها، validators و چهار Compose canonical نام process یکسان دارند.
- [x] healthcheckهای canonical همان port/bind جدید را می‌خوانند.
- [x] Console هنوز مستقیم Control/Runtime را صدا نمی‌زند.
- [x] Runtime key فقط بین Control و Runtime است و credential مدیریتی نیست.
- [x] نام‌های protocol، header، protobuf و HMAC domain separator تصادفی عوض نشده‌اند.
- [x] هیچ volume/path/database/bucket قدیمی حذف یا orphan نشده است.
- [ ] old-only و new-only هر دو executable evidence دارند.
- [x] conflict و malformed configuration واقعاً non-zero/fail-closed هستند.
- [ ] Windows PowerShell، Linux shell، Docker و native static gates پوشش دارند.
- [x] grep نهایی فقط compatibility boundary و historical evidence را نشان می‌دهد.

## rollback

rollback باید configuration-first باشد و تاریخچه Git بازنویسی نشود:

1. container/service جدید متوقف شود، بدون حذف volume؛
2. env قبلی `AION_*` از backup محلی برگردد؛
3. commit قبلی checkout یا revert عادی شود؛
4. Compose render و smoke old-only اجرا شود؛
5. persistence و lease state بررسی شود؛
6. علت rollback بدون secret value در acceptance report ثبت شود.

تا پایان M4 نباید `AION_*` از resolverها حذف شود. تا پایان migration مستقل wire و
storage نیز نباید `x-aion-*`, `aion.v1`, `.aion`, نام volumeها یا شواهد تاریخی با
این پروژه rename شوند.

## موارد quarantine شده در M0

- `deploy/docker/compose/catalog.yml` هنوز به مسیرهای حذف‌شده `aion/control` و
  `aion/worker` اشاره می‌کند؛ tokenهای اختصاصی آن تا تعیین مالک جدید مهاجرت
  نمی‌کنند.
- metadata بسته `aion-core` به entrypoint موجودی اشاره می‌کند که روی snapshot
  فعلی import نمی‌شود؛ rename package پیش از تعمیر مستقل packaging ممنوع است.
- Windows Bridge از `OMERTA_ADMIN_TOKEN` به‌صورت Bearer استفاده می‌کند، در حالی
  که Gateway credential داخلی را از header دیگری می‌پذیرد؛ این مورد یک تغییر
  auth جدا و نیازمند تست امنیتی است.
