"""Run both studies offline: python -m research.strategist_lab."""
import argparse
import json

from .data import freeze_sources,load_data
from .execution import ExecutionConfig,run_execution
from .portfolio import run_portfolio


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",choices=["all","execution","portfolio"],default="all")
    parser.add_argument("--refresh-data",action="store_true",help="Explicitly replace frozen data from original source")
    parser.add_argument("--keep-db",action="store_true",help="Keep generated SQLite ledger (not committed)")
    parser.add_argument("--orders-per-day",type=int,default=400)
    args=parser.parse_args()
    if args.orders_per_day<10:parser.error("At least ten orders per day required")
    if args.refresh_data:freeze_sources()
    industries,factors=load_data()
    result={}
    if args.project in ["all","execution"]:
        metrics,*_=run_execution(factors,ExecutionConfig(orders_per_day=args.orders_per_day),keep_db=args.keep_db)
        result["execution"]={key:metrics[key] for key in ["orders","fills","sessions","reconciliation","alert_evaluation"]}
    if args.project in ["all","portfolio"]:
        metrics,*_=run_portfolio(industries,factors)
        result["portfolio"]={key:metrics[key] for key in ["sessions","annual_vol","risk_reconciliation_error","performance"]}
    from .reports import build_reports
    build_reports()
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
