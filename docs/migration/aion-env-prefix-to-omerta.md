# برنامه مهاجرت namespace تنظیمات از AION به OMERTA

**وضعیت:** طرح بازبینی و چک‌لیست؛ مجوز اجرای rename نیست  
**مبنای بررسی:** branch `Radin/capo-r6-validation`، commit `1d9183b`  
**تاریخ inventory:** 2026-09-03

## تصمیم نام‌گذاری

هویت پایه محصول و runtime، `OMERTA` است. نام‌هایی مانند AION، CAPO و WARLOCK
edition/branch هستند و نباید namespace عمومی تنظیمات runtime را مالک باشند.
بنابراین مقصد تنظیمات اختصاصی محصول `OMERTA_*` است، نه `AION_*`.

این تغییر باید migration سازگار باشد، نه جایگزینی سراسری متن. در snapshot فعلی
و با کنار گذاشتن شواهد تاریخی `docs/migration/evidence/**`، جست‌وجوی tracked
repository حدود 929 رخداد، 162 token متمایز و 101 فایل درگیر را نشان می‌دهد.
این اعداد baseline هستند و باید در شروع اجرا دوباره تولید شوند.

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
| `AION_RUNTIME_LEASE_V1` | domain separator امضای HMAC است؛ تغییر آن تمام leaseهای در حال پرواز را نامعتبر می‌کند | ثابت بماند؛ تغییر فقط با protocol v2 و dual verification |
| headerهای `x-aion-*` | قرارداد wire بین Console، Gateway، Control و Runtime است | فعلاً ثابت؛ مهاجرت جداگانه با dual-read |
| package و RPCهای `aion.v1` | تغییر breaking برای protobuf/gRPC و generated clients | ثابت تا schema migration مستقل |
| مسیرهای `.aion/*` | rename ناگهانی state و secretهای موجود را orphan می‌کند | فقط با copy/verify/rollback مستقل |
| localStorageهای `aion-*` | تنظیمات UI کاربران reset می‌شود | dual-read و one-time browser migration مستقل |
| volume، network، container و systemd unitهای `aion-*` | داده یا service موجود ظاهراً گم می‌شود | rename عملیاتی مستقل، بدون حذف volume |
| package/image/chart names | روی lockfile، registry و deployment identity اثر دارد | خارج از این مرحله |
| DB user، database، bucket و hostnameهای دارای `aion` | ممکن است شناسه persistent یا credential باشند | بدون migration داده تغییر نکنند |
| `docs/migration/evidence/**` | شواهد تاریخی باید immutable بماند | تغییر نکند |
| استانداردهایی مثل `DATABASE_URL`, `NEXTAUTH_*`, `VAULT_*`, `HTTP_PROXY` | متعلق به ecosystem خارجی هستند | تغییر نکنند |

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

کلید R6.15 یعنی `AION_RUNTIME_LEASE_HMAC_KEY` باید به
`OMERTA_RUNTIME_LEASE_HMAC_KEY` مهاجرت کند. چون secret است، mismatch دو نام باید
بدون چاپ مقدار باعث fail-closed شود. همین قاعده برای admin tokenها، JWT/TLS،
Vault credentials، DSNهای credentialدار و کلید رمزگذاری Control لازم است.

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
  OMERTA_RUNTIME_LEASE_HMAC_KEY: >-
    ${OMERTA_RUNTIME_LEASE_HMAC_KEY:-${AION_RUNTIME_LEASE_HMAC_KEY:-}}
```

این الگو فقط پس از تست رفتار Compose در حالت unset، blank، old-only، new-only و
both-conflicting پذیرفته شود. برای blank باید تصمیم هر کلید صریح باشد؛ `${VAR:-x}`
و `${VAR-x}` رفتار یکسان ندارند.

## ترتیب اجرای بدون flag day

### M0 ـ تثبیت inventory و policy

- فهرست machine-readable از کلیدهای فعال تولید شود.
- owner، نوع، required/default، secret بودن و محل مصرف هر کلید ثبت شود.
- موارد غیر-env و evidence تاریخی از rename list حذف شوند.
- تست معماری اضافه شود که مصرف مستقیم جدید `AION_*` را خارج از compatibility
  module ممنوع کند.

### M1 ـ resolverهای dual-read

- helper مشترک برای Python، Gateway/Console TypeScript و Runtime Rust ساخته شود.
- `OMERTA_*` canonical و `AION_*` alias deprecated باشد.
- conflict test و redacted diagnostics قبل از تغییر templateها اضافه شود.
- R6.15 ابتدا برای lease key/TTL/state/endpoint مهاجرت شود، زیرا failure آن مسیر
  execution را fail-closed می‌کند.

### M2 ـ deployment writers

- `.env.example`, `dev.env`, Compose، install scripts و bundle envها به نام جدید
  بنویسند ولی ورودی قدیمی را در مرز host بپذیرند.
- `deploy/native/env/contract.json` با schema version جدید منتشر شود؛ بخش‌های
  `required`, `secret_keys`, `credential_url_keys`, `loopback_keys` و `port_keys`
  هم‌زمان تغییر کنند.
- systemd، Kubernetes Secret/ConfigMap و CI secrets با dual-name rollout هماهنگ
  شوند. secret واقعی هرگز خودکار کپی یا چاپ نشود.

### M3 ـ مصرف‌کنندگان canonical-only در داخل process

- Compose و systemd فقط `OMERTA_*` را به process تزریق کنند.
- alias قدیمی فقط در resolver ورودی یا installer باقی بماند.
- warning telemetry باید فقط key name، component و source alias را ثبت کند.
- یک run کامل old-only و یک run کامل new-only انجام شود.

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

- [ ] هیچ `os.getenv`, `process.env` یا `std::env::var` مستقیم خارج از resolver
  مجاز باقی نمانده است.
- [ ] هر secret قدیمی دقیقاً یک mapping جدید دارد و value در log/diff نیست.
- [ ] تمام templateها، validators، Compose و service managerها نام یکسان دارند.
- [ ] healthcheckها همان port/bind جدید را می‌خوانند.
- [ ] Console هنوز مستقیم Control/Runtime را صدا نمی‌زند.
- [ ] Runtime key فقط بین Control و Runtime است و credential مدیریتی نیست.
- [ ] نام‌های protocol، header، protobuf و HMAC domain separator تصادفی عوض نشده‌اند.
- [ ] هیچ volume/path/database/bucket قدیمی حذف یا orphan نشده است.
- [ ] old-only و new-only هر دو executable evidence دارند.
- [ ] conflict و malformed configuration واقعاً non-zero/fail-closed هستند.
- [ ] Windows PowerShell، Linux shell، Docker و native static gates پوشش دارند.
- [ ] grep نهایی فقط compatibility allowlist و historical evidence را نشان می‌دهد.

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
