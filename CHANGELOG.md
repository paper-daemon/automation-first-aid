# Changelog

## Unreleased
- `doctor --url` の結果ログで、URL userinfo と token/secret/password/api key/signature 系query値を伏せる。
- 実際のrequest先は変更せず、表示用URLだけを安全化。
- credential付きURL / signed URL の回帰テストを追加。

## 1.0.0 - 2026-08-29
- 環境・空き容量・任意ネットワーク診断
- エラー文から再試行可否を分類
- JSON / JSONL の破損位置チェック
- Linux systemd --user 診断
- JSON出力対応
