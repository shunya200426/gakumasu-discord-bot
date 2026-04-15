# test.py
import time
from pathlib import Path
import argparse

from ocr.core import OCR

def file_to_bytes(path: Path) -> bytes:
    # Botの attachment.read() 相当（bytesで取得）
    return path.read_bytes()

def main():
    ap = argparse.ArgumentParser(description="OCR 単体テスト（バイト列経由）")
    ap.add_argument("image", type=Path, help="入力画像のパス（PNG/JPG など）")
    ap.add_argument("--debug", type=Path, default=None, help="デバッグ出力ディレクトリ（任意）")
    ap.add_argument("--h", type=int, default=900, help="正規化する高さ target_h（既定: 900）")
    args = ap.parse_args()

    img_path: Path = args.image
    if not img_path.exists():
        raise FileNotFoundError(img_path)

    img_bytes = file_to_bytes(img_path)

    t0 = time.perf_counter()
    ocr = OCR(img_bytes)

    # パラメータ
    params = ocr.read_params()

    # パラメータボーナス
    # params = ocr.read_bonus(is_boost_active=False)

    # スコア
    # params = ocr.read_scores()

    ms = (time.perf_counter() - t0) * 1000
    print(f"[OK] time: {ms:.1f} ms")
    print(params)

if __name__ == "__main__":
    main()
