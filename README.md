# Gakumasu Discord Bot

「学園アイドルマスター」のスコア計算を支援するDiscord Botです。

『N.I.A』編および『初』編に対応しており、各シナリオの最終評価値計算・目標評価に必要なスコア計算を行えます。

また、ゲーム画面のスクリーンショットからYOLOによるUI検出とOCRを行い、
入力値を自動取得して計算する画像入力コマンドにも対応しています。

---

## 主な機能

- 最終評価値の計算
- 目標評価・目標スコアに必要な試験スコアの計算
- 画像からのUI自動検出
- OCRによるパラメータ・スコア読み取り
- 読み取り結果の手動修正
- Discord Componentsを利用した再計算
- 画像・推論結果・コマンド実行情報の保存
- SQLiteによるサーバー・ユーザー・推論ログ管理
- サーバー登録・利用停止・ユーザーブロックなどのアクセス制御

---

## 対応シナリオ

### N.I.A編

以下の計算に対応しています。

- 最終評価値計算
- 目標評価に必要なスコア計算
- 最終オーディションで獲得するパラメータの計算
- 画像入力による最終評価値計算
- 画像入力による必要スコア計算

画像入力では、ステータス画面・編成画面・スコア画面などから必要な情報を自動取得します。

### 初編

以下の計算に対応しています。

- 最終評価値計算
- 目標評価に必要な最終試験スコア計算
- 画像入力による最終評価値計算
- 画像入力による必要スコア計算

画像入力コマンドは現在 Legend に対応しています。

読み取ったVo / Da / Viパラメータ、中間試験スコア、最終試験スコア、
試験終了時アビリティなどはDiscord上から修正できます。

---

## 画像認識・OCR

画像入力コマンドでは、以下の流れでゲーム画面を解析します。

```text
Discordへ画像をアップロード
        ↓
YOLOによるUI検出
        ↓
必要領域をCrop
        ↓
OCR
        ↓
値の検証・補正
        ↓
スコア計算
        ↓
Discordへ結果を表示
````

UI検出には、YOLO11nをベースに学習した独自モデルを使用しています。

BotではONNX形式のモデルをONNX Runtimeから読み込み、
UI要素の検出を行っています。

学習コード・学習設定・学習済みモデルについては以下のリポジトリで公開しています。

[https://github.com/shunya200426/gakumasu-ui-detector](https://github.com/shunya200426/gakumasu-ui-detector)

### UI検出モデル

| 項目             | 内容        |
| -------------- | --------- |
| Base Model     | YOLO11n   |
| Input Size     | 640 × 640 |
| Classes        | 23        |
| Dataset Images | 1,100     |
| Export Format  | ONNX      |

Botで使用しているモデルは以下に配置しています。

```text
model_files/yolo/ui_detector.onnx
```

---

## コマンド

コマンドは `/gkms` グループ以下に登録されています。

### N.I.A編

```text
/gkms nia final_grade
/gkms nia final_grade_from_img
/gkms nia required_score
/gkms nia required_score_from_img
/gkms nia get_final_status
```

### 初編

```text
/gkms hajime final_grade
/gkms hajime final_grade_from_img
/gkms hajime required_score
/gkms hajime required_score_from_img
```

### Help

```text
/gkms help
```

画像入力コマンドでは、推論結果を確認したあとDiscord UIから値を修正し、
再計算できます。

---

## 技術スタック

主な使用技術は以下です。

* Python 3.12
* discord.py 2.6
* Ultralytics YOLO
* ONNX Runtime
* OpenCV
* tesserocr
* pytesseract
* NumPy
* SQLite
* pytest
* Ruff

画像認識モデルはUltralytics YOLOで学習し、
Bot上ではONNX Runtimeを使用して推論しています。

---

## セットアップ

### 1. リポジトリをClone

```bash
git clone https://github.com/shunya200426/gakumasu-discord-bot.git
cd gakumasu-discord-bot
```

### 2. Python仮想環境を作成

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

### 4. 環境変数を設定

プロジェクトルートに `.env` を作成します。

```env
DISCORD_BOT_TOKEN=your_bot_token
TESSDATA_PATH=/path/to/tessdata
```

必要に応じて以下の設定も利用できます。

```env
SYNC_MODE=global
TEST_GUILD_ID=
DEV_USER_ID=
ALERT_CHANNEL_ID=
DEV_DM_COOLDOWN_PER_GUILD=
DEV_DM_COOLDOWN_PER_USER=
DEV_DM_COOLDOWN_GLOBAL=
```

### 5. Botを起動

```bash
python main.py
```

---

## ディレクトリ構成

主な構成は以下です。

```text
.
├── bot/
│   └── Discord Bot本体・イベント処理
├── commands/
│   ├── nia_commands/
│   ├── hajime_commands/
│   └── help_command/
├── config/
│   └── Bot設定・パス・シナリオ設定
├── db/
│   └── SQLite・Repository
├── inference/
│   └── YOLO推論・推論結果モデル
├── model_files/
│   └── yolo/
│       └── ui_detector.onnx
├── models/
│   └── コマンド入出力モデル
├── ocr/
│   └── OCR・画像前処理
├── scenarios/
│   └── シナリオごとの計算ロジック
├── services/
│   └── 推論・画像保存・ログ等のService
├── tests/
│   └── 自動テスト
├── utils/
│   └── ログ・共通処理
├── main.py
├── requirements.txt
└── LICENSE
```

Discord入出力、計算ロジック、画像推論、OCR、保存処理を分離し、
各機能を独立して変更・テストできる構成にしています。

---

## 学習済みモデル・学習コード

UI検出モデルの学習コード、学習設定、評価結果、学習済みモデルは
以下のリポジトリで公開しています。

[https://github.com/shunya200426/gakumasu-ui-detector](https://github.com/shunya200426/gakumasu-ui-detector)

学習済みモデルはGitHub Releasesから取得できます。

[https://github.com/shunya200426/gakumasu-ui-detector/releases](https://github.com/shunya200426/gakumasu-ui-detector/releases)

学習リポジトリでは以下を公開しています。

* YOLO11nの学習コード
* Data Augmentation設定
* Dataset設定
* 23クラスの定義
* 評価結果
* ONNX Export処理
* `best.pt`
* `best.onnx`

学習に使用した画像およびアノテーションデータ本体は公開していません。

---

## データ保存・ログ

画像入力コマンドでは、設定およびユーザーの同意状態に応じて
入力画像や推論結果を保存します。

主な保存先は以下です。

```text
~/data/discord-bot/
├── bot.db
├── uploads/
│   ├── provided/
│   ├── inference/
│   ├── crops/
│   └── failed/
└── exports/
    └── inference/
```

ログは以下に保存します。

```text
~/logs/discord-bot/
```

入力画像および推論結果の保存期間は、現在デフォルトで180日です。

```python
IMAGE_RETENTION_DAYS = 180
```

ログについては保存期間を設けていません。

保存された画像・推論結果・DB記録は、
コマンド実行単位の `request_id` を利用して関連付けています。

---

## 開発・テスト

テストにはpytestを使用しています。

```bash
pytest
```

静的チェックにはRuffを使用しています。

```bash
ruff check .
```

---

## ライセンス

本リポジトリは GNU Affero General Public License v3.0
(AGPL-3.0) のもとで公開しています。

詳細は `LICENSE` を参照してください。

本プロジェクトでは Ultralytics YOLO を使用しています。

YOLOモデルの学習コードについては以下を参照してください。

[https://github.com/shunya200426/gakumasu-ui-detector](https://github.com/shunya200426/gakumasu-ui-detector)
