mov ecx, in // load structure addresses

mov edx, out

movaps xmm7, [ecx] // load x1 x2 x3 x4 => xmm7

movaps xmm6, [ecx+16] // load y1 y2 y3 y4 => xmm6

movaps xmm5, [ecx+32] // load z1 z2 z3 z4 => xmm5

movaps xmm4, [ecx+48] // load w1 w2 w3 w4 => xmm4

// START THE DESWIZZLING HERE

movaps xmm0, xmm7 // xmm0= x1 x2 x3 x4

unpcklps xmm7, xmm6 // xmm7= x1 y1 x2 y2

movlps [edx], xmm7 // v1 = x1 y1 -- --

movhps [edx+16], xmm7 // v2 = x2 y2 -- --

unpckhps xmm0, xmm6 // xmm0= x3 y3 x4 y4

movlps [edx+32], xmm0 // v3 = x3 y3 -- --

movhps [edx+48], xmm0 // v4 = x4 y4 -- --

movaps xmm0, xmm5 // xmm0= z1 z2 z3 z4

unpcklps xmm5, xmm4 // xmm5= z1 w1 z2 w2

unpckhps xmm0, xmm4 // xmm0= z3 w3 z4 w4

movlps [edx+8], xmm5 // v1 = x1 y1 z1 w1

movhps [edx+24], xmm5 // v2 = x2 y2 z2 w2

movlps [edx+40], xmm0 // v3 = x3 y3 z3 w3

movhps [edx+56], xmm0 // v4 = x4 y4 z4 w4

// DESWIZZLING ENDS HERE