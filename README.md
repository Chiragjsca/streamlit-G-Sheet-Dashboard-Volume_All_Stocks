
# 📊 Top 250 NSE Stock-Volume Breakout Dashboard

A professional, all‑in‑one dashboard for Indian stock market analysis.  
It combines live data from Google Sheets, AI (Gemini/Groq), advanced filtering, watchlists, a **bottom‑fishing** score, a GTT order calculator, dozens of embedded market portals, and much more.

---

## ✨ Key Features

- **📈 Live Market Indices** – NIFTY 50, NIFTY Next 50, NIFTY Midcap 50, etc. (Yahoo Finance, refreshes every 60s).
- **🏢 Top 250 Stocks Matrix** – CMP & daily % change cards, fully linked to NSE.
- **🏆 Advanced Ranking Dashboards** – Gainers/Losers, Volume Leaders, Most Active (Volume & Value), Top by Turnover.
- **🌍 National Exchange Scanner** – Embedded TradingView screeners for **all NSE/BSE** stocks (Gainers, Losers, 52W High/Low, Reversals, Top 100 Traded).
- **📄 Google Sheets Integration** – 6 different sheets (`Top 250 Stocks`, `Final List`, `Diff @ 200 DMA`, etc.) with full colour preservation.
- **🎨 Powerful Filtering** – Global search, colour filters, numeric sliders, DMA trend filters (e.g. 50 DMA > 200 DMA), date filters.
- **🤖 AI Analysis** – Gemini or Groq (Llama 3.3) analyses any selected stock using live sheet data. Pre‑defined prompts, exportable history.
- **💻 Pine Script Generator** – AI writes TradingView Pine Script v5 strategies (Volume Breakout, Moving Average Crossover, Trend Following, Mean Reversion).
- **🔬 Bottom Fishing Score** – 0–100 score based on 8 criteria (proximity to 52W low, uptrend, volume, debt, profit, RONW, promoter holding, pledge). Grades: Strong Buy / Watchlist / Caution / Avoid.
- **🎯 GTT Order Calculator** – Auto‑suggest Stop‑Loss (1×, 1.5×, 2× ATR), multiple targets (1R, 2R, 3R), position sizing, copy‑ready order summary.
- **📝 Watchlist Manager** – Persistent watchlist stored in a Google Sheet. Add notes, download Excel, share via WhatsApp/Telegram.
- **📅 Multi‑Horizon Performance Matrix** – Returns for 24 time horizons (1 day … 3 years) plus volume, coloured by performance.
- **🧭 National Analytics Portal** – 27 embedded iframes (NSE official pages, Moneycontrol, Chartink, Screener, ScanX, IPO Watch, etc.) with “Open in Browser” fallback.
- **📥 Full Excel Export** – Export filtered grids, watchlist, AI history, bottom‑fishing results.
- **🖼️ Responsive Design** – Works on desktop and mobile (with external links for embedded iframes).

--------------------------------------------------------------------------------------------------

📊 Top 250 NSE Stock-Volume Breakout Dashboard – User Guide
This dashboard is a complete technical & fundamental analysis platform for the top 250 NSE stocks, plus a full-market scanner for all NSE/BSE equities. It combines live data from Google Sheets, AI analysis (Gemini/Groq), advanced filtering, watchlists, order calculators, bottom‑fishing scores, and dozens of embedded market portals.

📈 2. Live Market Indices (Top Section)
Displays NIFTY 50, NIFTY NEXT 50, NIFTY MIDCAP 50 and other key indices.

Data is fetched from Yahoo Finance (refreshed every 60 seconds).

Each card shows: index name, current price, daily % change (green/red).

Click on any card → opens the official NSE live‑indices page.

💡 If no cards appear, Yahoo Finance data may be temporarily unavailable.

📊 3. Top 250 Stocks Matrix & Ranking Dashboards
3.1 Stock Ticker Cards
Shows CMP and daily % change for each stock in the “Top 250 Stocks” sheet.

Click a card → opens NSE quote page.

3.2 Advanced Ranking Dashboards (6 tabs)
Tab	What it shows
Gainers/Losers	Top 20 gainers & top 20 losers by % change
Volume Leaders	Highest & lowest 20 by volume
Active (Vol & Val)	Top 20 by volume, displaying both volume & traded value
Top by Value	Top 20 by traded value (₹)
Top by Turnover	Top 20 by turnover (₹)
Most Active	Top 20 by traded value (repeated, for convenience)
Each card includes: symbol, price, and a metric pill (e.g. +2.5% or Vol: 1.2M).

🌍 4. National Exchange Scanner (All NSE/BSE Stocks)
Embedded TradingView screeners inside 5 tabs:

Tab	Content
Gainers & Losers	Top gainers / top losers
Volume & Active	Volume leaders & most active (turnover)
52W High / Low	New 52‑week highs / lows
52W Reversals	Outperforming 52W high / underperforming 52W low
Top 100 Traded	General screener – sort by any metric
📱 If an iframe is blank on mobile, use the “Open in Browser” button above it.

🧩 5. Main Data Grid (Google Sheets)
5.1 Sheet selection (sidebar)
Choose from:
Top 250 Stocks | Final List | Final List 2 | Diff @ 200 DMA | +% | -%

5.2 Powerful filtering (sidebar)
Global search – any column.

Color filters – filter cells by background colour (e.g. all green cells in a column).

Categorical filters – Industry, Sector, Output, Start GTT Order, etc.

DMA trend filter – e.g. 50 DMA > 200 DMA.

Numeric range sliders – Volume, CMP, Promoters %, Net Profit, EPS, RONW %, Market Cap, and also Diff from 200 DMA, From 52W Low %, From 52W High %.

Date filters – 52W high / low dates (Past 5 days … Past 1 year).

5.3 Interactive table (AgGrid)
Click on any row → opens the Workspace Panel (see section 6).

Columns are dynamically coloured to match Google Sheets’ background/text colours.

Links (TradingView, Screener, Zerodha, etc.) are clickable directly in the grid.

Column width can be set to auto-fit row 1 or row 2.

5.4 Export
Download the currently filtered table as Excel (all colours removed).

🛠️ 6. Workspace Panel (after selecting a stock)
When you click a row in the main grid, a detailed panel appears with 11 tabs:

Tab	Description
Chart & Trade Info	NSE interactive chart (if the iframe is blocked, tap the “Open in Browser” link)
History Data	EquityPandit historical data iframe
Bullish/Bearish Zone	EquityPandit zone indicator
Screener Documents	Screener.in consolidated financials
Zerodha Portal	Zerodha markets page
MarketSmith India	Institutional evaluation
TradingView Profile	Asset profile from TradingView
🤖 AI Stock Analysis	Ask AI (Gemini or Groq) about the stock using live sheet data. Also includes suggested prompts, WhatsApp/Telegram share, and Excel export of AI history.
💻 AI Pine Script Builder	Generate a complete TradingView Pine Script v5 strategy based on the stock’s data. Choose from 4 strategy templates + add custom rules.
🔬 Bottom Fishing Score	Scores the stock (0–100) for buying near the 52W low. Shows grade (Strong Buy / Watchlist / Caution / Avoid) and detailed reasoning (proximity to low, uptrend, volume, debt, profit, RONW, promoter holding, pledge).
🎯 GTT Order Calculator	Automatically suggests stop‑loss (tight/standard/wide), targets (1R, 2R, 3R), ATR, position sizing, and a copy‑ready GTT summary. Share via WhatsApp/Telegram.
📊 Watchlist Manager	Add/remove the current stock to your personal watchlist (stored in a Google Sheet called Watchlist). Add a note, then view/manage the full watchlist, download as Excel, or share via messenger.
🤖 7. AI Features (Gemini & Groq)
Requirements
Add GEMINI_API_KEY and/or GROQ_API_KEY to Streamlit secrets.

If both are present, you can choose between ⚡ Groq (llama 3.3 70B) and 🧠 Gemini 2.5 Flash.

AI Stock Analysis
Select a stock from the grid, go to the AI tab.

Type your own question or pick from 10 suggested prompts (technical summary, entry zone, volume analysis, fundamentals, risk profile, buy/hold/sell recommendation, etc.).

The AI receives the full live row data (CMP, volumes, DMAs, fundamentals, etc.) and answers contextually.

Results are saved in st.session_state.ai_history and can be exported as a combined Excel file.

AI Pine Script Builder
Choose a strategy focus (volume breakout, moving average crossover, trend following, mean reversion).

Add custom rules (e.g., “use ATR trailing stop”).

AI generates ready‑to‑paste Pine Script v5 code.

Code can be saved as Excel.

Bottom Fishing AI Deep Analysis
Inside the Bottom Fishing Score tab, click “Get AI Deep Analysis”.

AI analyses the BF score, scoring breakdown, and gives specific entry/exit advice.

📝 8. Watchlist Manager
Stored in Google Sheet (tab name Watchlist) – persistent across sessions.

Columns: Symbol, CMP, Note, BF Score, BF Grade, Added On.

Add stocks from the Watchlist Manager tab of the workspace panel.

View, download, or share your watchlist directly from the sidebar or the workspace tab.

⚠️ If sheet write fails, check your gcp_service_account secrets.

🔬 9. Bottom Fishing Scanner (Standalone)
Located after the main grid.

Scores every stock from 0–100 based on 8 criteria (see table below).

Slider to set minimum BF score (default 55 = Watchlist grade).

Sort by score high→low or low→high.

Search a specific symbol.

Results show Symbol, Score, Grade, CMP, Sector, and the top 3 reasons.

Export results as Excel.

Criteria	Max Points
CMP within 8–15% of 52W low	30
CMP > 200 DMA (uptrend)	15
High volume (≥ 10M)	10
Low / zero debt (D/E ≤ 0.1)	10
Positive net profit	10
RONW ≥ 15%	10
Promoter holding ≥ 50%	8
Zero pledged shares	7
Grades:
🟢 STRONG BUY (≥75) | 🟡 WATCHLIST (55–74) | 🟠 CAUTION (35–54) | 🔴 AVOID (<35)

📅 10. Multi‑Horizon Performance Summary Matrix
Displays percentage returns over 24 time horizons (1 day, 2 days, … 3 years) plus Volume.

Ranks stocks based on any chosen horizon.

Includes BF Score & Grade columns.

Colours: green background for positive returns, red for negative.

Click the STOCK NAME cell → opens NSE chart.

Filter by symbol, adjust column widths, and export is available via the main Excel download.

🏆 11. Daily Top / Bottom Performers
Shows 10 best and 10 worst daily performers (based on the Price % column).

Each badge is a clickable link to the NSE chart.

🧭 12. National Analytics Portal (27 additional tabs)
A huge collection of embedded financial portals:

NSE official:

Most Active, Volume Gainers, Top Gainers/Losers, 52‑Week High/Low, Stocks Traded, Advances/Declines, Pre‑Open Market, Price Band Hitters, Index Heatmap, IPO Tracker, Document Reports

Third‑party:

Volume Shockers (Moneycontrol), TradingView Scripts, MunafaSutra, Dhan stock lists, ScanX (custom & live screener), Screener.in explore, Chittorgarh IPO, IPO Watch, NSE Pulse, Chartink (screeners, dashboard, atlas), Mahesh Kaushik, EFTI Wealth

Each tab has an “Open in Browser” button – use it if the iframe does not load on mobile.

⚙️ 13. Sidebar Controls – Summary
Clear All Filters – reset every filter and search.

Global Search – case‑insensitive search across all visible columns.

Sheet selector – change the active Google Sheet.

Symbol Column – choose which column contains the stock symbol.

Color Filters – pick a column and select background colours to show.

Categorical Filters – Industry, Sector, Output, etc.

DMA Trend Filter – e.g. 50 DMA < 100 DMA < 200 DMA.

Numeric sliders – Volume, CMP, Promoters %, Net Profit, EPS, RONW, etc.

Date filters – 52W high / low date.

Watchlist manager – view / remove stocks, download watchlist Excel.

AI History Export – download all AI queries and answers.

📥 14. Data Freshness & Caching
Google Sheets data: cached for 300 seconds (5 minutes).

Live indices (Yahoo Finance): cached for 60 seconds.

Use the browser refresh or the “Clear All Filters” button to force a reload.
