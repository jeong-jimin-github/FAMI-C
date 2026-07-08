# FAMI-C 日本語 Wiki

FAMI-C は NES / ファミコン向けの 6502 プログラムを C で書き、`.nes` ROM としてビルドするための小さな自己完結型ツールチェーンです。

## ページ一覧

- [[インストールと使い方|JA-Usage]]
- [[対応 C モデル|JA-C-Language]]
- [[コンパイラ構成|JA-Architecture]]
- [[テトリス例|JA-Tetris]]

## 主な特徴

- C ソースの解析、6502 アセンブリ生成、アセンブル、iNES パッケージングを 1 つの Python ファイルで実行します。
- NES に合わせた 8 ビット ABI と静的メモリモデルを使います。
- `wait_vblank`, `ppu_put`, `read_pad`, `rand8` などの基本ランタイムを提供します。
- `examples/tetris.c` にテトリス風のサンプルゲームがあります。
- Mesen 2.2.1 で実機に近い動作確認を行っています。

