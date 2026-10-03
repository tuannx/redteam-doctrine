# Alignment G-A-E — tối ưu redteam-doctrine cho 3 mặt trận điểm cao nhất

Date: 2026-10-02. Source cases: `arcade-attest/100-decision-cases.md` + `CATEGORY-AND-SCORING.md`.
Target repo: `tuannx/redteam-doctrine` (branch `mvp/pr-redteam-step1`).

Ba nhóm được chọn không phải 3 nhóm rời nhau. Chúng là 1 pipeline duy nhất:

```text
G. AI sinh code  ->  A. PR/CI chặn cổng  ->  E. Maintainer xử lý hàng đợi
(agent viết)        (máy ra verdict)       (người chỉ xem cái máy không chắc)
```

redteam-doctrine hiện tại đã có xương của A (PR gate, verdict.json, counters). Tối ưu lần này: biến doctrine từ "1 gate cho mọi PR" thành **3 lane có contract riêng**, dùng chung 1 Decision Core, chung 1 verdict schema.

Luật không đổi: name is contract, text is evidence, no LLM judge, owner merge = acceptance.

---

## 1. Bản đồ 30 cases -> gate trong doctrine

### G. AI-Generated Code Gate (#61-70) — lane AGENT

Agent chạy gate *trước khi mở PR*, ngay trên máy của agent. Khác người ở 1 điểm: agent không được phép "mở PR rồi nhờ người xem hộ" với trạng thái WARN. Agent phải tự sửa đến PASS hoặc dừng và báo owner.

| # | Case | Predicate / Counter trong doctrine | Hành động khi vi phạm |
|---|---|---|---|
| 61 | Agent tạo god module | `component_entity_cap` -> `largestComponentEntities`, `largestFileAddedLines` | BLOCK, agent tự tách file rồi chạy lại |
| 62 | Agent lén tạo cycle / smell mới | `no_new_smells` -> `newSmells` (zero tolerance) | BLOCK, không mở PR |
| 63 | Khi nào agent được tự merge | `routing.selfMergeEligible` = PASS 2 run liên tiếp + `responsibilityShifts=0` + actor là agent đã đăng ký | Chỉ owner bật trong policy; mặc định false |
| 64 | So 2 agent cùng task, chọn bản sạch | Chạy core 2 lần, so `(newSmells, responsibilityShifts, netLocChanged)` theo thứ tự từ điển | Bản thua bị đóng, không mở PR |
| 65 | Agent phình 1 file khổng lồ | `largestFileAddedLines` > policy `maxFileAddedLines` | BLOCK, bắt tách theo responsibility |
| 66 | Agent thêm thư viện lạ | `newDependencies > 0` và PR không có Decision Record justification | WARN với người, BLOCK với agent (agent phải tự bổ sung justification có evidence) |
| 67 | Đổi prompt làm agent tốt/xấu đi | Aggregate verdict trên N task: tỉ lệ PASS, trung bình `newSmells` | Prompt nào PASS rate thấp hơn bị loại, số lưu vào history |
| 68 | Chỉ trả tiền khi PASS | Verdict PASS + attestation hash là điều kiện escrow/contract đọc | Consumer ngoài doctrine; doctrine chỉ phát hành verdict ký được |
| 69 | Hồ sơ uy tín của agent thuê ngoài | Chuỗi verdict theo `actor.app` + `actor.agentId` qua thời gian | Marketplace/owner đọc history, không đọc lời tự giới thiệu |
| 70 | Multi-agent vượt ranh giới responsibility | `responsibilityShifts` tính theo phần việc đã đăng ký của từng agent | BLOCK + route owner; EXT, cần đăng ký responsibility map |

Field mới cho G (vào schema trước khi code emit): `actor.kind` (`human|agent`), `actor.agentId`, `actor.taskId`, `actor.attempt`.

### A. PR & CI Merge Gate (#1-10) — lane PR

Đây là lane gốc của doctrine, chạy trong GitHub Action, blocking. Tối ưu: verdict không chỉ pass/warn/block mà kèm `routing` để CI và người biết bước tiếp theo, khỏi đọc prose.

| # | Case | Predicate / Counter | Verdict rule |
|---|---|---|---|
| 1 | Merge có tạo smell mới | `no_new_smells` | `newSmells>0` -> BLOCK |
| 2 | Shift responsibility quá tay | `max_responsibility_shifts` | Vượt policy -> WARN, vượt 2x -> BLOCK |
| 3 | Component phình quá cap | `component_entity_cap` | `largestComponentEntities>cap` -> BLOCK |
| 4 | PR xoá lớn có an toàn | shifts=0, newSmells=0, netLocChanged âm lớn | PASS + nhãn `safe-large-deletion` |
| 5 | Migration làm lệch responsibility | Liệt kê shifts trong findings | WARN kèm evidence từng shift |
| 6 | Thêm tính năng, metrics có xấu đi | metrics delta (RCI/TurboMQ) trong evidence pack | Metrics xấu + smells mới -> BLOCK; metrics flat -> PASS |
| 7 | Dependency bị cấm (UI->DB) | `layerContractViolations` (import-linter/dependency-cruiser) | >0 -> BLOCK (EXT: cần edge diff đầy đủ) |
| 8 | Coupling ngược tầng | `layerContractViolations` | >0 -> BLOCK |
| 9 | "Refactor nhỏ" lén tạo cycle | `newSmells` (cycle là 1 smell class) | BLOCK |
| 10 | Hàng đợi PR, merge cái nào trước | `routing.triagePriority` (xem mục 3) | PASS lane xếp theo priority tăng dần |

### E. Monorepo & OSS Maintainer (#41-50) — lane MAINTAINER

Maintainer không đọc từng PR. Maintainer đọc *hàng đợi đã được máy sắp*. Doctrine tối ưu cho E bằng cách biến verdict thành quyết định phân luồng, và đếm theo package thay vì theo file.

| # | Case | Tính năng doctrine | Ghi chú |
|---|---|---|---|
| 41 | Contributor lạ, PR có tin được | PASS = fast lane, maintainer merge sau khi liếc evidence | Giảm thời gian review PR lạ từ đọc code -> đọc verdict |
| 42 | 100 PR/tuần, cái nào cần người | `routing.maintainerReviewRequired` chỉ true khi WARN/BLOCK | Người chỉ xem cái máy không chắc |
| 43 | Release này regress chỗ nào | Chạy core giữa 2 tag, `changelog_architecture` làm evidence | Release-Gate profile có sẵn trong SPEC |
| 44 | Package nào đang mục dần | `packagesTouched` + history verdict theo package | Cần history store; EXT nhẹ |
| 45 | Chạm package bị khoá (frozen core) | `protectedPathHits` theo `protectedPaths` trong policy | >0 -> BLOCK + bắt buộc owner review |
| 46 | Package mới trùng responsibility package cũ | shifts/overlap trong findings | WARN, maintainer quyết |
| 47 | Tách package có sạch hơn gốc | So `largestComponentEntities` + `newSmells` trước/sau | PASS nếu cap giảm và 0 smell mới |
| 48 | Bot chỉ lên tiếng khi cần | Comment chỉ render khi WARN/BLOCK hoặc PASS lần đầu của contributor | Chống spam PR, đã có marker `pr-redteam-verdict` để update thay vì comment mới |
| 49 | Maintainer vắng, agent tự approve PR sạch | `routing.selfMergeEligible` + policy owner bật + PASS 2 run | Mặc định tắt; bật là quyết định của owner, ghi trong policy ký |
| 50 | Chứng minh sức khoẻ repo cho sponsor | Chuỗi verdict + attestation theo release | Consumer ngoài; doctrine phát hành artifact ký được |

Field mới cho E: `counters.packagesTouched`, `counters.protectedPathHits`, `routing.lane`, `routing.maintainerReviewRequired`, `routing.triagePriority`, `routing.selfMergeEligible`.

---

## 2. Ba lane, một core

| | AGENT lane | PR lane | MAINTAINER lane |
|---|---|---|---|
| Chạy ở đâu | Máy agent, trước khi mở PR (Skill adapter) | GitHub Action trên PR | Sau verdict, ở tầng phân luồng/comment |
| Ai đọc verdict | Chính agent | CI check status | Maintainer |
| WARN nghĩa là gì | **BLOCK** — agent không được đẩy WARN cho người | WARN — người quyết | Chỉ WARN/BLOCK mới vào hộp thư người |
| Được tự sửa rồi chạy lại | Có, tối đa `maxAgentAttempts` (policy, mặc định 3) | Không, CI chỉ phán | Không |
| Tự merge | Chỉ khi `selfMergeEligible` và owner đã bật trong policy ký | Không | Không — owner merge vẫn là acceptance |

Tối ưu cốt lõi: **cùng 1 verdict, 3 cách hành xử.** Trước đây doctrine chỉ có 1 ngưỡng cho tất cả. Nay agent bị siết chặt hơn người (đúng bản chất: agent sinh code nhanh, phải bị chặn sớm), còn maintainer được nới lỏng (chỉ xem ngoại lệ).

---

## 3. Triage Priority — điểm sắp hàng đợi cho maintainer (deterministic, không LLM)

```text
triagePriority = 100*blockFlag
               + 40*min(newSmells,5)
               + 25*min(responsibilityShifts,4)
               + 20*protectedPathHits (cap 20)
               + 10*min(newDependencies,3)
               + 5*min(packagesTouched,4)
               - 15 nếu safe-large-deletion (shifts=0, newSmells=0, netLocChanged<0)
```

- Số càng cao, maintainer xem càng trước.
- Mọi hệ số nằm trong `policy.json` (`triageWeights`), owner ký. Đổi hệ số = đổi policyVersion.
- Đây là điểm *sắp xếp*, không phải điểm chất lượng. PASS vẫn có thể priority cao nếu chạm protected path — và khi đó `maintainerReviewRequired=true` dù verdict PASS.

---

## 4. Cái chưa làm được, khai thật

- #7, #8 bản đầy đủ và #70 cần edge-level dependency diff: doctrine hiện có `layerContractViolations` qua import-linter/dependency-cruiser ở tầng package, chưa có edge diff từng cặp module. Ghi EXT, không demo giả.
- #44, #67, #69 cần history store (chuỗi verdict theo thời gian). MVP chỉ phát hành từng verdict ký được; history là lớp đọc sau.
- `evaluateArchitecturePredicates` trong code hiện vẫn trả 0 (chưa wire arcade-agent). Lane nào cũng không được BLOCK dựa trên số 0 = "chưa chạy". Comment renderer phải nói rõ scope đã wire, giữ nguyên tắc cũ của SPEC.

---

## 5. Thứ tự rollout cho 3 lane

1. **PR lane siết zero-tolerance** (đang ở step 1 -> step 2 của SPEC): wire `no_new_smells`, `max_responsibility_shifts`, `component_entity_cap`.
2. **AGENT lane**: Skill chạy local, WARN->BLOCK với agent, `maxAgentAttempts=3`, ghi `actor.kind=agent`.
3. **MAINTAINER lane**: bật `routing` + comment chỉ khi WARN/BLOCK, hàng đợi sắp theo `triagePriority` trên dogfood repo `arcade-agent-examples`.
4. **selfMergeEligible**: chỉ sau khi 3 bước trên chạy ổn 1 tuần trên dogfood, và chỉ khi owner tự bật trong policy ký. Không mặc định.

Mỗi bước xong khi có fixture đo được: planted god-file của agent bị BLOCK ở lane AGENT; PR sạch của contributor lạ vào fast lane không cần maintainer đọc code; 1 tuần dogfood mà maintainer chỉ phải mở các PR WARN/BLOCK.
