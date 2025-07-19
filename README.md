# research_record_app
研究記録アプリテンプレートのBeta版

## セットアップ
### 1. 環境構築(リポジトリをクローンする)
```bash
git clone https://github.com/Michi-Tsubaki/research_record_app.git
cd research_record_app
```

### 2. python3-venvがない場合(ある場合はパスする)
```bash
sudo apt install python3-venv
```

### 3. venv(仮想環境)を構築する
```bash
./setup.sh
```

### 4. アプリを起動する
```bash
./app.py
```

ターミナルに
```bash
Running on http://localhost:8000/ (Press CTRL+C to quit)
```
のようにサーバのIPが表示されるので，ブラウザで確認する．

## アプリの使い方