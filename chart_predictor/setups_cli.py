"""Command line entry point for the P5 dev-only setup backtest."""
import json
from .setup_backtest import run

def main():
    report,jp,mp=run()
    print(json.dumps({"fingerprint":report["fingerprint"],"runtime_seconds":report["runtime_seconds"],"cells_tested":report["cells_tested"],"json":str(jp),"markdown":str(mp)},indent=2))

if __name__=="__main__":main()
