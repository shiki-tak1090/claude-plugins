# 機械的な検査の道具の選び方

依存の向きなどのアーキテクチャのルールを検査するための、言語ごとの道具の目安。ここに挙げたものを第一候補とし、リポジトリですでに使っている lint の仕組みがあれば、そちらに寄せることを優先する。道具の最新の使い方は、公式のドキュメントで確かめてから設定する。

| 言語・環境 | 第一候補 | 代わりの方法 | 備考 |
|---|---|---|---|
| TypeScript / JavaScript | dependency-cruiser（`forbidden` のルールで層の依存を禁止する） | ESLint の `import/no-restricted-paths`（eslint-plugin-import）や eslint-plugin-boundaries | ESLint を使っていない（Biome など）リポジトリでも動く dependency-cruiser を優先する |
| Python | import-linter（`layers` や `forbidden` の契約） | 参照を調べるテストを書く | `uv run lint-imports` のように実行できる。設定は `.importlinter` ではなく `pyproject.toml` の `[tool.importlinter]` に書く（Windows では、`.importlinter` に日本語のコメントがあると cp932 で読めずに失敗する）。検査対象のパッケージが import できる必要があるので、`src` レイアウトなら `pyproject.toml` に build-system を置いてパッケージとしてインストールされるようにする |
| Go | depguard（golangci-lint の linter） | go-arch-lint | 層をパッケージで分けておく |
| Rust | 層ごとにクレートを分ける（Cargo の workspace）。クレートの依存関係そのものが検査になる | `use crate::<層>` を調べるテスト | 開発の初期なら、クレートに分けるのがもっとも確実 |
| Java / Kotlin | ArchUnit（テストとして書く） | — | 単体テストと一緒に実行される |
| C# | NetArchTest または ArchUnitNET | プロジェクト（.csproj）を層ごとに分ける | |
| Terraform | モジュールの分け方を規約に書き、tflint で書き方を検査する | — | 依存の向きは、モジュールの呼び出し関係をレビューで確かめる |

## どの道具でも守ること

- 検査は、ローカルで 1 つのコマンドで実行できるようにする（`CLAUDE.md` の「テスト・lint・ビルド」の表に書く）
- 違反があれば、終了コードが 0 以外になるようにする（`/project-dev:implement` が失敗を見分けるため）
- 違反のメッセージに、どのルールに違反したかが分かる名前を付ける（例: `domain-must-not-depend-on-infrastructure`）
- 既存の違反の除外は、ファイル単位にする
