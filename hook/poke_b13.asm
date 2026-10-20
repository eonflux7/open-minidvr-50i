; SD-card poke hook, record-start part. Lives in bank13 free space (zero padding from E742).
; Entered from bank13:C203 (was MOV R7,#1 / RET at the end of the per-recording start routine, after the AVI header
; has been built in big memory 0x7D0000 by bank11:8000).
; Applies UPOKE.BIN entries flagged "record start" (bit1) from the XDATA 0x6A00 buffer filled at boot, then arms the
; per-field read-back logger (peek_b07.asm) if the file has "peek" entries (flags & F4 == 34).
;
; Log layout in the AVI header JUNK chunk (file offset 0x14A, body 0x152..0x7FF3; window XDATA 0x8000 = file offset 0):
;   0x160: "PLG2", record length, number of peek entries, 16 bytes = logger state 6BE0-6BEF left by the previous
;          recording (armed flag, ptr, reclen, seq, event counters), then a copy of each peek entry (flags, hi, lo, count)
;   then records (see peek_b07.asm) until the chunk is full (stop at XDATA 0xFFF0).

        .area   CODE (ABS)
        .org    0xE800

rec:    mov     r7,#0x02
        lcall   apply
        lcall   loginit
        mov     r7,#0x01            ; the instructions we replaced
        ret

; magic: A = 0 if the buffer holds "PK01"
magic:  mov     dptr,#0x6A00
        movx    a,@dptr
        xrl     a,#0x50             ; 'P'
        jnz     mret
        inc     dptr
        movx    a,@dptr
        xrl     a,#0x4B             ; 'K'
        jnz     mret
        inc     dptr
        movx    a,@dptr
        xrl     a,#0x30             ; '0'
        jnz     mret
        inc     dptr
        movx    a,@dptr
        xrl     a,#0x31             ; '1'
mret:   ret

; apply(R7 = flag mask): walk entries at 0x6A04..0x6BBF; ops 0 write, 1 OR, 2 AND, 5 XOR (3 peek / 4 hdr skipped)
apply:  lcall   magic
        jnz     aret
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
        add     a,#0xFD             ; A = op - 2: op 5 = XOR
        jz      axor
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
axor:   movx    a,@dptr
        xrl     a,r0
        movx    @dptr,a
        sjmp    aloop
aret:   ret

ishort: ret

; loginit: disarm, apply header writes (op 4, flags & F2 == 42: byte at AVI header offset), then (if there are peek
; entries) write the log header and arm the logger
loginit:
        mov     r0,#0xE0            ; snapshot logger state 6BE0-6BEF -> 6BC0-6BCF (goes into the log header)
lsnap:  mov     dph,#0x6B
        mov     dpl,r0
        movx    a,@dptr
        mov     r1,a
        mov     a,r0
        add     a,#0xE0             ; -0x20
        mov     dpl,a
        mov     a,r1
        movx    @dptr,a
        inc     r0
        cjne    r0,#0xF0,lsnap
        mov     dptr,#0x6BE0
        clr     a
        movx    @dptr,a             ; disarmed
        lcall   magic
        jnz     ishort
        mov     r6,#0               ; peek entries
        mov     r7,#6               ; record length (fixed part)
        mov     dptr,#0x6A04
iscan:  mov     a,0x83              ; stop at 0x6BC0
        cjne    a,#0x6B,isok
        mov     a,0x82
        cjne    a,#0xC0,ischk
ischk:  jnc     isend
isok:   movx    a,@dptr
        jz      isend
        mov     r5,a                ; flags
        inc     dptr
        inc     dptr
        inc     dptr
        movx    a,@dptr             ; count
        inc     dptr
        xch     a,r5
        anl     a,#0xF4
        cjne    a,#0x34,iscan
        inc     r6
        mov     a,r7
        add     a,r5
        mov     r7,a
        jnc     iscan
        mov     r6,#0               ; record longer than 255 bytes: no logging
        sjmp    isend
isend:  mov     dptr,#0x6BE3
        mov     a,r7
        movx    @dptr,a             ; record length
        inc     dptr
        clr     a
        movx    @dptr,a             ; seq
        push    0xA8                ; IE
        clr     0xAF                ; EA off while we own the window
        mov     dptr,#0x7008        ; save window pages (7008/09 = read page, 700A/0B = write page, cf. CODE:00A2)
        movx    a,@dptr
        push    0xE0
        inc     dptr
        movx    a,@dptr
        push    0xE0
        inc     dptr
        movx    a,@dptr
        push    0xE0
        inc     dptr
        movx    a,@dptr
        push    0xE0
        mov     dptr,#0x7008        ; read and write page 0x00FA -> big-memory 0x7D0000 (AVI header) at XDATA 0x8000
        mov     a,#0xFA
        movx    @dptr,a
        inc     dptr
        clr     a
        movx    @dptr,a
        inc     dptr
        mov     a,#0xFA
        movx    @dptr,a
        inc     dptr
        clr     a
        movx    @dptr,a
        mov     dptr,#0x814A        ; header must have the JUNK chunk where we expect it
        movx    a,@dptr
        cjne    a,#0x4A,ijunk        ; 'J'
        inc     dptr
        movx    a,@dptr
        cjne    a,#0x55,ijunk        ; 'U'
        inc     dptr
        movx    a,@dptr
        cjne    a,#0x4E,ijunk        ; 'N'
        inc     dptr
        movx    a,@dptr
        cjne    a,#0x4B,ijunk        ; 'K'
        sjmp    ijok
ijunk:  ljmp    iend
ijok:   mov     r4,#0x6A            ; header writes
        mov     r5,#0x04
hwloop: mov     a,r4                ; stop at 0x6BC0
        cjne    a,#0x6B,hwok
        mov     a,r5
        cjne    a,#0xC0,hwchk
hwchk:  jnc     hwend
hwok:   mov     0x83,r4
        mov     0x82,r5
        movx    a,@dptr
        jz      hwend
        mov     r1,a                ; flags
        inc     dptr
        movx    a,@dptr
        mov     r2,a                ; offset hi
        inc     dptr
        movx    a,@dptr
        mov     r3,a                ; offset lo
        inc     dptr
        movx    a,@dptr
        mov     r0,a                ; value
        inc     dptr
        mov     r4,0x83
        mov     r5,0x82
        mov     a,r1
        anl     a,#0xF2
        cjne    a,#0x42,hwloop
        mov     a,r2
        orl     a,#0x80             ; window address 0x8000 + offset
        mov     0x83,a
        mov     0x82,r3
        mov     a,r0
        movx    @dptr,a
        sjmp    hwloop
hwend:  mov     a,r6                ; any peek entries?
        jnz     ilog
        ljmp    iend
ilog:   mov     dptr,#0x8160
        mov     a,#0x50             ; "PLG2"
        movx    @dptr,a
        inc     dptr
        mov     a,#0x4C
        movx    @dptr,a
        inc     dptr
        mov     a,#0x47
        movx    @dptr,a
        inc     dptr
        mov     a,#0x32
        movx    @dptr,a
        inc     dptr
        mov     a,r7
        movx    @dptr,a
        inc     dptr
        mov     a,r6
        movx    @dptr,a
        inc     dptr
        mov     r2,0x83             ; dst
        mov     r3,0x82
        mov     r4,#0x6B            ; previous logger state, snapshot taken at loginit entry
        mov     r5,#0xC0
        mov     r0,#16
hstate: mov     0x83,r4
        mov     0x82,r5
        movx    a,@dptr
        inc     dptr
        mov     r4,0x83
        mov     r5,0x82
        mov     0x83,r2
        mov     0x82,r3
        movx    @dptr,a
        inc     dptr
        mov     r2,0x83
        mov     r3,0x82
        djnz    r0,hstate
        mov     r4,#0x6A            ; src
        mov     r5,#0x04
hcopy:  mov     0x83,r4             ; copy the peek entries (r6 of them)
        mov     0x82,r5
        movx    a,@dptr
        anl     a,#0xF4
        xrl     a,#0x34
        mov     r1,a                ; 0 = peek entry
        mov     r0,#4
hbyte:  mov     0x83,r4
        mov     0x82,r5
        movx    a,@dptr
        inc     dptr
        mov     r4,0x83
        mov     r5,0x82
        cjne    r1,#0,hskip
        mov     0x83,r2
        mov     0x82,r3
        movx    @dptr,a
        inc     dptr
        mov     r2,0x83
        mov     r3,0x82
hskip:  djnz    r0,hbyte
        cjne    r1,#0,hcopy
        djnz    r6,hcopy
        mov     dptr,#0x6BE1        ; write ptr = after the header
        mov     a,r2
        movx    @dptr,a
        inc     dptr
        mov     a,r3
        movx    @dptr,a
        mov     dptr,#0x6BE0
        mov     a,#0x5A
        movx    @dptr,a             ; armed
iend:   mov     dptr,#0x700B        ; restore window pages
        pop     0xE0
        movx    @dptr,a
        mov     dptr,#0x700A
        pop     0xE0
        movx    @dptr,a
        mov     dptr,#0x7009
        pop     0xE0
        movx    @dptr,a
        mov     dptr,#0x7008
        pop     0xE0
        movx    @dptr,a
        pop     0xA8
iret:   ret
