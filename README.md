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

## サイトの公開方法 (本番運用)

`python run.py` は開発用サーバーのため、本番運用（インターネット公開）には使用しないでください。
以下の手順で、OS に合わせた本番用サーバーを使用し、Cloudflare Tunnel を使って安全に公開します。

### ステップ 1: アプリケーションサーバーの起動

OS に合わせて以下のコマンドを実行してください。

#### Windows の場合 (Waitress 使用)

`waitress` を使用して起動します（`requirements.txt` に含まれています）。

```powershell
waitress-serve --listen=127.0.0.1:5000 run:app
```

#### Mac / Linux の場合 (Gunicorn 使用)

`gunicorn` をインストールして起動します。

```bash
pip install gunicorn
gunicorn -w 4 -b 127.0.0.1:5000 run:app
```

※ `-w 4` はワーカー数です。CPUコア数に合わせて調整してください。

---

### ステップ 2: インターネットへの公開 (Cloudflare Tunnel)

ポート開放を行わずに、安全にローカルサーバーをインターネットに公開するには **Cloudflare Tunnel** が最も推奨される方法です。

1.  **Cloudflare アカウント作成**: [Cloudflare](https://www.cloudflare.com/) でアカウントを作成し、ドメインを登録します（持っていない場合）。
2.  **cloudflared のインストール**:
    *   **Windows**: [ダウンロードページ](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/) から `.msi` をダウンロードしてインストール。
    *   **Mac**: `brew install cloudflare/cloudflare/cloudflared`
    *   **Linux**: パッケージマネージャーまたはバイナリでインストール。
3.  **トンネルの作成**:
    コマンドラインで以下を実行し、ブラウザ認証を行います。
    ```bash
    cloudflared tunnel login
    ```
4.  **トンネルの起動**:
    以下のコマンドで、ローカルの 5000 番ポートを一時的に公開できます（Quick Tunnel）。
    ```bash
    cloudflared tunnel --url http://127.0.0.1:5000
    ```
    *   実行後、`https://<random-name>.trycloudflare.com` のようなURLが表示されます。これが公開URLです。
    *   **永続的なドメインで使用する場合**は、Cloudflare Zero Trust ダッシュボードから Tunnel を作成し、`http://127.0.0.1:5000` をターゲットに設定してください。

### その他の公開方法 (上級者向け)

*   **Ngrok**: `ngrok http 5000` で公開できます（テスト用途に便利）。
*   **VPS (Ubuntuなど)**: Nginx をリバースプロキシとして設定し、Gunicorn と連携させます。

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

`config.py` で設定を変更できます。

*   `SECRET_KEY`: セッション暗号化キー（本番では必ず変更してください）。
*   `UPLOAD_FOLDER`: ファイル保存先。
*   `MAX_CONTENT_LENGTH`: アップロードサイズ制限。
*   `SESSION_COOKIE_SECURE`: HTTPS 通信を強制するかどうか（Cloudflare Tunnel 使用時は `True` 推奨）。

## Acknowledgements

Special thanks to [きゅすみゃ](https://github.com/kyusumya) for their contribution to the development of this project.

## ライセンス

MIT License
