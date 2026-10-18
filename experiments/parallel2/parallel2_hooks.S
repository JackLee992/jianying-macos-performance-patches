// Leaf-only ARM64 hooks for one exact Jianying build.
// This file makes no calls and creates no stack frame. Original C++ call sites,
// stack, callee-saved registers and exception/unwind metadata remain in place.
// The build tool resolves the five far-jump slots to original image addresses.
.text
.p2align 2
.globl _parallel2_scheduler
_parallel2_scheduler:
    // Original site: x19=helper, x20=current shared_ptr slot, x21=queue end.
    ldr x8, [x20]
    ldrb w9, [x8, #0x59]
    cbnz w9, L_audio_current
    ldp x9, x10, [x19, #0x78]
    mov w11, #0
    cmp x9, x10
    b.eq L_video_current
L_scheduler_count:
    ldr x12, [x9], #16
    ldrb w12, [x12, #0x58]
    cmp w12, #0
    cinc w11, w11, ne
    cmp w11, #2
    b.hs _far_scheduler_return
    cmp x9, x10
    b.lo L_scheduler_count
L_video_current:
    ldr x8, [x20]
    ldrb w8, [x8, #0x58]
    cbnz w8, _far_scheduler_advance
    b _far_scheduler_ready
L_audio_current:
    // Audio tasks keep the original active => return rule.
    ldrb w8, [x8, #0x58]
    cbnz w8, _far_scheduler_return
    b _far_scheduler_ready
.globl _far_scheduler_return
_far_scheduler_return:
#ifdef NATIVE_HARNESS
    b _test_scheduler_return
    nop
    nop
#else
    .space 12
#endif
.globl _far_scheduler_advance
_far_scheduler_advance:
#ifdef NATIVE_HARNESS
    b _test_scheduler_advance
    nop
    nop
#else
    .space 12
#endif
.globl _far_scheduler_ready
_far_scheduler_ready:
#ifdef NATIVE_HARNESS
    b _test_scheduler_ready
    nop
    nop
#else
    .space 12
#endif

// Fixed second hook offset permits reproducible checking and manifests.
.org 0x100
.globl _parallel2_admission
_parallel2_admission:
    // Original site: x8=current TaskInfo, x19=helper. No calls follow the
    // capacity check before setting active. x9 is overwritten by original code.
    ldrb w9, [x8, #0x59]
    cbnz w9, L_admit
    // A reentrant preflight may already have activated this same task.
    ldrb w9, [x8, #0x58]
    cbnz w9, _far_admission_defer
    ldp x9, x10, [x19, #0x78]
    mov w11, #0
    cmp x9, x10
    b.eq L_admit
L_admission_count:
    ldr x12, [x9], #16
    ldrb w12, [x12, #0x58]
    cmp w12, #0
    cinc w11, w11, ne
    cmp w11, #2
    b.hs _far_admission_defer
    cmp x9, x10
    b.lo L_admission_count
L_admit:
    mov w9, #1
    strb w9, [x8, #0x58]
    mov w9, #3
    b _far_admission_resume
.globl _far_admission_defer
_far_admission_defer:
#ifdef NATIVE_HARNESS
    b _test_admission_defer
    nop
    nop
#else
    .space 12
#endif
.globl _far_admission_resume
_far_admission_resume:
#ifdef NATIVE_HARNESS
    b _test_admission_resume
    nop
    nop
#else
    .space 12
#endif
.globl _parallel2_hooks_end
_parallel2_hooks_end:

#ifdef NATIVE_HARNESS
// Native harness adapters, excluded from the bytes installed in the app copy.
.globl _test_scheduler
_test_scheduler:
    stp x29, x30, [sp, #-0x40]!
    stp x19, x20, [sp, #0x10]
    stp x21, x22, [sp, #0x20]
    stp x23, x24, [sp, #0x30]
    mov x29, sp
    mov x19, x0
    mov x20, x1
    mov x21, x2
    b _parallel2_scheduler
.globl _test_scheduler_return
_test_scheduler_return:
    mov w0, #0
    b L_test_exit
.globl _test_scheduler_advance
_test_scheduler_advance:
    mov w0, #2
    b L_test_exit
.globl _test_scheduler_ready
_test_scheduler_ready:
    mov w0, #1
    b L_test_exit
.globl _test_admission
_test_admission:
    stp x29, x30, [sp, #-0x40]!
    stp x19, x20, [sp, #0x10]
    stp x21, x22, [sp, #0x20]
    stp x23, x24, [sp, #0x30]
    mov x29, sp
    mov x19, x0
    mov x8, x1
    b _parallel2_admission
.globl _test_admission_defer
_test_admission_defer:
    mov w0, #0
    b L_test_exit
.globl _test_admission_resume
_test_admission_resume:
    // The original next instruction consumes w9=3 and x8=TaskInfo.
    str w9, [x8, #0x5c]
    mov w0, #1
L_test_exit:
    ldp x23, x24, [sp, #0x30]
    ldp x21, x22, [sp, #0x20]
    ldp x19, x20, [sp, #0x10]
    ldp x29, x30, [sp], #0x40
    ret
#endif
