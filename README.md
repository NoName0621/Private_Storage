# Private Storage

Python (Flask) で構築された、セキュリティ重視のプライベートクラウドストレージです。
Windows、Mac、Linux すべての環境で動作し、インターネット上に安全に公開することが可能です。

## 特徴

*   **セキュリティ**: Argon2 ハッシュ、CSRF 対策、セッション管理、ファイル整合性チェック (SHA256)。
*   **機能**:
    *   ドラッグ＆ドロップによるファイルアップロード。
    *   ユーザーごとの容量制限 (Quota)。
    *   パスワード変更機能。
    *   管理者パネルによるユーザー管理。
    *   ダークモード対応。
    *   ファイルの共有可能。

## 必要要件

*   Python 3.8 以上
*   pip

## インストール

1.  リポジトリをクローンまたはダウンロードし、ディレクトリに移動します。
2.  依存ライブラリをインストールします。

```bash
pip install -r requirements.txt
```

---

## 起動方法

### 開発環境での起動（推奨）

開発・テスト用には、Flask内蔵サーバーを使用できます：

```bash
python run.py
```

**注意**: 開発用サーバーは本番環境（インターネット公開）には使用しないでください。

---

## 本番環境での起動（推奨）

本番運用には、`start_server.py` スクリプトを使用することを強く推奨します。

### start_server.py を使った起動（最も簡単）

このスクリプトは、OSを自動検出し、適切なサーバー（WindowsならWaitress、Mac/LinuxならGunicorn）を起動します。さらに、**自動更新サービス**も同時に起動します。

```bash
python start_server.py
```

#### 機能：
- ✅ **OSを自動検出**: Windows、Mac、Linuxに対応
- ✅ **本番用サーバーを自動起動**: Waitress（Windows）またはGunicorn（Mac/Linux）
- ✅ **自動更新サービス**: GitHubから新しいバージョンを自動チェック・適用
- ✅ **自動再起動**: アップデート後にサーバーを自動再起動
- ✅ **プロセス監視**: サーバーの状態を監視

#### 停止方法：
- `Ctrl+C` を押すと、すべてのプロセスが正常に終了します

---

### Cloudflare Tunnel でインターネットに公開

ポート開放を行わずに、安全にローカルサーバーをインターネットに公開するには **Cloudflare Tunnel** が最も推奨される方法です。

#### セットアップ手順：

1. **Cloudflare アカウント作成**: [Cloudflare](https://www.cloudflare.com/) でアカウントを作成し、ドメインを登録します（持っていない場合）。

2. **cloudflared のインストール**:
   - **Windows**: [ダウンロードページ](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/) から `.msi` をダウンロードしてインストール。
   - **Mac**: `brew install cloudflare/cloudflare/cloudflared`
   - **Linux**: パッケージマネージャーまたはバイナリでインストール。

3. **トンネルの作成**:
   コマンドラインで以下を実行し、ブラウザ認証を行います。
   ```bash
   cloudflared tunnel login
   ```

4. **トンネルの起動**:
   以下のコマンドで、ローカルの 5000 番ポートを一時的に公開できます（Quick Tunnel）。
   ```bash
   cloudflared tunnel --url http://127.0.0.1:5000
   ```
   - 実行後、`https://<random-name>.trycloudflare.com` のようなURLが表示されます。これが公開URLです。
   - **永続的なドメインで使用する場合**は、Cloudflare Zero Trust ダッシュボードから Tunnel を作成し、`http://127.0.0.1:5000` をターゲットに設定してください。

---

## 高度な起動方法（カスタマイズが必要な場合）

OS に合わせて手動でサーバーを起動したい場合や、カスタマイズが必要な場合は、以下の方法を使用できます。

### Windows の場合 (Waitress 使用)

```powershell
waitress-serve --threads=4 --listen=127.0.0.1:5000 run:app
```

### Mac / Linux の場合 (Gunicorn 使用)

まず Gunicorn をインストール：
```bash
pip install gunicorn
```

起動：
```bash
gunicorn -w 4 -b 127.0.0.1:5000 run:app
```

**ヒント**: ワーカー数（`-w 4`）やスレッド数（`--threads=4`）は、CPUコア数に合わせて調整できます。ただし、`config.py` で設定すれば `start_server.py` が自動的に適用します。

### その他の公開方法

- **Ngrok**: `ngrok http 5000` で公開できます（テスト用途に便利）。
- **VPS (Ubuntuなど)**: Nginx をリバースプロキシとして設定し、Gunicorn と連携させます。

---

## 管理者アカウント

初回起動時に自動作成されます。

*   ユーザー名: `admin`
*   パスワード: `admin_password_change_me`
*   **管理者パネル URL**: `/admin_secure_panel_z8x9/`
    *   (例: `http://127.0.0.1:5000/admin_secure_panel_z8x9/`)

**重要**: ログイン後、必ずパスワードを変更してください。

### 管理パネル URL の変更方法 (セキュリティ強化)

デフォルトの管理パネル URL (`/admin_secure_panel_z8x9/`) は推測されやすいため、本番環境では必ず変更することを強く推奨します。

#### 変更手順:

1. **`app/routes_admin.py` を開く**
2. **1行目のBlueprint定義を変更**:
   ```python
   # 変更前
   admin_bp = Blueprint('admin', __name__, url_prefix='/admin_secure_panel_z8x9')
   
   # 変更後 (例: ランダムな文字列に変更)
   admin_bp = Blueprint('admin', __name__, url_prefix='/my_secret_admin_xyz123')
   ```
3. **サーバーを再起動**
4. **新しいURLでアクセス**:
   - 例: `http://127.0.0.1:5000/my_secret_admin_xyz123/`

#### URL の推奨事項:

- **長くランダムな文字列を使用** (例: `/admin_8k2j9x4m7n1q5p/`)
- **推測されやすい単語を避ける** (`/admin/`, `/panel/` など)
- **記号や数字を組み合わせる**
- **変更後のURLは安全に保管**

#### セキュリティのヒント:

管理パネルURLを変更することで、自動化された攻撃やブルートフォース攻撃のリスクを大幅に軽減できます。

---

## 設定

`config.py` でアプリケーションの動作を細かく設定できます。

### すべての設定項目

#### 基本設定

*   **`SECRET_KEY`**: セッション暗号化キー
    - **デフォルト**: `'dev-secret-key-change-in-production-84758473'`
    - **重要**: 本番環境では必ず変更してください
    - **環境変数**: `SECRET_KEY`

*   **`SQLALCHEMY_DATABASE_URI`**: データベース接続URL
    - **デフォルト**: `'sqlite:///storage.db'`
    - **環境変数**: `DATABASE_URL`

#### アップロード設定

*   **`UPLOAD_FOLDER`**: アップロードファイルの保存先
    - **デフォルト**: プロジェクトルート内の `uploads/` フォルダ

*   **`MAX_CONTENT_LENGTH`**: アップロードサイズの上限
    - **デフォルト**: `5 * 1024 * 1024 * 1024` （5GB）

#### セキュリティ設定

*   **`SESSION_COOKIE_HTTPONLY`**: JavaScriptからのCookieアクセスを防止
    - **デフォルト**: `True`

*   **`SESSION_COOKIE_SECURE`**: HTTPS通信でのみCookieを送信
    - **デフォルト**: `False`（ローカル開発用）
    - **推奨**: Cloudflare Tunnel使用時は `True` に設定

*   **`SESSION_COOKIE_SAMESITE`**: CSRF攻撃対策
    - **デフォルト**: `'Lax'`

#### レート制限

*   **`RATELIMIT_DEFAULT`**: デフォルトのレート制限
    - **デフォルト**: `"1000000 per day"`

*   **`RATELIMIT_STORAGE_URL`**: レート制限情報の保存先
    - **デフォルト**: `"memory://"`

#### サーバー設定

*   **`SERVER_WORKERS`**: Gunicorn（Mac/Linux）のワーカー数
    - **デフォルト**: `4`
    - **推奨**: CPUコア数と同じか、CPUコア数の2倍程度
    - **環境変数**: `SERVER_WORKERS`
    - **注意**: `start_server.py` 使用時のみ有効

*   **`SERVER_THREADS`**: Waitress（Windows）のスレッド数
    - **デフォルト**: `4`
    - **推奨**: CPUコア数と同じか、CPUコア数の2倍程度
    - **環境変数**: `SERVER_THREADS`
    - **注意**: `start_server.py` 使用時のみ有効

---

### 設定の変更方法

#### 方法1: config.py を直接編集（推奨）

```python
class Config:
    SECRET_KEY = 'your-super-secret-key-here'
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024 * 1024  # 10GBに変更
    
    # Server Settings
    SERVER_WORKERS = 8  # Mac/Linux
    SERVER_THREADS = 8  # Windows
    
    # セキュリティ強化（HTTPS使用時）
    SESSION_COOKIE_SECURE = True
```

#### 方法2: 環境変数で設定

**Windows (PowerShell)**:
```powershell
$env:SECRET_KEY="your-super-secret-key"
$env:SERVER_WORKERS="8"
$env:SERVER_THREADS="8"
```

**Mac / Linux (Bash)**:
```bash
export SECRET_KEY="your-super-secret-key"
export SERVER_WORKERS=8
export SERVER_THREADS=8
```


## Acknowledgements

Special thanks to [きゅすみゃ](https://github.com/kyusumya) for their contribution to the development of this project.

## ライセンス

MIT License

