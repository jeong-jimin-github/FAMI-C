# 対応 C モデル

FAMI-C はホスト環境向けの ISO C 全体ではなく、NES 6502 で扱いやすい小さな C サブセットを対象にしています。

## 対応

- `char`, `unsigned char`, `int`, `unsigned int`, `void`
- グローバル変数と配列
- `const unsigned char` の ROM テーブル
- 関数宣言、関数呼び出し
- 静的ローカル変数
- 配列アクセス
- `if`, `else`, `while`, `for`, `break`, `continue`, `return`
- 8 ビット算術、比較、論理演算
- 単純なオブジェクト形式の `#define`

## 制限

- 算術 ABI は 8 ビットです。
- ローカル変数は静的に割り当てられます。
- 再帰はサポートしていません。
- ポインタ、構造体、共用体、キャスト、varargs、標準 C ライブラリは未実装です。
- 出力 ROM は NROM-128 / mapper 0 / 16 KB PRG + 8 KB CHR です。

## ランタイム API

```c
extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern unsigned char read_pad(void);
extern unsigned char rand8(void);
```

