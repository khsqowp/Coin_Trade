import os,sys,__main__,runpy
os.environ["TP_ROOT"]="/home/opc/trading/pipeline"
sys.path[:0]=["research/us_daily_v2","research/us_daily_v1","src"]
import usbt2
__main__.Panel=usbt2.Panel
ns=runpy.run_path("research/us_daily_v3_exploratory_20261108/us_v3.py",run_name="us_v3_a7_run")
ns["main"]()
