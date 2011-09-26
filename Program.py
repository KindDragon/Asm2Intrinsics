import ctypes
import os
import sys
import argparse
import re

intelSyntax = True
variableSet = False

def isreg(reg):
	return reg in ["eax", "ebx", "ecx", "edx", "esi", "edi", "ebp" ]

def isMMXreg(reg):
	return reg.lower().startswith('mmx') or reg.lower().startswith('xmm')

def isXMMreg(reg):
	return reg.lower().startswith('xmm')

def getValue(t, v):
	if v:
		global variableSet
		variableSet = v[1] != 4
		return {
			0: t[0] + " = " + v[0] + "(" + t[1] + ");",
			1: t[0] + " = " + v[0] + "(" + t[0] + ");",
			2: t[0] + " = " + v[0] + "(" + t[0] + ", " + t[1] + ");",
			3: t[0] + " = " + t[1] + ";",
			4: v[0] + "(" + t[0] + ", " + t[1] + ");",
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
	global variableSet
	variableSet = addResult
	if addResult:
		variableSet = v[1] != 4
		return t[0] + " = " + str
	else:
		return str

def comp2str(i):
	if i == 0:
		return "eq"		#xmm1 == xmm2	je, jz
	elif i == 1:
		return "lt"		#xmm1 < xmm2	jb, jnae, jc
	elif i == 2:
		return "le"		#xmm1 <= xmm2	jbe, jna
	elif i == 3:
		return "unord"	#xmm1 ? xmm2	jp, jpe
	elif i == 4:
		return "neq"	#xmm1 != xmm2	jne, jnz
	elif i == 5:
		return "nlt"	#xmm1 >= xmm2	jnb, jae, jnc
	elif i == 6:
		return "nle"	#xmm1 > xmm2	ja, jnbe
	elif i == 7:
		return "ord"	#!(xmm1 ? xmm2)	jnp, jpo
	else:
		throw

class InstSet:
	Unsupported=0
	x86=1
	SSE=2
	SSE2=3
	SSE2I=4
	SSE3=5
	SSSE3=6
	SSE4=7
	SSE4A=8
	SSE41=9
	SSE42=10

rounding = {
	0 : "round",
	1 : "floor",
	2 : "ceil",
	3 : "truncate"
}

ops = {		
	'mov':			(InstSet.x86, lambda t: t[0] + " = " + t[1] + ";"),
	'movzx':		(InstSet.x86, lambda t: t[0] + " = *((char*)" + t[1] + ");"),
	'lea':			(InstSet.x86, lambda t: t[0] + " = " + t[1] + ";"),
	'inc':			(InstSet.x86, lambda t: t[0] + "++;"),
	'dec':			(InstSet.x86, lambda t: t[0] + "--;"),
	'imul':			(InstSet.x86, lambda t: t[0] + " *= " + t[1] + ";"),
	'idiv':			(InstSet.x86, lambda t: t[0] + " /= " + t[1] + ";"),
	'neg':			(InstSet.x86, lambda t: t[0] + " = -" + t[0] + ";"),
	'add':			(InstSet.x86, lambda t: t[0] + " += " + t[1] + ";"),
	'sub':			(InstSet.x86, lambda t: t[0] + " -= " + t[1] + ";"),
	'and':			(InstSet.x86, lambda t: t[0] + " &= " + t[1] + ";"),
	'or':			(InstSet.x86, lambda t: t[0] + " |= " + t[1] + ";"),
	'xor':			(InstSet.x86, lambda t: t[0] + " ^= " + t[1] + ";" if t[0] != t[1] else t[0] + " = 0;"),
	'shr':			(InstSet.x86, lambda t: t[0] + " >>= " + t[1] + ";" if not t[1].isdigit() or int(t[1])>5 else t[0] + " /= " + str(2 ** int(t[1])) + ";"),
	'shl':			(InstSet.x86, lambda t: t[0] + " <<= " + t[1] + ";" if not t[1].isdigit() or int(t[1])>5 else t[0] + " *= " + str(2 ** int(t[1])) + ";"),
	'loop':			(InstSet.x86, lambda t: "ecx--;\n} while (ecx > 0); // start at " + t[0] + ":"),

	#sse (http://msdn.microsoft.com/en-us/library/t467de55.aspx)
	'movss':		(InstSet.SSE, lambda t: sseIntrin(t, ("_mm_load_ss",0), ("_mm_store_ss",4), ("_mm_move_ss",2), None)),
	'movaps':		(InstSet.SSE, lambda t: sseIntrin(t, ("_mm_load_ps",0), ("_mm_store_ps",4), ("",3), None)),
	'movups':		(InstSet.SSE, lambda t: sseIntrin(t, ("_mm_loadu_ps",0), ("_mm_storeu_ps",4), None, None)),

	'shufps':		(InstSet.SSE, lambda t: intrin(t, "_mm_shuffle_ps", 2)),
	'pshufw':		(InstSet.SSE, lambda t: intrin(t, "_mm_shuffle_pi16", 1)),
	'unpckhps':		(InstSet.SSE, lambda t: intrin(t, "_mm_unpackhi_ps")),
	'unpcklps':		(InstSet.SSE, lambda t: intrin(t, "_mm_unpacklo_ps")),
	'movhps':		(InstSet.SSE, lambda t: sseIntrin(t, ("_mm_loadh_pi",0), ("_mm_storeh_pi",0), None, None)),
	'movhlps':		(InstSet.SSE, lambda t: intrin(t, "_mm_movehl_ps")),
	'movlhps':		(InstSet.SSE, lambda t: intrin(t, "_mm_movelh_ps")),
	'movlps':		(InstSet.SSE, lambda t: sseIntrin(t, ("_mm_loadl_pi",0), ("_mm_storel_pi",0), None, None)),
	'movmskps':		(InstSet.SSE, lambda t: intrin(t, "_mm_movemask_ps", 4)),
	'stmxcsr':		(InstSet.SSE, lambda t: intrin(t, "_mm_getcsr")),
	'ldmxcsr':		(InstSet.SSE, lambda t: intrin(t, "_mm_setcsr")),
	
	'prefetch':		(InstSet.SSE, lambda t: intrin(t, "_mm_prefetch", 0, False)),
	'movntq':		(InstSet.SSE, lambda t: intrin(t, "_mm_stream_pi", 0, False)),
	'movntps':		(InstSet.SSE, lambda t: intrin(t, "_mm_stream_ps", 0, False)),
	'sfence':		(InstSet.SSE, lambda t: intrin(t, "_mm_sfence", 5)),
	
	'addss':		(InstSet.SSE, lambda t: intrin(t, "_mm_add_ss")),
	'addps':		(InstSet.SSE, lambda t: intrin(t, "_mm_add_ps")),
	'subss':		(InstSet.SSE, lambda t: intrin(t, "_mm_sub_ss")),
	'subps':		(InstSet.SSE, lambda t: intrin(t, "_mm_sub_ps")),
	'mulss':		(InstSet.SSE, lambda t: intrin(t, "_mm_mul_ss")),
	'mulps':		(InstSet.SSE, lambda t: intrin(t, "_mm_mul_ps")),
	'divss':		(InstSet.SSE, lambda t: intrin(t, "_mm_div_ss")),
	'divps':		(InstSet.SSE, lambda t: intrin(t, "_mm_div_ps")),
	'sqrtss':		(InstSet.SSE, lambda t: intrin(t, "_mm_sqrt_ss", 4)),
	'sqrtps':		(InstSet.SSE, lambda t: intrin(t, "_mm_sqrt_ps", 4)),
	'rcpss':		(InstSet.SSE, lambda t: intrin(t, "_mm_rcp_ss", 4)),
	'rcpps':		(InstSet.SSE, lambda t: intrin(t, "_mm_rcp_ps", 4)),
	'rsqrtss':		(InstSet.SSE, lambda t: intrin(t, "_mm_rsqrt_ss", 4)),
	'rsqrtps':		(InstSet.SSE, lambda t: intrin(t, "_mm_rsqrt_ps", 4)),
	'minss':		(InstSet.SSE, lambda t: intrin(t, "_mm_min_ss")),
	'minps':		(InstSet.SSE, lambda t: intrin(t, "_mm_min_ps")),
	'maxss':		(InstSet.SSE, lambda t: intrin(t, "_mm_max_ss")),
	'maxps':		(InstSet.SSE, lambda t: intrin(t, "_mm_max_ps")),

	'andps':		(InstSet.SSE, lambda t: intrin(t, "_mm_and_ps")),
	'andnps':		(InstSet.SSE, lambda t: intrin(t, "_mm_andnot_ps")),
	'orps':			(InstSet.SSE, lambda t: intrin(t, "_mm_or_ps")),
	'xorps':		(InstSet.SSE, lambda t: intrin(t, "_mm_xor_ps") if t[0] != t[1] else intrin(t, "_mm_setzero_ps", 5)),
	
	'cmpps':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmp" + comp2str(int(t[2])) + "_ps")),
	'cmpss':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmp" + comp2str(int(t[2])) + "_ss")),
	'cmpeqss':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpeq_ss")),
	'cmpeqps':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpeq_ps")),
	'cmpltss':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmplt_ss")),
	'cmpltps':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmplt_ps")),
	'cmpless':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmple_ss")),
	'cmpleps':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmple_ps")),
	'cmpltssr':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpgt_ss")),
	'cmpltpsr':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpgt_ps")),
	'cmplessr':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpge_ss")),
	'cmplepsr':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpge_ps")),
	'cmpneqss':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpneq_ss")),
	'cmpneqps':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpneq_ps")),
	'cmpnltss':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpnlt_ss")),
	'cmpnltps':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpnlt_ps")),
	'cmpnless':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpnle_ss")),
	'cmpnleps':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmple_ps")),
	'cmpnltssr':	(InstSet.SSE, lambda t: intrin(t, "_mm_cmpngt_ss")),
	'cmpnltpsr':	(InstSet.SSE, lambda t: intrin(t, "_mm_cmpngt_ps")),
	'cmpnlessr':	(InstSet.SSE, lambda t: intrin(t, "_mm_cmpnge_ss")),
	'cmpnlepsr':	(InstSet.SSE, lambda t: intrin(t, "_mm_cmpnge_ps")),
	'cmpordss':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpord_ss")),
	'cmpordps':		(InstSet.SSE, lambda t: intrin(t, "_mm_cmpord_ps")),
	'cmpunordss':	(InstSet.SSE, lambda t: intrin(t, "_mm_cmpunord_ss")),
	'cmpunordps':	(InstSet.SSE, lambda t: intrin(t, "_mm_cmpunord_ps")),
	'comiss':		(InstSet.SSE, lambda t: intrin(t, "_mm_comi??_ss")),
	'ucomiss':		(InstSet.SSE, lambda t: intrin(t, "_mm_ucomi??_ss")),

	'cvtss2si':		(InstSet.SSE, lambda t: intrin(t, "_mm_cvtss_si32")),
	'cvtps2pi':		(InstSet.SSE, lambda t: intrin(t, "_mm_cvtps_pi32")),
	'cvttss2si':	(InstSet.SSE, lambda t: intrin(t, "_mm_cvttss_si32")),
	'cvttps2pi':	(InstSet.SSE, lambda t: intrin(t, "_mm_cvttps_pi32")),
	'cvtsi2sd':		(InstSet.SSE, lambda t: intrin(t, "_mm_cvtsi32_sd")),
	'cvttps2pi':	(InstSet.SSE, lambda t: intrin(t, "_mm_cvtpi32_pd")),

	#sse2 - double (http://msdn.microsoft.com/en-us/library/kcwz153a.aspx)
	'movsd':		(InstSet.SSE2, lambda t: sseIntrin(t, ("_mm_load_sd",0), ("_mm_store_sd",4), ("_mm_move_sd",2), None)),
	'movapd':		(InstSet.SSE2, lambda t: sseIntrin(t, ("_mm_load_pd",0), ("_mm_store_pd",4), ("",3), None)),
	'movupd':		(InstSet.SSE2, lambda t: sseIntrin(t, ("_mm_loadu_pd",0), ("_mm_storeu_pd",4), None, None)),
	
	'movhpd':		(InstSet.SSE2, lambda t: sseIntrin(t, ("_mm_loadh_pd",0), ("_mm_storeh_pd",4), None, None)),
	'movlpd':		(InstSet.SSE2, lambda t: sseIntrin(t, ("_mm_loadl_pd",0), ("_mm_storel_pd ",4), None, None)),

	'movlpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_stream_pd", 0, False)),
	
	'addsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_add_sd")),
	'addpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_add_pd")),
	'divsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_div_sd")),
	'divpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_div_pd")),
	'maxsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_max_sd")),
	'maxpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_max_pd")),
	'minsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_min_sd")),
	'minpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_min_pd")),
	'mulsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_mul_sd")),
	'mulpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_mul_pd")),
	'sqrtsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_sqrt_sd", 4)),
	'sqrtpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_sqrt_pd", 4)),
	'subsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_sub_sd")),
	'subpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_sub_pd")),

	'andpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_and_pd")),
	'andnpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_andnot_pd")),
	'orpd':			(InstSet.SSE2, lambda t: intrin(t, "_mm_or_pd")),
	'xorpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_xor_pd") if t[0] != t[1] else intrin(t, "_mm_setzero_pd", 5)),
	
	'cmppd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmp" + comp2str(int(t[2])) + "_pd")),
	'cmpsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmp" + comp2str(int(t[2])) + "_sd")),
	'cmpeqsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpeq_sd")),
	'cmpeqpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpeq_pd")),
	'cmpltsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmplt_sd")),
	'cmpltpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmplt_pd")),
	'cmplesd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmple_sd")),
	'cmplepd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmple_pd")),
	'cmpltsdr':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpgt_sd")),
	'cmpltpdr':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpgt_pd")),
	'cmplesdr':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpge_sd")),
	'cmplepdr':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmp?ge_pd")),
	'cmpneqsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpneq_sd")),
	'cmpneqpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpneq_pd")),
	'cmpnltsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpnlt_sd")),
	'cmpnltpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpnlt_pd")),
	'cmpnlesd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpnle_sd")),
	'cmpnlepd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmple_pd")),
	'cmpnltsdr':	(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpngt_sd")),
	'cmpnltpdr':	(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpngt_pd")),
	'cmpnlesdr':	(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpnge_sd")),
	'cmpnlepdr':	(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpnge_pd")),
	'cmpordsd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpord_sd")),
	'cmpordpd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpord_pd")),
	'cmpunordsd':	(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpunord_sd")),
	'cmpunordpd':	(InstSet.SSE2, lambda t: intrin(t, "_mm_cmpunord_pd")),
	'comisd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_comi??_sd")),
	'ucomisd':		(InstSet.SSE2, lambda t: intrin(t, "_mm_ucomi??_sd")),

	#sse2 - int (http://msdn.microsoft.com/en-us/library/kcwz153a.aspx)
	'movdqa':		(InstSet.SSE2I, lambda t: sseIntrin(t, ("_mm_load_si128",0), ("_mm_store_si128",4), ("",3), None)),
	'movdqu':		(InstSet.SSE2I, lambda t: sseIntrin(t, ("_mm_loadu_si128",0), ("_mm_storeu_si128",4), None, None)),
	'movq':			(InstSet.SSE2I, lambda t: sseIntrin(t, ("_mm_loadl_epi64",4), None, ("_mm_move_epi64",0), None)),
	'maskmovdqu':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_maskmoveu_si128", 2, False)),

	'cvtpd2ps':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtpd_ps", 4)),
	'cvtps2pd':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtps_pd", 4)),
	'cvtdq2pd':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtepi32_pd", 4)),
	'cvtpd2dq':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtpd_epi32", 4)),
	'cvtsd2si':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtsd_si32", 4)),
	'cvtsd2ss':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtsd_ss", 4)),
	'cvtsi2sd':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtsi32_sd", 4)),
	'cvtss2sd':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtss_sd", 4)),
	'cvttpd2dq':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvttpd_epi32", 4)),
	'cvttsd2si':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvttsd_si32", 4)),
	'cvtdq2ps':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtepi32_ps", 4)),
	'cvtps2dq':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtps_epi32", 4)),
	'cvttps2dq':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvttps_epi32", 4)),
	'cvtpd2pi':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtpd_pi32", 4)),
	'cvttpd2pi':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvttpd_pi32", 4)),
	'cvtpi2pd':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cvtpi32_pd", 4)),

	'paddb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_add_epi8")),
	'paddw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_add_epi16")),
	'paddd':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_add_epi32")),
	'padddq':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_add_epi64")),
	'paddsb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_adds_epi8")),
	'paddsw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_adds_epi16")),
	'paddusb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_adds_epu8")),
	'paddusw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_adds_epu16")),
	'pavgb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_avg_epu8")),
	'pavgw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_avg_epu16")),
	'pmaddwd':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_madd_epi16")),
	'pmaxsw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_max_epi16")),
	'pmaxub':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_max_epu8")),
	'pminsw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_min_epi16")),
	'pminub':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_min_epu8")),
	'pmulhw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_mulhi_epi16")),
	'pmulhuw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_mulhi_epu16")),
	'pmullo':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_mullo_epi16")),
	'pmuludq':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_mul_epu32")),
	'pmuludq':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_mul_epu32")),
	'psadbw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_sad_epu8")),
	'psubb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_sub_epi8")),
	'psubw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_sub_epi16")),
	'psubd':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_sub_epi32")),
	'psubq':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_sub_epi64")),
	'psubsb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_subs_epi8")),
	'psubsw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_subs_epi16")),
	'psubusb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_subs_epu8")),
	'psubusw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_subs_epu16")),

	'pand':			(InstSet.SSE2I, lambda t: intrin(t, "_mm_and_si128")),
	'pandn':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_andnot_si128")),
	'por':			(InstSet.SSE2I, lambda t: intrin(t, "_mm_or_si128")),
	'pxor':			(InstSet.SSE2I, lambda t: intrin(t, "_mm_xor_si128") if t[0] != t[1] else intrin(t, "_mm_setzero_si128", 5)),

	'pslldq':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_slli_si128")),
	'psrldq':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_srli_si128")),
	'psllw':		(InstSet.SSE2I, lambda t: sseIntrin(t, ("_mm_slli_epi16",0), None, ("_mm_sll_epi16",0), None)),
	'pslld':		(InstSet.SSE2I, lambda t: sseIntrin(t, ("_mm_slli_epi32",0), None, ("_mm_sll_epi32",0), None)),
	'psllq':		(InstSet.SSE2I, lambda t: sseIntrin(t, ("_mm_slli_epi64",0), None, ("_mm_sll_epi64",0), None)),
	'psraw':		(InstSet.SSE2I, lambda t: sseIntrin(t, ("_mm_srai_epi16",0), None, ("_mm_sra_epi16",0), None)),
	'psrad':		(InstSet.SSE2I, lambda t: sseIntrin(t, ("_mm_srai_epi32",0), None, ("_mm_sra_epi32",0), None)),
	'psrlw':		(InstSet.SSE2I, lambda t: sseIntrin(t, ("_mm_srli_epi16",0), None, ("_mm_srl_epi16",0), None)),
	'psrld':		(InstSet.SSE2I, lambda t: sseIntrin(t, ("_mm_srli_epi32",0), None, ("_mm_srl_epi32",0), None)),
	'psrlq':		(InstSet.SSE2I, lambda t: sseIntrin(t, ("_mm_srli_epi64",0), None, ("_mm_srl_epi64",0), None)),

	'movd':			(InstSet.SSE2I, lambda t: mmxIntrin(t, ("_mm_cvtsi32_si128",0), ("_mm_cvtsi128_si32",0), None, None)),
	
	'pcmpeqb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cmpeq_epi8")),
	'pcmpeqw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cmpeq_epi16")),
	'pcmpeqd':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cmpeq_epi32")),
	'pcmpgtb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cmpgt_epi8")),
	'pcmpgtw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cmpgt_epi16")),
	'pcmpgtd':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cmpgt_epi32")),
	'pcmpgtbr':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cmplt_epi8")),
	'pcmpgtwr':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cmplt_epi16")),
	'pcmpgtdr':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_cmplt_epi32")),

	'packsswb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_packs_epi16")),
	'packssdw': 	(InstSet.SSE2I, lambda t: intrin(t, "_mm_packs_epi32")),
	'packuswb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_packus_epi16")),
	'punpckhbw':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_unpackhi_epi8")),
	'punpckhwd':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_unpackhi_epi16")),
	'punpckhdq':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_unpackhi_epi32")),
	'punpckhqdq':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_unpackhi_epi64")),
	'punpcklbw':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_unpacklo_epi8")),
	'punpcklwd':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_unpacklo_epi16")),
	'punpckldq':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_unpacklo_epi32")),
	'punpcklqdq':	(InstSet.SSE2I, lambda t: intrin(t, "_mm_unpacklo_epi64")),
	'pextrw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_extract_epi16", 1)),
	'pinsrw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_insert_epi16", 2)),
	'pmovmskb':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_movemask_epi8", 4)),
	'pshufd':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_shuffle_epi32", 1)),
	'pshufhw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_shufflehi_epi16", 1)),
	'pshuflw':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_shufflelo_epi16", 1)),
	'movdq2q':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_movepi64_pi64", 1)),
	'movq2dq':		(InstSet.SSE2I, lambda t: intrin(t, "_mm_movpi64_pi64", 1)),
	
	#sse3 (http://msdn.microsoft.com/en-us/library/x8zs5twb.aspx)
	'addsubpd':		(InstSet.SSE3, lambda t: intrin(t, "_mm_addsub_pd")),
	'addsubps':		(InstSet.SSE3, lambda t: intrin(t, "_mm_addsub_ps")),
	'haddpd':		(InstSet.SSE3, lambda t: intrin(t, "_mm_hadd_pd")),
	'haddps':		(InstSet.SSE3, lambda t: intrin(t, "_mm_hadd_ps")),
	'hsubpd':		(InstSet.SSE3, lambda t: intrin(t, "_mm_hsub_pd")),
	'hsubps':		(InstSet.SSE3, lambda t: intrin(t, "_mm_hsub_ps")),
	'monitor':		(InstSet.SSE3, lambda t: intrin(t, "_mm_monitor")),
	'movshd':		(InstSet.SSE3, lambda t: intrin(t, "_mm_movehdup_ps")),
	'movsld':		(InstSet.SSE3, lambda t: intrin(t, "_mm_moveldup_ps")),
	'mwait':		(InstSet.SSE3, lambda t: intrin(t, "_mm_mwait")),

	#ssse3 (http://msdn.microsoft.com/en-us/library/bb892952.aspx)
	'pabsb':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_abs_epi8")),
	'pabsw':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_abs_epi16")),
	'pabsd':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_abs_epi32")),
	'palignr':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_alignr_epi8")),
	'phaddsw':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_hadds_epi16")),
	'phaddw':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_hadd_epi16")),
	'phaddd':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_hadd_epi32")),
	'phsubsw':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_hsubs_epi16")),
	'phsubw':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_hsub_epi16")),
	'phsubd':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_hsub_epi32")),
	'pmaddubsw':	(InstSet.SSSE3, lambda t: intrin(t, "_mm_maddubs_epi16")),
	'pmulhrsw':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_mulhrs_epi16")),
	'pshufb':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_shuffle_epi8")),
	'psignb':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_sign_epi8")),
	'psignw':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_sign_epi16")),
	'psignd':		(InstSet.SSSE3, lambda t: intrin(t, "_mm_sign_epi32")),
	
	#sse4 (http://msdn.microsoft.com/en-us/library/bb892950.aspx)
	'pinsrd':		(InstSet.SSE4, lambda t: intrin(t, "_mm_insert_epi32", 3)),
	'blendvpb':		(InstSet.SSE4, lambda t: intrin(t, "_mm_blendv_epi8")),
	'blendvpd':		(InstSet.SSE4, lambda t: intrin(t, "_mm_blendv_pd")),
	'ptest':		(InstSet.SSE4, lambda t: intrin(t, "_mm_testc_si128")),
	
	#sse4a
	'extrq':		(InstSet.SSE4A, lambda t: intrin(t, "_mm_extract_si64")), 
	'insertq':		(InstSet.SSE4A, lambda t: intrin(t, "_mm_insert_si64")),
	'movntsd':		(InstSet.SSE4A, lambda t: intrin(t, "_mm_stream_sd")),
	'movntss':		(InstSet.SSE4A, lambda t: intrin(t, "_mm_stream_ss")),
	
	#sse4.1
	'dppd':			(InstSet.SSE41, lambda t: intrin(t, "_mm_dp_pd")),
	'dpps':			(InstSet.SSE41, lambda t: intrin(t, "_mm_dp_ps")),
	'extractps':	(InstSet.SSE41, lambda t: intrin(t, "_mm_extract_ps")),
	'insertps':		(InstSet.SSE41, lambda t: intrin(t, "_mm_insert_ps")),
	'movntdqa':		(InstSet.SSE41, lambda t: intrin(t, "_mm_stream_load_si128")),
	'mpsadbw':		(InstSet.SSE41, lambda t: intrin(t, "_mm_mpsadbw_epu8")),
	'packusdw':		(InstSet.SSE41, lambda t: intrin(t, "_mm_packus_epi32")),
	'pblendw':		(InstSet.SSE41, lambda t: intrin(t, "_mm_blend_epi16")),
	'blendpd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_blend_pd")),
	'blendps':		(InstSet.SSE41, lambda t: intrin(t, "_mm_blend_ps")),
	'pblendvb':		(InstSet.SSE41, lambda t: intrin(t, "_mm_blendv_epi8")),
	'blendvpd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_blendv_pd")),
	'blendvps':		(InstSet.SSE41, lambda t: intrin(t, "_mm_blendv_ps")),
	'pcmpeqq':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cmpeq_epi64")),
	'pextrb':		(InstSet.SSE41, lambda t: intrin(t, "_mm_extract_epi8")),
	'pextrd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_extract_epi32")),
	'pextrq':		(InstSet.SSE41, lambda t: intrin(t, "_mm_extract_epi64")),
	'pinsrb':		(InstSet.SSE41, lambda t: intrin(t, "_mm_insert_epi8")),
	'pinsrd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_insert_epi32")),
	'pinsrq':		(InstSet.SSE41, lambda t: intrin(t, "_mm_insert_epi64")),
	'pmaxsb':		(InstSet.SSE41, lambda t: intrin(t, "_mm_max_epi8")),
	'pmaxsd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_max_epi32")),
	'pmaxuw':		(InstSet.SSE41, lambda t: intrin(t, "_mm_max_epu16")),
	'pmaxud':		(InstSet.SSE41, lambda t: intrin(t, "_mm_max_epu32")),
	'pminsb':		(InstSet.SSE41, lambda t: intrin(t, "_mm_min_epi8")),
	'pminsd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_min_epi32")),
	'pminuw':		(InstSet.SSE41, lambda t: intrin(t, "_mm_min_epu16")),
	'pminud':		(InstSet.SSE41, lambda t: intrin(t, "_mm_min_epu32")),
	'pmovsxbw':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepi8_epi16")),
	'pmovsxbd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepi8_epi32")),
	'pmovsxbq':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepi8_epi64")),
	'pmovsxwd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepi16_epi32")),
	'pmovsxwq':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepi16_epi64")),
	'pmovsxdq':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepi32_epi64")),
	'pmovzxbw':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepu8_epi16")),
	'pmovzxbd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepu8_epi32")),
	'pmovzxwd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepu8_epi64")),
	'pmovzxwd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepu16_epi32")),
	'pmovzxwq':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepu16_epi64")),
	'pmovzxdq':		(InstSet.SSE41, lambda t: intrin(t, "_mm_cvtepu32_epi64")),
	'pmuldq':		(InstSet.SSE41, lambda t: intrin(t, "_mm_mul_epi32")),
	'pmullud':		(InstSet.SSE41, lambda t: intrin(t, "_mm_mullo_epi32")),
	'ptest':		(InstSet.SSE41, lambda t: intrin(t, "_mm_test?_si128")),
	'roundpd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_" + rounding[int(t[2])] + "_pd")),
	'roundps':		(InstSet.SSE41, lambda t: intrin(t, "_mm_" + rounding[int(t[2])] + "_ps")),
	'roundsd':		(InstSet.SSE41, lambda t: intrin(t, "_mm_" + rounding[int(t[2])] + "_sd")),
	'roundss':		(InstSet.SSE41, lambda t: intrin(t, "_mm_" + rounding[int(t[2])] + "_ss")),
}

variables = dict()

def op2intrin(op,params,instr):
	global variables
	op = op.replace('//','#')
	params = params.replace('//','#')
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
			#unroll params
			var = None
			global variableSet
			variableSet = False
			if op != 'lea': #cheat
				for i,p in enumerate(t):
					if re.search(r"\s*\[.*\]\s*", p):
						val = p.strip()[1:-1].split('+',1)
						if i == 0:
							var = val.split('\W',1)[0].strip()
						p = "((char*)"+val[0].strip()+")"
						if len(val) > 1:
							p += "["+val[1].strip()+"]";
						t[i] = p
					elif i == 0:
						var = t[0].split('\W',1)[0].strip()
				variableSet = op.startswith('mov')
			else:	# remove []
				variableSet = True
				t[1] = t[1].strip()[1:-1]
				var = t[0].split('\W',1).strip()
			#update statistic
			instType = ops[op][0]
			if instType in instr:
				instr[instType] += 1 
			else:
				instr[instType] = 1
			#execute
			currentOp = ops[op][1](t)
			#add variable declaration
			decl = ''
			if var:
				if not (var in variables):
					if variableSet:
						if isXMMreg(var):
							if instType == InstSet.SSE2I:
								decl = '_m128i '
							elif instType == InstSet.SSE2:
								decl = '_m128d '
							else:
								decl = '_m128 '
						else:
							decl = 'int '
					variables[var] = 1
				else:
					variables[var] += 1
			return decl + currentOp + "\t" + comment
		elif not (":" in op or op.startswith("#") or op.startswith("//")):
			if 0 in instr:
				instr[0] += 1 
			else:				
				instr[0] = 1
			return "// unsupported: " + op + " " + ", ".join(t) + comment
		else:
			return op + " " + comment
	else:
		return comment

def asm2intrin(assembler, dstFile):
	lines = assembler.split('\n')
	instr = {}
	for line in lines:
		tokens = line.split(None,1)
		if len(tokens):
			params = tokens[1] if len(tokens) > 1 else ''
			dstFile.write(op2intrin(tokens[0],params,instr) + '\n')
		else:
			dstFile.write(line + '\n')
	print('\nInstructions statistic:')
	dict = {InstSet.Unsupported : 'Unsupported', 
		 InstSet.x86 : 'x86', 
		 InstSet.SSE : 'SSE',
		 InstSet.SSE2 : 'SSE2',
		 InstSet.SSE2I : 'SSE2I',
		 InstSet.SSE3 : 'SSE3',
		 InstSet.SSSE3 : 'SSSE3',
		 InstSet.SSE4 : 'SSE4',
		 InstSet.SSE4A : 'SSE4A',
		 InstSet.SSE41 : 'SSE4.1',
		 InstSet.SSE42 : 'SSE4.2'}
	for i in instr:
		print(dict[i] + ": " + str(instr[i]))


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
	print('')
