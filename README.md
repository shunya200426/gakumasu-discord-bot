# Gakumasu Discord Bot

## 概要

本プロジェクトは、ゲーム「学園アイドルマスター」におけるスコア計算を支援するDiscord Botです。
ユーザーのステータスや試験スコアをもとに最終評価値を算出し、目標評価に必要なスコアを自動で計算します。

また、OCR（画像認識）を活用することで、画像からステータスを読み取り、入力の手間を削減する機能も実装しています。

---

## 主な機能

* 最終評価値の計算
* 目標評価に必要なスコアの算出
* 画像からステータスを読み取るOCR機能
* Discord UI を用いた再計算機能

---

## 技術スタック

* Python 3.12
* discord.py
* OpenCV
* pytesseract
* numpy

---

## 工夫した点

* コマンド処理とロジックを分離し、保守性を向上
* シナリオごとにモジュールを分割し、拡張しやすい設計を採用
* OCRの精度問題に対し、手動修正可能なUIを導入
* ログ管理を実装し、運用時のトラブルシュートを容易にした

---

## 実績

* 約10サーバーで利用
* 月間100回以上のコマンド実行

---

## 動作環境

* Python 3.12.3
* Ubuntu (WSL) 環境で動作確認済み

---

## セットアップ方法

```bash
git clone https://github.com/shunya200426/gakumasu-discord-bot.git
cd gakumasu-discord-bot

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 環境変数の設定

`.env` ファイルを作成し、以下を設定してください。

```env
DISCORD_BOT_TOKEN=your_token_here
```

---

## 今後の改善

* YOLOを用いたUI自動検出
* 新シナリオ『HIF』編への対応

---

## ライセンス

本リポジトリは個人のポートフォリオとして公開しています。
