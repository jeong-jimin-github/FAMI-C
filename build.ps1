param(
    [string]$Source = "examples/tetris.c",
    [string]$Output = "build/tetris.nes",
    [string]$Assembly = "build/tetris.asm"
)

python .\famic.py build $Source -o $Output --asm $Assembly
