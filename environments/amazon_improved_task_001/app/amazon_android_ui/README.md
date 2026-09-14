# DemoCart UI 2.1 — peach layout and recorded local evaluation

This is a separate Java/XML/SQLite Android app implementing the approved peach-header, six-tab design. The flow is local search or category browsing → product details → explicit add-to-cart → cart review. History, cart quantities, delivery location, display name, browsing history and simulated wallet credits persist on the device. SQLite work runs on one background executor; results are posted back to the Android UI thread.

This is an independent, offline prototype, not a verified pixel-exact copy of any current Amazon release. The user's final blueprint is the visual contract; it is not evidence of a universal Amazon layout. “Rufus” is labeled an offline demo, not a connection to Amazon AI. The original shoppingdemo benchmark app and its existing profile remain unchanged. The v2.0 milestone below was UI-only; the new opt-in v2.1 evaluation profile and recording changes are documented separately at the end of this file.

| Component / files | What changed and why | Evidence / how to verify |
|---|---|---|
| AndroidManifest.xml; res/values/styles.xml | Version 2.0 keeps the UI-only package identity. Native platform theme and font fallback; transparent status bar with inset padding; app delegates optional device intents. No INTERNET, CAMERA or RECORD_AUDIO permission in this app. Debuggable build is for local development, not production distribution. | Install the APK, inspect permissions and view the header. |
| res/layout/main.xml; layout_amazon_header.xml | Peach quick-action strip above an integrated search pill. Search icon sits inside the left edge, camera/mic inside the right edge, product-code scanner outside. Delivery capsule opens a real saved-location picker. Content scrolls above a fixed six-tab bar. | Home screenshot; search, camera/mic fallback and address checks. |
| res/layout/item_category_bubble.xml | Reusable circular category housing, real vector icon, compact label and category-specific click target. | Category taps filter the catalog. |
| res/layout/item_deal_card.xml | Rounded bordered cards, 1.5dp elevation, original product artwork, crimson discount chip, smaller raised currency symbol, strikethrough M.R.P. and explicit add button. | Deal cards and product results; add updates SQLite and badge. |
| res/layout/promo_banner.xml | Three promotions with swipe/dot selection. Banner opens its product detail, never silently adds it. Fictional Nimbus TV replaces an unlicensed branded product promotion. | Promotion switch and zero-cart-after-banner checks. |
| res/layout/item_nav.xml | Six distinct screens: Home, You, Wallet, Cart, Menu and Rufus. Active teal indicator, fixed Cart label, orange quantity badge; wallet dot disappears after opening Wallet. | Navigation and persisted wallet acknowledgement checks. |
| res/drawable/*.xml | Native XML shapes and original vector icons; no CardView, AppCompat or Material dependency required. | Compiled Android resources and screenshots. |
| src/.../MainActivity.java | Renders screens using XML templates. Controls perform real local navigation/actions. Handles search keyboard events, history suggestions, sorting, cart add/decrease/delete, address/profile forms, demo wallet, local catalog assistant, product preview and device fallbacks. Back stack and page state survive activity recreation. | Developer UI-check log and screenshots; no model or reward involved. |
| src/.../Store.java | Schema v2 non-destructively extends the original shopping.db. Preserves old cart rows; migrates rupees to integer paise. Adds history, settings and viewed tables. Transactional cart increments, a 99-per-product limit, bounded case-insensitive search history and try-with-resources cursor handling. Database closes after queued work. | 20 on-device storage checks passed, including a real v1 fixture upgraded to v2. |
| src/.../ProductArt.java | Original Java Canvas product illustrations: headphones, bottle, backpack, TV, fruit and organiser. A local animated TV preview uses no network/video stream. | Product and promo screens; no third-party images copied. |
| build_apk.sh | Fresh compile directory per build prevents stale classes. Java 8 compilation + D8 desugaring + Android resource packaging + debug signing. SDK/JDK installations remain read-only; all output/temp data stays here. | Signed APK in build/out/democart-ui.apk. |
| tests/StorageSmokeTest.java; tests/run_storage_tests.sh | Separate developer instrumentation APK tests migration, persistence and mutations using a uniquely named disposable database. Not a task verifier. | artifacts/v2/storage-tests.log; test APK is uninstalled afterward. |
| tests/check_device_ui.py | Host-side black-box developer UI checks. Uses ADB + Python standard library to tap real controls, inspect fresh accessibility XML and capture actual screenshots. Python is not part of the Android app. | artifacts/v2/ui-checks-final.log and artifacts/v2/final-screenshots/. |
| artifacts/v2/ | Build/run evidence only, excluded from Git. Previous version's PNGs remain under artifacts/ and previous APK is retained as before-redesign.apk. | Keep evidence; disposable emulator data can be recreated. |

## Device-dependent features and limits

Voice asks permission to delegate to the installed speech service and requests offline recognition. A recognized query executes search and is recorded in history. The device service may have its own data-handling behavior. If unavailable, the user can type the same query.

Lens opens the installed camera if available. A returned thumbnail is shown, then the user selects a product category. It deliberately does not claim visual recognition. Manual matching is available without camera support. QR/barcode search delegates to a compatible installed scanner, or accepts DC001–DC009 by manual entry. A toast is not treated as successful scanning.

Wallet credits are fictional and never pay for anything. The assistant performs deterministic local keyword/budget matching without an LLM. Video is a local illustrated product preview, not streaming. Pharma lists only a storage accessory, not medicines or medical advice. All discounts, ratings and availability are demonstration data.

Directly verified storage behavior is recorded in the storage-test log. Device UI results and captures are recorded separately. Recognition accuracy, compatible physical-device camera/scanner services, pixel parity with Amazon, broad device compatibility and any evaluation integration are not established by these app checks.

## Files

```text
amazon_android_ui/
├── AndroidManifest.xml
├── README.md
├── build_apk.sh
├── res/
│   ├── values/styles.xml
│   ├── layout/
│   │   ├── main.xml
│   │   ├── layout_amazon_header.xml
│   │   ├── item_category_bubble.xml
│   │   ├── item_deal_card.xml
│   │   ├── promo_banner.xml
│   │   └── item_nav.xml
│   └── drawable/                    # XML icons, cards, capsule, badges
├── src/com/primeintellect/amazonuidemo/
│   ├── MainActivity.java
│   ├── Store.java
│   └── ProductArt.java
├── tests/
│   ├── AndroidManifest.xml
│   ├── StorageSmokeTest.java
│   ├── run_storage_tests.sh
│   └── check_device_ui.py
├── build/out/democart-ui.apk         # Generated; ignored
└── artifacts/v2/                    # Actual UI evidence; ignored
```

## Build and inspect

From this directory:

```bash
bash build_apk.sh
```

Read-only defaults: SDK /data/Balram/android-sdk and JDK /usr/lib/jvm/java-21-openjdk-amd64. No Gradle, online dependency resolution or source checkout is needed. The application stack is exclusively Java, native XML resources and SQLite. The optional host-side UI-check helper uses Python's standard library.

Developer checks require a dedicated emulator. They deliberately exercise its local cart; never point the UI script at a user's existing shopping session. The storage checks use a separate disposable database and do not change the normal cart.

## Reference context

The current update follows the user's supplied visual specification, using original icons/artwork and system sans-serif instead of a proprietary font. The earlier reference review used:
- https://play.google.com/store/apps/details?id=in.amazon.mShop.android.shopping
- https://www.aboutamazon.com/news/retail/amazon-homepage-redesign-features
- https://github.com/mohamedezzeldeenhassanmohamed/Shopping-App-Android-Native-Java
- https://github.com/Amisha328/Mini-General-Store

These repositories are references, not copied dependencies or claims of exact current Amazon UI fidelity.

## Patch record

The original v1 build needed setAllCaps instead of setTextAllCaps and --release 8 compilation before D8 desugaring. This v2 update replaces the old flat layout and synchronous data access with the documented components above. Visual inspection caught left-aligned quick-action labels; they were centered. The developer UI check caught hardware Enter not executing search; the controller was corrected to consume the key-down submission event. Dialog selectors were made case-insensitive to match Android's uppercase button labels. Product-code errors moved from an overlapping platform tooltip to an inline, accessible validation label. Returning Home now clears the active search field without deleting its saved history. Final visual review found discount labels rounding upward; whole-percent savings now round down using (mrp - price) * 100 / mrp. Future patches must update this section together with their source changes and evidence.

The describe-systems format keeps the implementation, observed checks and unverified boundaries separate. That UI-only milestone ended at user review; the separately authorized recorded evaluation is described below.



## UI 2.0 handoff — historical

The final APK SHA-256 is `3488f3c58132e8cabe7bf7df32d60b2bd1f8c7566491d78ab0c5a68d46d136b6`. Its 20 storage checks passed again after the final build. The clean 27-check UI pass covered promotion selection, banner-to-detail navigation without adding, all three searches, cart arithmetic, cart review, wallet, history, address, category navigation, assistant screen, manual voice/Lens/code fallbacks, invalid-code feedback, correction, and persistence after force-stop/relaunch. Those 27 checks ran immediately before the final display-only discount-rounding correction, which was rebuilt and inspected separately. These are overlapping developer checks, not independent benchmark tasks or reward scores.

Final-APK captures are in `artifacts/v2/release-screenshots/`: `home.png`, `deals.png`, and `cart.png`, with matching UI XML. Additional screen captures from the complete interaction check remain in `artifacts/v2/final-screenshots/`. Earlier failed-check logs remain as evidence rather than being relabeled successful.

The dedicated API-33 emulator resolved camera and speech activities; it had no barcode-scanner activity. Actual photo capture and speech recognition accuracy were not tested. Manual fallback paths were tested. No task verifier or evaluation was invoked, no model was called, and nothing was uploaded to Prime or GitHub.


## Version 2.1: read-only evidence and a recorded local model episode

The new UI is still written in Java and Android XML and stores its data in SQLite. This patch does not replace the screens, add a real checkout, or turn the app into a cloud payment service. It connects this particular UI package to a separate, explicitly selected host-side evaluation profile. The older shoppingdemo task is not silently substituted.

The host creates a fresh random episode ID on a dedicated emulator. Passing that ID explicitly to MainActivity starts an empty evaluation cart and search history. Launching the app normally, without this extra, does not reset a user's cart. Reusing the same episode ID after a restart also preserves that episode. Each accepted cart mutation is recorded in the same SQLite transaction as the actual cart change, so a tap intention cannot stand in for a saved item.

| File | Exact logic added or changed |
|---|---|
| AndroidManifest.xml | App version becomes 2.1, code 3. Registers a provider under com.primeintellect.amazonuidemo.verifier with the Android DUMP read permission. It grants no task-writing API. |
| src/.../Store.java | Schema v3 adds eval_session and eval_events without dropping the existing tables. startEvaluation validates a random episode ID; add/decrease/remove/search write actual accepted mutation details atomically. viewport records the visible page, typed draft and committed query on the same serial worker. |
| src/.../MainActivity.java | Reads only the explicit episode_id launch extra. A text watcher and render callback queue viewport records; search text entry does not silently submit the search. UI design and ordinary navigation remain unchanged. |
| src/.../VerifierStateProvider.java | A fixed read-only query exposes products, cart, history, episode identity and committed events. Arbitrary query parameters and all writes are rejected. Episode/event revision is checked before and after reading to reject a changing snapshot. |
| ../../amazon_cart_001/specs/peach_task.json | Pins the new package, DC001/DC002/DC003, one of each, INR 4,997 total, separate searches and an open cart, with an 18-action limit. This is a separate profile from the original task.json. |
| ../../amazon_cart_001/harness/peach.py | Maps actual accessibility descriptions to stable action IDs; duplicate, disabled or off-screen targets are rejected. Captures fresh UI XML and a real PNG, brackets them with read-only provider snapshots, and compares those with an independently decoded SQLite file. All three reads must describe the same episode. |
| ../../amazon_cart_001/harness/peach_episode.py | Gives the actor its goal, screenshot and visible UI only. Executes the model's exact JSON action, without a reference-action replacement. Logs dispatch separately from actual app acceptance, rejects premature finish without stopping, and saves initial plus every-action evidence. |
| ../../amazon_cart_001/verification/peach.py | Replays actual committed events from reset, checks quantity changes and search-to-add provenance, and compares the reconstructed cart with saved rows. Evaluates the same fourteen policy IDs and unchanged five-slot support rule. Workflow progress remains separate from the episode reward. |
| ../../amazon_cart_001/harness/recording.py | Starts Android screenrecord before the first actor call. Uses PID-targeted graceful shutdown, retains genuine source MP4 segments and timestamps, and creates a compact H.264 playback MP4. Long runs rotate at 175 seconds and retain any boundary gaps explicitly; this is not a PNG slideshow. |
| ../../amazon_cart_001/peach_cli.py | Requires explicit --confirm-eval. Checks the selected OpenRouter model is currently free and supports images. Runs one local model episode, persists raw responses and provider/model receipts, finalizes video and writes a checksummed export. |
| ../../amazon_cart_001/integrations/prime_account.py | Reads existing terrano09 credentials without CLI configuration-directory creation or credential copying. Rejects another user or a team context. |
| ../../amazon_cart_001/integrations/peach_upload.py | Audits the frozen export before a remote write, includes all PNGs, JSON/XML logs and the actual MP4 in one sample, and verifies round-trip evidence. The evaluation name, model and description explicitly identify local-server execution, not Prime-hosted compute. |
| ../../tests/test_peach_profile.py | Adds thirteen regressions for a correct cart, wrong quantity, missing searches, missing or conflicting mutations, stale identity, incomplete cart, malformed actions and ambiguous targets. |

The scoring rule has not been retuned: each verifier returns PASS=1, FAIL=-1 or INVALID=0. Each policy has five expected slots; 0.5 + 0.1 times the passing count passes at >=0.7, except an all-INVALID policy returns zero. Any failed policy fails the episode. Two passing slots can therefore outweigh three failing or unavailable slots. This is the user's existing rule, not 70 percent agreement.

This first peach profile implements 34 of the 70 slots: two full-claim audit readers for each of eight execution policies, and three state readers for each of six outcome policies. The remaining 36 visual/additional readers explicitly return INVALID. SQLite, the read-only provider and the event journal are correlated channels from the same app database; they must not be described as independent proofs. Screenshots and video are saved for inspection, but saving a picture does not implement an OCR verifier.

### Validation and patch record, 2026-09-08

The first on-device provider check failed because Android beginTransaction uses BEGIN EXCLUSIVE even on a read-only database. That failed developer check is preserved under artifacts/peach_contract/20260908T145205Z_a3c5512c and in the task-local contract.log. Before any model call, the provider was changed to revision-bracketed read-only queries. The corrected APK hash is 8f91d7fe416b2c40794cfa867d9a29a1df6e15eee807840eb10adca5255f8c87.

The complete Python suite passes 59 tests using the already installed Prime Python environment. An initial invocation using system Python could not import verifiers; no task logic was changed to hide that dependency error. The corrected on-device developer contract completed eleven scripted actions and twelve PNGs, with all six workflow stages and a PASS verdict. Its actual 87.6-second, 540x1200 MP4 was decoded and visually inspected. This check has zero model calls and is not uploaded as a model evaluation. Evidence: ../../artifacts/peach_contract/20260908T145525Z_bf98cff5/.

Runtime settings, temporary data, encoding tools, logs and the disposable emulator are scoped under /data/Tirtha/browser-is-all-you-need/.agent_work/democart-peach-eval. The first emulator launch reported a default /tmp crash database despite TMPDIR. It was stopped; ANDROID_TMP and ANDROID_EMU_CRASH_REPORTING_DATABASE were then explicitly redirected under /data/Tirtha, and the replacement emulator log confirms the new crash path. The existing system ADB server was not stopped. SDK and JDK installations are read-only inputs.

Prime video round-trip storage and dashboard playback are separate claims. A verified stored MP4 does not prove that Prime's browser viewer offers an inline player. The final evaluation receipt records that boundary, along with the actual model name, reward, screenshots and video.



### Recorded model run and Prime handoff

The single model rollout completed on 2026-09-08: run 20260908T145806Z_ec428e1e, requested and returned model dots-studio/dots-3-note-preview:free, eleven model calls and eleven actor actions. Every provider receipt reports cost 0. No reference action was substituted. The final cart contains exactly DC001, DC002 and DC003, one each, with INR 4,997 subtotal; all fourteen policies passed under the existing threshold, and all six diagnostic stages completed. The episode reward is 1, and its elapsed local runtime was 167.42 seconds.

The evidence directory is ../../artifacts/peach_model_recorded/20260908T145806Z_ec428e1e/. frames/000/screen.png is the initial screen and frames/001 through frames/011 contain the original after-action PNGs, UI XML and SQLite evidence. video/segment-000.mp4 is the original recording; video/screen-recording.mp4 is the compact 153.9-second H.264 playback copy. All eleven action intervals fall inside the single recorded segment. The model video was decoded near the final cart state and visually inspected; it is a real recording, not a screenshot slideshow.

Prime evaluation: https://app.primeintellect.ai/dashboard/evaluations/h4ant6mjbyha8ac4k1dho9o1. Its owner is terrano09, model_name is dots-studio/dots-3-note-preview:free, status is COMPLETED, total_samples is 1, avg_score is 1.0, and is_hosted is false. The upload contains twelve PNGs, eighty-eight saved text logs and the MP4. API readback preserves the screenshot/video artifact hashes, log contents and reward. prime_upload.json and prime_samples.json preserve those receipts. Dashboard inline video playback has not been verified; the local MP4 remains directly downloadable.

The isolated emulator and its private ADB server on port 5044 were stopped. Its task-owned disposable AVD directory was removed, reclaiming approximately 1.2 GB; it can be recreated from the read-only system image. The pre-existing ADB server on port 5037 remains running. All APKs, model messages, JSON reports, screenshots, original video and upload receipts were retained. No Docker container was created, no hosted sandbox was launched, and no Git commit, push or PR update was performed for this request.



## Hosted publication patch — 0.3.1 (2026-09-09)

The latest peach UI now has a Prime-hosted loader, a bounded Android VM worker and real screenshot/video export. See the environment [README](../../README.md) for the exact file changes and launch boundaries. The app itself and the existing policy scoring were not changed. 76 offline tests passed, and wheel/sdist packaging passed.

The Hub package was uploaded as 0.3.0 and resolved through latest. Image preparation then exposed two CLI filtering problems: a bare double-star rule caused an IndexError, and directory exclusions omitted source folders. The 0.3.1 patch uses explicit parent-directory inclusions with no trailing slash; the actual CLI-generated archive now contains 98 files, all required source/build files, and no credentials, APKs, saved runs or caches. The retry of image build initiation returned Payment required before any build started. Do not describe this as a completed image or an evaluation. No further compute attempts are authorized by this publication step; fund and approve the smoke test separately.


## Hosted live-viewer integration — environment package 0.4.0 (2026-09-09)

The Python environment now includes an authenticated Prime HTTPS viewer for this same peach app. Its manual UI-inspection mode supports taps, drags, Back and focused text input; the model-evaluation mode independently rejects human controls. This patch changes the surrounding harness, not this app's Java/XML/SQLite behavior. It does not add Internet permission, cloud shopping, real payments or a task-completing side channel.

Browser rendering and security controls were checked offline with a historical PNG explicitly marked OFFLINE TEST. Prime image building remains blocked by the actual Payment required response and USD 0.00 balance; viewer-secret creation awaits approval. No real Prime live URL, smoke test, model run or dashboard-video rendering is claimed. See the [environment README](../../README.md#secured-prime-live-viewer--version-040-2026-09-09) for the new files, private access-link handling, current commands and validation boundaries.
