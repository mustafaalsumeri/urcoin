"""
Ur Coin Web Interface:
- Responsive, futuristic Dark-Mode Dashboard & Explorer
- Built-in Decentralized Trading Desk (UrDEX) with Live Order Book, Candlestick Chart, & Instant Swaps
- Adaptive Mining Controls for Low-End / Weak GPUs (Zero-VRAM Light Mode)
- Embedded single-page application served directly by Node HTTP server
"""

HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ur Coin (URC) - Node, Trading Exchange & Adaptive Miner</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #090d16;
            --surface: #111827;
            --surface-hover: #1f2937;
            --border: #1e293b;
            --primary: #f59e0b;
            --primary-glow: rgba(245, 158, 11, 0.25);
            --secondary: #06b6d4;
            --secondary-glow: rgba(6, 182, 212, 0.25);
            --accent: #10b981;
            --danger: #ef4444;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        body {
            background-color: var(--bg);
            color: var(--text-main);
            min-height: 100vh;
            padding: 24px;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(245, 158, 11, 0.04) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(6, 182, 212, 0.05) 0%, transparent 50%);
        }

        .container {
            max-width: 1440px;
            margin: 0 auto;
        }

        /* Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .coin-logo {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, #f59e0b, #d97706);
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: 800;
            color: #000;
            box-shadow: 0 0 20px var(--primary-glow);
        }

        .brand-title h1 {
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }

        .brand-title p {
            font-size: 13px;
            color: var(--text-muted);
        }

        .header-badges {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: var(--accent);
            padding: 8px 16px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 600;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background: var(--accent);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.9); }
        }

        /* Live Market Ticker Banner */
        .ticker-ribbon {
            background: linear-gradient(90deg, #111827 0%, #151d30 100%);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }

        .ticker-pair {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .ticker-symbol {
            font-size: 18px;
            font-weight: 800;
            color: #fff;
        }

        .ticker-price {
            font-size: 22px;
            font-weight: 800;
            color: var(--accent);
            font-family: 'JetBrains Mono', monospace;
        }

        .ticker-change {
            font-size: 13px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
            background: rgba(16, 185, 129, 0.2);
            color: var(--accent);
        }

        .ticker-stat {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .ticker-stat-label {
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
        }

        .ticker-stat-value {
            font-size: 14px;
            font-weight: 700;
            color: #e2e8f0;
            font-family: 'JetBrains Mono', monospace;
        }

        /* Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .metric-card {
            background: var(--surface);
            border: 1px solid var(--border);
            padding: 18px;
            border-radius: 14px;
            position: relative;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }

        .metric-card:hover {
            transform: translateY(-2px);
            border-color: rgba(245, 158, 11, 0.4);
        }

        .metric-label {
            font-size: 12px;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .metric-value {
            font-size: 24px;
            font-weight: 800;
            color: #ffffff;
            font-family: 'JetBrains Mono', monospace;
        }

        .metric-sub {
            font-size: 12px;
            color: #64748b;
            margin-top: 4px;
        }

        /* Navigation Tabs */
        .nav-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .tab-btn:hover {
            color: #fff;
            background: rgba(255, 255, 255, 0.05);
        }

        .tab-btn.active {
            color: #000;
            background: var(--primary);
            box-shadow: 0 0 15px var(--primary-glow);
        }

        /* Panel Container */
        .panel {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 22px;
            margin-bottom: 24px;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
            padding-bottom: 14px;
            border-bottom: 1px solid var(--border);
        }

        .panel-title {
            font-size: 17px;
            font-weight: 700;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* Main Grid: Miner & Wallet */
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }

        @media (max-width: 992px) {
            .main-grid { grid-template-columns: 1fr; }
            .exchange-grid { grid-template-columns: 1fr !important; }
        }

        /* Exchange Grid Layout */
        .exchange-grid {
            display: grid;
            grid-template-columns: 1.2fr 1fr 1fr;
            gap: 18px;
            margin-bottom: 24px;
        }

        /* Chart Canvas */
        .chart-box {
            background: #0d1322;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            min-height: 280px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .chart-svg {
            width: 100%;
            height: 220px;
        }

        /* Order Book Display */
        .orderbook-box {
            background: #0d1322;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 14px;
            font-size: 12px;
        }

        .book-row {
            display: flex;
            justify-content: space-between;
            padding: 5px 8px;
            position: relative;
            font-family: 'JetBrains Mono', monospace;
            border-radius: 4px;
            margin-bottom: 2px;
        }

        .book-depth-bar {
            position: absolute;
            top: 0;
            bottom: 0;
            right: 0;
            opacity: 0.15;
            z-index: 1;
            border-radius: 4px;
        }

        .book-row span { position: relative; z-index: 2; }
        .book-ask { color: #f87171; }
        .book-bid { color: #4ade80; }

        /* Trading Form */
        .trade-form-box {
            background: #0d1322;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
        }

        .trade-tabs {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-bottom: 16px;
        }

        .trade-tab-btn {
            padding: 10px;
            border: none;
            border-radius: 8px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 13px;
        }

        .trade-tab-buy.active {
            background: #10b981;
            color: #fff;
            box-shadow: 0 0 12px rgba(16, 185, 129, 0.4);
        }

        .trade-tab-sell.active {
            background: #ef4444;
            color: #fff;
            box-shadow: 0 0 12px rgba(239, 68, 68, 0.4);
        }

        .trade-tab-inactive {
            background: #1e293b;
            color: var(--text-muted);
        }

        .input-group {
            margin-bottom: 14px;
        }

        .input-group label {
            display: block;
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 6px;
            font-weight: 600;
        }

        .input-control {
            width: 100%;
            background: #151d30;
            border: 1px solid var(--border);
            color: #fff;
            padding: 12px 14px;
            border-radius: 10px;
            font-size: 14px;
            font-family: 'JetBrains Mono', monospace;
            outline: none;
            transition: border-color 0.2s;
        }

        .input-control:focus {
            border-color: var(--primary);
        }

        .quick-pcts {
            display: flex;
            gap: 6px;
            margin-bottom: 14px;
        }

        .quick-pcts button {
            flex: 1;
            padding: 6px;
            background: #1e293b;
            border: 1px solid #334155;
            color: #cbd5e1;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
        }

        .quick-pcts button:hover {
            background: #334155;
            color: #fff;
        }

        /* Buttons */
        .btn {
            width: 100%;
            padding: 14px;
            border-radius: 10px;
            border: none;
            font-weight: 800;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }

        .btn-buy {
            background: linear-gradient(135deg, #10b981, #059669);
            color: #ffffff;
            box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3);
        }
        .btn-buy:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4); }

        .btn-sell {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: #ffffff;
            box-shadow: 0 4px 14px rgba(239, 68, 68, 0.3);
        }
        .btn-sell:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4); }

        .btn-swap {
            background: linear-gradient(135deg, #8b5cf6, #6d28d9);
            color: #ffffff;
            box-shadow: 0 4px 14px rgba(139, 92, 246, 0.3);
        }
        .btn-swap:hover { transform: translateY(-2px); }

        .btn-start {
            background: linear-gradient(135deg, #f59e0b, #d97706);
            color: #000;
            box-shadow: 0 4px 14px var(--primary-glow);
        }
        .btn-start:hover { transform: translateY(-2px); }

        .btn-stop {
            background: linear-gradient(135deg, #ef4444, #b91c1c);
            color: #fff;
            box-shadow: 0 4px 14px rgba(239, 68, 68, 0.3);
        }

        /* Miner Controls Box */
        .miner-box {
            background: #0d1322;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
        }

        .gpu-spec {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: #151d30;
            border-radius: 10px;
            margin-bottom: 16px;
        }

        .gpu-name {
            font-weight: 700;
            color: #fff;
            font-size: 14px;
        }

        .gpu-badge-light {
            background: rgba(6, 182, 212, 0.15);
            color: var(--secondary);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
        }

        .hashrate-display {
            text-align: center;
            padding: 18px 0;
            background: radial-gradient(circle, rgba(245, 158, 11, 0.08) 0%, transparent 70%);
            margin-bottom: 16px;
        }

        .hashrate-number {
            font-size: 42px;
            font-weight: 800;
            color: var(--primary);
            font-family: 'JetBrains Mono', monospace;
        }

        .hashrate-unit {
            font-size: 16px;
            color: var(--text-muted);
            margin-left: 6px;
        }

        .miner-stats-row {
            display: flex;
            justify-content: space-around;
            padding: 12px 0;
            border-top: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
            margin-bottom: 16px;
            font-size: 13px;
        }

        /* Wallet Card */
        .wallet-card {
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.08) 0%, rgba(245, 158, 11, 0.04) 100%);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 18px;
            margin-bottom: 18px;
        }

        .wallet-balance {
            font-size: 28px;
            font-weight: 800;
            color: #fff;
            font-family: 'JetBrains Mono', monospace;
        }

        .wallet-address {
            background: #0d1322;
            border: 1px solid var(--border);
            padding: 10px 14px;
            border-radius: 8px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--secondary);
            word-break: break-all;
            cursor: pointer;
            transition: background 0.2s;
            margin-top: 6px;
        }

        .wallet-address:hover {
            background: #151d30;
        }

        /* Table */
        .table-responsive { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
        th { padding: 12px; color: var(--text-muted); font-weight: 600; border-bottom: 1px solid var(--border); text-transform: uppercase; font-size: 11px; }
        td { padding: 12px; border-bottom: 1px solid #1a2234; font-family: 'JetBrains Mono', monospace; }
        tr:hover td { background: rgba(255, 255, 255, 0.02); }
        .hash-truncate { max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--secondary); }
        .badge-block { background: rgba(245, 158, 11, 0.15); color: var(--primary); padding: 4px 8px; border-radius: 6px; font-weight: 700; }
        .btn-cancel { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 11px; font-weight: bold; }
        .btn-cancel:hover { background: #ef4444; color: #fff; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="brand">
                <div class="coin-logo">UR</div>
                <div class="brand-title">
                    <h1>Ur Coin (URC)</h1>
                    <p>Next-Gen Tradable Cryptocurrency with Adaptive PoW for High & Low-End GPUs</p>
                </div>
            </div>
            <div class="header-badges">
                <div class="status-badge">
                    <div class="status-dot"></div>
                    <span>NODE & P2P MARKET ONLINE</span>
                </div>
            </div>
        </header>

        <!-- Live Market Ticker Ribbon -->
        <div class="ticker-ribbon">
            <div class="ticker-pair">
                <span class="ticker-symbol">URC / USDT</span>
                <span class="ticker-price" id="t-last-price">$0.0520</span>
                <span class="ticker-change" id="t-change">+0.00%</span>
            </div>
            <div class="ticker-stat">
                <span class="ticker-stat-label">24h High</span>
                <span class="ticker-stat-value" id="t-high">$0.0545</span>
            </div>
            <div class="ticker-stat">
                <span class="ticker-stat-label">24h Low</span>
                <span class="ticker-stat-value" id="t-low">$0.0480</span>
            </div>
            <div class="ticker-stat">
                <span class="ticker-stat-label">24h Volume (URC)</span>
                <span class="ticker-stat-value" id="t-vol-urc">12,500 URC</span>
            </div>
            <div class="ticker-stat">
                <span class="ticker-stat-label">24h Volume (USDT)</span>
                <span class="ticker-stat-value" id="t-vol-usdt">$650.00</span>
            </div>
        </div>

        <!-- Metrics Grid -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Block Height</div>
                <div class="metric-value" id="val-height">#0</div>
                <div class="metric-sub">Block Time: 30s (EMA Time-Decay)</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Circulating Supply</div>
                <div class="metric-value" id="val-supply">0.00 URC</div>
                <div class="metric-sub">Halving every 210,000 blocks</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Current Block Reward</div>
                <div class="metric-value" id="val-reward">50 URC</div>
                <div class="metric-sub">Decentralized PoW Emission</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Mempool Transactions</div>
                <div class="metric-value" id="val-mempool">0</div>
                <div class="metric-sub">Pending mempool confirmation</div>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <div class="nav-tabs">
            <button class="tab-btn active" onclick="switchMainTab('exchange', this)">📈 البورصة والتداول (UrDEX Exchange)</button>
            <button class="tab-btn" onclick="switchMainTab('mining', this)">⚡ تعدين كروت الشاشة والمعالج (Mining)</button>
            <button class="tab-btn" onclick="switchMainTab('explorer', this)">⛓️ مستكشف البلوكات (Explorer)</button>
        </div>

        <!-- TAB 1: EXCHANGE & TRADING (URDEX) -->
        <div id="tab-exchange-panel">
            <div class="exchange-grid">
                <!-- Left: Price Chart Box -->
                <div class="panel" style="margin-bottom:0;">
                    <div class="panel-header">
                        <div class="panel-title">
                            <span>📊 الرسم البياني لسعر العملة (URC/USDT)</span>
                        </div>
                        <span style="font-size: 11px; color: var(--text-muted);">Real-time Market Depth</span>
                    </div>
                    <div class="chart-box">
                        <svg class="chart-svg" id="price-svg" viewBox="0 0 500 220">
                            <!-- Background Grid -->
                            <line x1="0" y1="40" x2="500" y2="40" stroke="#1e293b" stroke-dasharray="4"/>
                            <line x1="0" y1="90" x2="500" y2="90" stroke="#1e293b" stroke-dasharray="4"/>
                            <line x1="0" y1="140" x2="500" y2="140" stroke="#1e293b" stroke-dasharray="4"/>
                            <line x1="0" y1="190" x2="500" y2="190" stroke="#1e293b" stroke-dasharray="4"/>
                            <!-- Chart Line -->
                            <path id="chart-path" d="M 10 160 Q 100 140 180 110 T 320 70 T 490 50" fill="none" stroke="#10b981" stroke-width="3"/>
                            <path id="chart-area" d="M 10 160 Q 100 140 180 110 T 320 70 T 490 50 L 490 220 L 10 220 Z" fill="url(#chart-grad)" opacity="0.25"/>
                            <defs>
                                <linearGradient id="chart-grad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stop-color="#10b981"/>
                                    <stop offset="100%" stop-color="transparent"/>
                                </linearGradient>
                            </defs>
                        </svg>
                        <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; margin-top:8px;">
                            <span>24 Hours Ago</span>
                            <span>12 Hours Ago</span>
                            <span>Current Price</span>
                        </div>
                    </div>
                </div>

                <!-- Middle: Order Book Box -->
                <div class="panel" style="margin-bottom:0;">
                    <div class="panel-header">
                        <div class="panel-title">
                            <span>📖 دفتر الطلبات (Order Book)</span>
                        </div>
                        <span style="font-size: 11px; color: #64748b;">Live Depth</span>
                    </div>
                    <div class="orderbook-box">
                        <div style="display:flex; justify-content:space-between; color:#64748b; font-size:11px; margin-bottom:6px; font-weight:700;">
                            <span>Price (USDT)</span>
                            <span>Amount (URC)</span>
                            <span>Total</span>
                        </div>
                        <!-- Asks (Sells - Top) -->
                        <div id="orderbook-asks" style="display:flex; flex-direction:column-reverse; margin-bottom:8px;">
                            <div class="book-row book-ask"><span>0.0540</span><span>3,000</span><span>$162</span><div class="book-depth-bar" style="width:40%; background:#ef4444;"></div></div>
                            <div class="book-row book-ask"><span>0.0525</span><span>1,200</span><span>$63</span><div class="book-depth-bar" style="width:20%; background:#ef4444;"></div></div>
                        </div>

                        <!-- Spread Indicator -->
                        <div style="text-align:center; padding:4px 0; border-top:1px solid #1e293b; border-bottom:1px solid #1e293b; font-size:12px; font-weight:800; color:var(--primary); margin-bottom:8px;">
                            Market Spread: <span id="market-spread">0.0010 USDT</span>
                        </div>

                        <!-- Bids (Buys - Bottom) -->
                        <div id="orderbook-bids">
                            <div class="book-row book-bid"><span>0.0515</span><span>1,000</span><span>$51.5</span><div class="book-depth-bar" style="width:18%; background:#10b981;"></div></div>
                            <div class="book-row book-bid"><span>0.0500</span><span>2,500</span><span>$125</span><div class="book-depth-bar" style="width:35%; background:#10b981;"></div></div>
                        </div>
                    </div>
                </div>

                <!-- Right: Trading Form (Buy / Sell / Swap) -->
                <div class="panel" style="margin-bottom:0;">
                    <div class="panel-header">
                        <div class="panel-title">
                            <span>⚡ تنفيذ الصفقات (Trade Desk)</span>
                        </div>
                    </div>
                    <div class="trade-form-box">
                        <div class="trade-tabs">
                            <button class="trade-tab-btn trade-tab-buy active" id="tab-buy-btn" onclick="selectTradeSide('BUY')">شراء URC</button>
                            <button class="trade-tab-btn trade-tab-inactive" id="tab-sell-btn" onclick="selectTradeSide('SELL')">بيع URC</button>
                        </div>

                        <div class="input-group">
                            <label>سعر التداول (Price in USDT)</label>
                            <input type="number" step="0.0001" class="input-control" id="trade-price" placeholder="0.0520" oninput="calcTradeTotal()" />
                        </div>

                        <div class="input-group">
                            <label>الكمية (Amount in URC)</label>
                            <input type="number" step="0.1" class="input-control" id="trade-amount" placeholder="100" oninput="calcTradeTotal()" />
                        </div>

                        <div class="quick-pcts">
                            <button onclick="setTradePct(0.25)">25%</button>
                            <button onclick="setTradePct(0.50)">50%</button>
                            <button onclick="setTradePct(0.75)">75%</button>
                            <button onclick="setTradePct(1.00)">100%</button>
                        </div>

                        <div class="input-group">
                            <label>القيمة الإجمالية (Total USDT)</label>
                            <input type="text" class="input-control" id="trade-total" readonly placeholder="0.00 USDT" />
                        </div>

                        <button class="btn btn-buy" id="btn-execute-trade" onclick="executeTradeOrder()">
                            <span>تأكيد وشراء URC</span>
                        </button>

                        <div style="margin-top:14px; text-align:center;">
                            <a href="javascript:void(0)" onclick="openInstantSwapModal()" style="color:var(--secondary); font-size:12px; font-weight:700; text-decoration:none;">🔄 استخدام مجمع التحويل الفوري (Instant Swap)</a>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Bottom: Active Orders & Recent Trades -->
            <div class="main-grid">
                <!-- User Active Orders -->
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">
                            <span>📋 أوامرك المعلقة في السوق (Your Open Orders)</span>
                        </div>
                    </div>
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th>Side</th>
                                    <th>Price</th>
                                    <th>Amount</th>
                                    <th>Filled</th>
                                    <th>Status</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody id="user-orders-tbody">
                                <tr><td colspan="6" style="text-align:center; color:#64748b;">لا توجد أوامر معلقة حالياً</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Recent Market Trades -->
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">
                            <span>🔥 آخر الصفقات المنفذة في السوق (Recent Trades)</span>
                        </div>
                    </div>
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th>Price (USDT)</th>
                                    <th>Amount (URC)</th>
                                    <th>Total Value</th>
                                    <th>Time</th>
                                </tr>
                            </thead>
                            <tbody id="market-trades-tbody">
                                <tr><td colspan="4" style="text-align:center; color:#64748b;">جاري تحميل الصفقات...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- TAB 2: MINING & WALLET -->
        <div id="tab-mining-panel" style="display:none;">
            <div class="main-grid">
                <!-- Left: GPU / CPU Miner -->
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">
                            <span>⚡ مركز التعدين الذكي (Adaptive GPU & CPU Miner)</span>
                        </div>
                        <span id="miner-state-badge" style="font-size: 12px; font-weight: 700; color: #94a3b8;">IDLE</span>
                    </div>

                    <div class="miner-box">
                        <div class="gpu-spec">
                            <div>
                                <div class="gpu-name" id="miner-device-name">Auto-Detecting GPU / Hardware...</div>
                                <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Algorithm: UrHash-v1 (Zero-VRAM Light Mode Compatible)</div>
                            </div>
                            <div class="gpu-badge-light" id="miner-mode-badge">Adaptive Mode</div>
                        </div>

                        <!-- Hardware Profile Selector for Weak GPUs -->
                        <div class="input-group">
                            <label>نمط التعدين وقوة الهاردوير (Mining Hardware Profile)</label>
                            <select class="input-control" id="miner-profile-select">
                                <option value="eco">🌱 نمط التوفير وكروت الشاشة الضعيفة والمدمجة (Zero-VRAM Eco Mode - No Lag)</option>
                                <option value="medium" selected>⚖️ نمط متوازن لكروت الفئة المتوسطة (Balanced Mode)</option>
                                <option value="high">🚀 أقصى أداء لكروت الفئة العليا (Maximum Performance Mode)</option>
                            </select>
                        </div>

                        <div class="hashrate-display">
                            <span class="hashrate-number" id="miner-hashrate">0.00</span>
                            <span class="hashrate-unit" id="miner-unit">MH/s</span>
                        </div>

                        <div class="miner-stats-row">
                            <div>Blocks Mined: <strong id="miner-blocks-found" style="color: var(--accent);">0</strong></div>
                            <div>Total Hashes: <strong id="miner-total-hashes">0</strong></div>
                        </div>

                        <div class="input-group">
                            <label>عنوان محفظة استلام المكافآت (Coinbase Reward)</label>
                            <input type="text" class="input-control" id="miner-reward-address" readonly />
                        </div>

                        <button class="btn btn-start" id="btn-toggle-miner" onclick="toggleMiner()">
                            <span>بدء التعدين الآن (START MINING)</span>
                        </button>
                    </div>
                </div>

                <!-- Right: Wallet & Transfers -->
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">
                            <span>💼 محفظة العقدة المدمجة (Ur Coin Wallet)</span>
                        </div>
                    </div>

                    <div class="wallet-card">
                        <div class="metric-label">رصيد محفظتك المتاح (Available Balance)</div>
                        <div class="wallet-balance"><span id="wallet-balance">0.00000000</span> <span style="font-size: 18px; color: var(--primary);">URC</span></div>
                        
                        <div class="metric-label" style="margin-top: 14px;">عنوان المحفظة للإيداع واستقبال العملات (اضغط للنسخ)</div>
                        <div class="wallet-address" id="wallet-address" onclick="copyAddress()">Loading...</div>
                    </div>

                    <!-- Send Transfer Form -->
                    <div>
                        <h3 style="font-size: 15px; margin-bottom: 12px;">إرسال وتحويل URC لعنوان آخر</h3>
                        <div class="input-group">
                            <label>عنوان المستلم (Recipient urc1...)</label>
                            <input type="text" class="input-control" id="tx-recipient" placeholder="urc1..." />
                        </div>
                        <div class="input-group">
                            <label>الكمية (Amount in URC)</label>
                            <input type="number" step="0.00000001" class="input-control" id="tx-amount" placeholder="10.0" />
                        </div>
                        <button class="btn btn-start" style="background: linear-gradient(135deg, #06b6d4, #0284c7);" onclick="sendTransaction()">
                            إرسال المعاملة إلى الشبكة
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- TAB 3: EXPLORER -->
        <div id="tab-explorer-panel" style="display:none;">
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">
                        <span>⛓️ مستكشف شبكة البلوكتشين المباشر (Blockchain Explorer)</span>
                    </div>
                </div>

                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Height</th>
                                <th>Block Hash</th>
                                <th>Transactions</th>
                                <th>Nonce</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody id="blocks-tbody">
                            <tr><td colspan="5" style="text-align: center; color: #64748b;">Loading blocks...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- JavaScript Engine -->
    <script>
        let isMining = false;
        let activeTradeSide = "BUY";
        let currentWalletBal = 0;
        const RPC_COOKIE = "__URC_RPC_COOKIE__";

        function rpcHeaders(extra) {
            return Object.assign({ "X-Urcoin-Rpc-Cookie": RPC_COOKIE }, extra || {});
        }

        function rpcFetch(url, opts) {
            opts = opts || {};
            opts.headers = rpcHeaders(opts.headers);
            return fetch(url, opts);
        }

        function switchMainTab(tabName, btnElem) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btnElem.classList.add('active');

            document.getElementById('tab-exchange-panel').style.display = (tabName === 'exchange') ? 'block' : 'none';
            document.getElementById('tab-mining-panel').style.display = (tabName === 'mining') ? 'block' : 'none';
            document.getElementById('tab-explorer-panel').style.display = (tabName === 'explorer') ? 'block' : 'none';
        }

        function selectTradeSide(side) {
            activeTradeSide = side;
            const buyBtn = document.getElementById('tab-buy-btn');
            const sellBtn = document.getElementById('tab-sell-btn');
            const execBtn = document.getElementById('btn-execute-trade');

            if (side === "BUY") {
                buyBtn.className = "trade-tab-btn trade-tab-buy active";
                sellBtn.className = "trade-tab-btn trade-tab-inactive";
                execBtn.className = "btn btn-buy";
                execBtn.innerText = "تأكيد وشراء URC";
            } else {
                buyBtn.className = "trade-tab-btn trade-tab-inactive";
                sellBtn.className = "trade-tab-btn trade-tab-sell active";
                execBtn.className = "btn btn-sell";
                execBtn.innerText = "تأكيد وبيع URC";
            }
        }

        function calcTradeTotal() {
            const p = parseFloat(document.getElementById('trade-price').value) || 0;
            const a = parseFloat(document.getElementById('trade-amount').value) || 0;
            document.getElementById('trade-total').value = (p * a).toFixed(4) + " USDT";
        }

        function setTradePct(pct) {
            const price = parseFloat(document.getElementById('trade-price').value) || 0.0520;
            if (activeTradeSide === "SELL") {
                const amt = (currentWalletBal * pct);
                document.getElementById('trade-amount').value = amt.toFixed(2);
            } else {
                // Buy with simulated 100 USDT balance
                const usdtAvailable = 100.0;
                const amt = ((usdtAvailable * pct) / price);
                document.getElementById('trade-amount').value = amt.toFixed(2);
            }
            calcTradeTotal();
        }

        async function executeTradeOrder() {
            const price = parseFloat(document.getElementById('trade-price').value);
            const amount = parseFloat(document.getElementById('trade-amount').value);
            if (isNaN(price) || price <= 0 || isNaN(amount) || amount <= 0) {
                alert("يرجى إدخال سعر وكمية صحيحة للتداول.");
                return;
            }
            try {
                const res = await rpcFetch('/api/exchange/order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        side: activeTradeSide,
                        price: price,
                        amount: amount
                    })
                });
                const data = await res.json();
                if (data.success) {
                    alert("✓ تم وضع أمر التداول بنجاح في دفتر الطلبات!");
                    updateExchangeData();
                    updateDashboard();
                } else {
                    alert("فشل تنفيذ الأمر: " + data.error);
                }
            } catch (e) {
                alert("خطأ أثناء إرسال أمر التداول: " + e);
            }
        }

        async function cancelOrder(orderId) {
            if (!confirm("هل أنت متأكد من إلغاء هذا الأمر؟")) return;
            try {
                const res = await rpcFetch('/api/exchange/cancel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ order_id: orderId })
                });
                const data = await res.json();
                if (data.success) {
                    alert("تم إلغاء الأمر بنجاح.");
                    updateExchangeData();
                } else {
                    alert("تعذر الإلغاء: " + data.error);
                }
            } catch (e) {
                alert("خطأ: " + e);
            }
        }

        async function openInstantSwapModal() {
            const amt = prompt("أدخل كمية URC التي ترغب في تحويلها فوراً إلى USDT بسعر السوق المباشر:");
            if (!amt || isNaN(parseFloat(amt)) || parseFloat(amt) <= 0) return;
            try {
                const res = await rpcFetch('/api/exchange/swap', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        from_asset: "URC",
                        to_asset: "USDT",
                        amount_in: parseFloat(amt)
                    })
                });
                const data = await res.json();
                if (data.success) {
                    alert(`🎉 تم التحويل الفوري بنجاح!\nتم استبدال ${data.swap.amount_in} URC مقابل ${data.swap.amount_out.toFixed(4)} USDT.`);
                    updateExchangeData();
                    updateDashboard();
                } else {
                    alert("فشل التحويل: " + data.error);
                }
            } catch (e) {
                alert("خطأ في التحويل: " + e);
            }
        }

        async function updateExchangeData() {
            try {
                // 1. Ticker
                const tRes = await rpcFetch('/api/exchange/ticker');
                const tData = await tRes.json();
                document.getElementById('t-last-price').innerText = '$' + tData.last_price.toFixed(4);
                const ch = document.getElementById('t-change');
                ch.innerText = (tData.change_24h_pct >= 0 ? '+' : '') + tData.change_24h_pct.toFixed(2) + '%';
                ch.style.color = tData.change_24h_pct >= 0 ? '#10b981' : '#ef4444';
                ch.style.background = tData.change_24h_pct >= 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)';

                document.getElementById('t-high').innerText = '$' + tData.high_24h.toFixed(4);
                document.getElementById('t-low').innerText = '$' + tData.low_24h.toFixed(4);
                document.getElementById('t-vol-urc').innerText = tData.volume_urc_24h.toLocaleString() + ' URC';
                document.getElementById('t-vol-usdt').innerText = '$' + tData.volume_usdt_24h.toLocaleString();

                if (!document.getElementById('trade-price').value) {
                    document.getElementById('trade-price').value = tData.last_price.toFixed(4);
                }

                // 2. Order Book
                const obRes = await rpcFetch('/api/exchange/orderbook');
                const obData = await obRes.json();
                renderOrderBook(obData);

                // 3. User Orders
                const uoRes = await rpcFetch('/api/exchange/user_orders');
                const uoData = await uoRes.json();
                renderUserOrders(uoData);

                // 4. Market Trades
                const mtRes = await rpcFetch('/api/exchange/trades');
                const mtData = await mtRes.json();
                renderMarketTrades(mtData);

            } catch (e) {
                console.error("Exchange poll error:", e);
            }
        }

        function renderOrderBook(book) {
            const asksDiv = document.getElementById('orderbook-asks');
            const bidsDiv = document.getElementById('orderbook-bids');

            if (book.asks && book.asks.length > 0) {
                asksDiv.innerHTML = book.asks.slice(0, 5).map(a => `
                    <div class="book-row book-ask" onclick="document.getElementById('trade-price').value='${a.price.toFixed(4)}'; calcTradeTotal();">
                        <span>${a.price.toFixed(4)}</span>
                        <span>${a.amount.toLocaleString()}</span>
                        <span>$${a.total.toFixed(1)}</span>
                        <div class="book-depth-bar" style="width:${Math.min(100, (a.amount / 5000) * 100)}%; background:#ef4444;"></div>
                    </div>
                `).join('');
            }

            if (book.bids && book.bids.length > 0) {
                bidsDiv.innerHTML = book.bids.slice(0, 5).map(b => `
                    <div class="book-row book-bid" onclick="document.getElementById('trade-price').value='${b.price.toFixed(4)}'; calcTradeTotal();">
                        <span>${b.price.toFixed(4)}</span>
                        <span>${b.amount.toLocaleString()}</span>
                        <span>$${b.total.toFixed(1)}</span>
                        <div class="book-depth-bar" style="width:${Math.min(100, (b.amount / 5000) * 100)}%; background:#10b981;"></div>
                    </div>
                `).join('');
            }

            if (book.asks && book.bids && book.asks[0] && book.bids[0]) {
                const spread = Math.abs(book.asks[0].price - book.bids[0].price);
                document.getElementById('market-spread').innerText = spread.toFixed(4) + " USDT";
            }
        }

        function renderUserOrders(orders) {
            const tbody = document.getElementById('user-orders-tbody');
            if (!orders || orders.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#64748b;">لا توجد أوامر معلقة حالياً</td></tr>';
                return;
            }
            tbody.innerHTML = orders.map(o => `
                <tr>
                    <td style="color:${o.side === 'BUY' ? '#10b981' : '#ef4444'}; font-weight:700;">${o.side}</td>
                    <td>$${o.price.toFixed(4)}</td>
                    <td>${o.amount} URC</td>
                    <td>${o.filled} URC</td>
                    <td><span style="color:${o.status === 'FILLED' ? '#10b981' : '#f59e0b'}; font-weight:bold;">${o.status}</span></td>
                    <td>
                        ${(o.status === 'OPEN' || o.status === 'PARTIAL') ? `<button class="btn-cancel" onclick="cancelOrder('${o.order_id}')">إلغاء</button>` : '-'}
                    </td>
                </tr>
            `).join('');
        }

        function renderMarketTrades(trades) {
            const tbody = document.getElementById('market-trades-tbody');
            if (!trades || trades.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#64748b;">لا توجد صفقات منفذة</td></tr>';
                return;
            }
            tbody.innerHTML = trades.slice(0, 10).map(t => `
                <tr>
                    <td style="color:#10b981; font-weight:bold;">$${t.price.toFixed(4)}</td>
                    <td>${t.amount.toLocaleString()} URC</td>
                    <td>$${(t.price * t.amount).toFixed(2)}</td>
                    <td style="color:#64748b;">${new Date(t.timestamp * 1000).toLocaleTimeString()}</td>
                </tr>
            `).join('');
        }

        async function updateDashboard() {
            try {
                // 1. Fetch info
                const res = await rpcFetch('/api/info');
                const data = await res.json();
                document.getElementById('val-height').innerText = '#' + data.height;
                document.getElementById('val-supply').innerText = (data.circulating_supply / 100000000).toFixed(2) + ' URC';
                document.getElementById('val-reward').innerText = (data.current_reward / 100000000) + ' URC';
                document.getElementById('val-mempool').innerText = data.mempool_size;

                // 2. Fetch Wallet
                const wRes = await rpcFetch('/api/wallet');
                const wData = await wRes.json();
                document.getElementById('wallet-address').innerText = wData.address;
                document.getElementById('miner-reward-address').value = wData.address;
                currentWalletBal = (wData.balance / 100000000);
                document.getElementById('wallet-balance').innerText = currentWalletBal.toFixed(8);

                // 3. Fetch Blocks
                const bRes = await rpcFetch('/api/blocks');
                const bData = await bRes.json();
                renderBlocks(bData);

                // 4. Fetch Miner Status
                const mRes = await rpcFetch('/api/miner/status');
                const mData = await mRes.json();
                updateMinerUI(mData);

                // 5. Update Exchange Desk
                updateExchangeData();
            } catch (e) {
                console.error("Dashboard update error:", e);
            }
        }

        function renderBlocks(blocks) {
            const tbody = document.getElementById('blocks-tbody');
            if (!blocks || blocks.length === 0) return;
            tbody.innerHTML = blocks.map(b => `
                <tr>
                    <td><span class="badge-block">#${b.height}</span></td>
                    <td class="hash-truncate" title="${b.hash}">${b.hash}</td>
                    <td>${b.tx_count} txs</td>
                    <td>${b.nonce}</td>
                    <td>${new Date(b.timestamp * 1000).toLocaleTimeString()}</td>
                </tr>
            `).join('');
        }

        function updateMinerUI(mData) {
            isMining = mData.mining;
            const btn = document.getElementById('btn-toggle-miner');
            const badge = document.getElementById('miner-state-badge');
            const dev = document.getElementById('miner-device-name');
            
            if (mData.device_name) {
                dev.innerText = mData.device_name;
            }

            if (isMining) {
                btn.className = 'btn btn-stop';
                btn.innerHTML = '<span>إيقاف التعدين (STOP MINING)</span>';
                badge.innerText = 'MINING IN PROGRESS';
                badge.style.color = '#10b981';
            } else {
                btn.className = 'btn btn-start';
                btn.innerHTML = '<span>بدء التعدين الآن (START MINING)</span>';
                badge.innerText = 'IDLE';
                badge.style.color = '#94a3b8';
            }

            const hashrate = mData.hashrate || 0;
            if (hashrate >= 1000000) {
                document.getElementById('miner-hashrate').innerText = (hashrate / 1000000).toFixed(2);
                document.getElementById('miner-unit').innerText = 'MH/s';
            } else {
                document.getElementById('miner-hashrate').innerText = (hashrate / 1000).toFixed(2);
                document.getElementById('miner-unit').innerText = 'kH/s';
            }

            document.getElementById('miner-blocks-found').innerText = mData.blocks_found || 0;
            document.getElementById('miner-total-hashes').innerText = (mData.total_hashes || 0).toLocaleString();
        }

        async function toggleMiner() {
            try {
                if (!isMining) {
                    const addr = document.getElementById('miner-reward-address').value;
                    const profile = document.getElementById('miner-profile-select').value;
                    await rpcFetch('/api/miner/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ reward_address: addr, profile: profile })
                    });
                } else {
                    await rpcFetch('/api/miner/stop', { method: 'POST' });
                }
                setTimeout(updateDashboard, 500);
            } catch (e) {
                alert("Miner toggle error: " + e);
            }
        }

        async function sendTransaction() {
            const recipient = document.getElementById('tx-recipient').value.trim();
            const amount = parseFloat(document.getElementById('tx-amount').value);
            if (!recipient || isNaN(amount) || amount <= 0) {
                alert("Please enter a valid recipient address and positive amount.");
                return;
            }
            try {
                const res = await rpcFetch('/api/send_tx', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        recipient: recipient,
                        amount_urc: amount
                    })
                });
                const data = await res.json();
                if (data.success) {
                    alert("Transaction broadcasted successfully! TXID: " + data.txid);
                    document.getElementById('tx-recipient').value = "";
                    document.getElementById('tx-amount').value = "";
                    updateDashboard();
                } else {
                    alert("Transaction failed: " + data.error);
                }
            } catch (e) {
                alert("Error sending transaction: " + e);
            }
        }

        function copyAddress() {
            const addr = document.getElementById('wallet-address').innerText;
            navigator.clipboard.writeText(addr);
            alert("Address copied to clipboard: " + addr);
        }

        // Poll every 3 seconds
        setInterval(updateDashboard, 3000);
        updateDashboard();
    </script>
</body>
</html>
"""
