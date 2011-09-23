				push	ebx
				mov		ecx, tri_size
				mov		esi, triangles
				mov		edi, points
				mov		edx, img_data
				movdqu	xmm7, ones
			triangle_loop:				// for(int i = 0; i < tri_size; i++)
				mov		eax, [esi + 0]
				lea		eax, [eax + 2*eax]
				movdqu	xmm0, [edi + eax*4] 
				mov		eax, [esi + 4]
				lea		eax, [eax + 2*eax]
				movaps	xmm3, xmm0
				movdqu	xmm1, [edi + eax*4] 
				mov		eax, [esi + 8]
				lea		eax, [eax + 2*eax]
				addps	xmm3, xmm1
				movdqu	xmm2, [edi + eax*4]
				addps	xmm3, xmm2
				mulps	xmm3, fRabX3_fRabY3		// frabx3, -fraby3, x, x
				addps	xmm3, addx_addy
				cvttps2dq xmm3, xmm3			// ints
				// compare with bounds
				movaps	xmm4, xmm3
				movaps	xmm5, xmm3
				pcmpgtd	xmm4, upperbounds
				pcmpgtd xmm5, lowerbounds
				pxor	xmm5, xmm7
				orpd	xmm4, xmm5
				movlhps	xmm4, xmm4
				pmovmskb eax, xmm4
				cmp		eax, 0
				jne		skipdraw				// skip ouliers
				pshufd	xmm4, xmm3, 01b
				movd	eax, xmm3
				movd	ebx, xmm4
				// calculate index
				imul	ebx, asm_settsizex
				add		eax, ebx				// eax = index

				// calculate floats
				cvtdq2ps xmm3, xmm3		
				subps	xmm3, addx_addy
				mulps	xmm3, divX_divY		// xmm3 = x, y

				// calculate normal 
				// x = p1.y*p2.z - p1.z*p2.y
				// y = p1.z*p2.x - p1.x*p2.z
				// z = p1.x*p2.y - p1.y*p2.x
				subps	xmm0, xmm1 // p1		
				subps	xmm2, xmm1 // p2
				// cross product, result in xmm0
				movaps	xmm4, xmm0
				movaps	xmm5, xmm2
				shufps	xmm0, xmm0, 11001001b
				shufps	xmm2, xmm2, 11010010b
				shufps	xmm4, xmm4, 11010010b
				shufps	xmm5, xmm5, 11001001b
				mulps	xmm0, xmm2
				mulps	xmm4, xmm5
				subps	xmm0, xmm4 // xmm0 - normal vector
				
				// check normal z component
				pextrw  ebx, xmm0, 5
				cmp		ebx, 0
				je		skipdraw

				// calculate Z: z = (n.x*(p2.x - x) + n.y*(p2.y - y))/n.z + p2.z
				// xmm1 = p2
				pshufd	xmm2, xmm1, 10b	// p2.z
				pshufd	xmm4, xmm0, 10b // n.z
				subps	xmm1, xmm3
				mulps	xmm1, xmm0
				pshufd	xmm5, xmm1, 01b 
				addss	xmm1, xmm5		
				divss	xmm1, xmm4
				addss	xmm1, xmm2		// Z

				// check bounds and Z buffer
				minss	xmm1, [edx + eax*4] // z buffer check
				comiss	xmm1, asm_settminBoundz
				jc		skipdraw
				comiss	xmm1, asm_settmaxBoundz
				ja		skipdraw
				movd	[edx + eax*4], xmm1 // write result

				// next triangle 
			skipdraw:
				add		esi, 12
				dec		ecx
				jnz		triangle_loop
				pop		ebx