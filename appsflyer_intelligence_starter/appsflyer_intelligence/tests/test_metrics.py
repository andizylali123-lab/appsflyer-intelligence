def test_core_formulas():
    spend, installs, clicks, impressions, conversions, revenue = 100, 20, 50, 1000, 5, 250
    assert spend / installs == 5       # CPI
    assert spend / clicks == 2         # CPC
    assert spend / conversions == 20   # CPA
    assert clicks / impressions == .05 # CTR
    assert revenue / spend == 2.5      # ROAS
