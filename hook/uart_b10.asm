; UART pin finder (test only, run from RAM via ADJUST.BIN). Lives in bank10 free space at E000.
; Entered from bank10:8A7D instead of the boot hook. Re-runs the firmware's UART setup (bank11:B939 via stub
; CODE:0B80; the normal boot already does this at bank10:89A3), then stops the system (interrupts off) and sends 'U'
; (0x55 = 0101010101 with start/stop bits) back to back forever: the TX pin averages ~half the supply voltage, so a
; multimeter finds it. Power off to end the test.

        .area   CODE (ABS)
        .org    0xE000

ut:     lcall   0x0B80              ; UART setup (pins, baud, SCON = 0x50)
        clr     0xAF                ; EA off: nothing else runs
uloop:  mov     0x99,#0x55          ; SBUF = 'U'
uwait:  jnb     0x99,uwait          ; TI
        clr     0x99
        sjmp    uloop
