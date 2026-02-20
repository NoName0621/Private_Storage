# Private Storage

Python (Flask) で構築した、セキュリティ重視のプライベートクラウドストレージです。  
Windows / macOS / Linux で動作し、ローカル運用からインターネット公開まで対応できます。

## 概要 ✨

- セキュアな認証・セッション管理（Argon2, CSRF 対策）
- ユーザーごとの容量制限（Quota）
- 管理者パネルによるユーザー管理
- ファイル共有、フォルダ機能、プレビュー（β）
- 自動更新サービス（GitHub 連携）

## 主な機能

- ファイルアップロード（ドラッグ&ドロップ）
- パスワード変更
- ファイル整合性チェック（SHA256）
- ダークモード
- 自動更新後のサーバー再起動

## 必要要件

- Python 3.8 以上
- pip
- Linux / macOS で本番起動する場合: `gunicorn`

## インストール

1. リポジトリを clone（またはダウンロード）して、プロジェクトディレクトリへ移動します。
2. `start_server.py` を使う場合、`.venv` 作成と `requirements.txt` のインストールは起動時に自動実行されます。
3. `run.py` や手動コマンドで起動する場合のみ、事前に以下を実行してください。

```bash
pip install -r requirements.txt
```

Linux / macOS で Gunicorn を手動利用する場合は、必要に応じて以下も実行してください。

```bash
pip install gunicorn
```

## 起動方法 🚀

```bash
python start_server.py
```

`start_server.py` は以下を自動で実行します。

- OS 自動判定（Windows: Waitress / Linux・macOS: Gunicorn）
- `.venv` 作成
- `requirements.txt` のインストール
- 更新サービス (`update_service.py`) の起動
- プロセス監視と必要時の再起動

注意:

- Linux / macOS では `gunicorn` が必要です（未導入の場合は起動できません）
- 停止は `Ctrl + C`

## 手動での本番起動（カスタマイズしたい場合）

### Windows（Waitress）

```powershell
waitress-serve --threads=4 --listen=127.0.0.1:5000 run:app
```

### Linux / macOS（Gunicorn）

```bash
gunicorn -w 4 -b 127.0.0.1:5000 run:app
```

## Cloudflare Tunnel で公開 🌐

ポート開放なしで公開する場合は Cloudflare Tunnel が有効です。

```bash
cloudflared tunnel login
cloudflared tunnel --url http://127.0.0.1:5000
```

## 管理者アカウント

初回起動時に自動作成されます。

- ユーザー名: `admin`
- パスワード: `admin_password_change_me`
- 管理画面 URL: `/admin_secure_panel_z8x9/`

重要:

- 初回ログイン後は必ずパスワードを変更してください
- 本番環境では管理画面 URL の変更を推奨します

## 設定

`config.py` で主要設定を管理します。

主要な設定例:

- `SECRET_KEY`
- `SQLALCHEMY_DATABASE_URI`
- `MAX_CONTENT_LENGTH`
- `SESSION_COOKIE_SECURE`
- `SERVER_WORKERS`（Linux / macOS の Gunicorn ワーカー数）
- `SERVER_THREADS`（Windows の Waitress スレッド数）

環境変数でも一部設定を上書きできます（例: `SECRET_KEY`, `SERVER_WORKERS`, `SERVER_THREADS`）。

## セキュリティに関する注意 🔐

- 既定の管理者情報は必ず変更してください
- 本番運用では強固な `SECRET_KEY` を設定してください
- HTTPS 運用時は `SESSION_COOKIE_SECURE=True` を推奨します

## Acknowledgements

Special thanks to [きゅすみゃ](https://github.com/kyusumya) for contributions to this project.

## License

MIT License
