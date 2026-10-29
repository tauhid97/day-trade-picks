# Day Trade Picks: Boss's Bot Team

## The big idea (explained like you're 5)

Imagine you have a **team of little robot helpers**. Each one has **one job** it's really good at. Every school day (stock market day), they work together to find a few stocks that might go up today, and they **text you on Telegram**.

You check how they do for a while. When they've proven they're good, you let them post to your paid community too.

---

## Meet the team

| Robot | Its one job | Like... |
|---|---|---|
| **Scout** | Looks at ~180 popular stocks every morning and asks each **skill** "see anything good?" | A kid looking for the best shells on the beach |
| **Skills** (4 of them) | Each skill knows **one trick** for spotting a good trade (see below) | Different players on a sports team |
| **Weather** | Checks if the whole market is happy (**sunny**), unsure (**cloudy**), or falling (**stormy**). On stormy days, most skills sit out. | Checking for rain before going to the park |
| **Messenger** | Texts you the picks on Telegram, then the results after school | The friend who passes notes |
| **Judge** | After the market closes, checks every pick: did it win or lose? It's strict: if it's unsure, it counts a **loss**. | A referee |
| **Guard** | Watches each skill's scores. If a skill keeps losing, it gets **benched** (practice mode). If a practice skill starts winning, it gets **put back in the game**. | A coach deciding who plays |
| **Coach** | Every Saturday it tries small changes to each skill's settings to see if they'd work better. It **asks you before changing anything.** | A coach trying new plays at practice |

### The 4 skills

| Skill | The trick, explained like you're 5 |
|---|---|
| **Gap & Go** | A stock jumped up this morning and lots of people are buying. If it climbs above today's highest point, we hop on for the ride. |
| **VWAP Pullback** | A stock is having a good day. VWAP is the "average price" line. When the price dips back down to that line, we buy it on sale. |
| **Oversold Bounce** | A big, famous stock fell too far, too fast, like a ball dropped hard. We wait until it starts bouncing back up, then buy. |
| **ORB Stocks in Play** | **Copied from a real research paper.** We find the stocks everyone is crowding into today. If the price breaks above its first-30-minute high, we buy and hold until the end of the day. |

### Every pick has 3 numbers
- **Entry**: the price where you buy. If the price never gets there, there's no trade. That's fine.
- **Stop**: the "uh-oh" price. If it falls here, you sell to keep a small loss small.
- **Target**: the "yay" price where you take your profit. (Some skills just sell at the end of the day instead.)

### What is "R"?
**R = how much you risked.** If you risk $10 on a trade:
- +2R means you **won $20**
- -1R means you **lost $10**

Good skills win more R than they lose over time, even if they lose some trades.

### Live vs. practice
- **LIVE** skills: their picks are the real ones and count on your public scoreboard.
- **PRACTICE** skills: still tracked, so the Guard can see if they improve, but labeled "practice." They're never sent to your community.
- Every **new** skill starts in practice until it proves itself.

---

## Your daily routine (you do almost nothing)

| Time (New York) | What happens |
|---|---|
| ~10:40 AM | Your phone buzzes: today's picks, plus the market weather |
| ~5:30 PM | Your phone buzzes again: the results, plus any Guard news |
| Saturday | Weekly check-up: how each skill did, plus the Coach's ideas |

Your job: **read the picks, watch what happens, and learn.** Don't use real money until the scoreboard has looked good for a couple of months.

---

## One-time setup (about 20 minutes, all from a browser)

### Step 1: Make your Telegram bot (5 min, on your phone)
1. Open Telegram and search for **@BotFather**, then tap **Start**.
2. Send `/newbot`. Give it a name (like *Boss Signals*) and a username ending in `bot` (like `boss_signals_bot`).
3. BotFather replies with a long **token** (looks like `123456:ABC-xyz...`). **Copy it somewhere safe.** This is your bot's password.
4. Search for **your new bot** and tap **Start**. Bots can't text you until you say hi first.
5. Search for **@userinfobot** and tap **Start**. It replies with your **Id** (a number like `987654321`). Copy it too.

### Step 2: Put the project on GitHub (10 min)
1. Make a free account at **github.com**.
2. Tap **+**, then **New repository**. Name it `daytrade-picks`, choose **Public** (needed for the free scoreboard page), and tap **Create**.
3. Tap **"uploading an existing file"**. Unzip the folder on a computer and drag **everything inside it** in, then tap **Commit changes**.
   - If you don't see the `.github` folder (it's hidden on Mac and Windows): tap **Add file**, then **Create new file**. Type the name `.github/workflows/daily.yml`, paste in what's inside that file, and tap **Commit**.

### Step 3: Give GitHub your Telegram keys (3 min)
1. In your repo, open **Settings**, then **Secrets and variables**, then **Actions**, then **New repository secret**.
2. Add the first secret: Name `TELEGRAM_BOT_TOKEN`, Value = the token from BotFather.
3. Add the second secret: Name `TELEGRAM_CHAT_ID`, Value = your Id number from @userinfobot.

### Step 4: Say hello and run the first test (2 min)
1. Open the **Actions** tab. If GitHub asks, tap **"I understand, enable workflows."**
2. Tap **Daily picks**, then **Run workflow**, choose **`hello`**, and tap **Run**. Your phone should get "Hi Boss!" within a minute or two.
3. Run it again, this time choosing **`backtest`**. In about 10 minutes you get a report on how every skill did over the last 2 months. The Guard decides which skills start LIVE.

### Step 5: Turn on your public scoreboard (1 min)
**Settings**, then **Pages**. Choose **Deploy from a branch**, then **main**, then **/docs**, and tap **Save**. Your scoreboard will live at `https://YOUR-NAME.github.io/daytrade-picks/`.

**That's it. The robots now run by themselves every market day.**

---

## Buttons you can push (Actions → Daily picks → Run workflow)

| Button | What it does |
|---|---|
| `hello` | Sends a test text to make sure Telegram works |
| `backtest` | Weekly check-up now: practice on the past, Coach ideas, Guard decisions |
| `approve` | Says "yes" to the Coach's latest ideas |
| `report` | Rebuilds the scoreboard page |

---

## When you're ready for a community (after 2–3 good months)
1. Make a Discord server or a Telegram channel.
2. Add one or both as secrets: `DISCORD_WEBHOOK_URL` (Discord: Channel settings, then Integrations, then Webhooks, then Copy URL) or `TELEGRAM_COMMUNITY_CHAT_ID` (add your bot to the channel as an admin, then use `@yourchannelname`).
3. Ask Claude to flip `COMMUNITY_POSTING` to `True`. From then on, **live** picks go to the community and **you** still get everything, including practice picks.
4. Charge through **Whop**, **LaunchPass**, or **Patreon**. Signal groups often charge about $29–$99 a month. Start low and raise the price as your scoreboard grows.

## Adding new skills (from GitHub, YouTube, books...)
Found a strategy you like? **Send Claude the link.** Claude will check it's safe and real, then turn it into a new skill file. New skills always start in **practice**, so a bad one can't hurt your scoreboard. The Guard only lets it play if it wins.

Don't paste random code from the internet into the project yourself. Some of it is broken, and some is even harmful.

## The grown-up rules (please read; not legal advice, so ask a securities lawyer before charging money)
- **Same picks for everyone.** Don't give one-on-one "what should I buy" advice to paying members.
- **Never trade ahead of or against your own picks.** That's illegal front-running.
- **Show the losses too.** Your scoreboard does this automatically, and it's what makes people trust you.
- **Backtests are "pretend"** and must be labeled hypothetical. The page already does this.
- Outside the US? Check your country's rules. Some are stricter.

## Honest truths
- No robot wins every day. Losing weeks will happen. That's why the stops exist.
- Free stock data can be late or fail. If it does, the bot texts you "no data" and **never makes anything up**.
- Only about 2 months of free history is available, so the backtest is a warm-up, not proof. **Your live scoreboard is the real test.**
