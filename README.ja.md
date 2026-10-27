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

MCHOSE（マイコーズ）のワイヤレスマウス残量を、タスクトレイに常駐させてひと目で確認。ワンクリックでの DPI 切り替えや、秒単位の電池ログにも対応しています。ベンダー公式ソフトとはHID の独自エンドポイントで直接会話するので、MCHOSE Center を入れる必要は一切ありません。常駐物でこれだけ済むのは、なかなか爽快です。

<p align="center">
  <img src="docs/panel-dark.png" width="360" alt="ダークパネル">
  &nbsp;&nbsp;
  <img src="docs/panel-light.png" width="360" alt="ライトパネル">
</p>

## ✨ 機能

**残量は、ひと目で**
- トレイアイコンがそのままゲージ。減るにつれ下から満ちていくマウス型で、ライト/ダークのタスクバーに自動追従、しきい値を切ると赤に。マウス型が好みでなければ、バッテリー / 数字 / リングも用意済み
- 左クリックで Win11 Fluent 風のフライアウト：すりガラス調カード、DWM 角丸、読みやすいサイズの残量数字
- ホバーすれば全体像：デバイス名、電池、**現在の DPI**、接続方式、最終更新時刻

**DPI 切り替えは、ワンアクションで**
- 右クリックメニューから 6 段階（既定 400 / 800 / 1600 / 3200 / 6400 / 26000）をオンボード設定へ直書き込み
- USB / 2.4G の両パスに同時適用。書き込み後は必ず読み戻して検証し、テーブルが壊れていれば「書けたっぽい」ではなく、はっきりエラーを出します
- 有効段は接続方式に追従：有線なら USB 側、ワイヤレスなら 2.4G 側

**電池ログは、証拠を残す**
- 1% 変わるごとに秒単位で記録。ケーブルを刺すとポーリングが自動で 10 秒に加速し、外せば元の間隔へ静かに戻ります
- 日付ごとのグループ表示、統計付き、ワンクリック全消去
- ゴミパケット対策は三重構え：10% 超のジャンプは棄却、ベースラインは前回記録値を引き継ぎ（再起動でも脱落なし）、5% 超の変化は記録に残りません

**細かいところも、お任せ**
- 低電力しきい値（10%〜40%）、自動起動、30 秒〜10 分のポーリング間隔
- 読み取りに失敗しても前回値を表示し続けるので、深夜にアイコンが灰色にチラつくことはありません

<p align="center">
  <img src="docs/history-window.png" width="420" alt="電池ログ画面">
</p>

## 📦 入手方法

[Releases](https://github.com/Sanye223/mchose-2.4g-battery-tray/releases) のビルド済み exe が手軽です。データはユーザーディレクトリ配下に収まり、レジストリは汚しません。

自前でビルドする場合：

```bat
git clone https://github.com/Sanye223/mchose-2.4g-battery-tray.git
cd mchose-2.4g-battery-tray

:: Python 3.13+（tkinter 必須）
python -m venv tkvenv
tkvenv\Scripts\python -m pip install pyinstaller hidapi pillow
tkvenv\Scripts\python -m PyInstaller --noconfirm --clean "2.4G电量托盘.spec"
```

> `fetch_wheels.py` は PyPI に届かない環境向けの依存取得ヘルパーです。

## 🚀 使い方

| 操作 | 動作 |
|---|---|
| トレイアイコン**左クリック** | パネルの表示 / 非表示 |
| 右クリック → **DPI 档位** | DPI 段階の切り替え（現在段にチェック） |
| 右クリック → **电量记录…** | 日付ごとの電池ログを表示 |
| 右クリック → 刷新间隔 | 30 秒 / 1 / 2 / 5 / 10 分（充電中は自動で 10 秒） |
| 右クリック → 低电量阈值 | 10%〜40%、未満でアイコン赤化 |
| 右クリック → 图标样式 | マウス / バッテリー / 数字 / リング |
| 右クリック → 开机自启 | 自動起動（HKCU Run キー、現在ユーザーのみ） |

デバッグ用 CLI：

```bat
2.4G电量托盘.exe --cli          :: 1 回読んで表示して終了
2.4G电量托盘.exe --panel        :: 起動時にパネルを開く
2.4G电量托盘.exe --interval 10  :: 今回だけポーリング間隔を上書き
```

## 🗂 データの場所

すべて `%APPDATA%\MchoseBattery\` 配下：

| ファイル | 内容 |
|---|---|
| `tray.json` | 設定（間隔 / しきい値 / スタイル / 自動起動） |
| `history.json` | 電池ログ（800 件のローリング） |
| `tray.log` | 実行ログ。読み取り失敗の調査現場と DPI 切替の結果はここに落ちます |

## 🔌 プロトコル覚え書き

バイトレベルのフレーム定義は [`mchose_hid.py`](mchose_hid.py) のコメント、リバースの全容は [`docs/PROTOCOL.md`](docs/PROTOCOL.md) にまとめてあります。ハマりどころだけ先に：

- 電池照会のペイロードは `0x06`。**`F4 55` はプロファイル再読み込みコマンド**なので、誤送信するとオンボード設定が再ロードされ DPI も初期化されます。これは実機でやらかした話です
- A7 Pro の **DPI 書き込みフレームは、読み取りフレームと構造が別物**。読み取ったフレームを 1 バイトいじって書き戻すと、テーブル全体がズレて壊れます（実測：X が 26000/8193/16387 に）
- 2.4G リンクはたまに平気で嘘をつきます（実測：83% → 6% → 83%）。表示とログの両方にジャンプ除去がないと、ログがフィクションで埋まります
- ケーブルを刺すとマウスは有線モードに切り替わり PID が変わります。列挙条件を緩めておかないと、幽霊を追いかけることになります

## ❓ FAQ

**Q：「设备未响应」（デバイス無応答）と出る**
スリープ中や電源オフのマウスは HID ポーリングに答えません。マウスを動かせば戻ります。戻らないときはログの「found N interfaces」を見れば、リンク自体が生きているか分かります。

**Q：充電中に電池が読めない**
ケーブル接続で有線モード（別 PID）に切り替わりますが、候補インターフェースは全自動スキャンするように作ってあります。それでも失敗する場合は `tray.log` の「读取失败」部分を添えて issue をどうぞ。

**Q：DPI を変えたのにゲームに反映されない**
ログに「已切换到 XXX DPI」と出ているか確認を。一部のゲームエンジンはマウス設定をキャッシュするので、ゲームの再起動で収まります。

## 🧪 動作確認

| デバイス | 状態 |
|---|---|
| MCHOSE A7 Pro（PAW3395、2.4G + 有線） | ✅ 実機でフル検証済み。電池 / ログ / DPI / 充電時の切り替え、すべて |
| その他 MCHOSE A7 / A5 シリーズ | 同系プロトコルなので動く見込み。動作報告をいただけると助かります |

VID が `5253` / `3837` で始まるインターフェースはすべて候補にするので、他の MCHOSE 製品でもそのまま動くかもしれません。

## 🙏 謝辞

- [marsuyone/mchose-battery-tray](https://github.com/marsuyone/mchose-battery-tray) — **このプロジェクトの出発点**。A7 の電池プロトコル（`0x11` + `0x06`、65 バイト XOR フレーム）は、同プロジェクトによる MCHOSE 公式 Web ドライバ（WebHID）のリバースが元になっています。そこへパネル・ログ・DPI 切替を積み上げました
- [FerrisPulse](https://github.com/Ferris-echo/FerrisPulse) — コンフィグチャンネルの設計と A5 V2 プロトコルの参考
- [hidapi](https://github.com/libusb/hidapi) · [pystray](https://github.com/moses-palmer/pystray) · [Pillow](https://github.com/python-pillow/Pillow)

## License

[MIT](LICENSE) © 2026
