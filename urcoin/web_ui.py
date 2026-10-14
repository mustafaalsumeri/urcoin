"""
Ur Coin Web Interface:
- Responsive, futuristic Dark-Mode Dashboard & Explorer
- Embedded single-page application served directly by Node HTTP server
"""

HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ur Coin (URC) - Node & GPU Miner Dashboard</title>
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
            max-width: 1400px;
            margin: 0 auto;
        }

        /* Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 30px;
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

        /* Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 18px;
            margin-bottom: 30px;
        }

        .metric-card {
            background: var(--surface);
            border: 1px solid var(--border);
            padding: 20px;
            border-radius: 16px;
            position: relative;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }

        .metric-card:hover {
            transform: translateY(-2px);
            border-color: rgba(245, 158, 11, 0.4);
        }

        .metric-label {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .metric-value {
            font-size: 26px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-main);
        }

        .metric-sub {
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 6px;
        }

        /* Main Split */
        .main-grid {
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 24px;
            margin-bottom: 30px;
        }

        @media (max-width: 1024px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
        }

        .panel {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 24px;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .panel-title {
            font-size: 18px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* Mining Section */
        .miner-box {
            background: #0d131f;
            border: 1px solid #1e293b;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .gpu-spec {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 16px;
            border-bottom: 1px solid #1e293b;
            margin-bottom: 16px;
        }

        .gpu-name {
            font-weight: 700;
            color: var(--secondary);
            font-size: 15px;
        }

        .gpu-mem {
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            color: var(--text-muted);
        }

        .hashrate-display {
            text-align: center;
            padding: 20px 0;
        }

        .hashrate-number {
            font-size: 44px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            color: var(--primary);
            text-shadow: 0 0 20px var(--primary-glow);
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
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            margin-bottom: 20px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
        }

        .btn {
            cursor: pointer;
            border: none;
            outline: none;
            padding: 12px 24px;
            border-radius: 12px;
            font-weight: 700;
            font-size: 15px;
            transition: all 0.2s;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }

        .btn-start {
            background: linear-gradient(135deg, #10b981, #059669);
            color: #fff;
            box-shadow: 0 0 20px rgba(16, 185, 129, 0.3);
        }

        .btn-start:hover {
            opacity: 0.95;
            transform: translateY(-1px);
        }

        .btn-stop {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: #fff;
            box-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
        }

        /* Wallet Section */
        .wallet-card {
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.08), rgba(6, 182, 212, 0.08));
            border: 1px solid rgba(245, 158, 11, 0.3);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .wallet-address {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            word-break: break-all;
            background: rgba(0, 0, 0, 0.4);
            padding: 10px;
            border-radius: 8px;
            margin: 10px 0;
            color: var(--secondary);
            border: 1px dashed var(--border);
            cursor: pointer;
        }

        .wallet-balance {
            font-size: 32px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-main);
        }

        .input-group {
            margin-bottom: 14px;
        }

        .input-group label {
            display: block;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-muted);
            margin-bottom: 6px;
        }

        .input-control {
            width: 100%;
            background: #090d16;
            border: 1px solid var(--border);
            padding: 12px 14px;
            border-radius: 10px;
            color: #fff;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
        }

        .input-control:focus {
            border-color: var(--secondary);
            outline: none;
        }

        /* Blocks Table */
        .table-responsive {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }

        th {
            padding: 12px;
            color: var(--text-muted);
            font-weight: 600;
            border-bottom: 1px solid var(--border);
            text-transform: uppercase;
            font-size: 11px;
        }

        td {
            padding: 14px 12px;
            border-bottom: 1px solid #1a2234;
            font-family: 'JetBrains Mono', monospace;
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        .hash-truncate {
            max-width: 140px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--secondary);
        }

        .badge-block {
            background: rgba(245, 158, 11, 0.15);
            color: var(--primary);
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 700;
        }
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
                    <p>Next-Gen GPU Minable Memory-Hard Cryptocurrency (UrHash PoW)</p>
                </div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>NODE ONLINE & READY</span>
            </div>
        </header>

        <!-- Metrics Grid -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Block Height</div>
                <div class="metric-value" id="val-height">#0</div>
                <div class="metric-sub">Target Time: 30s</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Circulating Supply</div>
                <div class="metric-value" id="val-supply">50.00 URC</div>
                <div class="metric-sub">Max: 21,000,000 URC</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Block Reward</div>
                <div class="metric-value" id="val-reward">50 URC</div>
                <div class="metric-sub">Halving every 210,000</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Mempool Transactions</div>
                <div class="metric-value" id="val-mempool">0</div>
                <div class="metric-sub">Pending verification</div>
            </div>
        </div>

        <!-- Main Split: Miner & Wallet -->
        <div class="main-grid">
            <!-- Left: GPU Miner -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">
                        <span>⚡ GPU Mining Control Center</span>
                    </div>
                    <span id="miner-state-badge" style="font-size: 12px; font-weight: 700; color: #94a3b8;">IDLE</span>
                </div>

                <div class="miner-box">
                    <div class="gpu-spec">
                        <div>
                            <div class="gpu-name" id="miner-device-name">NVIDIA GeForce RTX 3050 6GB</div>
                            <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Algorithm: UrHash-v1 (Memory-Hard Proof-of-Work)</div>
                        </div>
                        <div class="gpu-mem">1.0 GB DAG in VRAM</div>
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
                        <label>Miner Reward Address (Coinbase)</label>
                        <input type="text" class="input-control" id="miner-reward-address" readonly />
                    </div>

                    <button class="btn btn-start" id="btn-toggle-miner" onclick="toggleMiner()">
                        <span>START GPU MINING</span>
                    </button>
                </div>
            </div>

            <!-- Right: Wallet -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">
                        <span>💼 Built-in Wallet</span>
                    </div>
                </div>

                <div class="wallet-card">
                    <div class="metric-label">Your Wallet Balance</div>
                    <div class="wallet-balance"><span id="wallet-balance">0.00000000</span> <span style="font-size: 18px; color: var(--primary);">URC</span></div>
                    
                    <div class="metric-label" style="margin-top: 14px;">Your Receiving Address (Click to copy)</div>
                    <div class="wallet-address" id="wallet-address" onclick="copyAddress()">Loading...</div>
                </div>

                <!-- Send Transfer Form -->
                <div>
                    <h3 style="font-size: 15px; margin-bottom: 12px;">Transfer Ur Coin (URC)</h3>
                    <div class="input-group">
                        <label>Recipient Address (urc1...)</label>
                        <input type="text" class="input-control" id="tx-recipient" placeholder="urc1..." />
                    </div>
                    <div class="input-group">
                        <label>Amount (URC)</label>
                        <input type="number" step="0.00000001" class="input-control" id="tx-amount" placeholder="10.0" />
                    </div>
                    <button class="btn btn-start" style="background: linear-gradient(135deg, #06b6d4, #0284c7);" onclick="sendTransaction()">
                        SEND TRANSACTION
                    </button>
                </div>
            </div>
        </div>

        <!-- Blockchain Explorer -->
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>⛓️ Live Blockchain Explorer</span>
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

    <script>
        let isMining = false;
        let minerPollInterval = null;

        async function updateDashboard() {
            try {
                // 1. Fetch info
                const res = await fetch('/api/info');
                const data = await res.json();
                document.getElementById('val-height').innerText = '#' + data.height;
                document.getElementById('val-supply').innerText = (data.circulating_supply / 100000000).toFixed(2) + ' URC';
                document.getElementById('val-reward').innerText = (data.current_reward / 100000000) + ' URC';
                document.getElementById('val-mempool').innerText = data.mempool_size;

                // 2. Fetch Wallet
                const wRes = await fetch('/api/wallet');
                const wData = await wRes.json();
                document.getElementById('wallet-address').innerText = wData.address;
                document.getElementById('miner-reward-address').value = wData.address;
                document.getElementById('wallet-balance').innerText = (wData.balance / 100000000).toFixed(8);

                // 3. Fetch Blocks
                const bRes = await fetch('/api/blocks');
                const bData = await bRes.json();
                renderBlocks(bData);

                // 4. Fetch Miner Status
                const mRes = await fetch('/api/miner/status');
                const mData = await mRes.json();
                updateMinerUI(mData);
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
                btn.innerHTML = '<span>STOP GPU MINING</span>';
                badge.innerText = 'MINING IN PROGRESS';
                badge.style.color = '#10b981';
            } else {
                btn.className = 'btn btn-start';
                btn.innerHTML = '<span>START GPU MINING</span>';
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
                    await fetch('/api/miner/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ reward_address: addr })
                    });
                } else {
                    await fetch('/api/miner/stop', { method: 'POST' });
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
                const res = await fetch('/api/send_tx', {
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

        // Poll every 2 seconds
        setInterval(updateDashboard, 2000);
        updateDashboard();
    </script>
</body>
</html>
"""
