# Memo numbers (generated)

Model metrics:

- cv_auc: 0.7196717119746548
- cv_pr_auc: 0.5182800883289049
- cv_log_loss: 0.5331354272750424
- cv_brier: 0.17688125447800904
- top_20pct_rto_capture: 0.3858407079646018
- n: 1984
- positive_rate: 0.2847782258064516
- seed: 42
- logistic_auc: 0.7203789281994672
- logistic_pr_auc: 0.5208250553521877
- logistic_log_loss: 0.5335581937518122
- logistic_brier: 0.1768947367434842
- boosting_auc: 0.7225567051457154
- boosting_pr_auc: 0.5234665865531168
- boosting_log_loss: 0.5307106647543683
- boosting_brier: 0.1759612455194352
- selected_boosting: 0.0
- logistic_c: 0.3
- time_auc: 0.746626471432673
- time_pr_auc: 0.5312288639786473
- time_log_loss: 0.49855339330868936
- time_brier: 0.163171722739612
- time_test_month: 2026-09
- time_test_n: 329

## Data findings

# Data findings

| Segment | Orders | RTO | RTO rate |
|---|---:|---:|---:|
| Overall | 1987 | 565 | 28.4% |
| state=Assam | 63 | 22 | 34.9% |
| state=Bihar | 145 | 78 | 53.8% |
| state=Delhi | 244 | 53 | 21.7% |
| state=Karnataka | 212 | 53 | 25.0% |
| state=Madhya Pradesh | 126 | 48 | 38.1% |
| state=Maharashtra | 385 | 70 | 18.2% |
| state=Rajasthan | 159 | 48 | 30.2% |
| state=Tamil Nadu | 155 | 33 | 21.3% |
| state=Telangana | 174 | 44 | 25.3% |
| state=Uttar Pradesh | 195 | 86 | 44.1% |
| state=West Bengal | 129 | 30 | 23.3% |
| city=Bareilly | 33 | 20 | 60.6% |
| city=Bengaluru | 212 | 53 | 25.0% |
| city=Chennai | 155 | 33 | 21.3% |
| city=Darbhanga | 61 | 36 | 59.0% |
| city=Delhi | 243 | 53 | 21.8% |
| city=Gorakhpur | 45 | 28 | 62.2% |
| city=Guwahati | 42 | 15 | 35.7% |
| city=Hyderabad | 173 | 44 | 25.4% |
| city=Indore | 73 | 22 | 30.1% |
| city=Jaipur | 119 | 31 | 26.1% |
| city=Kolkata | 129 | 30 | 23.3% |
| city=Kota | 39 | 16 | 41.0% |
| city=Lucknow | 117 | 38 | 32.5% |
| city=Mumbai | 214 | 39 | 18.2% |
| city=Nagaon | 21 | 7 | 33.3% |
| city=Patna | 80 | 38 | 47.5% |
| city=Pune | 171 | 31 | 18.1% |
| city=Sagar | 53 | 26 | 49.1% |
| first_time=0 | 492 | 113 | 23.0% |
| first_time=1 | 1495 | 452 | 30.2% |
| prior_rto=0 | 1845 | 501 | 27.2% |
| prior_rto=1 | 112 | 42 | 37.5% |
| prior_rto=2 | 30 | 22 | 73.3% |
| utm_source=direct | 253 | 58 | 22.9% |
| utm_source=google_ads | 244 | 69 | 28.3% |
| utm_source=influencer | 225 | 61 | 27.1% |
| utm_source=instagram_organic | 232 | 68 | 29.3% |
| utm_source=meta_ads | 765 | 239 | 31.2% |
| utm_source=whatsapp_broadcast | 268 | 70 | 26.1% |
| value_bin=(-0.001, 449.0] | 534 | 143 | 26.8% |
| value_bin=(1347.0, 2999.0] | 378 | 127 | 33.6% |
| value_bin=(449.0, 648.0] | 282 | 98 | 34.8% |
| value_bin=(648.0, 948.0] | 416 | 116 | 27.9% |
| value_bin=(948.0, 1347.0] | 377 | 81 | 21.5% |
| utm_source=direct, first_time=0 | 58 | 15 | 25.9% |
| utm_source=direct, first_time=1 | 195 | 43 | 22.1% |
| utm_source=google_ads, first_time=0 | 63 | 11 | 17.5% |
| utm_source=google_ads, first_time=1 | 181 | 58 | 32.0% |
| utm_source=influencer, first_time=0 | 56 | 13 | 23.2% |
| utm_source=influencer, first_time=1 | 169 | 48 | 28.4% |
| utm_source=instagram_organic, first_time=0 | 49 | 16 | 32.7% |
| utm_source=instagram_organic, first_time=1 | 183 | 52 | 28.4% |
| utm_source=meta_ads, first_time=0 | 202 | 48 | 23.8% |
| utm_source=meta_ads, first_time=1 | 563 | 191 | 33.9% |
| utm_source=whatsapp_broadcast, first_time=0 | 64 | 10 | 15.6% |
| utm_source=whatsapp_broadcast, first_time=1 | 204 | 60 | 29.4% |
| Junk address | 141 | 91 | 64.5% |
| Fake name | 28 | 21 | 75.0% |
| Pin/state mismatch | 3 | 1 | 33.3% |
| Invalid phone | 17 | 8 | 47.1% |

## Computed highlights

- state=Bihar: 78/145 RTO (53.8%).
- state=Uttar Pradesh: 86/195 RTO (44.1%).
- state=Maharashtra: 70/385 RTO (18.2%).
- Junk address: 91/141 RTO (64.5%).
- Fake name: 21/28 RTO (75.0%).
- Pin/state mismatch: 1/3 RTO (33.3%).
- Invalid phone: 8/17 RTO (47.1%).


## Policy comparison and sensitivity

# Backtest policy comparison

Scaled values use the sample monthly COD count and are estimates.

```text
        period                      policy  count  rto_avoided  genuine_lost    saved_inr      lost_inr  discount_cost_inr  message_cost_inr        net_inr  first_time_held  ship_count  confirm_count  nudge_count  hold_count  scaled_net_inr  scale_factor
    all_months                    ship_all   1984     0.000000      0.000000     0.000000      0.000000           0.000000               0.0       0.000000                0        1984              0            0           0        0.000000      4.989919
    all_months                ops_proposal   1984   260.000000    269.000000 44044.000000 219416.340000           0.000000               0.0 -175372.340000              393        1455              0            0         529  -875093.833669      4.989919
    all_months                   our_rules   1984    81.056400     14.821636 13730.954200  14001.656176         868.102886             946.0   -2084.804862                5        1016            526          432          10   -10403.008134      4.989919
    all_months rules_same_first_time_bands   1984   119.274443     25.695084 20205.090692  23394.152539         858.887498            1322.0   -5369.949344               11         634            908          426          16   -26795.614168      4.989919
held_out_month                    ship_all    329     0.000000      0.000000     0.000000      0.000000           0.000000               0.0       0.000000                0         329              0            0           0        0.000000      4.989919
held_out_month                ops_proposal    329    46.000000     49.000000  7792.400000  37781.160000           0.000000               0.0  -29988.760000               75         234              0            0          95  -149641.493952      4.989919
held_out_month                   our_rules    329    13.055562      2.138850  2211.612147   1869.736288         131.086993             148.0      62.788865                1         178             90           60           1      313.311375      4.989919
held_out_month rules_same_first_time_bands    329    20.018084      3.438885  3391.063366   2818.167406         126.850114             202.0     244.045845                3         122            146           58           3     1217.769086      4.989919
```

## Sensitivity

```text
 catch_share  genuine_drop_share  prepaid_conversion_multiplier      net_inr
         0.2                0.01                            0.5   219.917653
         0.2                0.01                            1.0   319.749983
         0.2                0.01                            1.5   419.582314
         0.2                0.03                            0.5  -899.653473
         0.2                0.03                            1.0  -799.821142
         0.2                0.03                            1.5  -699.988811
         0.2                0.08                            0.5 -3698.581285
         0.2                0.08                            1.0 -3598.748955
         0.2                0.08                            1.5 -3498.916624
         0.4                0.01                            0.5  1082.527660
         0.4                0.01                            1.0  1182.359991
         0.4                0.01                            1.5  1282.192321
         0.4                0.03                            0.5   -37.043465
         0.4                0.03                            1.0    62.788865
         0.4                0.03                            1.5   162.621196
         0.4                0.08                            0.5 -2835.971278
         0.4                0.08                            1.0 -2736.138947
         0.4                0.08                            1.5 -2636.306617
         0.6                0.01                            0.5  1945.137668
         0.6                0.01                            1.0  2044.969998
         0.6                0.01                            1.5  2144.802329
         0.6                0.03                            0.5   825.566542
         0.6                0.03                            1.0   925.398873
         0.6                0.03                            1.5  1025.231203
         0.6                0.08                            0.5 -1973.361270
         0.6                0.08                            1.0 -1873.528940
         0.6                0.08                            1.5 -1773.696609
```

Break-even confirmation catch share: 0.0.


## Discount calculations

# Discount calculations

aov,risk,saving,discount,customer_benefit_pct,prepaid_rto,company_net_per_conversion,expected_conversion

349,0.3,36.58000000000001,20.0,5.730659025787966,0.04285714285714285,16.580000000000013,0.11693409742120342

349,0.4,51.10000000000001,25.0,7.163323782234957,0.05714285714285714,26.10000000000001,0.1202865329512894

349,0.5,65.62,34.9,10.0,0.07142857142857142,30.720000000000006,0.125

349,0.7,94.66,34.9,10.0,0.09999999999999998,59.76,0.07500000000000001

649,0.3,30.58000000000001,20.0,3.0816640986132513,0.04285714285714285,10.580000000000009,0.07142912172573189

649,0.4,45.10000000000001,25.0,3.8520801232665636,0.05714285714285714,20.10000000000001,0.07278120184899844

649,0.5,59.620000000000005,30.0,4.622496147919876,0.07142857142857142,29.620000000000005,0.07028120184899846

649,0.7,88.66,45.0,6.933744221879815,0.09999999999999998,43.66,0.05853620955315871

1198,0.3,19.60000000000001,0.0,0.0,0.04285714285714285,19.60000000000001,0.034999999999999996

1198,0.4,34.12000000000001,20.0,1.669449081803005,0.05714285714285714,14.120000000000012,0.046694490818030045

1198,0.5,48.64000000000001,25.0,2.0868113522537564,0.07142857142857142,23.640000000000008,0.04239009460211464

1198,0.7,77.68,40.0,3.33889816360601,0.09999999999999998,37.68000000000001,0.03254173622704508



These generated figures are supporting analysis, not the founder memo.
