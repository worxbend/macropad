/* RP2354A: 2 MB of flash stacked in the package, 520 kB of RAM (512 kB used here). */
MEMORY {
    FLASH : ORIGIN = 0x10000000, LENGTH = 2048K
    RAM : ORIGIN = 0x20000000, LENGTH = 512K
}

SECTIONS {
    /* The boot ROM looks for the image definition block in the first 4 kB of flash. */
    .start_block : ALIGN(4)
    {
        __start_block_addr = .;
        KEEP(*(.start_block));
    } > FLASH
} INSERT AFTER .vector_table;

/* Code starts after the image definition block. */
_stext = ADDR(.start_block) + SIZEOF(.start_block);
