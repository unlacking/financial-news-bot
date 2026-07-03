import os
from dotenv import load_dotenv
# Use the clean, official unified vnstock package
from vnstock import Market

load_dotenv()

def collect_prices(ticker_list=None):
    """
    Fetches the latest and previous session close prices for a list of stock tickers,
    calculates the percentage change, and returns the data as a dictionary.
    """
    if ticker_list is None:
        ticker_list = ["VCB", "FPT", "HPG", "VNM"]

    price_data = {}
    print(f"Starting automated stock price collection for: {ticker_list}...")

    # Initialize the core market data domain from vnstock
    market = Market()

    for ticker in ticker_list:
        try:
            # Fetch the historical Open-High-Low-Close-Volume (OHLCV) data
            # Setting count=5 ensures we get plenty of rows to capture the last 2 trading days safely
            df = market.equity(symbol=ticker).ohlcv(count=5)
            
            if df.empty or len(df) < 2:
                print(f"⚠ Warning: Not enough historical data found for ticker: {ticker}")
                continue
            
            # Ensure the records are ordered chronologically (oldest to newest)
            df = df.sort_index(ascending=True)

            # Extract the last two active trading sessions
            prev_session = df.iloc[-2]  # Second to last row (Yesterday/Previous close)
            latest_session = df.iloc[-1] # Last row (Today/Latest close)

            # Extract close values (mapping cleanly from the dataframe columns)
            latest_price = float(latest_session['close'])
            prev_price = float(prev_session['close'])

            # Calculate the percentage change metric
            if prev_price > 0:
                pct_change = ((latest_price - prev_price) / prev_price) * 100
            else:
                pct_change = 0.0

            pct_change = round(pct_change, 2)

            # Save explicitly to the required schema
            price_data[ticker] = {
                "price": latest_price,
                "percentage_change": pct_change
            }
            print(f"✓ Successfully fetched {ticker}: Price = {latest_price}, Change = {pct_change}%")

        except Exception as e:
            print(f"❌ Error: Failed to process ticker {ticker}: {e}")
            continue

    return price_data


if __name__ == "__main__":
    watchlist = ["VCB", "FPT", "HPG", "VNM"]
    results = collect_prices(watchlist)
    
    print("\n================ RETURNED DICTIONARY RESULTS ================")
    import pprint
    pprint.pprint(results)