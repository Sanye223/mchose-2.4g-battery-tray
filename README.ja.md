<p align="center">
  <a href="README.md">简体中文</a> | <a href="README.en.md">English</a> | <b>日本語</b>
</p>

# MCHOSE 2.4G Battery Tray

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/protocol-HID%20vendor%20page%200xFF01-8A2BE2" alt="HID">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT">
  <img src="https://img.shields.io/badge/verified%20on-MCHOSE%20A7%20Pro-orange" alt="A7 Pro">
</p>

ベンダー専用ソフトなしで動く Windows 常駐トレイアプリ。MCHOSE（マイコーズ）のワイヤレスマウス残量をタスクトレイに常時表示しつつ、**DPI 段階の切り替え**と**電池変化のログ**もできます。通信はすべて公式ファームウェアのベンダー独自 HID エンドポイント直叩きなので、MCHOSE Center のインストールは不要です。

> 電池も、機能も、全部入りです。

<p align="center">
  <img src="docs/panel-dark.png" width="360" alt="ダークパネル">
  &nbsp;&nbsp;
  <img src="docs/panel-light.png" width="360" alt="ライトパネル">
</p>

## ✨ 機能

**電池表示**
- トレイアイコンがそのまま電池ゲージ：下から満ちていくマウス型で、ライト/ダークのタスクバーに自動追従、しきい値以下で赤化。バッテリー / 数字 / リングの各スタイルも選択可
- 左クリックで Win11 Fluent 風のフライアウトを表示：すりガラス風カード、DWM 角丸、大きめの残量 %、プログレスバー、充電バッジ
- ホバーチップ：デバイス名 · 電池 · **現在の DPI** · 接続方式 · 最終更新時刻

**DPI 切り替え**
- 右クリックメニューから 6 段階（既定 400 / 800 / 1600 / 3200 / 6400 / 26000）をマウスのオンボード設定に直接書き込み
- USB / 2.4G の両パスに同時適用。書き込み後は必ず読み戻して検証し、段階テーブルが一致しなければ黙って通すのではなくはっきりエラーを報告
- 有効段は接続方式に追従：有線なら USB 側、ワイヤレスなら 2.4G 側を参照

**電池ログ**
- 1% 変わるごとに秒単位で記録。ケーブル接続中はポーリングを自動で 10 秒に引き上げ、外せば元の間隔へ復帰
- 日付ごとにグループ化して閲覧（曜日・統計付き）、ワンクリックで全消去
- 三重のデータ汚れ対策：ゴミパケット除去（10% 超のジャンプは棄却）、記録ベースラインは前回記録値を引き継ぎ（再起動でも脱落なし）、1 エントリ 5% 超の変化は記録しない

**その他**
- 低電力しきい値（10%〜40%）、自動起動、30 秒〜10 分のポーリング間隔
- 読み取り失敗時は前回値を表示し続け、アイコンが灰色にチラつかない

<p align="center">
  <img src="docs/history-window.png" width="420" alt="電池ログ画面">
</p>

## 📦 入手方法

[Releases](https://github.com/Sanye223/mchose-2.4g-battery-tray/releases) からビルド済み exe をダウンロードしてダブルクリック（データはユーザーディレクトリに保存、レジストリは触りません）。

ソースからビルドする場合：

```bat
git clone https://github.com/Sanye223/mchose-2.4g-battery-tray.git
cd mchose-2.4g-battery-tray

:: Python 3.13+（tkinter 必須）
python -m venv tkvenv
tkvenv\Scripts\python -m pip install pyinstaller hidapi pillow
tkvenv\Scripts\python -m PyInstaller --noconfirm --clean "2.4G电量托盘.spec"
```

> `fetch_wheels.py` は PyPI に繋がらない環境向けの依存取得ヘルパーです。

## 🚀 使い方

| 操作 | 機能 |
|---|---|
| トレイアイコン**左クリック** | パネルの表示 / 非表示 |
| 右クリック → **DPI 档位** | DPI 段階の切り替え（現在段にチェック） |
| 右クリック → **电量记录…** | 日付ごとの電池変化ログを表示 |
| 右クリック → 刷新间隔 | 30 秒 / 1 / 2 / 5 / 10 分（充電中は自動で 10 秒） |
| 右クリック → 低电量阈值 | 10%〜40%、しきい値未満でアイコン赤化 |
| 右クリック → 图标样式 | マウス / バッテリー / 数字 / リング |
| 右クリック → 开机自启 | 自動起動（HKCU Run キー、現在ユーザーのみ） |

デバッグ用 CLI フラグ：

```bat
2.4G电量托盘.exe --cli          :: 電池を 1 回読んで表示して終了
2.4G电量托盘.exe --panel        :: 起動時にパネルを開く
2.4G电量托盘.exe --interval 10  :: 今回の実行だけポーリング間隔を上書き
```

## 🗂 データの場所

すべて `%APPDATA%\MchoseBattery\` 配下：

| ファイル | 内容 |
|---|---|
| `tray.json` | 設定（間隔 / しきい値 / スタイル / 自動起動） |
| `history.json` | 電池変化ログ（最大 800 件のローリング） |
| `tray.log` | 実行ログ（読み取り失敗の現場や DPI 切替結果はここ） |

## 🔌 プロトコルとリバースの覚え書き

バイトレベルのフレーム形式は [`mchose_hid.py`](mchose_hid.py) のコメントに、詳しいリバース過程は [`docs/PROTOCOL.md`](docs/PROTOCOL.md) にあります。要点だけ：

- 電池照会のペイロードは `0x06`。**`F4 55` はプロファイル再読み込みコマンド**なので誤送信するとオンボード設定が再ロードされ、DPI もリセットされます
- A7 Pro の **DPI 書き込みフレームは読み取りフレームと構造が別物**：読み取ったフレームを 1 バイト変えて書き戻すとテーブル全体がズレて壊れます（実測で X が 26000/8193/16387 に）
- 2.4G リンクは時々完全なゴミパケットを返します（実測：83% → 6% → 83%）。表示とログの両方にジャンプ除去が必須
- ケーブル接続時はマウスが有線モードに切り替わり PID が変わるため、列挙条件は緩めに

## ❓ FAQ

**Q：「设备未响应」（デバイス無応答）と出る**
スリープ中や電源オフのマウスは HID ポーリングに応答しません。マウスを動かせば復帰します。戻らない場合はログの「found N interfaces」でリンクの有無を確認してください。

**Q：充電中に電池が読めない**
ケーブル接続で有線モードに切り替わり PID が変わりますが、アプリは候補インターフェースを全自動スキャンします。それでも失敗する場合は `tray.log` の「读取失败」部分を添えて issue をどうぞ。

**Q：DPI を変えたのにゲームに反映されない**
ログに「已切换到 XXX DPI」と出ているか確認。一部のゲームエンジンはマウス設定をキャッシュするので、ゲームを再起動してください。

## 🧪 動作確認

| デバイス | 状態 |
|---|---|
| MCHOSE A7 Pro（PAW3395、2.4G + 有線） | ✅ 実機でフル検証済み（電池 / ログ / DPI / 充電切替） |
| その他 MCHOSE A7 / A5 シリーズ | 同系プロトコルのため動くはず。動作報告お待ちしています |

VID が `5253` / `3837` で始まるインターフェースは全て試すので、他の MCHOSE 製品でもそのまま動く可能性があります。

## 🙏 謝辞

- [marsuyone/mchose-battery-tray](https://github.com/marsuyone/mchose-battery-tray) — **このプロジェクトの出発点**。A7 の電池プロトコル（`0x11` + `0x06`、65 バイト XOR フレーム）は同プロジェクトによる MCHOSE 公式 Web ドライバ（WebHID）のリバースに基づいています。そこからパネル・ログ・DPI 切替を発展させました
- [FerrisPulse](https://github.com/Ferris-echo/FerrisPulse) — コンフィグチャンネルの設計と A5 V2 プロトコルの参考
- [hidapi](https://github.com/libusb/hidapi) · [pystray](https://github.com/moses-palmer/pystray) · [Pillow](https://github.com/python-pillow/Pillow)

## License

[MIT](LICENSE) © 2026
