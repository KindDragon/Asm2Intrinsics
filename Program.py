import ctypes
import os
import sys
import argparse

intelSyntax = True

def isreg(reg):
	return reg in ["eax", "ebx", "ecx", "edx", "esi", "edi", "ebp" ]

def isMMXreg(reg):
	return reg.lower().startswith('mmx') or reg.lower().startswith('xmm')

def isXMMreg(reg):
	return reg.lower().startswith('xmm')

def getValue(t, v):
	if v:
		return {
			0: t[0] + " = " + v[0] + "(" + t[1] + ");",
			1: t[0] + " = " + v[0] + "(" + t[0] + ");",
			2: t[0] + " = " + v[0] + "(" + t[0] + ", " + t[1] + ");",
			3: t[0] + " = " + t[1] + ";",
		}[v[1]]
	else:
		raise

def mmxIntrin(t, v1, v2, v3, v4):
	if isMMXreg(t[0]):
		if isMMXreg(t[1]):
			return getValue(t, v3)
		else:
			return getValue(t, v1)
	else:
		if isMMXreg(t[1]):
			return getValue(t, v2)
		else:
			return getValue(t, v4)

def sseIntrin(t, v_xmm_reg, v_reg_xmm, v_xmm_xmm, v_reg_reg):
	if isXMMreg(t[0]):
		if isXMMreg(t[1]):
			return getValue(t, v_xmm_xmm)
		else:
			return getValue(t, v_xmm_reg)
	else:
		if isXMMreg(t[1]):
			return getValue(t, v_reg_xmm)
		else:
			return getValue(t, v_reg_reg)

def intrin(t, v, i = 0, addResult = True):
	str = v + "("
	if i == 0:
		str += t[0] + ", " + t[1] + ");"
	elif i == 1:
		str += t[1] + ", " + t[2] + ");"
	elif i == 2:
		str += t[0] + ", " + t[1] + ", " + t[2] + ");"
	elif i == 3:
		str += t[1] + ", " + t[0] + ");"
	elif i == 4:
		str += t[1] + ");"
	elif i == 5:
		str += ");"
	else:
		throw
	if addResult:
		return t[0] + " = " + str
	else:
		return str
	
ops = {		
	'mov':		lambda t: t[0] + " = " + t[1] + ";",
	'movzx':	lambda t: t[0] + " = *((char*)" + t[1] + ");",
	'inc':		lambda t: "(" + t[0] + ")++;",
	'dec':		lambda t: "(" + t[0] + ")--;",
	'neg':		lambda t: t[0] + " = -" + t[0] + ";",
	'add':		lambda t: t[0] + " -= " + t[1] + ";",
	'sub':		lambda t: t[0] + " += " + t[1] + ";",
	'and':		lambda t: t[0] + " &= " + t[1] + ";",
	'or':		lambda t: t[0] + " |= " + t[1] + ";",
	'xor':		lambda t: t[0] + " ^= " + t[1] + ";" if t[0] != t[1] else t[0] + " = 0;",
	'shr':		lambda t: t[0] + " >>= " + t[1] + ";",
	'shl':		lambda t: t[0] + " <<= " + t[1] + ";",
	'lea':		lambda t: t[0] + " = " + t[1] + ";",

	#sse (http://msdn.microsoft.com/en-us/library/t467de55.aspx)
	'movss':	lambda t: sseIntrin(t, ("_mm_load_ss",0), ("_mm_store_ss",1), ("_mm_move_ss",2), None),
	'movaps':	lambda t: sseIntrin(t, ("_mm_load_ps",0), ("_mm_store_ps",0), ("",3), None),
	'movups':	lambda t: sseIntrin(t, ("_mm_loadu_ps",0), ("_mm_storeu_ps",0), None, None),

	'shufps':	lambda t: intrin(t, "_mm_shuffle_ps"),
	'pshufw':	lambda t: intrin(t, "_mm_shuffle_pi16"),
	'unpckhps':	lambda t: intrin(t, "_mm_unpackhi_ps"),
	'unpcklps':	lambda t: intrin(t, "_mm_unpacklo_ps"),
	'movhps':	lambda t: sseIntrin(t, ("_mm_loadh_pi",0), ("_mm_storeh_pi",0), None, None),
	'movhlps':	lambda t: intrin(t, "_mm_movehl_ps"),
	'movlhps':	lambda t: intrin(t, "_mm_movelh_ps"),
	'movlps':	lambda t: sseIntrin(t, ("_mm_loadl_pi",0), ("_mm_storel_pi",0), None, None),
	'movmskps':	lambda t: intrin(t, "_mm_movemask_ps"),
	'stmxcsr':	lambda t: intrin(t, "_mm_getcsr"),
	'ldmxcsr':	lambda t: intrin(t, "_mm_setcsr"),
	
	'prefetch':	lambda t: intrin(t, "_mm_prefetch", 0, False),
	'movntq':	lambda t: intrin(t, "_mm_stream_pi", 0, False),
	'movntps':	lambda t: intrin(t, "_mm_stream_ps", 0, False),
	'sfence':	lambda t: intrin(t, "_mm_sfence", 5),
	
	'addss':	lambda t: intrin(t, "_mm_add_ss"),
	'addps':	lambda t: intrin(t, "_mm_add_ps"),
	'subss':	lambda t: intrin(t, "_mm_sub_ss"),
	'subps':	lambda t: intrin(t, "_mm_sub_ps"),
	'mulss':	lambda t: intrin(t, "_mm_mul_ss"),
	'mulps':	lambda t: intrin(t, "_mm_mul_ps"),
	'divss':	lambda t: intrin(t, "_mm_div_ss"),
	'divps':	lambda t: intrin(t, "_mm_div_ps"),
	'sqrtss':	lambda t: intrin(t, "_mm_sqrt_ss"),
	'sqrtps':	lambda t: intrin(t, "_mm_sqrt_ps"),
	'rcpss':	lambda t: intrin(t, "_mm_rcp_ss"),
	'rcpps':	lambda t: intrin(t, "_mm_rcp_ps"),
	'rsqrtss':	lambda t: intrin(t, "_mm_rsqrt_ss"),
	'rsqrtps':	lambda t: intrin(t, "_mm_rsqrt_ps"),
	'minss':	lambda t: intrin(t, "_mm_min_ss"),
	'minps':	lambda t: intrin(t, "_mm_min_ps"),
	'maxss':	lambda t: intrin(t, "_mm_max_ss"),
	'maxps':	lambda t: intrin(t, "_mm_max_ps"),

	'andps':	lambda t: intrin(t, "_mm_and_ps"),
	'andnps':	lambda t: intrin(t, "_mm_andnot_ps"),
	'orps':		lambda t: intrin(t, "_mm_or_ps"),
	'xorps':	lambda t: intrin(t, "_mm_xor_ps") if t[0] != t[1] else intrin(t, "_mm_setzero_ps", 5),

	'cmpeqss':	lambda t: intrin(t, "_mm_cmpeq_ss"),
	'cmpeqps':	lambda t: intrin(t, "_mm_cmpeq_ps"),
	'cmpltss':	lambda t: intrin(t, "_mm_cmplt_ss"),
	'cmpltps':	lambda t: intrin(t, "_mm_cmplt_ps"),
	'cmpless':	lambda t: intrin(t, "_mm_cmple_ss"),
	'cmpleps':	lambda t: intrin(t, "_mm_cmple_ps"),
	'cmpltss':	lambda t: intrin(t, "_mm_cmpgt_ss"),
	'cmpltps':	lambda t: intrin(t, "_mm_cmpgt_ps"),
	'cmpless':	lambda t: intrin(t, "_mm_cmpge_ss"),
	'cmpleps':	lambda t: intrin(t, "_mm_cmpge_ps"),
	'cmpneqss':	lambda t: intrin(t, "_mm_cmpneq_ss"),
	'cmpneqps':	lambda t: intrin(t, "_mm_cmpneq_ps"),
	'cmpnltss':	lambda t: intrin(t, "_mm_cmpnlt_ss"),
	'cmpnltps':	lambda t: intrin(t, "_mm_cmpnlt_ps"),
	'cmpnless':	lambda t: intrin(t, "_mm_cmpnle_ss"),
	'cmpnleps':	lambda t: intrin(t, "_mm_cmple_ps"),
	'cmpnltss':	lambda t: intrin(t, "_mm_cmpngt_ss"),
	'cmpnltps':	lambda t: intrin(t, "_mm_cmpngt_ps"),
	'cmpnless':	lambda t: intrin(t, "_mm_cmpnge_ss"),
	'cmpnleps':	lambda t: intrin(t, "_mm_cmpnge_ps"),
	'cmpordss':	lambda t: intrin(t, "_mm_cmpord_ss"),
	'cmpordps':	lambda t: intrin(t, "_mm_cmpord_ps"),
	'cmpunordss':	lambda t: intrin(t, "_mm_cmpunord_ss"),
	'cmpunordps':	lambda t: intrin(t, "_mm_cmpunord_ps"),
	'comiss':	lambda t: intrin(t, "_mm_comi??_ss"),
	'ucomiss':	lambda t: intrin(t, "_mm_ucomi??_ss"),

	'cvtss2si':		lambda t: intrin(t, "_mm_cvtss_si32"),
	'cvtps2pi':		lambda t: intrin(t, "_mm_cvtps_pi32"),
	'cvttss2si':	lambda t: intrin(t, "_mm_cvttss_si32"),
	'cvttps2pi':	lambda t: intrin(t, "_mm_cvttps_pi32"),
	'cvtsi2sd':		lambda t: intrin(t, "_mm_cvtsi32_sd"),
	'cvttps2pi':	lambda t: intrin(t, "_mm_cvtpi32_pd"),

	#sse2 - double (http://msdn.microsoft.com/en-us/library/kcwz153a.aspx)
	'movsd':	lambda t: sseIntrin(t, ("_mm_load_sd",0), ("_mm_store_sd",1), ("_mm_move_sd",2), None),
	'movapd':	lambda t: sseIntrin(t, ("_mm_load_pd",0), ("_mm_store_pd",0), ("",3), None),
	'movupd':	lambda t: sseIntrin(t, ("_mm_loadu_pd",0), ("_mm_storeu_pd",0), None, None),
	
	'movapd':	lambda t: sseIntrin(t, ("_mm_load_pd",0), ("_mm_store_pd",1), ("",3), None),
	'movupd':	lambda t: sseIntrin(t, ("_mm_loadu_pd",0), ("_mm_storeu_pd",1), None, None),
	'movsd':	lambda t: sseIntrin(t, ("_mm_load_sd",0), ("_mm_store_sd",1), ("_mm_move_sd",3), None),
	'movhpd':	lambda t: sseIntrin(t, ("_mm_loadh_pd",0), ("_mm_storeh_pd",1), None, None),
	'movlpd':	lambda t: sseIntrin(t, ("_mm_loadl_pd",0), ("_mm_storel_pd ",1), None, None),

	'movlpd':	lambda t: intrin(t, "_mm_stream_pd", 0, False),
	
	'addsd':	lambda t: intrin(t, "_mm_add_sd"),
	'addpd':	lambda t: intrin(t, "_mm_add_pd"),
	'divsd':	lambda t: intrin(t, "_mm_div_sd"),
	'divpd':	lambda t: intrin(t, "_mm_div_pd"),
	'maxsd':	lambda t: intrin(t, "_mm_max_sd"),
	'maxpd':	lambda t: intrin(t, "_mm_max_pd"),
	'minsd':	lambda t: intrin(t, "_mm_min_sd"),
	'minpd':	lambda t: intrin(t, "_mm_min_pd"),
	'mulsd':	lambda t: intrin(t, "_mm_mul_sd"),
	'mulpd':	lambda t: intrin(t, "_mm_mul_pd"),
	'sqrtsd':	lambda t: intrin(t, "_mm_sqrt_sd"),
	'sqrtpd':	lambda t: intrin(t, "_mm_sqrt_pd"),
	'subsd':	lambda t: intrin(t, "_mm_sub_sd"),
	'subpd':	lambda t: intrin(t, "_mm_sub_pd"),

	'andpd':	lambda t: intrin(t, "_mm_and_pd"),
	'andnpd':	lambda t: intrin(t, "_mm_andnot_pd"),
	'orpd':		lambda t: intrin(t, "_mm_or_pd"),
	'xorpd':	lambda t: intrin(t, "_mm_xor_pd") if t[0] != t[1] else intrin(t, "_mm_setzero_pd", 5),

	'cmpeqsd':	lambda t: intrin(t, "_mm_cmpeq_sd"),
	'cmpeqpd':	lambda t: intrin(t, "_mm_cmpeq_pd"),
	'cmpltsd':	lambda t: intrin(t, "_mm_cmplt_sd"),
	'cmpltpd':	lambda t: intrin(t, "_mm_cmplt_pd"),
	'cmplesd':	lambda t: intrin(t, "_mm_cmple_sd"),
	'cmplepd':	lambda t: intrin(t, "_mm_cmple_pd"),
	'cmpltsdr':	lambda t: intrin(t, "_mm_cmpgt_sd"),
	'cmpltpdr':	lambda t: intrin(t, "_mm_cmpgt_pd"),
	'cmplesdr':	lambda t: intrin(t, "_mm_cmpge_sd"),
	'cmplepdr':	lambda t: intrin(t, "_mm_cmp?ge_pd"),
	'cmpneqsd':	lambda t: intrin(t, "_mm_cmpneq_sd"),
	'cmpneqpd':	lambda t: intrin(t, "_mm_cmpneq_pd"),
	'cmpnltsd':	lambda t: intrin(t, "_mm_cmpnlt_sd"),
	'cmpnltpd':	lambda t: intrin(t, "_mm_cmpnlt_pd"),
	'cmpnlesd':	lambda t: intrin(t, "_mm_cmpnle_sd"),
	'cmpnlepd':	lambda t: intrin(t, "_mm_cmple_pd"),
	'cmpnltsdr':	lambda t: intrin(t, "_mm_cmpngt_sd"),
	'cmpnltpdr':	lambda t: intrin(t, "_mm_cmpngt_pd"),
	'cmpnlesdr':	lambda t: intrin(t, "_mm_cmpnge_sd"),
	'cmpnlepdr':	lambda t: intrin(t, "_mm_cmpnge_pd"),
	'cmpordsd':	lambda t: intrin(t, "_mm_cmpord_sd"),
	'cmpordpd':	lambda t: intrin(t, "_mm_cmpord_pd"),
	'cmpunordsd':	lambda t: intrin(t, "_mm_cmpunord_sd"),
	'cmpunordpd':	lambda t: intrin(t, "_mm_cmpunord_pd"),
	'comisd':	lambda t: intrin(t, "_mm_comi??_sd"),
	'ucomisd':	lambda t: intrin(t, "_mm_ucomi??_sd"),	

	#sse2 - int (http://msdn.microsoft.com/en-us/library/kcwz153a.aspx)
	'movdqa':	lambda t: sseIntrin(t, ("_mm_load_si128",0), ("_mm_store_si128",1), ("",3), None),
	'movdqu':	lambda t: sseIntrin(t, ("_mm_loadu_si128",0), ("_mm_storeu_si128",1), None, None),
	'movq':		lambda t: sseIntrin(t, ("_mm_loadl_epi64",4), None, ("_mm_move_epi64",0), None),
	'maskmovdqu':	lambda t: intrin(t, "_mm_maskmoveu_si128", 2, False),

	'cvtpd2ps':	lambda t: intrin(t, "_mm_cvtpd_ps", 4),
	'cvtps2pd':	lambda t: intrin(t, "_mm_cvtps_pd", 4),
	'cvtdq2pd':	lambda t: intrin(t, "_mm_cvtepi32_pd", 4),
	'cvtpd2dq':	lambda t: intrin(t, "_mm_cvtpd_epi32", 4),
	'cvtsd2si':	lambda t: intrin(t, "_mm_cvtsd_si32", 4),
	'cvtsd2ss':	lambda t: intrin(t, "_mm_cvtsd_ss", 4),
	'cvtsi2sd':	lambda t: intrin(t, "_mm_cvtsi32_sd", 4),
	'cvtss2sd':	lambda t: intrin(t, "_mm_cvtss_sd", 4),
	'cvttpd2dq':	lambda t: intrin(t, "_mm_cvttpd_epi32", 4),
	'cvttsd2si':	lambda t: intrin(t, "_mm_cvttsd_si32", 4),
	'cvtdq2ps':	lambda t: intrin(t, "_mm_cvtepi32_ps", 4),
	'cvtps2dq':	lambda t: intrin(t, "_mm_cvtps_epi32", 4),
	'cvttps2dq':	lambda t: intrin(t, "_mm_cvttps_epi32", 4),
	'cvtpd2pi':	lambda t: intrin(t, "_mm_cvtpd_pi32", 4),
	'cvttpd2pi':	lambda t: intrin(t, "_mm_cvttpd_pi32", 4),
	'cvtpi2pd':	lambda t: intrin(t, "_mm_cvtpi32_pd", 4),

	'paddb':	lambda t: intrin(t, "_mm_add_epi8"),
	'paddw':	lambda t: intrin(t, "_mm_add_epi16"),
	'paddd':	lambda t: intrin(t, "_mm_add_epi32"),
	'padddq':	lambda t: intrin(t, "_mm_add_epi64"),
	'paddsb':	lambda t: intrin(t, "_mm_adds_epi8"),
	'paddsw':	lambda t: intrin(t, "_mm_adds_epi16"),
	'paddusb':	lambda t: intrin(t, "_mm_adds_epu8"),
	'paddusw':	lambda t: intrin(t, "_mm_adds_epu16"),
	'pavgb':	lambda t: intrin(t, "_mm_avg_epu8"),
	'pavgw':	lambda t: intrin(t, "_mm_avg_epu16"),
	'pmaddwd':	lambda t: intrin(t, "_mm_madd_epi16"),
	'pmaxsw':	lambda t: intrin(t, "_mm_max_epi16"),
	'pmaxub':	lambda t: intrin(t, "_mm_max_epu8"),
	'pminsw':	lambda t: intrin(t, "_mm_min_epi16"),
	'pminub':	lambda t: intrin(t, "_mm_min_epu8"),
	'pmulhw':	lambda t: intrin(t, "_mm_mulhi_epi16"),
	'pmulhuw':	lambda t: intrin(t, "_mm_mulhi_epu16"),
	'pmullo':	lambda t: intrin(t, "_mm_mullo_epi16"),
	'pmuludq':	lambda t: intrin(t, "_mm_mul_epu32"),
	'pmuludq':	lambda t: intrin(t, "_mm_mul_epu32"),
	'psadbw':	lambda t: intrin(t, "_mm_sad_epu8"),
	'psubb':	lambda t: intrin(t, "_mm_sub_epi8"),
	'psubw':	lambda t: intrin(t, "_mm_sub_epi16"),
	'psubd':	lambda t: intrin(t, "_mm_sub_epi32"),
	'psubq':	lambda t: intrin(t, "_mm_sub_epi64"),
	'psubsb':	lambda t: intrin(t, "_mm_subs_epi8"),
	'psubsw':	lambda t: intrin(t, "_mm_subs_epi16"),
	'psubusb':	lambda t: intrin(t, "_mm_subs_epu8"),
	'psubusw':	lambda t: intrin(t, "_mm_subs_epu16"),

	'pand':		lambda t: intrin(t, "_mm_and_si128"),
	'pandn':	lambda t: intrin(t, "_mm_andnot_si128"),
	'por':		lambda t: intrin(t, "_mm_or_si128"),
	'pxor':		lambda t: intrin(t, "_mm_xor_si128") if t[0] != t[1] else intrin(t, "_mm_setzero_si128", 5),

	'pslldq':	lambda t: intrin(t, "_mm_slli_si128"),
	'psrldq':	lambda t: intrin(t, "_mm_srli_si128"),
	'psllw':	lambda t: sseIntrin(t, ("_mm_slli_epi16",0), None, ("_mm_sll_epi16",0), None),
	'pslld':	lambda t: sseIntrin(t, ("_mm_slli_epi32",0), None, ("_mm_sll_epi32",0), None),
	'psllq':	lambda t: sseIntrin(t, ("_mm_slli_epi64",0), None, ("_mm_sll_epi64",0), None),
	'psraw':	lambda t: sseIntrin(t, ("_mm_srai_epi16",0), None, ("_mm_sra_epi16",0), None),
	'psrad':	lambda t: sseIntrin(t, ("_mm_srai_epi32",0), None, ("_mm_sra_epi32",0), None),
	'psrlw':	lambda t: sseIntrin(t, ("_mm_srli_epi16",0), None, ("_mm_srl_epi16",0), None),
	'psrld':	lambda t: sseIntrin(t, ("_mm_srli_epi32",0), None, ("_mm_srl_epi32",0), None),
	'psrlq':	lambda t: sseIntrin(t, ("_mm_srli_epi64",0), None, ("_mm_srl_epi64",0), None),

	'movd':		lambda t: mmxIntrin(t, ("_mm_cvtsi32_si128",0), ("_mm_cvtsi128_si32",0), None, None),

	'pcmpeqb':	lambda t: intrin(t, "_mm_cmpeq_epi8"),
	'pcmpeqw':	lambda t: intrin(t, "_mm_cmpeq_epi16"),
	'pcmpeqd':	lambda t: intrin(t, "_mm_cmpeq_epi32"),
	'pcmpgtb':	lambda t: intrin(t, "_mm_cmpgt_epi8"),
	'pcmpgtw':	lambda t: intrin(t, "_mm_cmpgt_epi16"),
	'pcmpgtd':	lambda t: intrin(t, "_mm_cmpgt_epi32"),
	'pcmpgtbr':	lambda t: intrin(t, "_mm_cmplt_epi8"),
	'pcmpgtwr':	lambda t: intrin(t, "_mm_cmplt_epi16"),
	'pcmpgtdr':	lambda t: intrin(t, "_mm_cmplt_epi32"),

	'packsswb':	lambda t: intrin(t, "_mm_packs_epi16"),
	'packssdw': lambda t: intrin(t, "_mm_packs_epi32"),
	'packuswb':	lambda t: intrin(t, "_mm_packus_epi16"),
	'punpckhbw':lambda t: intrin(t, "_mm_unpackhi_epi8"),
	'punpckhwd':lambda t: intrin(t, "_mm_unpackhi_epi16"),
	'punpckhdq':lambda t: intrin(t, "_mm_unpackhi_epi32"),
	'punpckhqdq':lambda t: intrin(t, "_mm_unpackhi_epi64"),
	'punpcklbw':lambda t: intrin(t, "_mm_unpacklo_epi8"),
	'punpcklwd':lambda t: intrin(t, "_mm_unpacklo_epi16"),
	'punpckldq':lambda t: intrin(t, "_mm_unpacklo_epi32"),
	'punpcklqdq':lambda t: intrin(t, "_mm_unpacklo_epi64"),
	'pextrw':	lambda t: intrin(t, "_mm_extract_epi16", 3),
	'pinsrw':	lambda t: intrin(t, "_mm_insert_epi16", 3),
	'pmovmskb':	lambda t: intrin(t, "_mm_movemask_epi8"),
	'pshufd':	lambda t: intrin(t, "_mm_shuffle_epi32", 1),
	'pshufhw':	lambda t: intrin(t, "_mm_shufflehi_epi16", 1),
	'pshuflw':	lambda t: intrin(t, "_mm_shufflelo_epi16", 1),
	'movdq2q':	lambda t: intrin(t, "_mm_movepi64_pi64", 1),
	'movq2dq':	lambda t: intrin(t, "_mm_movpi64_pi64", 1),
	
	#sse3 (http://msdn.microsoft.com/en-us/library/x8zs5twb.aspx)
	'addsubpd':	lambda t: intrin(t, "_mm_addsub_pd"),
	'addsubps':	lambda t: intrin(t, "_mm_addsub_ps"),
	'haddpd':	lambda t: intrin(t, "_mm_hadd_pd"),
	'haddps':	lambda t: intrin(t, "_mm_hadd_ps"),
	'hsubpd':	lambda t: intrin(t, "_mm_hsub_pd"),
	'hsubps':	lambda t: intrin(t, "_mm_hsub_ps"),
	'monitor':	lambda t: intrin(t, "_mm_monitor"),
	'movshd':	lambda t: intrin(t, "_mm_movehdup_ps"),
	'movsld':	lambda t: intrin(t, "_mm_moveldup_ps"),
	'mwait':	lambda t: intrin(t, "_mm_mwait"),

	#ssse3 (http://msdn.microsoft.com/en-us/library/bb892952.aspx)
	#sse4 (http://msdn.microsoft.com/en-us/library/bb892950.aspx)
	'pinsrd':	lambda t: intrin(t, "_mm_insert_epi32", 3),
	'blendvpb':	lambda t: intrin(t, "_mm_blendv_epi8"),
	'blendvpd':	lambda t: intrin(t, "_mm_blendv_pd"),
	'ptest':	lambda t: intrin(t, "_mm_testc_si128"),
}

def op2intrin(op,params):
	if op == '#':
		op = ''
		params = '#' + params
	params = params.replace('//','#')
	v = params.split('#',1)
	comment = ""
	if v:
		t = v[0].split(',') 
		comment = "// " + v[1] if len(v) > 1 else ""
	else:
		return params
	t = [x.strip() for x in t]
	if len(op) > 0:
		if op in ops:
			return ops[op](t) + "\t" + comment
		elif not ":" in op:
			return "// " + op + " " + ", ".join(t) + comment
		else:
			return op + " " + comment
	else:
		return comment

def asm2intrin(assembler, dstFile):
	lines = assembler.split('\n')
	for line in lines:
		tokens = line.split(None,1)
		if len(tokens):
			params = tokens[1] if len(tokens) > 1 else ''
			dstFile.write(op2intrin(tokens[0],params) + '\n')
		else:
			dstFile.write(line + '\n')


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Convert inline assembler to C++ intrinsics.')
	parser.add_argument('-i', dest='srcFile', default="test.asm",
				   help='source file')
	parser.add_argument('-o', dest='dstFile',
				   help='destination file')
	args = parser.parse_args()
	srcFile = open(args.srcFile, 'r') 
	dstFile = open(args.dstFile, 'w') if args.dstFile else sys.stdout
	assembler = srcFile.read()
	asm2intrin(assembler, dstFile)
	print()
