# 成功済み処理を、ログの古いエラー文字だけで再試行しない

Automation First Aid の `retry` 判定を実fixtureで見直した時、`exit_code=0` なのにログ本文へ `timeout` や `permission denied` が残っていると、再試行や停止判定へ入るケースがありました。

## 再現したケース

```text
exit_code = 0
log = "timeout while polling, final result saved"
```

修正前は `RETRY_WITH_BACKOFF`。でもこの入力では、最終結果は保存済みでプロセスも成功終了しています。

同じように、optional probe の警告として `permission denied` が残っていても、全体の exit code が 0 なら処理自体は成功済みです。

## 判定順序

今回の小さいCLIでは、次の順序へ変更しました。

1. `exit_code == 0` なら `NO_RETRY`
2. それ以外で permanent/configuration-like な語を確認
3. transient/network/resource-like な語や既知の一時失敗exit codeを確認
4. 分からなければ `REVIEW`

ポイントは、ログ文字列を無視することではなく、**より強い結果証拠を先に見ること**です。

## なぜ大事か

再試行は安全とは限りません。外部API、メッセージ送信、ファイル生成、課金処理などは、成功済みなのにもう一度走らせると二重副作用になることがあります。

本番ではexit codeだけで完全に判断できるわけでもありません。外部副作用がある処理なら、provider側ID、effect receipt、read-backなども合わせて確認する方が安全です。

この修正では、成功終了を優先する回帰テストを追加し、既存のtransient/permanent判定を含めて4テストを通しています。
