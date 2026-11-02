"""Command center for the bot team.

  python main.py scan       # Scout + Weather: find today's picks, send to Boss (10:30-12:00 ET)
  python main.py grade      # Judge + Guard: grade picks after the close, bench/promote skills
  python main.py backtest   # Practice on the past + Coach ideas + Guard check (weekly)
  python main.py approve    # accept the Coach's latest suggestions
  python main.py hello      # send a test message to your Telegram
  python main.py report     # rebuild the track-record page
  python main.py auto       # picks the right job based on the time (used by the schedule)
  python main.py commands   # answer Boss's /status /picks /scoreboard /skills messages (every ~15 min)
"""
import sys

import pandas as pd

from screener import backtest, commands, live, plain, report
from screener import config as C
from screener.bots import coach, guard, news
from screener.notify import to_boss


def weekly():
    trades, summary, prepared, intraday = backtest.run()
    msg = ["Boss, here's the weekly check-up.", ""]
    if len(summary):
        msg.append("Practice on the past (last ~2 months, hypothetical - not real trades):")
        for _, r in summary.iterrows():
            msg.append(f"- {plain.nick(r['setup'])}: {int(r['filled'])} trades, won {r['win_rate_pct']}%, "
                       f"total {plain.money(r['total_R'])} if you risked ${plain.RISK_DOLLARS} each")
        if "breadth" in trades:
            msg += ["", "Breadth bot [practice - info only, all skills, by market breadth]:"] + backtest.by_breadth(trades)
        msg += ["", "News bot [practice - info only, real picks so far, by news label]:"] + news.summary(live.load_picks())
        msg += ["", coach.run(prepared, intraday)]
    status, changes = guard.run(live.load_picks(), pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d"))
    msg += ["", guard.team_sheet(status)]
    text = "\n".join(msg)
    print(text)
    to_boss(text)
    report.build()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "auto"
    if cmd == "scan":
        live.scan(force="--force" in sys.argv)
    elif cmd == "grade":
        live.grade(); report.build()
    elif cmd == "backtest":
        weekly()
    elif cmd == "approve":
        text = coach.approve(); print(text); to_boss(text)
    elif cmd == "hello":
        ok = to_boss(f"Hi Boss! Your {C.BRAND_NAME} bot is connected. Signals will arrive here.")
        print("Sent!" if ok else "Telegram secrets are missing - see README step 3.")
    elif cmd == "report":
        report.build()
    elif cmd == "commands":
        commands.handle()
    elif cmd == "auto":
        hm = pd.Timestamp.now(tz="America/New_York").strftime("%H:%M")
        if C.SCAN_TIME <= hm <= C.SCAN_WINDOW_END:
            live.scan()
        elif hm >= "16:10" or hm < "09:00":
            live.grade(); report.build()
        else:
            print(f"Nothing scheduled at {hm} ET.")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
