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
- 出力 ROM は NROM-256 / mapper 0 / 32 KB PRG + 8 KB CHR です。

## ランタイム API

```c
extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);
extern unsigned char read_pad(void);
extern unsigned char rand8(void);
```
### 効果音

プログラムが `sfx_play` を宣言し、ドライバーが参照する 5 つの const テーブルを
用意すると効果音を使えます。

```c
extern void sfx_play(unsigned char effect);

const unsigned char SFX_START[16];      /* 効果音ごとの開始フレーム */
const unsigned char SFX_LENGTH[16];     /* フレーム数。0 は未使用スロット */
const unsigned char SFX_CTRL[N];        /* フレームごとの $4004 デューティ／音量 */
const unsigned char SFX_TIMER_LO[N];    /* フレームごとの $4006 */
const unsigned char SFX_TIMER_HI[N];    /* 下位 3 ビットが $4007 へ */
```

スロット 0 は予約されており、`sfx_play(0)` は再生中の効果音を停止します。
3 つのフレームテーブルは同じ長さで、最大 256 要素です。効果音の再生中は
音楽ドライバーの後にパルス 2 を上書きし、終了するとチャンネルを BGM に
返します。


