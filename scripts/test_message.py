"""Test script to debug Telegram message formatting."""

# Reproduce the exact message that's failing
stocks_valid = ["BIDU", "BMNR", "DUOL", "NVDA", "PGY", "PLTR", "RGTI"]
stocks_invalid = ["ADYEN", "CSG", "VTY"]
etf_valid = ["INQQ"]
etf_invalid = ["SGLD", "QDV5", "VUTY"]

validation_msg = "📊 Portfolio Validation Summary\n\n"

if stocks_valid or etf_valid:
    validation_msg += "✅ **Valid Tickers:**\n"
    if stocks_valid:
        validation_msg += f"  Stocks ({len(stocks_valid)}): {', '.join(stocks_valid)}\n"
    if etf_valid:
        validation_msg += f"  ETFs ({len(etf_valid)}): {', '.join(etf_valid)}\n"

if stocks_invalid or etf_invalid:
    validation_msg += "\n❌ **Invalid Tickers:**\n"
    if stocks_invalid:
        validation_msg += f"  Stocks ({len(stocks_invalid)}): {', '.join(stocks_invalid)}\n"
    if etf_invalid:
        validation_msg += f"  ETFs ({len(etf_invalid)}): {', '.join(etf_invalid)}\n"
    validation_msg += "\n💡 **Quick Actions:**\n"
    validation_msg += "  • /remove_all - Remove all invalid tickers\n"
    validation_msg += "  • /remove TICKER - Remove specific ticker\n"

if not stocks_valid and not etf_valid and not stocks_invalid and not etf_invalid:
    validation_msg += "📭 Portfolio is empty.\n\n"
else:
    validation_msg += (
        f"\n🔍 Monitoring {len(stocks_valid) + len(etf_valid)} valid tickers.\n\n"
    )

validation_msg += (
    "📋 **Available Commands:**\n"
    "/list - View portfolio\n"
    "/addstock TICKER - Add stock\n"
    "/addetf TICKER - Add ETF\n"
    "/remove TICKER - Remove ticker\n"
    "/status - Get news now\n"
    "/help - Show full help"
)

print("Message content:")
print(validation_msg)
print("\n" + "=" * 80)
print(f"Message length: {len(validation_msg)}")
print(f"Byte offset 252: {repr(validation_msg[252:260])}")
print("\n" + "=" * 80)

# Count ** markers
bold_markers = validation_msg.count("**")
print(f"Number of ** markers: {bold_markers}")
if bold_markers % 2 != 0:
    print("⚠️  WARNING: Odd number of ** markers - Markdown is BROKEN!")
else:
    print("✓ Even number of ** markers")
