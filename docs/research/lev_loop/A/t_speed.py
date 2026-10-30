from lib import *
import time
init()
t=time.time(); r=[one(((4.0,.35),"FULL","BASE",1,0,0,True)) for _ in range(5)]; print((time.time()-t)/5, r[0]['wend'], r[0]['g'], r[0]['kills'], r[0]['liq_flat'], r[0]['cush_flat'], r[0]['top5_syms'], r[0]['gain'])
