"""The ratio trap, in ten lines of data.

Two days of one campaign. Averaging the daily CPAs gives one answer;
dividing total spend by total conversions gives another. Only the second is
the campaign's actual cost per acquisition.

Run: python examples/ratio_trap.py
"""
days = [
    # (day, spend, conversions)
    ("Monday", 1000.0, 50),
    ("Tuesday", 1000.0, 10),
]

for day, spend, conv in days:
    print(f"{day:<8} spend ${spend:,.0f}  conversions {conv:>3}  CPA ${spend / conv:,.2f}")

avg_of_ratios = sum(s / c for _, s, c in days) / len(days)
ratio_of_sums = sum(s for _, s, _ in days) / sum(c for _, _, c in days)

print(f"\nAverage of daily CPAs:          ${avg_of_ratios:,.2f}   (wrong)")
print(f"Total spend / total conversions: ${ratio_of_sums:,.2f}   (right)")
