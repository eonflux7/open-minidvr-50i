; Keep UPOKE.BIN on the card. The file loader (bank04:8000, CODE:0E3E) deletes every file it has loaded
; (bank04:81E3 LCALL 1066, needed for UPDATE.TXT). That call now comes here and skips the delete only for our
; boot hook's request (generic name pointer 01:6BF0, see poke_b10.asm).

        .area   CODE (ABS)
        .org    0xDA00

nodel:  cjne    r3,#0x01,del
        cjne    r2,#0x6B,del
        cjne    r1,#0xF0,del
        ret
del:    ljmp    0x1066
