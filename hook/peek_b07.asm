; Read-back logger + experiment switches, interrupt part. Lives in bank07 free space (zero padding from D9F5).
; The INT0 dispatcher (CODE:4D12, register bank 2, saves ACC/B/DPTR/PSW) calls its four bank07 sub-handlers through
; stubs CODE:1ACE/1AD4/1ADA/1AE0 (90 hi lo 02 02AE). The stubs now point at the jump table below; each wrapper logs
; one record and then jumps to the original handler:
;   ev1 bit4 -> B26E (TV-out vsync)   ev2 bit1 -> B222 (capture done)   ev3 bit14 -> 9E43   ev4 bit2 -> B6E8 (JPEG done)
;   ev5 = JPEG start for video recording: bank07:AB1E (output address [5676] -> 7324, source descriptor 1E75 via A943,
;         start bit 7300.2 via 82DA), entered only by LJMP from the JPEG scheduler at 96A9
;   ev6 = capture-done for a field the gate rejects (not passed to B222)
; Delays (x256 DJNZ loops, 0 = none; tearing experiments): [6BEB] before B222 (accepted capture-done, before the
;   buffer swap), [6BEE] before the JPEG start (ev5), [6BEF] at a rejected field's capture-done.
;   [6BEE] = FF: instead wait until the capture has finished the current field (720D bit2 set), max 255x256 polls.
; Edge fix [6BFB] (bit0 = top, bit1 = bottom; 0 = off): right before the JPEG start bit is set (82DA, called from the two
;   D1 start paths AB72 / AC8F), copy field row 1 over row 0 (top field: WSS data line) and row 286 over row 287 (last
;   line: PAL half line / blanking) in BOTH capture buffers (table 16FC, 20-byte entries, address in bytes 1-3 of
;   entries 0 and 1; line pitch 1440 bytes). In D1 the JPEG engine reads the capture buffer directly (lock-step);
;   [5676] at this point is the bitstream OUTPUT address (7324/7410), not the picture. The buffer about to be encoded is
;   complete (JPEG start waits for end of field); the other one is fixed again before its own encode.
;   The AC8F path is logged as event 3 (bit14 never fires). It starts mid-field: with [6BFC] = FF it first waits for
;   the end of the field too (as ev5 does with [6BEE] = FF), so the edge fix sees complete rows 286/287.
; Field gate (50i experiments): the dispatcher's own "720D.0 = 1" test (CODE:4DB7) is NOPed; ev2 decides by [6BEC]:
;   0 = stock (field with 720D.0 = 1 only), 1 = both fields, 2 = field with 720D.0 = 0 only.
; Per-frame pokes: UPOKE.BIN entries with flags bit3 ("frame") are applied on every accepted capture-done, before B222.
;
; Logging is armed by the record-start hook (poke_b13.asm, loginit) and writes into the JUNK chunk of the AVI header
; that the firmware builds in big memory at 0x7D0000 (window page 0xFA at XDATA 0x8000; flushed to the card at stop).
; Big-memory window: 7008/09 = read page, 700A/0B = write page.
; XDATA: 6BE0 = 0x5A armed, 6BE1/6BE2 = write ptr (XDATA address in the window), 6BE3 = record length,
; 6BE4 = sequence number, 6BE5-6BEA = call counters ev1-ev6 (always counted), 6BEB = delay before B222,
; 6BEC = field gate, 6BED = event mask (bit n = log event n; 0 = log all), 6BEE / 6BEF = delays (see above).
; All cleared at boot (poke_b10.asm).
; Record: A0+event, seq, TH0, TL0, TH2, TL2, then the bytes of every "peek" entry (flags & F4 == 34) in file order.
; Peek addresses must be below 0x8000 (0x8000-0xFFFF is the window, mapped to the log page while we read).

        .area   CODE (ABS)
        .org    0xDA00

        ljmp    ev1                 ; DA00 <- stub 1ACE
        ljmp    ev2                 ; DA03 <- stub 1AD4
        ljmp    ev3                 ; DA06 <- stub 1ADA
        ljmp    ev4                 ; DA09 <- stub 1AE0
        ljmp    ev5                 ; DA0C <- bank07:96A9 (LJMP AB1E)
        ljmp    efa                 ; DA0F <- bank07:AB72 (LCALL 82DA, start path AB1E)
        ljmp    efb                 ; DA12 <- bank07:AC8F (LCALL 82DA, start path AC40)

ev1:    mov     0xF0,#1
        lcall   log
        ljmp    0xB26E
ev3:    mov     0xF0,#3
        lcall   log
        ljmp    0x9E43
ev4:    mov     0xF0,#4
        lcall   log
        ljmp    0xB6E8
ev5:    push    0xE0
        mov     0xF0,#5
        lcall   log
        mov     dptr,#0x6BEE
        movx    a,@dptr
        cjne    a,#0xFF,ev5d
        lcall   weof                ; FF: wait for end of field
        sjmp    ev5go
ev5d:   lcall   delay
ev5go:  pop     0xE0
        ljmp    0xAB1E

; weof: wait until the capture has finished the current field (720D bit2 = 1), max 64K polls
weof:   mov     r7,#0
weo:    mov     r6,#0
wei:    mov     dptr,#0x720D
        movx    a,@dptr
        jb      0xE2,weret
        djnz    r6,wei
        djnz    r7,weo
weret:  ret

; edge fix wrappers: fix the field buffer, then the start bit (82DA)
efb:    mov     0xF0,#3
        lcall   log
        mov     dptr,#0x6BFC        ; optional end-of-field wait on this path
        movx    a,@dptr
        cjne    a,#0xFF,efa
        lcall   weof
efa:    mov     dptr,#0x6BFB
        movx    a,@dptr
        jz      efgo
        mov     0xF0,a              ; B = which edges
        mov     dptr,#0x16FD        ; capture buffer 0 (16FC entry 0, address bytes 16FD-16FF)
        lcall   efbuf
        mov     dptr,#0x1711        ; capture buffer 1 (entry 1 at 1710)
        lcall   efbuf
efgo:   ljmp    0x82DA
efbuf:  lcall   ldbase              ; 6BF0-6BF2 = buffer address from [DPTR..DPTR+2]
        mov     dptr,#0x6BF0        ; sanity: only 0x100000..0x79FFFF (never the program RAM at 0..0xFFFFF)
        movx    a,@dptr
        cjne    a,#0x10,eflo
eflo:   jc      efret
        cjne    a,#0x7A,efhi
efhi:   jnc     efret
        jnb     0xF0,efbot          ; B.0: top edge
        lcall   cprow
efbot:  jnb     0xF1,efret          ; B.1: bottom edge
        lcall   cprow2
efret:  ret

; cprow: copy row 1 -> row 0, cprow2: row 286 -> row 287, 1408 bytes each, buffer at 6BF0-6BF2 (pitch 0x5A0).
; Scratch 6BF0-6BF8 (the boot hook's file-name buffer, free while recording): 6BF0-6BF2 base, 6BF3 src page,
; 6BF4/6BF5 src window offset, 6BF6 dst page, 6BF7/6BF8 dst window offset.
cprow:  mov     a,#0x00             ; dst = base + 0x000000
        mov     r4,a
        mov     r5,a
        mov     r6,a
        lcall   setdst
        mov     r4,#0x00            ; src = base + 0x0005A0
        mov     r5,#0x05
        mov     r6,#0xA0
        lcall   setsrc
        sjmp    cpgo
cprow2: mov     r4,#0x06            ; dst = base + 0x064E60
        mov     r5,#0x4E
        mov     r6,#0x60
        lcall   setdst
        mov     r4,#0x06            ; src = base + 0x0648C0
        mov     r5,#0x48
        mov     r6,#0xC0
        lcall   setsrc
cpgo:   push    0xA8                ; IE
        clr     0xAF
        mov     dptr,#0x7008        ; save window pages
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
        mov     dptr,#0x6BF3        ; src page -> 7008, write page -> 700A, 7009 = 700B = 0
        movx    a,@dptr
        mov     dptr,#0x7008
        movx    @dptr,a
        inc     dptr
        clr     a
        movx    @dptr,a
        mov     dptr,#0x6BF6        ; dst page
        movx    a,@dptr
        mov     dptr,#0x700A
        movx    @dptr,a
        inc     dptr
        clr     a
        movx    @dptr,a
        mov     dptr,#0x6BF4        ; src window offset -> r2:r3
        movx    a,@dptr
        mov     r2,a
        inc     dptr
        movx    a,@dptr
        mov     r3,a
        mov     dptr,#0x6BF7        ; dst window offset -> r4:r5 (6BF7 hi, 6BF8 lo)
        movx    a,@dptr
        mov     r4,a
        inc     dptr
        movx    a,@dptr
        mov     r5,a
        mov     r7,#0x80            ; 1408 = 0x80 + 5 x 256
        mov     r6,#6
cploop: mov     dph,r2
        mov     dpl,r3
        movx    a,@dptr
        mov     r1,a
        inc     dptr
        mov     a,dph
        jnz     cps
        mov     dph,#0x80           ; src crossed into the next 32 KB page
        push    0x82
        mov     dptr,#0x7008
        movx    a,@dptr
        inc     a
        movx    @dptr,a
        pop     0x82
        mov     dph,#0x80
cps:    mov     r2,dph
        mov     r3,dpl
        mov     dph,r4
        mov     dpl,r5
        mov     a,r1
        movx    @dptr,a
        inc     dptr
        mov     a,dph
        jnz     cpd
        push    0x82                ; dst crossed into the next page
        mov     dptr,#0x700A
        movx    a,@dptr
        inc     a
        movx    @dptr,a
        pop     0x82
        mov     dph,#0x80
cpd:    mov     r4,dph
        mov     r5,dpl
        djnz    r7,cploop
        djnz    r6,cploop
        mov     dptr,#0x700B        ; restore window pages
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
        ret

; ldbase: 6BF0-6BF2 = 24-bit buffer address from [DPTR..DPTR+2] (low 3 bytes of a big-endian long)
ldbase: movx    a,@dptr
        mov     r1,a
        inc     dptr
        movx    a,@dptr
        mov     r2,a
        inc     dptr
        movx    a,@dptr
        mov     dptr,#0x6BF2
        movx    @dptr,a
        mov     dptr,#0x6BF1
        mov     a,r2
        movx    @dptr,a
        mov     dptr,#0x6BF0
        mov     a,r1
        movx    @dptr,a
        ret

; addr24: r1:r2:r3 = base (6BF0-6BF2) + r4:r5:r6; returns page in A, window offset in r2:r3 (0x8000 | addr & 0x7FFF)
addr24: mov     dptr,#0x6BF2
        movx    a,@dptr
        add     a,r6
        mov     r3,a
        mov     dptr,#0x6BF1
        movx    a,@dptr
        addc    a,r5
        mov     r2,a
        mov     dptr,#0x6BF0
        movx    a,@dptr
        addc    a,r4
        mov     r1,a                ; r1:r2:r3 = address
        mov     a,r2                ; page = r1 << 1 | r2 >> 7
        rlc     a
        mov     a,r1
        rlc     a
        push    0xE0
        mov     a,r2
        orl     a,#0x80
        mov     r2,a
        pop     0xE0
        ret
setsrc: lcall   addr24
        mov     dptr,#0x6BF3        ; 6BF3 page, 6BF4/6BF5 window offset
        movx    @dptr,a
        inc     dptr
        mov     a,r2
        movx    @dptr,a
        inc     dptr
        mov     a,r3
        movx    @dptr,a
        ret
setdst: lcall   addr24
        mov     dptr,#0x6BF6        ; 6BF6 page, 6BF7/6BF8 window offset
        movx    @dptr,a
        inc     dptr
        mov     a,r2
        movx    @dptr,a
        inc     dptr
        mov     a,r3
        movx    @dptr,a
        ret

; delay: wait [DPTR] x 256 DJNZ loops (0 = none)
delay:  movx    a,@dptr
        jz      dret
        mov     r7,a
dlo:    mov     r6,#0
dli:    djnz    r6,dli
        djnz    r7,dlo
dret:   ret

ev2:    mov     dptr,#0x720D        ; which field just finished?
        movx    a,@dptr
        mov     r7,a
        mov     dptr,#0x6BEC        ; field gate
        movx    a,@dptr
        jz      gstock
        dec     a
        jz      gtake
        mov     a,r7                ; 2: field with 720D.0 = 0 only
        jnb     0xE0,gtake
        sjmp    grej
gstock: mov     a,r7                ; 0: stock, field with 720D.0 = 1 only
        jb      0xE0,gtake
grej:   mov     0xF0,#6
        lcall   log
        mov     dptr,#0x6BEF
        ljmp    delay               ; and return to the dispatcher
gtake:  mov     0xF0,#2
        lcall   log
        lcall   fapply
        mov     dptr,#0x6BEB
        lcall   delay
        ljmp    0xB222

; fapply: apply UPOKE.BIN entries with flags bit3 ("frame"), ops 0 write / 1 OR / 2 AND, entries 0x6A04..0x6BBF
fapply: mov     dptr,#0x6A00
        movx    a,@dptr
        cjne    a,#0x50,fret        ; 'P'
        inc     dptr
        movx    a,@dptr
        cjne    a,#0x4B,fret        ; 'K'
        mov     r2,#0x6A
        mov     r3,#0x04
floop:  mov     a,r2                ; stop at 0x6BC0
        cjne    a,#0x6B,fok
        mov     a,r3
        cjne    a,#0xC0,fchk
fchk:   jnc     fret
fok:    mov     dph,r2
        mov     dpl,r3
        movx    a,@dptr
        jz      fret
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
        inc     dptr
        mov     r2,dph
        mov     r3,dpl
        mov     a,r4
        jnb     0xE3,floop          ; not a "frame" entry
        mov     dph,r5
        mov     dpl,r6
        swap    a
        anl     a,#0x0F
        jz      fwr
        dec     a
        jz      for_
        dec     a
        jnz     floop
        movx    a,@dptr             ; AND
        anl     a,r0
        movx    @dptr,a
        sjmp    floop
fwr:    mov     a,r0
        movx    @dptr,a
        sjmp    floop
for_:   movx    a,@dptr
        orl     a,r0
        movx    @dptr,a
        sjmp    floop
fret:   ret

; log(B = event 1-6)
log:    mov     a,#0xE4             ; count: 6BE4 + event
        add     a,0xF0
        mov     dpl,a
        mov     dph,#0x6B
        movx    a,@dptr
        inc     a
        movx    @dptr,a
        mov     dptr,#0x6BED        ; event mask (0 = all)
        movx    a,@dptr
        jz      log1
        mov     r6,0xF0
lmask:  rr      a
        djnz    r6,lmask
        jb      0xE0,log1
lshort: ret
log1:   mov     dptr,#0x6BE0
        movx    a,@dptr
        cjne    a,#0x5A,lshort
        inc     dptr
        movx    a,@dptr
        mov     r2,a                ; dst hi
        cjne    a,#0x81,lchk        ; dst must be inside the header page above 0x8100
lchk:   jc      lshort
        inc     dptr
        movx    a,@dptr
        mov     r3,a                ; dst lo
        inc     dptr
        movx    a,@dptr             ; record length
        add     a,r3
        mov     r5,a                ; end lo
        mov     a,r2
        addc    a,#0
        jc      lshort                ; past 0xFFFF
        mov     r6,a                ; end hi
        cjne    a,#0xFF,lroom
        mov     a,r5                ; end hi = FF: need end lo <= F0
        add     a,#0x0F
        jc      lshort
lroom:  mov     dptr,#0x6BE1        ; advance ptr first
        mov     a,r6
        movx    @dptr,a
        inc     dptr
        mov     a,r5
        movx    @dptr,a
        mov     dptr,#0x6BE4
        movx    a,@dptr
        inc     a
        movx    @dptr,a
        mov     r1,a                ; seq
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
        mov     dptr,#0x814A        ; still a header with our JUNK chunk?
        movx    a,@dptr
        cjne    a,#0x4A,lend        ; 'J'
        inc     dptr
        movx    a,@dptr
        cjne    a,#0x55,lend        ; 'U'
        mov     dph,r2
        mov     dpl,r3
        mov     a,#0xA0             ; A0 + event
        orl     a,0xF0
        movx    @dptr,a
        inc     dptr
        mov     a,r1
        movx    @dptr,a
        inc     dptr
        mov     a,0x8C              ; TH0
        movx    @dptr,a
        inc     dptr
        mov     a,0x8A              ; TL0
        movx    @dptr,a
        inc     dptr
        mov     a,0xCD              ; TH2
        movx    @dptr,a
        inc     dptr
        mov     a,0xCC              ; TL2
        movx    @dptr,a
        inc     dptr
        mov     r2,dph
        mov     r3,dpl
        mov     r4,#0x6A            ; walk entries at 0x6A04..0x6BBF
        mov     r5,#0x04
pscan:  mov     a,r4
        cjne    a,#0x6B,pok
        mov     a,r5
        cjne    a,#0xC0,pchk
pchk:   jnc     lend
pok:    mov     dph,r4
        mov     dpl,r5
        movx    a,@dptr
        jz      lend
        mov     r1,a                ; flags
        inc     dptr
        movx    a,@dptr
        mov     r6,a                ; addr hi
        inc     dptr
        movx    a,@dptr
        mov     r7,a                ; addr lo
        inc     dptr
        movx    a,@dptr
        mov     r0,a                ; count
        inc     dptr
        mov     r4,dph
        mov     r5,dpl
        mov     a,r1
        anl     a,#0xF4
        cjne    a,#0x34,pscan
        mov     a,r0
        jz      pscan
pcopy:  mov     dph,r6
        mov     dpl,r7
        movx    a,@dptr
        inc     dptr
        mov     r6,dph
        mov     r7,dpl
        mov     dph,r2
        mov     dpl,r3
        movx    @dptr,a
        inc     dptr
        mov     r2,dph
        mov     r3,dpl
        djnz    r0,pcopy
        sjmp    pscan
lend:   mov     dptr,#0x700B        ; restore window pages
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
lret:   ret
