extern void wait_vblank(void);
extern void ppu_put(unsigned char x, unsigned char y, unsigned char tile);

const unsigned char table[4] = { 1, 2, 3, 4 };
unsigned char data[4];

unsigned char twice(unsigned char value)
{
    return value + value;
}

void main(void)
{
    unsigned char i;
    i = 0;
    while (i < 4) {
        data[i] = twice(table[i]);
        i = i + 1;
    }

    while (1) {
        wait_vblank();
        ppu_put(1, 1, data[0]);
        ppu_put(2, 1, data[1]);
        ppu_put(3, 1, data[2]);
        ppu_put(4, 1, data[3]);
    }
}
