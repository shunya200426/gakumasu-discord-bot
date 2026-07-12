# ocr/ocr.py
import re

import cv2
import numpy as np
import pytesseract

from utils.logger import get_logger

logger = get_logger()

MAX_AREA_KSIZE = (7, 7)
PARAMETER_KSIZE = (13,13)
FANS_KSIZE = (7, 7)
BONUS_KSIZE = (17, 17)
SCORE_KSIZE = (7, 7)

# PARAMETER_MERGE_PX = 25
FANS_MERGE_PX = 30
BONUS_MERGE_PX = 20
KRMK_MERGE_PX = 15
SCORE_MERGE_PX = 7

class OCR:
    def __init__(self, image_bytes: bytes):
        """
        画像を読み込んでグレースケール変換
        """
        self._orig_bgr = self._decode(image_bytes)
        self._orig_gray = cv2.cvtColor(self._orig_bgr, cv2.COLOR_BGR2GRAY)

        # 入力画像の情報を取得
        height, width, channel = self._orig_bgr.shape
        logger.debug("height: %s, width: %s, channel: %s", height, width, channel)

    def _decode(self, b: bytes) -> np.ndarray:
        """
        バイナリから画像へ
        """
        arr = np.frombuffer(b, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Invalid image bytes")
        return img
    
    def _get_contours(self, bin_img: np.ndarray, ksize: tuple[int, int]):
        """
        輪郭検出
        """
        # ガウシアン -> エッジ検出 -> 輪郭検出
        gaussian = cv2.GaussianBlur(bin_img, ksize, sigmaX=0, sigmaY=0)
        canny_img = cv2.Canny(gaussian, threshold1 = 50, threshold2 = 100)
        contours, hierarchy = cv2.findContours(canny_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours
    
    def _merge_boxes_on_line(self, boxes, y_tol=5, gap_tol=20, margin=3,
                            contain_tol=3, iou_tol=0.9):
        """
        boxes: [(x,y,w,h), ...]
        y_tol: 同じ行とみなす縦方向の許容（px）
        gap_tol: 横に並ぶ矩形を同一クラスタとみなす隙間（px）
        margin: マージ後の外接矩形に足す余白（px）
        contain_tol: 内包判定のゆとり（px）
        iou_tol: ほぼ同一/強オーバーラップを1つにまとめる閾値（無効化は>1を指定）
        """
        if not boxes:
            return [], []

        # --- 0) helper ---
        def to_xyxy(b):  # (x,y,w,h) -> (x1,y1,x2,y2)
            x,y,w,h = b; return (x, y, x+w, y+h)
        def to_xywh(b):  # (x1,y1,x2,y2) -> (x,y,w,h)
            x1,y1,x2,y2 = b; return (x1, y1, x2-x1, y2-y1)
        def area(b):
            x1,y1,x2,y2 = b; return max(0, x2-x1) * max(0, y2-y1)
        def contains(outer, inner, tol=0):
            ox1,oy1,ox2,oy2 = outer; ix1,iy1,ix2,iy2 = inner
            return (ix1 >= ox1 - tol and iy1 >= oy1 - tol and
                    ix2 <= ox2 + tol and iy2 <= oy2 + tol)
        def iou(a,b):
            ax1,ay1,ax2,ay2 = a; bx1,by1,bx2,by2 = b
            ix1,iy1 = max(ax1,bx1), max(ay1,by1)
            ix2,iy2 = min(ax2,bx2), min(ay2,by2)
            iw,ih = max(0, ix2-ix1), max(0, iy2-iy1)
            inter = iw*ih
            if inter == 0: return 0.0
            return inter / float(area(a) + area(b) - inter)

        # --- 1) [前処理] 内包ボックスの抑制 + 強オーバーラップの統合 ---
        boxes_xyxy = [to_xyxy(b) for b in boxes]
        keep = []
        for b in sorted(boxes_xyxy, key=area, reverse=True):
            # 既に残した外側の箱に完全内包されていればスキップ（外側へマージ扱い）
            if any(contains(k, b, contain_tol) for k in keep):
                continue
            # ほぼ同一/強オーバーラップは union でまとめる（任意）
            merged = False
            if iou_tol <= 1.0:
                for i, k in enumerate(keep):
                    if iou(k, b) >= iou_tol:
                        x1 = min(k[0], b[0]); y1 = min(k[1], b[1])
                        x2 = max(k[2], b[2]); y2 = max(k[3], b[3])
                        keep[i] = (x1, y1, x2, y2)
                        merged = True
                        break
            if not merged:
                keep.append(b)

        boxes = [to_xywh(b) for b in keep]

        # --- 2) 行ごとにまとめる（元の処理） ---
        lines = []
        for (x,y,w,h) in sorted(boxes, key=lambda b: b[1]):  # yでソート
            cy = y + h/2
            placed = False
            for line in lines:
                ly = np.mean([bb[1] + bb[3]/2 for bb in line])  # 行の平均y中心
                if abs(cy - ly) <= y_tol:
                    line.append((x,y,w,h))
                    placed = True
                    break
            if not placed:
                lines.append([(x,y,w,h)])

        # --- 3) 各行内で x ソート→近接クラスタで外接矩形に ---
        merged = []
        line_groups = []
        for line in lines:
            line = sorted(line, key=lambda b: b[0])
            cluster = [line[0]]
            groups = []
            for b in line[1:]:
                px = cluster[-1][0] + cluster[-1][2]   # 直前の右端
                gap = b[0] - px
                if gap <= gap_tol:
                    cluster.append(b)
                else:
                    groups.append(cluster)
                    cluster = [b]
            groups.append(cluster)

            merged_line = []
            for group in groups:
                xs = [bb[0] for bb in group]; ys = [bb[1] for bb in group]
                xe = [bb[0]+bb[2] for bb in group]; ye = [bb[1]+bb[3] for bb in group]
                x1, y1 = max(0, min(xs)-margin), max(0, min(ys)-margin)
                x2, y2 = max(xe)+margin, max(ye)+margin
                merged_line.append((x1, y1, x2-x1, y2-y1))
                merged.append((x1, y1, x2-x1, y2-y1))
            line_groups.append(merged_line)

        return merged, line_groups
    
    def _get_max_area(self, contours) -> tuple[int, int, int, int]:
        """
        面積が最も大きい短形の取得
        """
        num_contours = len(contours)
        max_area = -1
        for i in range(0, num_contours):
            x, y, w, h = cv2.boundingRect(contours[i])
            area = h * w
            if max_area < area:
                max_area = area
                max_area_box = x, y, w, h
        return max_area_box
    
    def read_params(self, hi=2300) -> dict[str: int]:
        """
        Vo/Da/Vi/ファン数 の数字を読み取る
        """
        logger.debug("start read params")
        orig_height, orig_width = self._orig_bgr.shape[:2]

        # ゲーム全体画面から最も面積の大きい短形を検出
        gray_img = self._orig_gray.copy()
        ret, bin_img = cv2.threshold(gray_img, 240, 255, cv2.THRESH_BINARY)
        contours = self._get_contours(bin_img, MAX_AREA_KSIZE)

        # 面積が最も大きい短形の探索
        x, y, w, h = self._get_max_area(contours)

        # パラメータ部分のみをトリミング
        param_gray_img = gray_img[y:y+int(h*0.09), x:x+w]

        # ファン数の部分のみをトリミング
        fans_gray_img = gray_img[int(y*0.7):y,x+int(w*0.75):x+w]

        # トリミング画像の情報を取得
        height, width = param_gray_img.shape[:2]
        PARAMETER_MERGE_PX = int(height*0.35)
        logger.debug("PARAMETER_MERGE_PX: %s", PARAMETER_MERGE_PX)

        # トリミングの微調整
        cut = 0.095
        param_gray_img = param_gray_img[int(height*cut):, int(height*cut):int(-height*cut)]
        logger.debug("trimming fin: height %d width %d", param_gray_img.shape[0], param_gray_img.shape[1])


        # パラメータのバウンディングボックスの取得とマージ
        ret, param_bin_img = cv2.threshold(param_gray_img, 210, 255, cv2.THRESH_BINARY)
        contours = self._get_contours(param_bin_img, PARAMETER_KSIZE)
        digit_boxes = []
        for i in range(0, len(contours)):
            x, y, w, h = cv2.boundingRect(contours[i])
            digit_boxes.append((x,y,w,h))
        merged_boxes, line_groups = self._merge_boxes_on_line(digit_boxes, y_tol=PARAMETER_MERGE_PX, gap_tol=PARAMETER_MERGE_PX)
        logger.debug("merge fin: param: %dboxes", len(merged_boxes))


        # x軸で並び替え
        parameters_boxes = merged_boxes
        for i in range(len(parameters_boxes)):
            for j in range(len(parameters_boxes) - i -1):
                if parameters_boxes[j][0] > parameters_boxes[j+1][0]:
                    box = parameters_boxes[j]
                    parameters_boxes[j] = parameters_boxes[j+1]
                    parameters_boxes[j+1] = box
        logger.debug("sort fin")

        # パラメータの読み取り
        lo = hi / 10
        parameter_list = []
        for i in range(len(parameters_boxes)):
            x, y, w, h = parameters_boxes[i]
            try:
                parameter = self._ocr_digits_only(param_bin_img[y:y+h, x+int(h*0.921):x+w])
            except:
                continue
            if parameter is not None and 75 < parameter <= hi:
                parameter_list.append(parameter)

        logger.debug(f"parameter list: {parameter_list}")
        param_list = ["vo", "da", "vi"]
        parameter_dict = {key: None for key in param_list}
        for key, value in zip(param_list, parameter_list):
            parameter_dict[key] = value

        if None in parameter_dict.values():
            logger.debug("retry read params")
            numbers = self._ocr_digits_only(param_bin_img)
            try:
                vo, da, vi = self._split_params_3(str(numbers))
                parameter_dict["vo"] = vo
                parameter_dict["da"] = da
                parameter_dict["vi"] = vi
            except:
                pass

        
        # ファン数の読み取り
        MIN_FANS = 20000
        ret, fans_bin_img = cv2.threshold(fans_gray_img, 180, 255, cv2.THRESH_BINARY_INV)
        fans = self._ocr_digits_only(fans_bin_img)

        if fans is not None and MIN_FANS < fans:
            parameter_dict["fans"] = fans
            logger.debug("success read fans: %s", fans)

        else:
            logger.debug("retry read fans")
            contours = self._get_contours(fans_bin_img, FANS_KSIZE)
            fan_boxes = []
            for i in range(0, len(contours)):
                x, y, w, h = cv2.boundingRect(contours[i])
                fan_boxes.append((x,y,w,h))
            merged_fan_boxes, line_groups = self._merge_boxes_on_line(fan_boxes, gap_tol=FANS_MERGE_PX)
            
            for i in range(len(merged_fan_boxes)):
                x, y, w, h = merged_fan_boxes[i]
                fans_roi = fans_gray_img[y:y+h, x:x+w]
                try:
                    fans_roi = cv2.resize(fans_roi, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                except:
                    continue
                ret, roi_bin = cv2.threshold(fans_roi, 150, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
                fans = self._ocr_digits_only(roi_bin)
                if fans is not None:
                    logger.debug("fans: %s", fans)
                    if 20000 < fans:
                        parameter_dict["fans"] = fans
                        logger.debug("success read fans: %s", fans)
                        break

        if parameter_dict.get("fans") is None or parameter_dict["fans"] < MIN_FANS:
            logger.warning("invalid fans detected: %s (min=%d) -> treat as None",
                           parameter_dict.get("fans"), MIN_FANS)
            parameter_dict["fans"] = None

        return parameter_dict
    
    def read_bonus(self, is_boost_active: bool = False) -> dict[str: int]:
        """
        パラメータボーナスの読み取り
        """
        bonus_gray_img = self._orig_gray.copy()
        ret, bin_img = cv2.threshold(bonus_gray_img, 240, 255, cv2.THRESH_BINARY_INV)
        contours = self._get_contours(bin_img, MAX_AREA_KSIZE)

        # 面積が最も大きい短形の探索
        x, y, w, h = self._get_max_area(contours)

        # 最大面積部分の上半分をリトリミングして画像情報を取得
        bonus_gray_img = bonus_gray_img[y:y+int(h*0.5), x:x+w]
        height, width = bonus_gray_img.shape

        # このままだとグレー部分の輪郭がとれないので
        # 画像の両端10pxを白に塗りたくることで輪郭を取れるようにする
        for y in range(height):
            for x in range(10):
                bonus_gray_img[y, x] = 255
                bonus_gray_img[y, -x] = 255

        # グレー部分だけ切り取る
        ret, bin_img = cv2.threshold(bonus_gray_img, 250, 255, cv2.THRESH_BINARY_INV)
        contours = self._get_contours(bin_img, MAX_AREA_KSIZE)
        x, y, w, h = self._get_max_area(contours)
        bonus_gray_img = bonus_gray_img[y:y+h, x:x+w]

        # トリミング画像の情報を取得
        height, width = bonus_gray_img.shape

        # きらめきの読み取り
        if is_boost_active:
            logger.debug("boost active")
            # きらめき部分とグレー部分で切り分け
            krmk_gray_img = bonus_gray_img[:int(height*0.22),:]
            bonus_gray_img = bonus_gray_img[int(height*0.22):,:]

            # きらめきボックスの取得
            krmk_h, krmk_w = krmk_gray_img.shape
            ret, krmk_bin_img = cv2.threshold(krmk_gray_img[:,int(krmk_w*0.82):], 210, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
            krmk_h, krmk_w = krmk_gray_img.shape
            for y in range(krmk_h):
                for x in range(10):
                    krmk_bin_img[y,x] = 0
            contours = self._get_contours(krmk_bin_img, PARAMETER_KSIZE)
            x, y, w, h = self._get_max_area(contours)
            krmk_bin_img = krmk_bin_img[y:y+h, x:x+w]

        # トリミングの微調整
        height_cut = 0.3
        left_cut = 0.2
        right_cut = 0.12
        bonus_gray_img = bonus_gray_img[int(height*height_cut):int(-height*height_cut), int(width*left_cut):int(-width*right_cut)]

        # 輪郭再検出
        ret, bonus_bin_img = cv2.threshold(bonus_gray_img, 235, 255, cv2.THRESH_BINARY_INV)
        contours = self._get_contours(bonus_bin_img, BONUS_KSIZE)
        digit_boxes = []
        for i in range(0, len(contours)):
            x, y, w, h = cv2.boundingRect(contours[i])
            digit_boxes.append((x,y,w,h))

        # パラメータボーナスのバウンディングボックスのマージ
        merged_boxes, line_groups = self._merge_boxes_on_line(digit_boxes, gap_tol=BONUS_MERGE_PX)
        logger.debug("merge fin: bounus: %dboxes", len(merged_boxes))

        # 面積が大きい順に並び替え
        for i in range(len(merged_boxes)):
            for j in range(len(merged_boxes) - i -1):
                if merged_boxes[j][2] * merged_boxes[j][3] < merged_boxes[j+1][2] * merged_boxes[j+1][3]:
                    box = merged_boxes[j]
                    merged_boxes[j] = merged_boxes[j+1]
                    merged_boxes[j+1] = box

        # x軸で並び替え
        parameters_boxes = merged_boxes[:10]
        for i in range(len(parameters_boxes)):
            for j in range(len(parameters_boxes) - i -1):
                if parameters_boxes[j][0] > parameters_boxes[j+1][0]:
                    box = parameters_boxes[j]
                    parameters_boxes[j] = parameters_boxes[j+1]
                    parameters_boxes[j+1] = box

        # パラメータボーナスの読み取り
        bonus_list = []
        for i in range(len(parameters_boxes)):
            if 3 <= len(bonus_list):
                break
            x, y, w, h = parameters_boxes[i]
            try:
                bonus_roi = bonus_gray_img[y:y+h, x:x+w]
                bonus_roi = cv2.resize(bonus_roi, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
            except:
                continue
            ret, roi_bin = cv2.threshold(bonus_roi, 150, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
            try:
                val, has_pct, raw = self._ocr_number_with_percent(roi_bin[:,int(w*0.5):], return_ratio=False)
                if has_pct and val < 100.0:
                    bonus_list.append(val)
            except:
                pass

        param_list = ["vo", "da", "vi"]
        bonus_dict = {key: None for key in param_list}
        for key, value in zip(param_list, bonus_list):
            bonus_dict[key] = value

        # きらめき数の取得
        if is_boost_active:
            kirameki = self._ocr_digits_only(krmk_bin_img)
            if kirameki is not None:
                bonus_dict["kirameki"] = kirameki
            else: 
                bonus_dict["kirameki"] = None

        return bonus_dict
    
    def read_scores(self) -> dict[str: int]:
        """
        オーディションスコアの読み取り
        """
        scores_gray_img = self._orig_gray.copy()
        ret, bin_img = cv2.threshold(scores_gray_img, 240, 255, cv2.THRESH_BINARY_INV)
        contours = self._get_contours(bin_img, MAX_AREA_KSIZE)

        # 面積が最も大きい短形の探索
        x, y, w, h = self._get_max_area(contours)

        # スコア部分のみトリミング
        scores_gray_img = scores_gray_img[y:y+int(h*0.130), x:x+int(w*0.65)]

        # トリミング画像の情報を取得
        height, width = scores_gray_img.shape

        # トリミングの微調整
        cut_out = 0.08
        scores_gray_img = scores_gray_img[int(height*cut_out):, int(height*cut_out):]

        # 輪郭再検出
        ret, scores_bin_img = cv2.threshold(scores_gray_img, 150, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        contours = self._get_contours(scores_bin_img, SCORE_KSIZE)
        digit_boxes = []
        for i in range(0, len(contours)):
            x, y, w, h = cv2.boundingRect(contours[i])
            digit_boxes.append((x,y,w,h))

        # バウンディングボックスのマージ
        merged_boxes, line_groups = self._merge_boxes_on_line(digit_boxes, gap_tol=SCORE_MERGE_PX)

        # y軸で並び替え
        for i in range(len(merged_boxes)):
            for j in range(len(merged_boxes) - i -1):
                if merged_boxes[j][1] > merged_boxes[j+1][1]: #左の方が大きい場合
                    box = merged_boxes[j]
                    merged_boxes[j] = merged_boxes[j+1]
                    merged_boxes[j+1] = box

        # バーのバウンディングボックスの特定
        aspect = 0
        for i in range(len(merged_boxes)):
            x, y, w, h = merged_boxes[i]
            if aspect <= w/h:
                aspect = w/h
                num = i
        score_box = merged_boxes[num+1:]

        # 面積の大きい順に並び替え
        for i in range(len(score_box)):
            for j in range(len(score_box) - i -1):
                if score_box[j][2] * score_box[j][3] < score_box[j+1][2] * score_box[j+1][3]: #右の方が大きい場合
                    box = score_box[j]
                    score_box[j] = score_box[j+1]
                    score_box[j+1] = box
        vo_da_vi_box = score_box[:3]

        # x軸で並び替え
        for i in range(len(vo_da_vi_box)):
            for j in range(len(vo_da_vi_box) - i -1):
                if vo_da_vi_box[j][0] > vo_da_vi_box[j+1][0]: #左の方が大きい場合
                    box = vo_da_vi_box[j]
                    vo_da_vi_box[j] = vo_da_vi_box[j+1]
                    vo_da_vi_box[j+1] = box

        score_list = []
        param_list = ["sum_score", "vo", "da", "vi"]
        score_dict = {key: None for key in param_list}

        # 総スコアの読み取り
        x, y, w, h = merged_boxes[num-1]
        sum_score_roi = scores_bin_img[y:y+h, x:x+w]
        sum_score = self._ocr_digits_only(sum_score_roi)
        score_list.append(sum_score)

        # 各パラメータのスコア読み取り
        for i in range(len(vo_da_vi_box)):
            x, y, w, h = vo_da_vi_box[i]
            score_roi = scores_gray_img[y:y+h, x:x+w]
            score_roi = cv2.resize(score_roi, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
            ret, roi_bin = cv2.threshold(score_roi, 150, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
            score = self._ocr_digits_only(roi_bin)
            score_list.append(score)

        for key, value in zip(param_list, score_list):
            score_dict[key] = value

        return score_dict
    
    def _ocr_digits_only(self, bw, allow_comma: bool = False):
        """
        数字読み取り(数字のみ)
        """
        wl = "0123456789" + ("," if allow_comma else "")
        cfg = fr'--oem 1 --psm 7 -c tessedit_char_whitelist={wl}'
        txt = pytesseract.image_to_string(bw, lang='eng', config=cfg).strip()
        digits = ''.join(ch for ch in txt if ch.isdigit())
        return int(digits) if digits else None
    
    def _ocr_number_with_percent(self, bw, return_ratio = False):
        """
        bw: 2値画像
        戻り値: (value, has_percent, raw_text) or None
        """
        cfg = ("--oem 1 --psm 7 "
            "-c tessedit_char_whitelist=0123456789.% "
            "-c user_defined_dpi=300")
        raw = pytesseract.image_to_string(bw, lang="eng", config=cfg).strip()

        # 文字の揺れを正規化（全角や似た記号）
        t = (raw.replace("％", "%")
                .replace("．", ".")
                .replace("，", ",")
                .replace("·", ".")
                .replace("•", ".")
                .replace(" ", ""))   # スペース除去（必要なら）

        # 13.9%, 29%, 33.3% などを拾う
        m = re.search(r"(\d+(?:\.\d+)?)\s*(%)?$", t)
        if not m:
            return None

        val = float(m.group(1))
        has_pct = bool(m.group(2))

        if return_ratio and has_pct:
            val = val / 100.0

        return val, has_pct, raw
    
    def _split_params_3(self, digits: str, lo = 230, hi=2300):
        """
        digits: 連続数字列
        返り値: (vo, da, vi) 
        ルール: 各値は3～4桁、[lo, hi] に入る。優先: 4桁を多く含む分割。
        """
        
        n = len(digits)
        # 候補パターンを“4桁が多い順”に列挙
        patterns = []
        for a in (3, 4):
            for b in (3, 4):
                for c in (3, 4):
                    if a + b + c == n:
                        patterns.append((a, b, c))
        patterns.sort(key=lambda p: (-sum(x == 4 for x in p), ))  # 4が多いほど優先

        def valid(seg):
            # 先頭0は弾く（ゲームの表示上はゼロ埋めされない想定）
            if seg[0] == '0': return False
            v = int(seg)
            return lo < v <= hi

        for a, b, c in patterns:
            s1, s2, s3 = digits[:a], digits[a:a+b], digits[a+b:a+b+c]
            if all(map(valid, (s1, s2, s3))):
                return int(s1), int(s2), int(s3)

        # フォールバック: 下限を少し緩める（例: 200）
        if lo > 200:
            return self._split_params_3(digits, lo=200, hi=hi)

        raise ValueError(f"split failed: digits='{digits}' (len={n})")