#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm công thức chấm F-09: ví dụ tính tay, các ca lỗi, và tái lập bảng sức phân biệt ở L15
bằng CHÍNH hàm score() của cham_diem.py (một mã, thị trường độc lập cân bằng 50%)."""
import random, unittest, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cham_diem as cd

def hist_rows(ticker, ups, prefix):
    return [{"ticker": ticker, "date": "%s%04d" % (prefix, i), "up": str(u)} for i, u in enumerate(ups)]

class HandExamples(unittest.TestCase):
    def test_t_table_sample_values(self):
        self.assertEqual(cd.t90(29), 1.31143)
        self.assertEqual(cd.t90(59), 1.29607)
        self.assertEqual(cd.t90(119), 1.28871)

    def test_hand_computed_session(self):
        # 121 phiên lịch sử xen kẽ 1,0,1,0,... (chỉ số chẵn = tăng); phiên chấm là chỉ số 121 (lẻ => y=0)
        pre = [1 if i % 2 == 0 else 0 for i in range(121)]
        hist = hist_rows("AAA", pre + [0], "h")
        # đổi ngày của phiên chấm sang 't0000' để tách khỏi lịch sử
        hist[-1]["date"] = "t0000"
        fc = [{"target_date": "t0000", "ticker": "AAA", "p_up": "0.30", "flag": ""}]
        r = cd.score(hist, fc)
        # c = 0.5 (60 phiên tăng trong 120); d = 0 (sau phiên tăng luôn là phiên giảm) -> d_t tính tay:
        # Brier AI = 0.3^2 = 0.09; mốc 50% = 0.25; (c) = 0.25; (d) = 0.0
        self.assertAlmostEqual(r["brier"]["ai"], 0.09)
        self.assertAlmostEqual(r["brier"]["b"], 0.25)
        self.assertAlmostEqual(r["brier"]["c"], 0.25)
        self.assertAlmostEqual(r["brier"]["d"], 0.0)

    def test_p_validation(self):
        self.assertEqual(cd.valid_p("0.55"), 0.55)
        for bad in ("0.5", "0.555", ".55", "1.00", "0.97", "0.04", "", None, "abc"):
            self.assertIsNone(cd.valid_p(bad), bad)

    def test_parse_answer_needs_exactly_one_line(self):
        txt = "Phân tích ngắn\nFPT: p_up=0.55\nVIC p_up=0.48\nVIC p_up=0.60\nHPG p_up=0.5\n"
        out = cd.parse_answer(txt, ["FPT", "VIC", "HPG", "VIX"])
        self.assertEqual(out["FPT"], "0.55")
        self.assertEqual(out["VIC"], "")      # hai dòng -> hỏng
        self.assertEqual(out["HPG"], "0.5")    # lấy được chuỗi nhưng valid_p sẽ loại
        self.assertEqual(out["VIX"], "")       # thiếu dòng -> hỏng

class MissingData(unittest.TestCase):
    def test_exact_line_is_missing_data(self):
        self.assertTrue(cd.is_missing_data_answer("THIẾU DỮ LIỆU"))
        self.assertTrue(cd.is_missing_data_answer("  THIẾU DỮ LIỆU.\n"))

    def test_any_probability_blocks_resend(self):
        self.assertFalse(cd.is_missing_data_answer("THIẾU DỮ LIỆU\nFPT p_up=0.52"))
        self.assertFalse(cd.is_missing_data_answer("Phần khối dữ liệu đang bị khuyết, bạn vui lòng dán bổ sung."))
        self.assertFalse(cd.is_missing_data_answer("FPT p_up=0.52\nVIC p_up=0.47\nHPG p_up=0.50"))

class Classification(unittest.TestCase):
    def test_always_half_is_never_suggestive(self):
        n = 60
        db = [0.0] * n                      # AI nói 0,50: d_t(b) = 0 mọi phiên
        dc = [random.Random(1).uniform(0.0, 0.02) for _ in range(n)]
        dd = [0.0] * n
        self.assertEqual(cd.evaluate(db, dc, dd)["class"], "ii")   # LB(b)=0, không lớn hơn 0

    def test_clearly_bad_is_class_iii(self):
        n = 30
        db = [-0.56] * n                    # AI nói 0,90 khi thị trường đi xuống: Brier 0,81 so với 0,25
        self.assertEqual(cd.evaluate(db, db, db)["class"], "iii")

    def test_class_iv_beats_constants_not_one_step_rule(self):
        rng = random.Random(3)
        db = [0.05 + rng.uniform(-0.01, 0.01) for _ in range(60)]
        dc = [0.05 + rng.uniform(-0.01, 0.01) for _ in range(60)]
        dd = [-0.02 + rng.uniform(-0.01, 0.01) for _ in range(60)]
        self.assertEqual(cd.evaluate(db, dc, dd)["class"], "iv")

    def test_gate_order(self):
        # n=30 và (iii) -> dừng vô vọng; n=29 -> chưa tới mốc
        bad = [-0.56] * 30
        self.assertEqual(cd.decide(bad, bad, bad, 0)["state"], "STOP_futility")
        self.assertEqual(cd.decide(bad[:29], bad[:29], bad[:29], 0)["state"], "CONTINUE")

    def test_error_cap(self):
        z = [0.0] * 40
        self.assertEqual(cd.decide(z, z, z, 4)["state"], "STOP_v")   # 4 lỗi > 3
        self.assertNotEqual(cd.decide(z, z, z, 3)["state"], "STOP_v")

class SessionFlags(unittest.TestCase):
    def setUp(self):
        pre = [random.Random(7).choice([0, 1]) for _ in range(121)]
        self.hist = hist_rows("AAA", pre, "h") + [
            {"ticker": "AAA", "date": "t000%d" % i, "up": "1"} for i in range(4)]

    def test_flags_and_malformed(self):
        fc = [
            {"target_date": "t0000", "ticker": "AAA", "p_up": "0.60", "flag": ""},
            {"target_date": "t0001", "ticker": "", "p_up": "", "flag": "MISSED"},
            {"target_date": "t0002", "ticker": "", "p_up": "", "flag": "VOID"},
            {"target_date": "t0003", "ticker": "AAA", "p_up": "0.5", "flag": ""},   # hỏng định dạng
        ]
        r = cd.score(self.hist, fc)
        self.assertEqual(r["scored_sessions"], 2)   # t0000 và t0003 (chấm 0,50)
        self.assertEqual(r["errors"], 2)            # MISSED + hỏng; VOID không tính lỗi
        self.assertEqual((r["missed"], r["malformed"], r["voids"]), (1, 1, 1))

    def test_g1_not_scored(self):
        fc = [{"target_date": "t0000", "ticker": "AAA", "p_up": "0.60", "flag": ""},
              {"target_date": "t0002", "ticker": "AAA", "p_up": "0.60", "flag": ""}]
        r = cd.score(self.hist, fc, g2_start="t0001")
        self.assertEqual(r["scored_sessions"], 1)

def simulate(kind, q, trials, seed):
    """Trả về tỷ lệ cuối cùng nhận 'gợi ý' (G3) và các trạng thái khác, dùng score() thật."""
    rng = random.Random(seed)
    counts = {}
    for _ in range(trials):
        pre = [1 if rng.random() < 0.5 else 0 for _ in range(121)]
        ys = [1 if rng.random() < 0.5 else 0 for _ in range(120)]
        rows = hist_rows("AAA", pre, "h") + [{"ticker": "AAA", "date": "t%04d" % i, "up": str(y)}
                                             for i, y in enumerate(ys)]
        fc = []
        for i, y in enumerate(ys):
            if kind == "const":
                p = 0.5
            else:
                right = rng.random() < q
                says_up = (y == 1) if right else (y == 0)
                c = 0.60 if kind == "A" else q
                c = min(max(c, 0.05), 0.95)
                p = c if says_up else 1 - c
            fc.append({"target_date": "t%04d" % i, "ticker": "AAA", "p_up": "%.2f" % p, "flag": ""})
        r = cd.score(rows, fc)
        st = r["decision"]["state"]
        counts[st] = counts.get(st, 0) + 1
    return {k: v / trials for k, v in counts.items()}

class Simulation(unittest.TestCase):
    TRIALS = 500
    def test_always_half_never_suggestive(self):
        r = simulate("const", 0.5, 200, 11)
        self.assertEqual(r.get("G3_OWNER_DECIDES", 0.0), 0.0)

    def test_no_skill_false_positive_low(self):
        r = simulate("A", 0.5, self.TRIALS, 12)
        self.assertLess(r.get("G3_OWNER_DECIDES", 0.0), 0.10)

    def test_kind_A_q60_about_half(self):
        r = simulate("A", 0.60, self.TRIALS, 13)
        self.assertGreater(r.get("G3_OWNER_DECIDES", 0.0), 0.38)
        self.assertLess(r.get("G3_OWNER_DECIDES", 0.0), 0.60)   # bảng L15: 49%

    def test_kind_B_q65_about_70(self):
        r = simulate("B", 0.65, self.TRIALS, 14)
        self.assertGreater(r.get("G3_OWNER_DECIDES", 0.0), 0.58)
        self.assertLess(r.get("G3_OWNER_DECIDES", 0.0), 0.82)   # bảng L15: 70%

if __name__ == "__main__":
    unittest.main(verbosity=2)
