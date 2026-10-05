# Dogfood E2E — cách kiểm chứng redteam-doctrine

Nguyên tắc (owner stamp 2026-10-03): **không dựa unit test. Dùng E2E thật + dogfooding liên tục + scripting.**

## Chạy

```bash
PATH=$PWD/.venv/bin:$PATH .venv/bin/python scripts/dogfood/e2e_dogfood.py
```

Script tự dựng repo git thật trong temp, commit planted PR thật, gọi CLI `pr_redteam` bằng subprocess thật, đọc `verdict.json` thật. Không mock, không import core vào assert.

## 11 scenarios hiện có

1. clean-pass — PR sạch PASS, và `gates.notRun` khai architecture chưa chạy
2. invented-symbol-block — F821 BLOCK
3. secret-block — planted token BLOCK
4. agent-godfile-block — file 502 dòng, agent policy cap 400 -> BLOCK
5. human-godfile-under-pr-cap-pass — cùng file, PR policy cap 800 -> PASS (lane khác nhau, hành vi khác nhau)
6. agent-dependency-block — thêm dependency, agent -> BLOCK
7. human-dependency-warn — thêm dependency, human -> WARN
8. agent-protected-block — chạm `schema/` , agent -> BLOCK + review
9. human-protected-warn-review — chạm `schema/`, human -> WARN + review
10. determinism-diff-runid — 2 lần chạy khác run-id, cùng verdict hash
11. self-dogfood-own-head — gate tự chạy trên HEAD của chính repo này

Kết quả 2026-10-03: 11/11 pass, chạy lặp 3 vòng liên tiếp đều 11/11. Self-dogfood trên HEAD hiện tại ra WARN (vì merge commit chạm protected paths) — đúng kỳ vọng, không phải fail.

## Dogfooding liên tục

- GitHub Actions `.github/workflows/dogfood-e2e.yml`: chạy mỗi PR, mỗi push main, và **schedule daily 08:17 UTC**. Concurrency cancel-in-progress, permissions `contents: read`, timeout 10 phút, pip cache.
- `.github/workflows/selftest.yml` đã bỏ pytest khỏi vị trí kiểm chứng chính, thay bằng e2e dogfood script, và self-gate nay truyền `--policy policy.pr.json --actor-kind ci` (trước đây policy là dead config).
- Ở local: chạy script trước khi mở PR. PR nào làm script đỏ thì không mở.

## Cái E2E này bắt được mà unit test cũ không bắt

- Policy file có nối vào CLI thật hay không (R1 trong REVIEW-2026-10-03)
- Hash có ổn định khi run-id đổi hay không (R6)
- Lane agent/human có hành vi khác nhau trên cùng 1 diff hay không (R3, R5)
- Gate có tự ăn được code của chính nó hay không (self-dogfood)

## Chưa xong, khai thật

- Architecture predicates vẫn `notRun`; E2E hiện assert nó nằm trong `gates.notRun` chứ không giả vờ PASS kiến trúc.
- E2E chưa có scenario rename/binary/tên file ký tự đặc biệt (R13), chưa có TypeScript (R10).
- Thêm scenario mới = thêm planted PR vào script. Không thêm unit test mới trừ khi scenario E2E không diễn đạt được.
