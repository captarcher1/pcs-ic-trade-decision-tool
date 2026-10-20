import sys, math, datetime
sys.path.insert(0,'.')
from data import option_chain as oc
from data.option_chain import Contract
S=7669.19; T=28/365; r=.04; q=.013
def ncdf(x): return .5*(1+math.erf(x/math.sqrt(2)))
def price(K,iv,call):
    d1=(math.log(S/K)+(r-q+.5*iv*iv)*T)/(iv*math.sqrt(T)); d2=d1-iv*math.sqrt(T)
    if call: return S*math.exp(-q*T)*ncdf(d1)-K*math.exp(-r*T)*ncdf(d2)
    return K*math.exp(-r*T)*ncdf(-d2)-S*math.exp(-q*T)*ncdf(-d1)
exp=datetime.date(2026,11,17); chain=[]
for K in range(6000,9100,5):
    iv=min(.40,max(.09,.165-.9*math.log(K/S)))
    for cp in "PC":
        mid=price(K,iv,cp=="C"); sp=max(.10,.04*mid); bid=max(0,round((mid-sp/2)/.05)*.05); ask=round((mid+sp/2)/.05)*.05
        d=oc.bs_delta(S,K,T,r,q,iv,cp=="C")
        chain.append(Contract("SPXW",exp,cp,float(K),bid,ask,d,iv,100,10))
for floor in (0.07,0.03,0.01):
    pr,_=oc.build_rows(chain,"P",25,True); ca=oc.build_all(chain,"C",25,True,floor)
    pairs,un=oc.pair_ic_distance(pr,ca,S)
    print("call floor",floor,"-> pairs",len(pairs),"unpaired",un)
    for p in pairs: print("  put %d (%.1fd, -%d)  call %d (%.1fd, +%d)  gap %.1f  credit mid %.2f+%.2f" % (p["put"]["short_strike"],p["put"]["delta"]*100,p["dist_put"],p["call"]["short_strike"],p["call"]["delta"]*100,p["dist_call"],p["dist_gap"],p["put"]["mid"],p["call"]["mid"]))
print("--- put tier rows")
for p in pr: print(" put",p["short_strike"],round(p["delta"]*100,1),"dist",round(S-p["short_strike"]),"mid",p["mid"])
print("--- call_all (floor .03): n=",len(ca)," strikes",min(c["short_strike"] for c in ca),"-",max(c["short_strike"] for c in ca))
for c in ca[::6]: print(" call",c["short_strike"],round(c["delta"]*100,1),"dist",round(c["short_strike"]-S),"mid",c["mid"])
