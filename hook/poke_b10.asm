; SD-card poke hook, boot part. Lives in bank10 free space (zero padding from D9F5).
; Entered from bank10:8A7D (was LCALL A517, right after the firmware's own UPDATE.TXT check).
;
; If the card is ready and UPOKE.BIN exists, the firmware's loader (CODE:0E3E, bank04:8000) copies it to
; big-memory 0x7FFE00 (names starting with 'U' go there; <= 512 bytes). We copy those 512 bytes through the
; XDATA window (page 0xFF at 0xFE00) to XDATA 0x6A00 and apply entries flagged "boot".
;
; UPOKE.BIN: "PK01", then 4-byte entries [flags][addr hi][addr lo][value], flags 0 = end.
;   flags bit0 = apply at boot, bit1 = apply at record start, high nibble = op: 0 write, 1 OR, 2 AND.
; Entries are read from 0x6A04 up to 0x6BBF (6BC0-6BCF: logger state snapshot, 6BE0-6BE8: logger state).

        .area   CODE (ABS)
        .org    0xDA00

boot:   mov     dptr,#0x6BE0        ; logger disarmed; state, counters and experiment switches 6BE0-6BEF cleared
        mov     r7,#16
        clr     a
bclr:   movx    @dptr,a
        inc     dptr
        djnz    r7,bclr
        mov     dptr,#0x6BFB        ; edge fix switch, AC40-path wait (peek_b07.asm) off
        movx    @dptr,a
        inc     dptr
        movx    @dptr,a
        lcall   0x0CEE              ; card ready? (bank04:A543) -> R7
        mov     a,r7
        jz      bdone
        mov     dptr,#0x6BFF        ; RAM self-test of the buffer area
        mov     a,#0x5A
        movx    @dptr,a
        movx    a,@dptr
        cjne    a,#0x5A,bdone
        mov     a,#0xA5
        movx    @dptr,a
        movx    a,@dptr
        cjne    a,#0xA5,bdone
        mov     dptr,#0x6A00        ; invalidate any stale buffer
        clr     a
        movx    @dptr,a
        mov     r0,#0xF0            ; copy 11-char 8.3 name to XDATA 0x6BF0 (bank10:BA7A, src in CODE)
        mov     r4,#0x6B
        mov     r2,#>name
        mov     r1,#<name
        lcall   0xBA7A
        mov     r3,#0x01            ; generic ptr 01:6BF0 -> look up + load file
        mov     r2,#0x6B
        mov     r1,#0xF0
        lcall   0x0E3E
        mov     a,r7
        jz      bdone
        push    0xA8                ; IE
        clr     0xAF                ; EA off while we own the window
        mov     dptr,#0x7008        ; save window read page (we only read; 700A/0B is the write page)
        movx    a,@dptr
        push    0xE0
        inc     dptr
        movx    a,@dptr
        push    0xE0
        mov     dptr,#0x7008        ; page 0x00FF -> big-memory 0x7F8000 at XDATA 0x8000
        mov     a,#0xFF
        movx    @dptr,a
        inc     dptr
        clr     a
        movx    @dptr,a
        mov     r2,#0xFE            ; src 0xFE00
        mov     r3,#0x00
        mov     r4,#0x6A            ; dst 0x6A00
        mov     r5,#0x00
        mov     r6,#2               ; 2 x 256 bytes
        mov     r7,#0
cpy:    mov     0x83,r2
        mov     0x82,r3
        movx    a,@dptr
        inc     dptr
        mov     r2,0x83
        mov     r3,0x82
        mov     0x83,r4
        mov     0x82,r5
        movx    @dptr,a
        inc     dptr
        mov     r4,0x83
        mov     r5,0x82
        djnz    r7,cpy
        djnz    r6,cpy
        mov     dptr,#0x7009        ; restore window page
        pop     0xE0
        movx    @dptr,a
        mov     dptr,#0x7008
        pop     0xE0
        movx    @dptr,a
        pop     0xA8
        mov     r7,#0x01            ; apply "boot" entries
        lcall   apply
bdone:  ljmp    0xA517              ; the call we replaced

; apply(R7 = flag mask): walk entries at 0x6A04..0x6BBF
apply:  mov     dptr,#0x6A00
        movx    a,@dptr
        cjne    a,#0x50,aret        ; 'P'
        inc     dptr
        movx    a,@dptr
        cjne    a,#0x4B,aret        ; 'K'
        inc     dptr
        movx    a,@dptr
        cjne    a,#0x30,aret        ; '0'
        inc     dptr
        movx    a,@dptr
        cjne    a,#0x31,aret        ; '1'
        mov     r2,#0x6A
        mov     r3,#0x04
aloop:  mov     a,r2                ; stop at 0x6BC0
        xrl     a,#0x6B
        jnz     aok
        mov     a,r3
        clr     c
        subb    a,#0xC0
        jnc     aret
aok:    mov     0x83,r2
        mov     0x82,r3
        movx    a,@dptr
        jz      aret
        mov     r4,a                ; flags
        inc     dptr
        movx    a,@dptr
        mov     r5,a                ; addr hi
        inc     dptr
        movx    a,@dptr
        mov     r6,a                ; addr lo
        inc     dptr
        movx    a,@dptr
        mov     r0,a                ; value
        mov     a,r3
        add     a,#4
        mov     r3,a
        mov     a,r2
        addc    a,#0
        mov     r2,a
        mov     a,r4
        anl     a,r7
        jz      aloop
        mov     0x83,r5
        mov     0x82,r6
        mov     a,r4
        swap    a
        anl     a,#0x0F
        jz      awr
        dec     a
        jz      aor
        dec     a
        jz      aand
        sjmp    aloop
awr:    mov     a,r0
        movx    @dptr,a
        sjmp    aloop
aor:    movx    a,@dptr
        orl     a,r0
        movx    @dptr,a
        sjmp    aloop
aand:   movx    a,@dptr
        anl     a,r0
        movx    @dptr,a
        sjmp    aloop
aret:   ret

name:   .ascii  "UPOKE   BIN"
