# research_record_app
研究記録アプリテンプレートのBeta版

![画像]("./images/image.png")
## アプリの特徴
「研究ノート」に代わる研究記録アプリとして，改ざん防止のために，各ページ・各画像に固有のハッシュを付している．さらに，自身のプライベートなGitLab, GitHub環境にcommit, pushすることで研究内容を秘匿しつつ，「研究ノート」として管理できる 

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

