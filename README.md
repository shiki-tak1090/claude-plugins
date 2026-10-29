# claude-plugins

プロジェクトで共通して使う Claude Code のプラグインを管理するマーケットプレイスです。各プロジェクトのドキュメントリポジトリ（`<案件名>_document`）の `.claude/settings.json` から参照され、フォルダを信頼したメンバーの Claude Code に自動で読み込まれます。

## プラグイン一覧

| プラグイン | スキル | 内容 |
|---|---|---|
| `project-docs` | `/project-docs:basic-design` | 要件定義書から基本設計の納品物と開発ガイドラインを作成する。前提と判断事項を人に決めてもらい、基本設計の粒度で書き、文書のまとまりごとと横断のレビュー、指摘の仕分け、推敲を経て仕上げる |
| | `/project-docs:detailed-design` | 基本設計を前提に、機能ごとの詳細設計書を作成し、API と DB の統合仕様に反映する。前提と判断事項を人に決めてもらい、粒度を分けて書き、文書ごとと横断のレビュー、指摘の仕分け、推敲を経て仕上げる |
| | `/project-docs:design-export` | 設計書を Word・Excel に変換し、内容の欠落を照合する |
| `project-dev` | `/project-dev:design-to-tasks` | 確定した詳細設計を、PR 1 つ分の実装タスクに分解する（Backlog に貼る文面付き） |
| | `/project-dev:implement` | タスクを設計どおりに実装し、設計との照合レビューを経て PR を作る |
| | `/project-dev:setup-architecture` | 基本設計のアーキテクチャの方針を、コードリポジトリの実装規約（CLAUDE.md）と、依存の向きなどを機械的に検査する仕組みに落とし込む |

Backlog には接続しません。課題の起票、コメント、ステータスの変更は人が行い、スキルは貼り付ける文面を用意します。

## 更新の手順

1. スキルを直したら、`plugins/<プラグイン>/.claude-plugin/plugin.json` の `version` を上げる（版を上げないと、利用者に更新が届かない）
2. `claude plugin validate .` で形式を確認する
3. commit・push する

各プロジェクトの設定では自動更新を有効にしているため、利用者が Claude Code を次に起動したときに更新されます。すぐに反映したい場合は、利用者が `/plugin marketplace update project-plugins` を実行し、`/reload-plugins` で読み込み直します。

記法ルール（`skills/design-export/references/markdown-rules.md`。basic-design と detailed-design もこれに従って書く）や変換スクリプトの挙動を変える更新は、進行中のプロジェクトの設計書や納品物に影響します。変更内容を利用者に知らせてから push してください。

## 手元で試す

```bash
claude plugin validate .
```

```bash
claude --plugin-dir ./plugins/project-docs
```
