#  
#  optimizing.py
#  Loop_TRG
#  Perform SVD to transform square to octagon and optimize it
#
#  Copyright (C) 2018 Yue Zhengyuan, Liu Honghui and Zhang Wenqian. All rights reserved.
#  Article reference: Phys. Rev. Lett. 118, 110504 (2017)
#

import numpy as np
from itertools import product
# from sympy import *

# get the initial value of the 8 S's using SVD
# ts_T: the tuple of tensors (TA, TB)
# d_cut: the upper limit of number of singular values to be kept
# return: tuple of the initial values of the 8 S's
#         whether the cutoff is used (0: not used; 1: used)  
def init_S(ts_T, d_cut):
    d = ts_T[0].shape[0]
    d2 = d**2
    dc = d_cut
    used_cutoff = 1
    if (d_cut >= d2):
        dc = d2
        used_cutoff = 0
    mat = []
    # convert T[0]/T[1] to (d^2)x(d^2) matrix mat[0], mat[1]
    mat.append(ts_T[0].reshape((d2,d2))) 
    mat.append((np.einsum('lijk->ijkl',ts_T[1])).reshape((d2,d2)))
    # do svd for mat
    ts_Result = []
    for i in range(2):
        mat_U, s, mat_V = np.linalg.svd(mat[i], full_matrices=True)
        # keep the largest Dc singular values
        s = s[0:dc]
        diag_s = np.diag(s)
        s1 = np.sqrt(diag_s)
        s2 = np.sqrt(diag_s)
        # keep the corresponding (first dc) rows/columns in u/v
        mat_U = mat_U[:,0:dc]
        mat_V = mat_V[0:dc,:]
        # find the decomposition
        mat1 = np.matmul(mat_U,s1)
        mat2 = np.matmul(s2,mat_V)
        # convert the resulted matrix to d x d x dc tensor
        ts_S1 = mat1.reshape((d,d,dc))
        ts_S2 = mat2.reshape((dc,d,d))
        ts_Result.append(ts_S1)
        ts_Result.append(ts_S2)
    
    ts_Result.append(np.einsum('nkb->kbn',ts_Result[1]))
    ts_Result.append(np.einsum('ajn->naj',ts_Result[0]))
    ts_Result.append(np.einsum('rnc->ncr',ts_Result[3]))
    ts_Result.append(np.einsum('bmr->rbm',ts_Result[2]))
    # elements in result:
    # S1, S2, S3, S4, S2, S1, S4, S3
    return tuple(ts_Result), used_cutoff

# calculate the constant C
def const_C(ts_T):
    # transpose the tensors TA, TB
    ts_T_list = []
    ts_T_list.append(ts_T[0])
    ts_T_list.append(np.einsum('cbmn->bmnc', ts_T[1]))
    ts_T_list.append(np.einsum('qdcp->cpqd', ts_T[0]))
    ts_T_list.append(np.einsum('liad->dlia', ts_T[1]))

    for i in range(4):
        ts_Temp = np.einsum('ebch,abcd->ehad',ts_T_list[i], ts_T_list[i])
        if i == 0:
            ts_C = ts_Temp
        elif i == 3:
            ts_C = np.einsum('heda,ehad',ts_C,ts_Temp)
        else:
            ts_C = np.einsum('mena,ehad->mhnd',ts_C,ts_Temp)
    return ts_C

# calculate the tensor N_i (i = 0 ~ 7)
# ts_S: the tuple of tensors S[k] (k = 0 ~ 7)
# return: ts_N_i
def tensor_N(i, ts_S):
    num = len(ts_S)     # should be 8
    ts_S_conj = np.conj(ts_S)
    for j in range(i+1, i+num):
        # k takes values i+1, ..., num-1, 0, ..., i-1
        if j <= num - 1:
            k = j
        elif j >= num:
            k = j - num
        # contract (S[k]+) and S[k] first to find a tensor ts_A
        ts_A = np.einsum('icj,sct->ijst', ts_S_conj[k], ts_S[k])
        if j == i + 1:
            ts_N = ts_A
        else: 
            ts_N = np.einsum('ijst,jktu->iksu', ts_N, ts_A)
    return ts_N

# calculate the tensor W_i
# ts_S: the tuple of tensors S[j] (j = 0 ~ 7)
# ts_T: the tuple of tensors (TA, TB)
# return: ts_W_i
def tensor_W(i, ts_S, ts_T):
    # grouping the tensors
    # 0: S[0],S[1],T[0]; 1: S[2],S[3],T[1];
    # 2: S[4],S[5],T[0]; 3: S[6],S[7],T[1];
    # --> j: S[2j],S[2j+1],T[j]
    pair = int(i / 2)
    ts_S_conj = np.conj(ts_S)

    # transpose the tensors TA, TB
    ts_T_list = []
    ts_T_list.append(ts_T[0])
    ts_T_list.append(np.einsum('cbmn->bmnc', ts_T[1]))
    ts_T_list.append(np.einsum('qdcp->cpqd', ts_T[0]))
    ts_T_list.append(np.einsum('liad->dlia', ts_T[1]))

    # contract the complete part
    for p in range(pair + 1, pair + 4):
        # j takes the value p+1, ... 3, 0, ..., p-1
        if p <= 3:
            j = p
        elif p >= 4:
            j = p - 4
        ts_B = np.einsum('dpm,mqn,gpqr->dngr', ts_S_conj[2*j], ts_S_conj[2*j+1], ts_T_list[j])
        if p == pair + 1:
            ts_Complete = ts_B
        else:
            ts_Complete = np.einsum('bngr,ndrf->bdgf', ts_Complete, ts_B)
    
    # contract the incomplete part
    if i % 2 == 0:              # W starts with C
        ts_C = np.einsum('bed,fceg->bdfcg', ts_S_conj[i+1], ts_T_list[pair])
        ts_W = np.einsum('bdfcg,dagf->bac', ts_C, ts_Complete)
    elif i % 2 != 0:            # W starts with B
        ts_C = np.einsum('dea,fecg->dafcg', ts_S_conj[i-1], ts_T_list[pair])
        ts_W = np.einsum('bdgf,dafcg->bac', ts_Complete, ts_C)
    return ts_W

# solve the equation (N_i)(S_i) = (W_i) for (S_i)
# return: the solution S_i = (N_i)^(-1) * (W_i)
def optimize_S(ts_N, ts_W):
    # convert tensor N_(abcd) to matrix N_(ab,cd)
    mat_N = ts_N.reshape((ts_N.shape[0]*ts_N.shape[1], ts_N.shape[2]*ts_N.shape[3]))
    # convert tensor W_(abe) to matrix W_(ab,e)
    mat_W = ts_W.reshape((ts_W.shape[0]*ts_W.shape[1], ts_W.shape[2]))
    # find matrix S'_(cd,e)
    # mat_S = np.dot(np.linalg.inv(mat_N), mat_W)
    mat_S = np.linalg.solve(mat_N, mat_W)
    # convert matrix S' to tensor S'_(cde)
    ts_S = mat_S.reshape((ts_N.shape[2], ts_N.shape[3], ts_W.shape[2]))
    # find the required S using S_(dec) = S'_(cde)
    ts_S = np.einsum('cde->dec', ts_S)
    return ts_S

# the cost function for the replacement of the 4 T by the 8 S
def cost_func(i, ts_S, ts_T):
    term1 = const_C(ts_T)

    ts_N = tensor_N(i, ts_S)
    term2 = np.einsum('cea,acbd,deb',np.conj(ts_S[i]),ts_N,ts_S[i])

    ts_W = tensor_W(i, ts_S, ts_T)
    term3 = np.einsum('acb,bac',ts_S[i],np.conj(ts_W))
    term4 = np.einsum('acb,bac',np.conj(ts_S[i]),ts_W)

    return term1 + term2 - term3 - term4

# loop-optimize the 8 tensors ts_S[i] (i = 0 ~ 7)
# then build the new TA, TB from the 8 S's
# ts_T: the tuple of the two tensors TA, TB
# d_cut: the upper limit of number of singular values to be kept
# error: "distance" between two successive optimization results
# return: the new TA, TB built from the optimized S's
def loop_optimize(ts_T, d_cut, error_limit):
    error = np.inf
    # initialize the 8 tensors S
    ts_S_old, used_cutoff = init_S(ts_T, d_cut)
    ts_S_old = list(ts_S_old)
    ts_S_new = ts_S_old.copy()
    num = len(ts_S_old)    # should be 8
    
    # loop-optimizing the 8 S's
    # if used_cutoff == 0:
    #     pass
    # elif used_cutoff == 1:
    loop_round = 0
    while (error > error_limit):
        cost_old = cost_func(0, ts_S_new, ts_T)
        for i in range(num):
            ts_N = tensor_N(i, ts_S_new)
            ts_W = tensor_W(i, ts_S_new, ts_T)
            ts_S_new[i] = optimize_S(ts_N, ts_W)
        cost_new = cost_func(0, ts_S_new, ts_T)
        error_raw = cost_new - cost_old
        error = np.abs(error_raw)
        loop_round += 1

    # construct new tensors TA/TB from the optimized 8 S's
    # transposition is needed
    # ts_S_new[0] = np.einsum('dcj->cjd',ts_S_new[0])
    # ts_S_new[1] = np.einsum('lba->alb',ts_S_new[1])
    # ts_S_new[2] = np.einsum('adk->dka',ts_S_new[2])
    # ts_S_new[3] = np.einsum('icb->bic',ts_S_new[3])
    # ts_S_new[4] = np.einsum('bal->alb',ts_S_new[4])
    # ts_S_new[5] = np.einsum('jdc->cjd',ts_S_new[5])
    # ts_S_new[6] = np.einsum('cbi->bic',ts_S_new[6])
    # ts_S_new[7] = np.einsum('kad->dka',ts_S_new[7])

    # ts_TA = np.einsum('alb,bic,cjd,dka->lijk',ts_S_new[4],ts_S_new[3],ts_S_new[0],ts_S_new[7])
    # ts_TB = np.einsum('alb,bic,cjd,dka->lijk',ts_S_new[1],ts_S_new[6],ts_S_new[5],ts_S_new[2])

    ts_TA = np.einsum('bal,icb,dcj,kad->lijk',ts_S_new[4],ts_S_new[3],ts_S_new[0],ts_S_new[7])
    ts_TB = np.einsum('lba,cbi,jdc,adk->lijk',ts_S_new[1],ts_S_new[6],ts_S_new[5],ts_S_new[2])
    return ts_TA, ts_TB
