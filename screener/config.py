"""Global settings. Each skill's own settings live in its file in screener/skills/."""

UNIVERSE_FILE = "universe.txt"
PICKS_FILE = "data/picks.csv"
BACKTEST_TRADES_FILE = "data/backtest_trades.csv"
BACKTEST_SUMMARY_FILE = "data/backtest_summary.csv"
SKILL_STATUS_FILE = "data/skill_status.json"     # written by the Guard bot
TUNED_FILE = "data/tuned_params.json"            # settings you approved from the Coach bot
COACH_FILE = "data/coach_suggestions.json"       # Coach bot's latest ideas
REPORT_FILE = "docs/index.html"
TODAY_POST_FILE = "data/today_post.md"
STUDY_FILE = "data/study_notes.json"             # what the Study bot learned from past charts
HYPE_HISTORY_FILE = "data/hype_history.csv"      # nightly Reddit mention counts (Hype bot)
NEWS_HISTORY_FILE = "data/news_history.csv"      # nightly headline count + mood (News bot)
WATCHLIST_FILE = "data/watchlist.json"           # beaten-down + red-day watchlist (Watchlist bot)
LONG_TEST_FILE = "data/long_test_summary.csv"    # 2-year practice test on hourly prices (weekly)

BRAND_NAME = "Day Trade Picks"

# False = signals go ONLY to you (Boss) on Telegram.
# True  = live signals ALSO go to your community (Discord / community Telegram).
COMMUNITY_POSTING = False

# --- Timing (US/Eastern) ---
SCAN_TIME = "10:30"
SCAN_WINDOW_END = "12:00"
OPENING_RANGE_END = "10:00"
LAST_ENTRY_TIME = "15:00"
EXIT_TIME = "15:55"

# --- Universe filters ---
MIN_PRICE = 5.0
MIN_AVG_DOLLAR_VOL = 20_000_000
MARKET_TICKER = "SPY"          # used by the Weather bot, never picked
BREADTH_URL = "https://tradermonty.github.io/market-breadth-analysis/market_breadth_data.csv"  # Breadth bot (practice only)

# --- Costs ---
SLIPPAGE_PCT = 0.0005          # 0.05% per side

# --- Output limits ---
MAX_PICKS_PER_SETUP = 2
MAX_PICKS_TOTAL = 5
MIN_RISK_PCT = 0.4
MAX_RISK_PCT = 6.0
RVOL_LOOKBACK_DAYS = 10

# --- Guard bot (benches losing skills, promotes winning ones) ---
GUARD_WINDOW = 20              # look at each skill's last 20 triggered trades
GUARD_MIN_TRADES = 10          # need at least this many before judging
GUARD_BENCH_BELOW_R = -0.10    # live skill averaging worse than this -> practice
GUARD_PROMOTE_ABOVE_R = 0.10   # practice skill averaging better than this -> live
# Boss's choice after the 2-year test (Nov 4): the Guard follows this until a skill has
# GUARD_MIN_TRADES real trades, then real results decide again.
BOSS_CHOICES = {"VWAP Pullback": "practice", "ORB Stocks in Play": "live"}

# --- Coach bot (tests better settings) ---
COACH_TRAIN_SHARE = 0.6        # learn on the first 60% of days, check on the last 40%
COACH_MIN_TRADES = 8
COACH_MIN_IMPROVEMENT_R = 1.0  # new settings must beat old ones by 1R+ on unseen days
