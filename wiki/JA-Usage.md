# インストールと使い方

## 必要なもの

- Python 3.10 以降
- Git
- NES エミュレーター。Windows では Mesen 2.2.1 で確認済みです。

## リポジトリを取得

```powershell
git clone https://github.com/jeong-jimin-github/FAMI-C.git
cd FAMI-C
```

## テトリス ROM をビルド

```powershell
python .\famic.py build .\examples\tetris.c -o .\build\tetris.nes --asm .\build\tetris.asm
```

Windows では次のスクリプトも使えます。

```powershell
.\build.ps1
```

## テスト

```powershell
python -m unittest discover -s tests
```

## コマンド

`build` は C ソースから iNES ROM を生成します。

```powershell
python .\famic.py build source.c -o build/game.nes --asm build/game.asm
```

`check` は ROM を書き出さず、コンパイルとアセンブルだけを確認します。

```powershell
python .\famic.py check source.c
```

`asm` は FAMI-C アセンブリを直接 ROM にします。

```powershell
python .\famic.py asm build/game.asm -o build/game.nes
```

