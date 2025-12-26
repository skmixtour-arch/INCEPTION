# Liquidity Trading Knowledge Base

## Core Concept: What is Liquidity?
Liquidity = How easily an asset can be bought/sold without moving the price.
- **High Liquidity** → Many buyers/sellers → Stable prices → Low slippage
- **Low Liquidity** → Few participants → Volatile prices → High slippage

---

## 1. Order Book Liquidity

### Order Book Depth
The quantity of buy (bid) and sell (ask) orders at various price levels.

| Term | Definition |
|------|------------|
| **Bids** | Buy orders (below current price) |
| **Asks** | Sell orders (above current price) |
| **Spread** | Gap between best bid and best ask |
| **Depth** | Total volume at each price level |

### What Deep vs Shallow Order Books Tell Us:
- **Deep Order Book** → High liquidity, hard to move price, stable
- **Shallow Order Book** → Low liquidity, easy to manipulate, volatile

### Trading Application:
- Use Order Book Depth Delta (from CoinAnk) to see where liquidity walls exist
- Large bid walls = potential support
- Large ask walls = potential resistance
- Walls disappearing = possible breakout incoming

---

## 2. Liquidity Pools (ICT Concept)

### Buy-Side Liquidity (BSL)
- **Location**: Above resistance levels & swing highs
- **What's there**: Stop-losses from shorts + Buy-stop orders from breakout traders
- **Smart Money Target**: Drive price UP to trigger these orders, then SELL into them

### Sell-Side Liquidity (SSL)
- **Location**: Below support levels & swing lows
- **What's there**: Stop-losses from longs + Sell-stop orders from breakdown traders
- **Smart Money Target**: Drive price DOWN to trigger these orders, then BUY from them

### Where Liquidity Pools Form:
1. Previous swing highs/lows
2. Equal highs/lows (double tops/bottoms)
3. Round numbers ($100,000, $90,000)
4. Daily/Weekly/Monthly highs and lows
5. Previous session ranges (Asian/London highs/lows)

---

## 3. Liquidity Grabs & Sweeps

### Definition
A rapid price spike through a liquidity zone, triggering stop orders, then reversing.

### Characteristics:
- Sharp, aggressive move
- Volume spike
- Long wicks on candles
- Quick reversal after sweep

### Types:
| Type | Action | Result |
|------|--------|--------|
| **Bullish Sweep** | Price drops below SSL, triggers sell stops | Smart money buys → Price reverses UP |
| **Bearish Sweep** | Price spikes above BSL, triggers buy stops | Smart money sells → Price reverses DOWN |

### Trading Application:
- Wait for sweep BEFORE entering
- Enter AFTER the reversal candle forms
- Use the sweep high/low as your stop loss

---

## 4. Stop Hunts

### Definition
Deliberate price manipulation to trigger clustered stop-loss orders.

### How to Identify:
1. Price moves sharply to "obvious" stop levels
2. Creates long wicks on candles
3. Quickly reverses direction
4. Often happens during low-volume periods (Asia session)

### Common Stop Hunt Levels:
- Just below support
- Just above resistance
- Round numbers (psychological levels)
- Previous day/week highs and lows

### Integration with Brinks Box:
The Brinks Box session (14:00-15:00) often sets up liquidity traps:
- If Brinks High > Asian High → Potential SHORT (liquidity swept above)
- If Brinks Low < Asian Low → Potential LONG (liquidity swept below)

---

## 5. Smart Money Concepts

### Who is Smart Money?
- Banks, hedge funds, market makers
- They need LIQUIDITY to fill large orders
- They CREATE moves to TARGET retail stop losses

### Smart Money Cycle:
1. **Accumulation**: Build position slowly in a range
2. **Manipulation**: Fake breakout to grab liquidity (stop hunt)
3. **Distribution**: Move price to target and exit

### How to Trade WITH Smart Money:
1. Identify liquidity pools (where stops are clustered)
2. Wait for sweep/grab of that liquidity
3. Enter on reversal confirmation
4. Target the opposite liquidity pool

---

## 6. Data Sources for Liquidity Analysis

| Data Type | Source | What It Shows |
|-----------|--------|---------------|
| **Order Book Depth** | MEXC API / CoinAnk | Bid/Ask walls, immediate liquidity |
| **Order Depth Delta** | CoinAnk (Plan3) | Aggregated depth across exchanges |
| **Liquidation Heatmap** | CoinAnk (Plan4) | Where leverage longs/shorts will be liquidated |
| **Long/Short Ratio** | CoinAnk (Plan1) | Sentiment, where stops might cluster |
| **Funding Rate** | CoinAnk (Plan1) | Overcrowded positions |
| **Large Orders** | CoinAnk (Plan3) | Whale activity |

---

## 7. Integration with Our Strategies

### Brinks Box + Liquidity:
- Mark Asian session high/low as liquidity zones
- If Brinks sweeps Asian high AND re-enters box → SHORT (liquidity grabbed)
- If Brinks sweeps Asian low AND re-enters box → LONG (liquidity grabbed)

### Vector Candles + Liquidity:
- High-volume candles often indicate liquidity being absorbed
- Green vectors near liquidity pools = smart money buying
- Red vectors near liquidity pools = smart money selling

### Entry Confirmation Checklist:
- [ ] Liquidity pool identified (previous high/low)
- [ ] Sweep/grab of that pool occurred
- [ ] Reversal candle formed (vector candle ideal)
- [ ] Entry in direction of the reversal
- [ ] Stop loss behind the sweep wick
- [ ] Target: opposite liquidity pool

---

## 8. Key Rules

1. **"Liquidity is the fuel"** - Price moves TO liquidity, not away from it
2. **"Hunt the hunters"** - Trade the reversal AFTER the stop hunt, not during
3. **"Obvious levels get hit"** - If you can see a support/resistance, so can everyone else
4. **"Time + Liquidity"** - Best setups occur when time-based sessions align with liquidity targets
