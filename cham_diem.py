#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CÔNG THỨC CHẤM F-09 — theo bộ luật v0.5 (L3, L7, L9, L10, L11, L13, L17).
Soạn bởi Tổng công trình sư (Claude). Chạy bằng Python 3, không cần thư viện ngoài.

Tệp vào (CSV, dòng đầu là tên cột, mã hóa UTF-8):
  history.csv    : ticker,date,up
        up = 1 nếu cột "Thay đổi" của bảng Lịch sử giá SSI của phiên đó lớn hơn 0, ngược lại 0.
        Gồm ít nhất 121 phiên TRƯỚC phiên chấm đầu tiên của mỗi mã, và được nối thêm mỗi ngày.
  forecasts.csv  : target_date,ticker,p_up,flag
        target_date = ngày của phiên được dự báo (phiên kế tiếp). p_up là chuỗi đúng như AI viết.
        flag rỗng = bình thường; MISSED = không có tệp hợp lệ trong cửa sổ giờ (khi đó ticker, p_up để trống);
        VOID = phiên bị loại theo L8 (không tính là lỗi, không chấm).
Lệnh:
  python3 cham_diem.py history.csv forecasts.csv --g2-start 2026-12-01
"""
import csv, math, re, sys, json, argparse, statistics

WINDOW = 120            # L10: cửa sổ 120 phiên
ERR_CAP_PER_60 = 3      # L7: tối đa 3 phiên lỗi cho mỗi 60 phiên được chấm

# Hàm tra t duy nhất (L10): phân vị 0,90 của Student, một phía, theo bậc tự do.
# Giá trị mẫu bắt buộc: df 29 = 1.31143; df 59 = 1.29607; df 119 = 1.28871.
T90 = {
    1: 3.07768, 2: 1.88562, 3: 1.63774, 4: 1.53321, 5: 1.47588, 6: 1.43976,
    7: 1.41492, 8: 1.39682, 9: 1.38303, 10: 1.37218, 11: 1.36343, 12: 1.35622,
    13: 1.35017, 14: 1.34503, 15: 1.34061, 16: 1.33676, 17: 1.33338, 18: 1.33039,
    19: 1.32773, 20: 1.32534, 21: 1.32319, 22: 1.32124, 23: 1.31946, 24: 1.31784,
    25: 1.31635, 26: 1.31497, 27: 1.3137, 28: 1.31253, 29: 1.31143, 30: 1.31042,
    31: 1.30946, 32: 1.30857, 33: 1.30774, 34: 1.30695, 35: 1.30621, 36: 1.30551,
    37: 1.30485, 38: 1.30423, 39: 1.30364, 40: 1.30308, 41: 1.30254, 42: 1.30204,
    43: 1.30155, 44: 1.30109, 45: 1.30065, 46: 1.30023, 47: 1.29982, 48: 1.29944,
    49: 1.29907, 50: 1.29871, 51: 1.29837, 52: 1.29805, 53: 1.29773, 54: 1.29743,
    55: 1.29713, 56: 1.29685, 57: 1.29658, 58: 1.29632, 59: 1.29607, 60: 1.29582,
    61: 1.29558, 62: 1.29536, 63: 1.29513, 64: 1.29492, 65: 1.29471, 66: 1.29451,
    67: 1.29432, 68: 1.29413, 69: 1.29394, 70: 1.29376, 71: 1.29359, 72: 1.29342,
    73: 1.29326, 74: 1.2931, 75: 1.29294, 76: 1.29279, 77: 1.29264, 78: 1.2925,
    79: 1.29236, 80: 1.29222, 81: 1.29209, 82: 1.29196, 83: 1.29183, 84: 1.29171,
    85: 1.29159, 86: 1.29147, 87: 1.29136, 88: 1.29125, 89: 1.29114, 90: 1.29103,
    91: 1.29092, 92: 1.29082, 93: 1.29072, 94: 1.29062, 95: 1.29053, 96: 1.29043,
    97: 1.29034, 98: 1.29025, 99: 1.29016, 100: 1.29007, 101: 1.28999, 102: 1.28991,
    103: 1.28982, 104: 1.28974, 105: 1.28967, 106: 1.28959, 107: 1.28951, 108: 1.28944,
    109: 1.28937, 110: 1.2893, 111: 1.28922, 112: 1.28916, 113: 1.28909, 114: 1.28902,
    115: 1.28896, 116: 1.28889, 117: 1.28883, 118: 1.28877, 119: 1.28871, 120: 1.28865,
    121: 1.28859, 122: 1.28853, 123: 1.28847, 124: 1.28842, 125: 1.28836, 126: 1.28831,
    127: 1.28825, 128: 1.2882, 129: 1.28815, 130: 1.2881, 131: 1.28805, 132: 1.288,
    133: 1.28795, 134: 1.2879, 135: 1.28785, 136: 1.28781, 137: 1.28776, 138: 1.28772,
    139: 1.28767, 140: 1.28763, 141: 1.28758, 142: 1.28754, 143: 1.2875, 144: 1.28746,
    145: 1.28742, 146: 1.28738, 147: 1.28734, 148: 1.2873, 149: 1.28726, 150: 1.28722,
    151: 1.28718, 152: 1.28715, 153: 1.28711, 154: 1.28707, 155: 1.28704, 156: 1.287,
    157: 1.28697, 158: 1.28693, 159: 1.2869, 160: 1.28687, 161: 1.28683, 162: 1.2868,
    163: 1.28677, 164: 1.28673, 165: 1.2867, 166: 1.28667, 167: 1.28664, 168: 1.28661,
    169: 1.28658, 170: 1.28655, 171: 1.28652, 172: 1.28649, 173: 1.28646, 174: 1.28644,
    175: 1.28641, 176: 1.28638, 177: 1.28635, 178: 1.28633, 179: 1.2863, 180: 1.28627,
    181: 1.28625, 182: 1.28622, 183: 1.28619, 184: 1.28617, 185: 1.28614, 186: 1.28612,
    187: 1.2861, 188: 1.28607, 189: 1.28605, 190: 1.28602, 191: 1.286, 192: 1.28598,
    193: 1.28595, 194: 1.28593, 195: 1.28591, 196: 1.28589, 197: 1.28586, 198: 1.28584,
    199: 1.28582, 200: 1.2858, 201: 1.28578, 202: 1.28576, 203: 1.28574, 204: 1.28572,
    205: 1.28569, 206: 1.28567, 207: 1.28565, 208: 1.28563, 209: 1.28562, 210: 1.2856,
    211: 1.28558, 212: 1.28556, 213: 1.28554, 214: 1.28552, 215: 1.2855, 216: 1.28548,
    217: 1.28547, 218: 1.28545, 219: 1.28543, 220: 1.28541, 221: 1.28539, 222: 1.28538,
    223: 1.28536, 224: 1.28534, 225: 1.28533, 226: 1.28531, 227: 1.28529, 228: 1.28528,
    229: 1.28526, 230: 1.28524, 231: 1.28523, 232: 1.28521, 233: 1.2852, 234: 1.28518,
    235: 1.28516, 236: 1.28515, 237: 1.28513, 238: 1.28512, 239: 1.2851, 240: 1.28509,
    241: 1.28507, 242: 1.28506, 243: 1.28505, 244: 1.28503, 245: 1.28502, 246: 1.285,
    247: 1.28499, 248: 1.28497, 249: 1.28496, 250: 1.28495, 251: 1.28493, 252: 1.28492,
    253: 1.28491, 254: 1.28489, 255: 1.28488, 256: 1.28487, 257: 1.28485, 258: 1.28484,
    259: 1.28483, 260: 1.28482, 261: 1.2848, 262: 1.28479, 263: 1.28478, 264: 1.28477,
    265: 1.28475, 266: 1.28474, 267: 1.28473, 268: 1.28472, 269: 1.28471, 270: 1.28469,
    271: 1.28468, 272: 1.28467, 273: 1.28466, 274: 1.28465, 275: 1.28464, 276: 1.28463,
    277: 1.28462, 278: 1.2846, 279: 1.28459, 280: 1.28458, 281: 1.28457, 282: 1.28456,
    283: 1.28455, 284: 1.28454, 285: 1.28453, 286: 1.28452, 287: 1.28451, 288: 1.2845,
    289: 1.28449, 290: 1.28448, 291: 1.28447, 292: 1.28446, 293: 1.28445, 294: 1.28444,
    295: 1.28443, 296: 1.28442, 297: 1.28441, 298: 1.2844, 299: 1.28439, 300: 1.28438,
    301: 1.28437, 302: 1.28436, 303: 1.28435, 304: 1.28434, 305: 1.28433, 306: 1.28432,
    307: 1.28432, 308: 1.28431, 309: 1.2843, 310: 1.28429, 311: 1.28428, 312: 1.28427,
    313: 1.28426, 314: 1.28425, 315: 1.28424, 316: 1.28424, 317: 1.28423, 318: 1.28422,
    319: 1.28421, 320: 1.2842, 321: 1.28419, 322: 1.28419, 323: 1.28418, 324: 1.28417,
    325: 1.28416, 326: 1.28415, 327: 1.28415, 328: 1.28414, 329: 1.28413, 330: 1.28412,
    331: 1.28411, 332: 1.28411, 333: 1.2841, 334: 1.28409, 335: 1.28408, 336: 1.28408,
    337: 1.28407, 338: 1.28406, 339: 1.28405, 340: 1.28405, 341: 1.28404, 342: 1.28403,
    343: 1.28402, 344: 1.28402, 345: 1.28401, 346: 1.284, 347: 1.284, 348: 1.28399,
    349: 1.28398, 350: 1.28398, 351: 1.28397, 352: 1.28396, 353: 1.28395, 354: 1.28395,
    355: 1.28394, 356: 1.28393, 357: 1.28393, 358: 1.28392, 359: 1.28391, 360: 1.28391,
    361: 1.2839, 362: 1.28389, 363: 1.28389, 364: 1.28388, 365: 1.28388, 366: 1.28387,
    367: 1.28386, 368: 1.28386, 369: 1.28385, 370: 1.28384, 371: 1.28384, 372: 1.28383,
    373: 1.28383, 374: 1.28382, 375: 1.28381, 376: 1.28381, 377: 1.2838, 378: 1.2838,
    379: 1.28379, 380: 1.28378, 381: 1.28378, 382: 1.28377, 383: 1.28377, 384: 1.28376,
    385: 1.28375, 386: 1.28375, 387: 1.28374, 388: 1.28374, 389: 1.28373, 390: 1.28373,
    391: 1.28372, 392: 1.28371, 393: 1.28371, 394: 1.2837, 395: 1.2837, 396: 1.28369,
    397: 1.28369, 398: 1.28368, 399: 1.28368, 400: 1.28367,
}
def t90(df):
    if df < 1:
        raise ValueError("bac tu do < 1")
    if df > 400:
        return 1.28155      # phân vị chuẩn 0,90 (df rất lớn)
    return T90[df]

P_RE = re.compile(r"^0\.\d\d$")
def valid_p(s):
    """L3: đúng dạng 0.XX và nằm trong [0.05, 0.95]."""
    s = (s or "").strip()
    if not P_RE.match(s):
        return None
    v = float(s)
    return v if 0.05 <= v <= 0.95 else None

def parse_answer(text, tickers):
    """Đọc câu trả lời của AI. Mỗi mã cần ĐÚNG MỘT dòng bắt đầu bằng 'MÃ p_up=0.XX'
    (cho phép 'MÃ: p_up=0.XX'). Trả về {mã: chuỗi p hoặc ''}; '' nghĩa là hỏng (L3)."""
    out = {}
    for t in tickers:
        pat = re.compile(r"^\s*" + re.escape(t) + r"\s*:?\s*p_up\s*=\s*(\S+)\s*$", re.M)
        found = pat.findall(text)
        out[t] = found[0] if len(found) == 1 else ""
    return out

def is_missing_data_answer(text):
    """L5 (ngoại lệ): câu trả lời đầu tiên đúng là một dòng 'THIẾU DỮ LIỆU' (không có xác suất nào)."""
    lines = [ln.strip() for ln in (text or "").strip().splitlines() if ln.strip()]
    return len(lines) == 1 and lines[0].rstrip(".").upper() == "THIẾU DỮ LIỆU" and "p_up" not in text

def base_rates(up_list, i):
    """Mốc (c) và (d) cho phiên ở vị trí i của chuỗi up_list (chỉ dùng phiên < i, cửa sổ 120)."""
    lo = i - WINDOW
    if lo < 0:
        raise ValueError("thieu lich su: can it nhat %d phien truoc phien cham" % (WINDOW + 1))
    win = up_list[lo:i]
    c = sum(win) / WINDOW
    prev = up_list[i - 1]
    n = u = 0
    for j in range(lo + 1, i):             # cặp (j-1, j) trong cửa sổ
        if up_list[j - 1] == prev:
            n += 1
            u += up_list[j]
    d = (u / n) if n > 0 else 0.5
    return c, d

def evaluate(db, dc, dd):
    """L10, L11: trả về thống kê và phân loại (i) (ii) (iii) (iv) trên các mảng d_t."""
    n = len(db)
    res = {"n": n}
    for name, arr in (("b", db), ("c", dc), ("d", dd)):
        m = sum(arr) / n
        sd = statistics.stdev(arr) if n > 1 else 0.0
        se = (t90(n - 1) * sd / math.sqrt(n)) if (sd > 0 and n > 1) else 0.0
        res[name] = {"mean": m, "lb": m - se, "ub": m + se}
    b, c, d = res["b"], res["c"], res["d"]
    if b["ub"] < 0:
        res["class"] = "iii"
    elif b["lb"] > 0 and c["lb"] > 0 and d["mean"] >= 0:
        res["class"] = "i"
    elif b["lb"] > 0 and c["lb"] > 0 and d["mean"] < 0:
        res["class"] = "iv"
    else:
        res["class"] = "ii"
    return res

def decide(db, dc, dd, errors):
    """L11 và L7: trạng thái theo các mốc 30, 60, 120 (đếm theo phiên ĐƯỢC CHẤM)."""
    n = len(db)
    allowed = ERR_CAP_PER_60 * max(1, math.ceil(n / 60))
    if errors > allowed:
        return {"state": "STOP_v", "why": "vuot tran phien loi (%d > %d): cau ket (v)" % (errors, allowed)}
    if n < 30:
        return {"state": "CONTINUE", "why": "chua den moc 30 phien cham (n=%d)" % n}
    at30 = evaluate(db[:30], dc[:30], dd[:30])
    if at30["class"] == "iii":
        return {"state": "STOP_futility", "why": "moc 30: (iii) AI kem moc 50%% co y nghia", "at30": at30}
    if n < 60:
        return {"state": "CONTINUE", "why": "qua moc 30, cho moc 60 (n=%d)" % n, "at30": at30}
    at60 = evaluate(db[:60], dc[:60], dd[:60])
    if at60["class"] == "i":
        return {"state": "G3_OWNER_DECIDES", "why": "moc 60: (i) goi y", "at60": at60}
    if at60["class"] == "iii":
        return {"state": "STOP_iii", "why": "moc 60: (iii) bat loi", "at60": at60}
    if n < 120:
        return {"state": "CONTINUE_TO_120", "why": "moc 60: (%s), chay tiep toi 120" % at60["class"], "at60": at60}
    at120 = evaluate(db[:120], dc[:120], dd[:120])
    if at120["class"] == "i":
        return {"state": "G3_OWNER_DECIDES", "why": "moc 120: (i) goi y", "at120": at120}
    return {"state": "STOP_end", "why": "het 120 phien: (%s), khong co (i)" % at120["class"], "at120": at120}

def score(history_rows, forecast_rows, g2_start=None):
    """Chấm từ hai bảng đọc sẵn. Trả về dict đầy đủ."""
    hist = {}
    for r in sorted(history_rows, key=lambda x: (x["ticker"], x["date"])):
        hist.setdefault(r["ticker"], []).append((r["date"], int(r["up"])))
    pos = {t: {d: i for i, (d, _) in enumerate(v)} for t, v in hist.items()}
    ups = {t: [u for _, u in v] for t, v in hist.items()}

    by_date = {}
    for r in forecast_rows:
        by_date.setdefault(r["target_date"], []).append(r)

    sessions = []                      # các phiên được chấm
    errors = voids = missed = malformed = 0
    for date in sorted(by_date):
        if g2_start and date < g2_start:
            continue                    # G1: không chạy công thức chấm
        rows = by_date[date]
        flags = {(r.get("flag") or "").strip().upper() for r in rows}
        if "VOID" in flags:
            voids += 1
            continue
        if "MISSED" in flags:
            errors += 1; missed += 1
            continue
        sess_err = False
        bai = bb = bc = bd = 0.0
        k = 0
        for r in rows:
            t = r["ticker"]
            y = ups[t][pos[t][date]]
            p = valid_p(r["p_up"])
            if p is None:
                p = 0.5; sess_err = True      # L3: chấm 0,50, vẫn giữ trong mẫu, tính là phiên lỗi
            c, d = base_rates(ups[t], pos[t][date])
            bai += (p - y) ** 2
            bb += (0.5 - y) ** 2
            bc += (c - y) ** 2
            bd += (d - y) ** 2
            k += 1
        if sess_err:
            errors += 1; malformed += 1
        sessions.append({"date": date, "ai": bai / k, "b": bb / k, "c": bc / k, "d": bd / k})

    db = [s["b"] - s["ai"] for s in sessions]
    dc = [s["c"] - s["ai"] for s in sessions]
    dd = [s["d"] - s["ai"] for s in sessions]
    out = {"scored_sessions": len(sessions), "errors": errors, "missed": missed,
           "malformed": malformed, "voids": voids}
    if sessions:
        out["brier"] = {k: sum(s[k] for s in sessions) / len(sessions) for k in ("ai", "b", "c", "d")}
        out["full"] = evaluate(db, dc, dd) if len(sessions) > 1 else None
        out["decision"] = decide(db, dc, dd, errors)
    return out

def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def main(argv=None):
    ap = argparse.ArgumentParser(description="Công thức chấm F-09 (luật v0.5)")
    ap.add_argument("history"); ap.add_argument("forecasts")
    ap.add_argument("--g2-start", default=None, help="ngày bắt đầu chấm (YYYY-MM-DD); G1 không chấm")
    a = ap.parse_args(argv)
    res = score(read_csv(a.history), read_csv(a.forecasts), a.g2_start)
    print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
