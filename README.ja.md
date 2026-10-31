<p align="center">
  <a href="README.md">简体中文</a> | <a href="README.en.md">English</a> | <b>日本語</b> | <a href="README.es.md">Español</a> | <a href="README.ru.md">Русский</a>
</p>

# MCHOSE 2.4G Battery Tray

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/protocol-HID%20vendor%20page%200xFF01-8A2BE2" alt="HID">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT">
  <a href="https://github.com/Sanye223/mchose-2.4g-battery-tray/releases"><img src="https://img.shields.io/badge/release-v1.0.0-blue" alt="release v1.0.0"></a>
  <img src="https://img.shields.io/badge/verified%20on-MCHOSE%20A7%20Pro-orange" alt="A7 Pro">
</p>

**ベンダー専用ソフトに依存しない** Windows 常駐トレイアプリです。タスクトレイに MCHOSE ワイヤレスマウスの電池残量を常に表示し、DPI 段階の直接切り替えや、すべての電池変化の記録に対応しています。通信はすべて公式ファームウェアのベンダー独自 HID チャンネルを使うため、MCHOSE M HUB のインストールは不要です。

<p align="center">
  <img src="docs/panel-dark.png" width="360" alt="ダークパネル">
  &nbsp;&nbsp;
  <img src="docs/panel-light.png" width="360" alt="ライトパネル">
</p>

## ✨ 機能

**電池表示**
- トレイアイコンがそのまま電池ゲージ：マウス型が下から満ちていき、ライト/ダークのタスクバーに自動追従、しきい値を下回ると赤に。バッテリー / 数字 / リングの 3 スタイルも用意
- 左クリックで Win11 Fluent 風のパネルを表示：すりガラス調カード、DWM 角丸、大きめの残量数字、プログレスバー、充電バッジ
- ホバー表示：デバイス名 · 電池 · 現在の DPI · 接続方式 · 最終更新時刻

**DPI 切り替え**
- 右クリックメニューで 6 段階の DPI（既定 400 / 800 / 1600 / 3200 / 6400 / 26000）をマウスのオンボード設定にリアルタイム書き込み
- USB と 2.4G の両チャンネルに同時適用。書き込み後は必ず読み戻して検証し、段階テーブルが一致しない場合は黙って成功を装らず、明確にエラーを報告
- 有効段は接続方式で決まります：有線モードは USB 側、ワイヤレスモードは 2.4G 側を参照

**電池記録**
- 1% 変化するごとに 1 件記録し、時刻は秒単位。ケーブル接続中はポーリングが自動で 10 秒に切り替わり、外すと元の間隔に戻ります
- 日付ごとにグループ化して閲覧（曜日見出しと統計付き）、ワンクリック消去に対応
- 不正データへの三重防御：ゴミパケット除去（10% 超のジャンプは採用しない）、記録ベースラインは前回記録値を引き継ぐ（再起動でも脱落しない）、1 エントリ 5% 超の変化は記録しない

**その他**
- 低電力しきい値の通知（10%〜40% で調整可能）、自動起動、30 秒〜10 分の更新間隔
- 読み取り異常時は前回の残量を保持し、アイコンが灰色に点滅しません。ケーブル接続時は自動で有線リンクに切り替えて読み取ります

<p align="center">
  <img src="docs/history-window.png" width="420" alt="電池記録ウィンドウ">
</p>

## 📦 入手方法

[Releases](https://github.com/Sanye223/mchose-2.4g-battery-tray/releases) からビルド済み exe をダウンロードし、ダブルクリックで実行できます（データはユーザーディレクトリに保存され、レジストリには書き込みません）。

ソースからビルドする場合：

```bat
git clone https://github.com/Sanye223/mchose-2.4g-battery-tray.git
cd mchose-2.4g-battery-tray

:: Python 3.13+（tkinter が必要）
python -m venv tkvenv
tkvenv\Scripts\python -m pip install pyinstaller hidapi pillow
tkvenv\Scripts\python -m PyInstaller --noconfirm --clean "2.4G电量托盘.spec"
```

> `fetch_wheels.py` は補助スクリプトです。PyPI に直接接続できないネットワーク環境で、ビルド依存関係をオフラインで取得します。

## 🚀 使い方

| 操作 | 機能 |
|---|---|
| トレイアイコンを**左クリック** | 電池パネルの表示 / 非表示 |
| 右クリック → **DPI 档位** | DPI 段階の切り替え（ラジオボタンが現在段） |
| 右クリック → **电量记录…** | 日付ごとにグループ化された電池変化を表示 |
| 右クリック → 刷新间隔 | 30 秒 / 1 / 2 / 5 / 10 分（充電中は自動で 10 秒に短縮） |
| 右クリック → 低电量阈值 | 10%〜40%。しきい値を下回るとアイコンが赤に |
| 右クリック → 图标样式 | マウス / バッテリー / 数字 / リング |
| 右クリック → 开机自启 | 自動起動（HKCU Run キーに書き込み、現在ユーザーのみ） |

コマンドラインオプション（トラブルシューティング用）：

```bat
2.4G电量托盘.exe --cli          :: 電池を 1 回読み取って表示し、終了
2.4G电量托盘.exe --panel        :: 起動直後にパネルを開く（トレイアイコンが折りたたまれているとき用）
2.4G电量托盘.exe --interval 10  :: 今回の実行に限り更新間隔を上書き
```

## 🖱 DPI 段階の適応

トレイアイコンを右クリック → **DPI 档位**。6 段階が実際の数値（400〜26000）で表示され、ラジオボタンが現在段を示します。クリック 1 回でマウスのオンボード設定に書き込まれます：

![DPI 段階メニュー](docs/dpi-menu.png)

トレイのホバー表示にも、現在有効な DPI が同期表示されます。段階の判定は接続方式に従います：有線モードは USB 側、ワイヤレスモードは 2.4G 側を参照。X / Y の感度設定が異なる場合は `800/400` のように表示されます：

![DPI ホバー表示](docs/dpi-tooltip.png)

**段階切り替えの流れ**：オンボード設定を読み取り（コマンドバイト検証と全ゼロエコー除去つき）→ A7 Pro の書き込みフレーム形式で書き戻し → 250ms 待って読み戻し、「段階が反映 + テーブル無傷」を検証 → メニューとホバー表示を更新。全体は約 1 秒で、どの段階が失敗してもログに記録して元の設定を保持するため、テーブルが黙って壊されることはありません。

> A7 Pro の書き込みフレームのレイアウトは読み取りフレームと**同型ではありません**。読み取ったフレームをそのまま書き戻すとテーブル全体がズレて壊れます。これが FerrisPulse 実装との決定的な違いです。詳細は [docs/PROTOCOL.md](docs/PROTOCOL.md) を参照してください。

## 🗂 データの場所

データはすべて `%APPDATA%\MchoseBattery\` に保存されます：

| ファイル | 内容 |
|---|---|
| `tray.json` | 設定（間隔 / しきい値 / スタイル / 自動起動） |
| `history.json` | 電池変化の記録（最大 800 件、超過分は自動的にローリング） |
| `tray.log` | 実行ログ（読み取り失敗の状況や DPI 切替の結果はここに記録） |

## 🔌 プロトコルとリバースのノート

完全なフレーム形式は [`mchose_hid.py`](mchose_hid.py) のソースコメントを、リバースの詳細な過程とハマりどころは [`docs/PROTOCOL.md`](docs/PROTOCOL.md) を参照してください。特に重要な結論：

- 電池照会のペイロードは `0x06`。**`F4 55` はプロファイル再読み込みコマンド**です。送信するとマウスがオンボード設定を再読み込みし、DPI がリセットされます
- A7 Pro の **DPI 書き込みフレームは読み取りフレームと同型ではありません**：読み取ったフレームのバイトを書き換えて戻すと、テーブル全体がズレて壊れます（実測で X が 26000/8193/16387 に）
- 2.4G リンクは時々ゴミパケットを返します（実測：83% → 6% → 83%）。表示と記録の両方にジャンプ除去が必要です
- ケーブル接続時はマウスが有線モードに切り替わり PID が変わるため、デバイス列挙の条件は緩めておく必要があります

## ❓ FAQ

**Q：「设备未响应」（デバイス無応答）と表示される**
マウスがスリープ中または電源オフのとき、ファームウェアは応答しません。正常な挙動なので、マウスを動かせば復帰します。長時間応答しない場合は、ログの「found N interfaces」でリンクの状態を確認できます。

**Q：充電中に電池が読み取れない**
ケーブル接続するとマウスは有線モード（別 PID）に切り替わりますが、プログラムが候補インターフェースをすべて自動スキャンします。それでも失敗する場合は、`tray.log` の「读取失败」の部分を添えて issue を立ててください。

**Q：DPI を切り替えたのにゲームに反映されない**
ログに「已切换到 XXX DPI」と記録されているか確認してください。一部のゲームエンジンはマウス設定をキャッシュするため、ゲームを再起動すれば解決します。

## 🧪 互換性

| デバイス | 状態 |
|---|---|
| MCHOSE A7 Pro（PAW3395、2.4G + 有線） | ✅ 完全検証済み（電池 / 記録 / DPI / 充電時の切り替え） |
| その他の MCHOSE A7 シリーズ / A5 シリーズ | 同系プロトコルのため動作するはずです。動作報告を歓迎します |

VID が `5253` / `3837` で始まるインターフェースはすべて試行対象となるため、他の MCHOSE 製品でもそのまま動作する可能性があります。

## 🙏 謝辞

- [marsuyone/mchose-battery-tray](https://github.com/marsuyone/mchose-battery-tray) — **本プロジェクトの出発点**。A7 の電池プロトコル（`0x11` + `0x06`、65 バイト XOR フレーム、65 バイトへの補完が必須で不足時は err 87）は、同プロジェクトによる MCHOSE 公式 Web ドライバ（WebHID）のリバースによるものです。本プロジェクトはその電池プロトコルの上に、パネル・記録・DPI 切り替えを拡張しました
- [FerrisPulse](https://github.com/Ferris-echo/FerrisPulse) — コンフィグチャンネルのフレームワークと A5 V2 プロトコルの参考
- [hidapi](https://github.com/libusb/hidapi) · [pystray](https://github.com/moses-palmer/pystray) · [Pillow](https://github.com/python-pillow/Pillow)

## License

[MIT](LICENSE) © 2026
