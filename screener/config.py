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

# --- Coach bot (tests better settings) ---
COACH_TRAIN_SHARE = 0.6        # learn on the first 60% of days, check on the last 40%
COACH_MIN_TRADES = 8
COACH_MIN_IMPROVEMENT_R = 1.0  # new settings must beat old ones by 1R+ on unseen days
