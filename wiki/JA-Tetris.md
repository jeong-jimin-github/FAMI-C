# テトリス例

サンプルは `examples/tetris.c` です。

## ビルド

```powershell
python .\famic.py build .\examples\tetris.c -o .\build\tetris.nes --asm .\build\tetris.asm
```

## 操作

- Left / Right: 移動
- Down: ソフトドロップ
- A: 回転

## 内容

- ROM テーブルによるブロック形状
- ボード配列と衝突判定
- ライン消去
- コントローラー入力
- vblank に合わせた PPU 更新
- ネイティブキュー描画による高速なアクティブブロック更新

