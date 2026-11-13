v3 (leverage / kill-switch decomposition, kill sweep, extended stop curves): see section "v3" at the end of this file.

The symmetric both-side stop selected by IS is 20.0%; IS/OOS Calmar_i is 1.821/0.549 versus baseline 0.841/1.314.
At 0.5%, IS/OOS CAGR is -81.24%/-70.06%, intraday MDD 98.38%/94.06%, and Calmar_i -0.825/-0.745.
At 1.0%, IS/OOS CAGR is -73.08%/-50.31%, intraday MDD 96.32%/86.59%, and Calmar_i -0.757/-0.581.
At 3.0%, IS/OOS CAGR is -55.16%/-25.29%, intraday MDD 92.60%/94.74%, and Calmar_i -0.592/-0.267.
At 5.0%, IS/OOS CAGR is -33.60%/-16.18%, intraday MDD 86.03%/90.69%, and Calmar_i -0.390/-0.178.
At 10.0%, IS/OOS CAGR is 16.13%/60.47%, intraday MDD 73.48%/74.90%, and Calmar_i 0.219/0.807.
At 15.0% (interpolated between tested 14% and 16%), IS/OOS CAGR is 69.42%/60.01%, intraday MDD 70.21%/73.62%, and Calmar_i 1.018/0.826.
At 30.0%, IS/OOS CAGR is 27.34%/2.02%, intraday MDD 73.94%/71.60%, and Calmar_i 0.370/0.028.
At 100.0%, IS/OOS CAGR is 55.05%/81.34%, intraday MDD 65.48%/79.64%, and Calmar_i 0.841/1.021.
The grid therefore does not show an OOS stop benefit at the IS-selected level; OOS remains held-out diagnosis.

## 4x stop curve

| s | margin PnL equiv | IS CAGR / IMDD / Calmar_i | OOS CAGR / IMDD / Calmar_i | full CAGR / IMDD / Calmar_i | stops/year L/S | 7d whipsaw | label |
|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | — | 55.05% / 65.48% / 0.841 | 104.62% / 79.64% / 1.314 | 79.15% / 79.64% / 0.994 | 0.0/0.0 | n/a | baseline |
| 0.0% | 0.0% | -82.01% / 98.64% / -0.831 | -78.50% / 97.00% / -0.809 | -80.46% / 99.96% / -0.805 | 793.2/794.8 | 74.5% | noise |
| 0.5% | 2.0% | -81.24% / 98.38% / -0.825 | -70.06% / 94.06% / -0.745 | -76.82% / 99.90% / -0.769 | 706.5/689.2 | 72.6% | noise |
| 1.0% | 4.0% | -73.08% / 96.32% / -0.757 | -50.31% / 86.59% / -0.581 | -64.55% / 99.37% / -0.649 | 640.0/596.7 | 70.2% | noise |
| 1.5% | 6.0% | -64.23% / 93.23% / -0.688 | -48.59% / 93.95% / -0.517 | -57.59% / 99.23% / -0.580 | 558.9/529.7 | 67.6% | noise |
| 2.0% | 8.0% | -75.70% / 97.62% / -0.775 | -12.00% / 87.91% / -0.137 | -55.06% / 98.61% / -0.558 | 506.1/460.3 | 65.2% | noise |
| 3.0% | 12.0% | -55.16% / 92.60% / -0.592 | -25.29% / 94.74% / -0.267 | -42.77% / 97.35% / -0.438 | 420.1/383.6 | 60.4% | noise |
| 4.0% | 16.0% | -25.75% / 81.70% / -0.315 | -1.62% / 92.39% / -0.017 | -14.25% / 92.39% / -0.154 | 348.6/299.0 | 55.4% | noise |
| 5.0% | 20.0% | -33.60% / 86.03% / -0.390 | -16.18% / 90.69% / -0.178 | -24.96% / 92.24% / -0.270 | 294.0/248.4 | 51.3% | noise |
| 6.0% | 24.0% | 18.56% / 70.51% / 0.264 | -4.41% / 91.64% / -0.048 | 7.69% / 91.64% / 0.084 | 238.5/208.5 | 47.0% | noise |
| 7.0% | 28.0% | -14.07% / 85.69% / -0.164 | 77.74% / 70.66% / 1.100 | 22.91% / 85.69% / 0.267 | 206.1/177.7 | 43.7% | noise |
| 8.0% | 32.0% | -10.46% / 80.46% / -0.097 | 49.07% / 81.94% / 0.599 | 15.00% / 86.73% / 0.181 | 171.6/153.8 | 39.3% | noise |
| 9.0% | 36.0% | -22.43% / 86.09% / -0.260 | 60.39% / 79.45% / 0.760 | 9.64% / 87.91% / 0.110 | 142.1/133.8 | 37.4% | noise |
| 10.0% | 40.0% | 16.13% / 73.48% / 0.219 | 60.47% / 74.90% / 0.807 | 37.00% / 74.90% / 0.494 | 127.1/106.7 | 32.9% | noise |
| 12.0% | 48.0% | 14.95% / 76.43% / 0.210 | 39.77% / 76.99% / 0.517 | 27.37% / 79.11% / 0.351 | 91.1/87.2 | 30.3% | noise |
| 14.0% | 56.0% | 68.02% / 71.50% / 0.956 | 52.10% / 78.73% / 0.662 | 61.94% / 78.73% / 0.787 | 67.8/66.7 | 25.5% | noise |
| 16.0% | 64.0% | 70.82% / 68.92% / 1.081 | 67.91% / 68.52% / 0.991 | 71.15% / 72.83% / 0.984 | 51.8/50.5 | 21.0% | noise |
| 18.0% | 72.0% | 68.70% / 66.36% / 1.035 | 43.35% / 69.50% / 0.624 | 57.82% / 70.20% / 0.825 | 35.6/37.6 | 16.6% | noise |
| 20.0% | 80.0% | 108.89% / 61.66% / 1.821 | 36.46% / 66.43% / 0.549 | 72.46% / 68.69% / 1.060 | 28.3/29.6 | 15.3% | noise |
| 22.5% | 90.0% | 109.95% / 62.37% / 1.763 | 14.38% / 76.91% / 0.187 | 59.01% / 76.91% / 0.767 | 19.2/22.8 | 9.8% | noise |
| 25.0% † | 100.0% | 79.83% / 57.20% / 1.396 | 42.74% / 72.65% / 0.588 | 63.06% / 72.65% / 0.868 | 14.0/16.5 | 8.2% | noise |
| 27.5% † | 110.0% | 43.96% / 61.51% / 0.717 | 48.81% / 76.23% / 0.640 | 48.01% / 76.23% / 0.630 | 9.7/15.1 | 6.5% | noise |
| 30.0% † | 120.0% | 27.34% / 73.94% / 0.370 | 2.02% / 71.60% / 0.028 | 15.96% / 73.94% / 0.216 | 4.8/11.7 | 5.1% | noise |
| 35.0% † | 140.0% | 72.92% / 76.89% / 0.954 | 3.57% / 83.12% / 0.043 | 36.80% / 83.12% / 0.443 | 2.8/5.3 | 2.6% | noise |
| 40.0% † | 160.0% | 104.86% / 64.10% / 1.648 | 38.33% / 74.88% / 0.512 | 71.78% / 74.88% / 0.959 | 1.4/3.4 | 8.8% | noise |
| 50.0% † | 200.0% | 46.13% / 66.21% / 0.697 | 55.60% / 79.64% / 0.698 | 52.43% / 79.64% / 0.658 | 0.8/1.7 | 8.1% | noise |
| 60.0% † | 240.0% | 96.56% / 63.63% / 1.536 | 4.66% / 83.63% / 0.056 | 46.61% / 83.63% / 0.557 | 0.6/1.1 | 12.0% | noise |
| 75.0% † | 300.0% | 78.48% / 63.13% / 1.254 | 88.63% / 79.64% / 1.113 | 85.27% / 79.64% / 1.071 | 0.0/0.7 | 0.0% | noise |
| 100.0% † | 400.0% | 55.05% / 65.48% / 0.841 | 81.34% / 79.64% / 1.021 | 69.13% / 79.64% / 0.868 | 0.0/0.2 | 0.0% | noise |

† At/beyond isolated liquidation equivalent. Margin PnL equivalent = s × leverage; equivalences are 25% at 4x, 33.3% at 3x, 50% at 2x. At 100%, a long stop is unreachable unless price reaches zero; short stop triggers at 2× entry. Intraday cross-margin liquidation is checked before SL realization; the kill switch is later.

## 3x and 2x curve

| leverage | s | IS CAGR / IMDD / Calmar_i | OOS CAGR / IMDD / Calmar_i | full CAGR / IMDD / Calmar_i | stops/year | label |
|---:|---:|---:|---:|---:|---:|---|
| 3x | baseline | 77.26% / 56.62% / 1.365 | 95.13% / 63.09% / 1.562 | 86.61% / 63.96% / 1.375 | 0.0 | baseline |
| 3x | 0.0% | -73.48% / 96.39% / -0.762 | -70.53% / 93.84% / -0.752 | -72.13% / 99.78% / -0.723 | 1635.9 | noise |
| 3x | 0.5% | -68.97% / 94.86% / -0.727 | -55.09% / 85.22% / -0.646 | -63.06% / 99.19% / -0.636 | 1431.5 | noise |
| 3x | 1.0% | -65.96% / 93.80% / -0.703 | -44.22% / 86.24% / -0.513 | -57.14% / 98.97% / -0.577 | 1277.7 | noise |
| 3x | 1.5% | -69.25% / 95.31% / -0.726 | -25.51% / 86.47% / -0.295 | -53.00% / 97.83% / -0.542 | 1125.2 | noise |
| 3x | 2.0% | -59.79% / 91.39% / -0.654 | -22.84% / 86.38% / -0.264 | -45.19% / 95.73% / -0.472 | 999.7 | noise |
| 3x | 3.0% | -50.24% / 87.95% / -0.566 | -11.98% / 88.61% / -0.135 | -34.53% / 92.92% / -0.370 | 825.3 | noise |
| 3x | 4.0% | -33.35% / 82.11% / -0.406 | 34.23% / 68.10% / 0.503 | -6.25% / 82.11% / -0.076 | 690.6 | noise |
| 3x | 5.0% | -0.67% / 65.24% / -0.011 | 23.85% / 74.96% / 0.318 | 11.33% / 74.96% / 0.151 | 558.6 | noise |
| 3x | 6.0% | -14.95% / 72.90% / -0.198 | 35.30% / 68.77% / 0.513 | 7.03% / 73.86% / 0.101 | 474.7 | noise |
| 3x | 7.0% | -4.75% / 68.73% / -0.056 | 84.09% / 63.10% / 1.430 | 31.25% / 69.92% / 0.469 | 398.6 | noise |
| 3x | 8.0% | 9.22% / 63.02% / 0.146 | 84.43% / 62.56% / 1.350 | 41.43% / 63.02% / 0.657 | 339.6 | noise |
| 3x | 9.0% | 2.70% / 65.23% / 0.047 | 67.83% / 61.21% / 1.143 | 30.29% / 67.76% / 0.441 | 284.7 | noise |
| 3x | 10.0% | 2.66% / 72.15% / 0.097 | 97.73% / 55.19% / 1.792 | 40.36% / 72.49% / 0.611 | 247.5 | noise |
| 3x | 12.0% | 24.49% / 69.43% / 0.378 | 43.61% / 68.20% / 0.639 | 34.14% / 72.13% / 0.479 | 180.4 | noise |
| 3x | 14.0% | 51.01% / 61.57% / 0.828 | 77.27% / 64.47% / 1.199 | 64.33% / 64.47% / 0.998 | 137.0 | noise |
| 3x | 16.0% | 40.53% / 67.72% / 0.605 | 64.35% / 63.36% / 1.062 | 51.96% / 67.72% / 0.779 | 104.1 | noise |
| 3x | 18.0% | 42.20% / 56.89% / 0.766 | 125.89% / 52.90% / 2.381 | 78.77% / 58.71% / 1.380 | 81.5 | noise |
| 3x | 20.0% | 74.76% / 58.01% / 1.307 | 62.77% / 59.15% / 1.061 | 70.31% / 60.58% / 1.164 | 61.8 | noise |
| 3x | 22.5% | 46.44% / 54.02% / 0.894 | 91.31% / 63.96% / 1.452 | 67.69% / 67.55% / 1.002 | 46.2 | noise |
| 3x | 25.0% | 66.42% / 58.02% / 1.145 | 96.21% / 58.15% / 1.655 | 81.48% / 58.33% / 1.397 | 30.9 | noise |
| 3x | 27.5% | 69.53% / 58.83% / 1.181 | 77.89% / 56.65% / 1.375 | 74.76% / 58.83% / 1.271 | 23.7 | noise |
| 3x | 30.0% | 64.21% / 52.40% / 1.227 | 96.72% / 57.19% / 1.691 | 80.45% / 57.38% / 1.402 | 16.9 | noise |
| 3x | 35.0% † | 66.56% / 52.17% / 1.274 | 86.99% / 60.80% / 1.431 | 77.50% / 60.80% / 1.275 | 9.0 | noise |
| 3x | 40.0% † | 72.79% / 50.21% / 1.468 | 119.13% / 50.71% / 2.367 | 95.17% / 54.52% / 1.744 | 5.4 | noise |
| 3x | 50.0% † | 76.50% / 57.76% / 1.325 | 92.48% / 56.57% / 1.635 | 85.41% / 57.94% / 1.474 | 2.7 | noise |
| 3x | 60.0% † | 62.56% / 63.99% / 0.992 | 115.80% / 54.30% / 2.133 | 87.46% / 63.99% / 1.379 | 1.6 | noise |
| 3x | 75.0% † | 69.26% / 58.14% / 1.191 | 133.36% / 47.34% / 2.817 | 98.92% / 58.14% / 1.702 | 0.6 | noise |
| 3x | 100.0% † | 58.22% / 59.64% / 0.981 | 143.04% / 53.52% / 2.676 | 95.54% / 59.64% / 1.605 | 0.3 | noise |
| 2x | baseline | 62.82% / 33.95% / 1.867 | 78.70% / 43.15% / 1.836 | 71.06% / 43.15% / 1.653 | 0.0 | baseline |
| 2x | 0.0% | -59.75% / 89.74% / -0.666 | -58.68% / 86.67% / -0.677 | -59.27% / 98.63% / -0.601 | 1697.1 | noise |
| 2x | 0.5% | -59.97% / 90.11% / -0.666 | -42.54% / 74.21% / -0.573 | -52.46% / 97.22% / -0.540 | 1492.7 | noise |
| 2x | 1.0% | -56.42% / 88.32% / -0.639 | -18.99% / 70.82% / -0.262 | -41.37% / 93.35% / -0.443 | 1317.5 | noise |
| 2x | 1.5% | -57.24% / 88.81% / -0.642 | -17.34% / 75.30% / -0.230 | -41.73% / 94.90% / -0.439 | 1178.8 | noise |
| 2x | 2.0% | -48.72% / 84.14% / -0.578 | 0.76% / 62.43% / 0.020 | -29.21% / 86.03% / -0.337 | 1052.1 | noise |
| 2x | 3.0% | -17.76% / 56.88% / -0.312 | 15.88% / 60.53% / 0.264 | -2.75% / 60.82% / -0.045 | 858.0 | noise |
| 2x | 4.0% | -8.24% / 54.52% / -0.147 | 21.77% / 55.77% / 0.390 | 5.59% / 56.72% / 0.100 | 699.1 | noise |
| 2x | 5.0% | 3.36% / 49.99% / 0.067 | 54.20% / 44.57% / 1.216 | 25.83% / 49.99% / 0.520 | 571.1 | noise |
| 2x | 6.0% | 14.60% / 45.40% / 0.322 | 49.05% / 45.70% / 1.089 | 30.61% / 46.75% / 0.660 | 481.2 | noise |
| 2x | 7.0% | 1.11% / 53.54% / 0.067 | 49.39% / 46.27% / 1.068 | 21.84% / 55.26% / 0.423 | 409.7 | noise |
| 2x | 8.0% | 8.94% / 48.52% / 0.191 | 58.85% / 48.24% / 1.220 | 31.18% / 50.86% / 0.615 | 346.5 | noise |
| 2x | 9.0% | 10.29% / 47.31% / 0.228 | 59.59% / 49.65% / 1.211 | 32.25% / 52.25% / 0.616 | 293.4 | noise |
| 2x | 10.0% | 13.35% / 53.24% / 0.256 | 80.25% / 36.50% / 2.199 | 42.19% / 53.24% / 0.798 | 254.4 | noise |
| 2x | 12.0% | 27.14% / 48.35% / 0.563 | 46.33% / 56.91% / 0.814 | 36.75% / 56.91% / 0.646 | 184.9 | noise |
| 2x | 14.0% | 33.08% / 45.15% / 0.744 | 64.44% / 45.28% / 1.477 | 47.97% / 47.69% / 1.021 | 138.7 | noise |
| 2x | 16.0% | 41.96% / 39.68% / 1.105 | 59.28% / 47.56% / 1.267 | 50.87% / 50.33% / 1.014 | 106.8 | noise |
| 2x | 18.0% | 45.75% / 38.89% / 1.209 | 61.74% / 46.79% / 1.363 | 54.10% / 47.82% / 1.164 | 82.2 | noise |
| 2x | 20.0% | 41.41% / 36.45% / 1.163 | 58.19% / 47.31% / 1.233 | 50.03% / 47.31% / 1.056 | 64.0 | noise |
| 2x | 22.5% | 46.77% / 38.05% / 1.257 | 62.59% / 46.12% / 1.402 | 55.04% / 46.12% / 1.228 | 47.0 | noise |
| 2x | 25.0% | 43.10% / 36.56% / 1.206 | 65.37% / 48.06% / 1.384 | 54.25% / 48.06% / 1.149 | 34.5 | noise |
| 2x | 27.5% | 53.33% / 37.85% / 1.440 | 52.28% / 50.06% / 1.066 | 53.72% / 50.06% / 1.090 | 24.6 | noise |
| 2x | 30.0% | 55.91% / 37.92% / 1.502 | 44.92% / 51.75% / 0.873 | 51.42% / 51.75% / 0.996 | 18.2 | noise |
| 2x | 35.0% | 59.86% / 35.78% / 1.681 | 71.38% / 39.71% / 1.812 | 66.28% / 39.71% / 1.682 | 8.7 | noise |
| 2x | 40.0% | 63.41% / 34.29% / 1.865 | 71.80% / 39.70% / 1.825 | 68.37% / 39.70% / 1.734 | 5.3 | noise |
| 2x | 50.0% † | 62.39% / 34.59% / 1.829 | 65.07% / 43.53% / 1.594 | 64.44% / 43.53% / 1.547 | 2.8 | noise |
| 2x | 60.0% † | 57.39% / 37.66% / 1.617 | 74.04% / 40.44% / 1.857 | 66.05% / 42.93% / 1.574 | 1.4 | noise |
| 2x | 75.0% † | 58.95% / 36.76% / 1.673 | 73.73% / 45.61% / 1.688 | 66.53% / 46.79% / 1.461 | 0.6 | noise |
| 2x | 100.0% † | 57.17% / 35.51% / 1.668 | 85.23% / 42.87% / 1.995 | 70.99% / 42.87% / 1.661 | 0.3 | noise |

## Best candidates and annual diagnosis

- s=20.0%: IS/OOS Calmar_i 1.821/0.549; CAGR 108.89%/36.46%; ending multiple 6.364x/2.029x.
- s=22.5%: IS/OOS Calmar_i 1.763/0.187; CAGR 109.95%/14.38%; ending multiple 6.401x/1.358x.
- s=40.0%: IS/OOS Calmar_i 1.648/0.512; CAGR 104.86%/38.33%; ending multiple 6.129x/2.093x.
- Best eligible lockout s=20.0%: IS/OOS Calmar_i 1.687/0.292; CAGR 102.57%/23.05%. All 28 lockout rows remain in results_v2.json.

| year | baseline CAGR / IMDD / end | selected CAGR / IMDD / end |
|---:|---:|---:|
| 2022 | 45.68% / 51.85% / 1.457x | 56.42% / 51.40% / 1.564x |
| 2023 | 35.00% / 61.12% / 1.350x | 106.20% / 61.22% / 2.062x |
| 2024 | 404.52% / 54.36% / 5.068x | 426.59% / 58.81% / 5.290x |
| 2025 | 134.89% / 68.80% / 2.349x | 32.01% / 63.93% / 1.320x |
| 2026 | -36.93% / 74.64% / 0.700x | -43.68% / 57.03% / 0.642x |

## Crash-filter reference rows

Mode 0 disables crash flattening; mode 2 flattens longs and retains normal short positions. These comparisons are descriptive and do not recommend changing the crash filter.

| mode | stop | IS Calmar_i | OOS Calmar_i | IS/OOS end | liq / kill |
|---:|---:|---:|---:|---:|---:|
| 0 | none | 1.466 | 0.499 | 5.006x / 2.243x | 0 / 11.7 |
| 0 | 0.2 | 0.479 | -0.048 | 2.163x / 0.907x | 0 / 15.0 |
| 2 | none | 0.362 | 0.253 | 1.749x / 1.535x | 0 / 14.7 |
| 2 | 0.2 | 0.615 | -0.464 | 2.400x / 0.289x | 0 / 14.3 |

Across 42 BTC crash episodes, the fixed short book averaged 8.96% of starting equity per episode-phase after 0.2% round-trip costs; 102/126 episode-phase observations were profitable. Long-book equivalent averaged -8.21%, profitable in 17/126. Thus the full-flat filter did sell profitable shorts during sell-offs in this sample, while longs lost overall; this remains descriptive and does not recommend changing the filter.

## STX events, concentration, and trial accounting


| episode | start–end | BTC 14d | short book after cost (phase mean) | long book after cost (phase mean) | crash-off equity change | live-flat equity change |
|---:|---|---:|---:|---:|---:|---:|
| 1 | 2022-01-05–2022-01-11 | -10.6% | 16.17% | -13.57% | 2.20% | 0.05% |
| 2 | 2022-01-21–2022-01-30 | -12.3% | 34.87% | -30.09% | 5.27% | 2.98% |
| 3 | 2022-02-02–2022-02-02 | -11.4% | 5.30% | -8.07% | -0.46% | -1.61% |
| 4 | 2022-02-21–2022-02-24 | -15.6% | 11.18% | -9.31% | 1.52% | -0.67% |
| 5 | 2022-02-27–2022-02-27 | -10.4% | 2.15% | -7.82% | -2.98% | -3.15% |
| 6 | 2022-03-15–2022-03-15 | -11.5% | -1.35% | -0.08% | -4.81% | -4.76% |
| 7 | 2022-04-11–2022-04-18 | -16.2% | 9.37% | -7.94% | 0.71% | 0.08% |
| 8 | 2022-05-07–2022-05-22 | -10.0% | 20.60% | -14.01% | 6.09% | 5.10% |
| 9 | 2022-06-13–2022-06-26 | -29.2% | 9.58% | -6.25% | 1.88% | 2.50% |
| 10 | 2022-06-29–2022-06-29 | -10.9% | -1.73% | 3.09% | 1.72% | 1.82% |
| 11 | 2022-08-19–2022-08-19 | -10.6% | 12.18% | -20.75% | -7.97% | -7.97% |
| 12 | 2022-08-22–2022-08-22 | -10.2% | 0.83% | -0.01% | 0.00% | 0.00% |
| 13 | 2022-08-24–2022-08-24 | -10.8% | 2.82% | -1.03% | 0.00% | 0.00% |
| 14 | 2022-08-26–2022-09-01 | -17.1% | 21.42% | -12.84% | 0.00% | 0.00% |
| 15 | 2022-09-06–2022-09-06 | -12.7% | 11.31% | -16.95% | -5.28% | -5.28% |
| 16 | 2022-09-08–2022-09-08 | -10.4% | -1.64% | 3.94% | 2.78% | 2.68% |
| 17 | 2022-09-24–2022-09-26 | -12.6% | 3.02% | -5.20% | -2.44% | -0.80% |
| 18 | 2022-11-09–2022-11-22 | -23.4% | 27.03% | -17.75% | 2.78% | -4.19% |
| 19 | 2023-03-08–2023-03-11 | -10.2% | 16.49% | -15.09% | 1.39% | 0.00% |
| 20 | 2023-08-18–2023-08-19 | -10.5% | -11.38% | 2.87% | -6.88% | -4.94% |
| 21 | 2023-08-21–2023-08-28 | -10.6% | 3.61% | -4.83% | -0.88% | -2.49% |
| 22 | 2024-01-22–2024-01-25 | -15.8% | 12.57% | -8.68% | 1.42% | 3.62% |
| 23 | 2024-06-24–2024-06-24 | -13.3% | -5.91% | -1.71% | -6.96% | -6.96% |
| 24 | 2024-06-26–2024-06-26 | -10.9% | 2.44% | -0.43% | 5.52% | 2.38% |
| 25 | 2024-07-04–2024-07-05 | -12.0% | 21.33% | -16.84% | 5.97% | 3.21% |
| 26 | 2024-07-07–2024-07-07 | -11.7% | 11.88% | -14.38% | -2.66% | -2.12% |
| 27 | 2024-08-04–2024-08-07 | -14.7% | 17.91% | -12.09% | -0.66% | -0.20% |
| 28 | 2024-08-09–2024-08-12 | -10.4% | 3.94% | -2.41% | 4.32% | -0.23% |
| 29 | 2024-08-15–2024-08-15 | -12.0% | 6.82% | -4.62% | 1.10% | 1.28% |
| 30 | 2024-09-06–2024-09-08 | -15.8% | 1.03% | -1.29% | -0.30% | 1.30% |
| 31 | 2024-12-29–2024-12-31 | -10.3% | 10.66% | -9.14% | 1.42% | 1.54% |
| 32 | 2025-02-26–2025-03-01 | -13.9% | 0.27% | -0.98% | -3.00% | 2.49% |
| 33 | 2025-03-08–2025-03-10 | -10.7% | 20.86% | -16.79% | 0.00% | 0.11% |
| 34 | 2025-03-16–2025-03-16 | -12.4% | 9.25% | -5.63% | 0.00% | 4.67% |
| 35 | 2025-04-08–2025-04-08 | -12.7% | 7.84% | -3.17% | 4.43% | 3.63% |
| 36 | 2025-10-16–2025-10-22 | -10.3% | 10.35% | -9.06% | 0.94% | -5.92% |
| 37 | 2025-11-14–2025-11-17 | -13.7% | 10.66% | -3.89% | 0.00% | 5.01% |
| 38 | 2025-11-19–2025-11-26 | -11.9% | 14.44% | -16.06% | 0.00% | 1.06% |
| 39 | 2026-01-29–2026-02-17 | -11.5% | 16.62% | -20.04% | 0.00% | 0.00% |
| 40 | 2026-03-30–2026-03-30 | -10.8% | -4.11% | 1.33% | -1.90% | -1.90% |
| 41 | 2026-06-02–2026-06-14 | -13.1% | 9.75% | -10.76% | 0.49% | -1.04% |
| 42 | 2026-06-30–2026-06-30 | -10.7% | 6.00% | -6.33% | 0.00% | -0.44% |

## STX events, concentration, and trial accounting

STX-type baseline spells (>=20% adverse underlying excursion): 847 phase occurrences and 336 distinct symbol/side/entry spells. For each spell, all 28 stop thresholds' trigger day, underlying loss and 3/7-day whipsaw outcome are in results_v2.json. Top-five positive OOS daily excess share: 0.08974337055191252; top-five matched stopped-event improvement share: 0.26242978747199247 (245/829 stops matched to a baseline spell).

| rank | symbol | phase | side | entry date | stop PnL | baseline spell PnL | improvement / entry equity |
|---:|---:|---|---:|---:|---:|---:|
| 1 | FIL | 1 | short | 2022-07-16 | -0.0673 | -0.2782 | 15.09% |
| 2 | QNT | 1 | short | 2026-09-18 | -0.6394 | -2.2237 | 12.04% |
| 3 | OP | 1 | short | 2022-07-13 | -0.0626 | -0.1646 | 7.97% |
| 4 | BCH | 1 | short | 2026-09-06 | -0.5134 | -1.2299 | 6.83% |
| 5 | QNT | 0 | short | 2026-09-18 | -0.7617 | -1.7521 | 6.32% |

Contiguous helps bands under the preregistered neighbor test: 4x: none; 3x: none; 2x: none.

For high-s 4x rows (s >=25%), the intraday liquidation count and daily-close kill count by cell are: 25.0%: liquidation=0, mean kills=10.67, 27.5%: liquidation=0, mean kills=9.67, 30.0%: liquidation=0, mean kills=13.67, 35.0%: liquidation=0, mean kills=11.67, 40.0%: liquidation=0, mean kills=9.67, 50.0%: liquidation=0, mean kills=10.33, 60.0%: liquidation=0, mean kills=11.67, 75.0%: liquidation=0, mean kills=9.67, 100.0%: liquidation=0, mean kills=10.33. Where liquidation occurred, the engine intraday liquidation check precedes stop realization and the later kill switch; these high-s rows had the listed zero/nonzero liquidation counts.

Trials: v1 98 + v2 127 = 225 unique cells; nominal 0.05/trials=0.000222. V1 results were observed before v2 revision, creating forking-paths risk. V2 grid and selection rule were fixed before v2 runs, but the preregistered count estimate was 125 while 127 unique IDs actually ran; this discrepancy was appended after execution. Survivorship: 45 current listings omit delisted assets. Three phase offsets are correlated slices of one historical path, not independent samples. Fill prices are range-clamped approximations.

## v3

Rewritten by the coordinating agent from the ledger after the executor's automatic v3 text proved number-free (see the v3 completion addendum in prereg.md). All numbers are phase means over 3 rebalance phases; IS = 2022-01..2024-06, OOS = 2024-07..2026-10-09; no-stop baselines use crash filter on, 0.1%/side cost, real funding, kill 35%/14d unless stated.

### v3 summary (Q1-Q4)

1. Q1: 4x does not earn 2x of the 2x result mainly because of the KILL SWITCH. With kill off, 4x earns 129.5% CAGR vs 70.2% at 2x (1.84x; log growth 0.825 vs 0.530). With the live 35%/14d kill, 4x falls to 79.2% (log growth 0.583) while 2x stays 71.1%: the kill costs 4x -0.24 log growth (1.95 kills/yr, 27% of days flat) and 2x +0.01 (0.07 kills/yr).
2. Q1 ladder, full-period log growth (2x -> 3x -> 4x): frictionless 0.643 -> 0.857 -> 1.019; funding -0.01/-0.01/-0.02; costs -0.16/-0.24/-0.33 (scale ~2x with leverage, ~linear); crash filter +0.06/+0.10/+0.15; kill -0.00(+0.01)/-0.08/-0.24. Volatility drag (sigma^2/2) grows with leverage squared (0.138 -> 0.285 -> 0.477), so even frictionless 4x gets only 1.58x the 2x log growth (arithmetic mean return scales 1.91x). Costs and drag are the structural part; the kill switch is the avoidable part.
3. Q2: the kill sweep is chaotic, not smooth. At 2x a kill >= 40% never fires; at 3x >= 60%, at 4x >= 70% (kill never fires inside this sample). Below that, results jump with the cooldown (4x, kill 15%: Calmar_i IS/OOS 2.43/2.55 at 1d, 1.08/1.67 at 7d, 0.28/0.40 at 14d, 3.58/0.56 at 30d). Cooldown 0 (permanent halt after the first kill) is catastrophic wherever the kill fires (full CAGR -3% to 25% at 2x for kills <= 30%; -2% to 16% at 3x/4x for kills <= 50%).
4. Q2 selection: IS-only selection picks 2x 15%/30d, 3x 20%/1d, 4x 15%/30d. OOS Calmar_i vs live (IS/OOS): 2x 2.69/1.19 vs 1.87/1.84 (worse OOS); 3x 2.72/2.19 vs 1.36/1.56 (better in both); 4x 3.58/0.56 vs 0.84/1.31 (much worse OOS). Across the 29-31 non-permanent sweep cells per leverage, the IS-vs-OOS Spearman rank correlation of Calmar_i is +0.36 (2x), +0.15 (3x), -0.02 (4x): IS selection of the kill setting has essentially no out-of-sample predictive power at 3x/4x.
5. Q2 kill OFF: removing the kill gives IS/OOS Calmar_i 1.87/1.77 (2x), 2.04/1.87 (3x), 2.18/1.88 (4x), zero liquidations and no wipe-out in any of 3 phases at any leverage (worst intraday MDD 72% at 4x full). Calmar is nearly flat in leverage without the kill and falls with leverage with it (live: 1.65/1.37/0.99). Kill-off is a statement about this one 4.8-year path: 4x intraday MDD 72% is close to what the account can survive, one more adverse hour of the wrong size would be a liquidation.
6. Q3: the stop-curve shape is leverage- and kill-invariant in its broad form: stops < ~15-20% underlying (inside normal 3-day noise) destroy returns (4x kill-off: 5% stop gives IS/OOS Calmar_i -0.33/0.63 vs baseline 2.18/1.88; IS CAGR is negative for every s <= 8%), and levels >= liquidation-equivalent converge back to the baseline. With kill OFF, no stop level improves Calmar in both IS and OOS at any leverage (hurts-label for 33-36 of 41 levels; best IS level is 40% at every leverage, with IS Calmar_i equal to baseline and OOS lower: 1.74 vs 1.77, 1.75 vs 1.87, 1.70 vs 1.88).
7. Q3 live kill: the only 'helps' label in the 12 curves x 41 levels is 3x live at 37.5% (IS/OOS Calmar_i 1.39/2.01 vs 1.36/1.56; neighbours 32.5-42.5% all improve both). It is above the 33.3% liquidation-equivalent level and fires ~7 stops/yr (about 2 long, 5 short); it cannot be separated from kill-switch path chaos: the s=100% sanity row (which should equal baseline, but short squeezes >= +100% fire ~0.3 times/yr) moves 3x-live Calmar_i from 1.36/1.56 to 0.98/2.68. Differences of +-0.4 (IS) and +-1.1 (OOS) Calmar_i are therefore noise-level when a kill switch is active. Not a finding.
8. Q4: between 31% and 100% the curve is flat and noisy around the baseline (4x kill-off: IS Calmar_i 2.02-2.18 and OOS 1.64-1.89 over 40-100% vs baseline 2.18/1.88, i.e. slightly worse, never better; 3x live: OOS Calmar_i swings 1.43-2.68 over 31-100% with no pattern, because the kill-switch path changes). No sharp optimum exists; stops that sit above liquidation-equivalent (25% at 4x, 33% at 3x, 50% at 2x) are daggered and act, if at all, mostly on short squeezes.
9. Crash-filter-off interaction (D, 3 IS-best pairs, 123 cells): stops and crash filter do not substitute; with the filter off the curves again show no level improving both windows except isolated single levels (3x 20%/1d: 80%; 4x 15%/30d: 32.5%; 4x 30%/14d: 47.5%, 65%), none with the 80%-neighbour rule ('helps' = none).
10. Conclusion: leverage 4x is hurt by the kill switch (a tripped kill costs 14 flat days and a restart), not by the strategy; a per-position stop does not fix it. No stop level qualifies as 'helps' except a single noise-level cell (3x live 37.5%). Kill settings cannot be reliably chosen from this sample (rank correlation ~0 IS->OOS) and results rest on a handful of kill events (4x live: about 9 over the sample; per-year returns of the selected settings differ mostly in 2022, 2023 and 2026, see B2). No recommendation to change live settings is made here.

Trial counts (cumulative): v1 98 + v2 127 + v3 642 (639 + 3 crash-off no-stop baselines) = 867 unique parameter cells (each 3 phases). The kill sweep alone has 132 cells; the per-leverage kill selection, the 12 stop curves x 41 levels and the 2 selected-vs-neighbour labelling passes are all correlated looks at the same 4.8-year path; nominal 0.05/867 ~ 6e-5 is a warning, not a corrected p-value. Label rule: helps if >= 80% of the level and its +-2 neighbours improve Calmar_i vs the same-(leverage, kill, crash) no-stop baseline in both IS and OOS with CAGR >= 0.9x baseline; hurts if >= 80% worsen Calmar_i in both; else noise. Survivorship (today's listings) and the single 2022-2026 path apply as in v2.

### A. Decomposition ladder (no stops; phase means; IS/OOS/full)

mu = annualised arithmetic mean daily return, sigma = annualised daily std, drag = sigma^2/2, logG = ln(end)/years (approx. mu - drag). Sharpe from daily returns*sqrt(365).

| lev | stage | win | CAGR | logG | mu | sigma | drag | Sharpe | close MDD | intraday MDD | kills/yr | flat share | liq (3 ph) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2x | (a) no cost/fund/crash/kill | IS | 80.0% | 0.587 | 0.704 | 0.488 | 0.119 | 1.44 | 30.4% | 34.2% | 0.00 | 11.0% | 0 |
| 2x | (a) no cost/fund/crash/kill | OOS | 102.1% | 0.691 | 0.851 | 0.565 | 0.160 | 1.50 | 37.2% | 44.3% | 0.00 | 11.0% | 0 |
| 2x | (a) no cost/fund/crash/kill | full | 90.4% | 0.643 | 0.780 | 0.526 | 0.138 | 1.48 | 38.0% | 44.3% | 0.00 | 11.0% | 0 |
| 2x | (b) + funding | IS | 76.8% | 0.568 | 0.686 | 0.489 | 0.119 | 1.41 | 29.7% | 33.5% | 0.00 | 11.0% | 0 |
| 2x | (b) + funding | OOS | 102.6% | 0.693 | 0.852 | 0.566 | 0.160 | 1.50 | 36.8% | 44.6% | 0.00 | 11.0% | 0 |
| 2x | (b) + funding | full | 88.8% | 0.634 | 0.771 | 0.527 | 0.139 | 1.46 | 37.1% | 44.6% | 0.00 | 11.0% | 0 |
| 2x | (c) + cost 0.1%/side | IS | 50.9% | 0.410 | 0.529 | 0.491 | 0.121 | 1.08 | 34.0% | 38.1% | 0.00 | 11.0% | 0 |
| 2x | (c) + cost 0.1%/side | OOS | 71.2% | 0.524 | 0.685 | 0.568 | 0.161 | 1.20 | 42.4% | 50.8% | 0.00 | 11.0% | 0 |
| 2x | (c) + cost 0.1%/side | full | 60.4% | 0.471 | 0.609 | 0.529 | 0.140 | 1.15 | 43.0% | 50.8% | 0.00 | 11.0% | 0 |
| 2x | (d) + crash filter | IS | 62.8% | 0.487 | 0.598 | 0.473 | 0.112 | 1.26 | 30.0% | 34.0% | 0.00 | 20.9% | 0 |
| 2x | (d) + crash filter | OOS | 76.8% | 0.564 | 0.701 | 0.525 | 0.138 | 1.33 | 35.0% | 43.8% | 0.00 | 20.9% | 0 |
| 2x | (d) + crash filter | full | 70.2% | 0.530 | 0.653 | 0.499 | 0.124 | 1.31 | 35.5% | 43.8% | 0.00 | 20.9% | 0 |
| 2x | (e) + kill 35%/14d (live) | IS | 62.8% | 0.487 | 0.598 | 0.473 | 0.112 | 1.26 | 30.0% | 34.0% | 0.07 | 21.1% | 0 |
| 2x | (e) + kill 35%/14d (live) | OOS | 78.7% | 0.576 | 0.711 | 0.523 | 0.137 | 1.36 | 35.4% | 43.2% | 0.07 | 21.1% | 0 |
| 2x | (e) + kill 35%/14d (live) | full | 71.1% | 0.536 | 0.658 | 0.497 | 0.124 | 1.32 | 36.0% | 43.2% | 0.07 | 21.1% | 0 |
| 3x | (a) no cost/fund/crash/kill | IS | 126.9% | 0.816 | 1.064 | 0.711 | 0.253 | 1.50 | 42.0% | 47.1% | 0.00 | 11.0% | 0 |
| 3x | (a) no cost/fund/crash/kill | OOS | 148.4% | 0.882 | 1.200 | 0.801 | 0.321 | 1.50 | 50.4% | 59.3% | 0.00 | 11.0% | 0 |
| 3x | (a) no cost/fund/crash/kill | full | 136.3% | 0.857 | 1.138 | 0.755 | 0.285 | 1.51 | 51.4% | 59.3% | 0.00 | 11.0% | 0 |
| 3x | (b) + funding | IS | 121.2% | 0.790 | 1.039 | 0.713 | 0.254 | 1.46 | 41.1% | 46.3% | 0.00 | 11.0% | 0 |
| 3x | (b) + funding | OOS | 148.5% | 0.882 | 1.200 | 0.801 | 0.321 | 1.50 | 49.9% | 59.8% | 0.00 | 11.0% | 0 |
| 3x | (b) + funding | full | 133.1% | 0.843 | 1.125 | 0.756 | 0.286 | 1.49 | 50.4% | 59.8% | 0.00 | 11.0% | 0 |
| 3x | (c) + cost 0.1%/side | IS | 74.6% | 0.554 | 0.806 | 0.717 | 0.257 | 1.12 | 46.4% | 51.8% | 0.00 | 11.0% | 0 |
| 3x | (c) + cost 0.1%/side | OOS | 93.1% | 0.629 | 0.951 | 0.806 | 0.325 | 1.18 | 56.3% | 66.2% | 0.00 | 11.0% | 0 |
| 3x | (c) + cost 0.1%/side | full | 82.5% | 0.599 | 0.884 | 0.761 | 0.289 | 1.16 | 57.1% | 66.2% | 0.00 | 11.0% | 0 |
| 3x | (d) + crash filter | IS | 95.1% | 0.668 | 0.901 | 0.690 | 0.238 | 1.31 | 41.5% | 47.0% | 0.00 | 20.9% | 0 |
| 3x | (d) + crash filter | OOS | 108.4% | 0.720 | 0.999 | 0.752 | 0.283 | 1.33 | 46.8% | 59.1% | 0.00 | 20.9% | 0 |
| 3x | (d) + crash filter | full | 102.4% | 0.702 | 0.956 | 0.720 | 0.259 | 1.33 | 48.1% | 59.1% | 0.00 | 20.9% | 0 |
| 3x | (e) + kill 35%/14d (live) | IS | 77.3% | 0.568 | 0.798 | 0.686 | 0.235 | 1.16 | 51.4% | 56.6% | 0.98 | 23.9% | 0 |
| 3x | (e) + kill 35%/14d (live) | OOS | 95.1% | 0.658 | 0.932 | 0.747 | 0.279 | 1.25 | 59.4% | 63.1% | 0.98 | 23.9% | 0 |
| 3x | (e) + kill 35%/14d (live) | full | 86.6% | 0.620 | 0.871 | 0.716 | 0.256 | 1.22 | 61.5% | 64.0% | 0.98 | 23.9% | 0 |
| 4x | (a) no cost/fund/crash/kill | IS | 176.7% | 1.011 | 1.430 | 0.927 | 0.430 | 1.54 | 51.8% | 58.0% | 0.00 | 11.0% | 0 |
| 4x | (a) no cost/fund/crash/kill | OOS | 186.4% | 1.002 | 1.526 | 1.028 | 0.528 | 1.48 | 61.6% | 72.1% | 0.00 | 11.0% | 0 |
| 4x | (a) no cost/fund/crash/kill | full | 178.6% | 1.019 | 1.488 | 0.976 | 0.477 | 1.52 | 62.6% | 72.1% | 0.00 | 11.0% | 0 |
| 4x | (b) + funding | IS | 168.0% | 0.978 | 1.400 | 0.929 | 0.432 | 1.51 | 50.9% | 57.4% | 0.00 | 11.0% | 0 |
| 4x | (b) + funding | OOS | 185.6% | 0.999 | 1.524 | 1.028 | 0.529 | 1.48 | 61.0% | 72.6% | 0.00 | 11.0% | 0 |
| 4x | (b) + funding | full | 173.3% | 1.001 | 1.471 | 0.977 | 0.478 | 1.50 | 61.5% | 72.6% | 0.00 | 11.0% | 0 |
| 4x | (c) + cost 0.1%/side | IS | 95.6% | 0.663 | 1.091 | 0.937 | 0.439 | 1.16 | 56.7% | 62.8% | 0.00 | 11.0% | 0 |
| 4x | (c) + cost 0.1%/side | OOS | 103.9% | 0.660 | 1.192 | 1.036 | 0.537 | 1.15 | 67.9% | 78.1% | 0.00 | 11.0% | 0 |
| 4x | (c) + cost 0.1%/side | full | 97.2% | 0.674 | 1.151 | 0.985 | 0.486 | 1.17 | 68.5% | 78.1% | 0.00 | 11.0% | 0 |
| 4x | (d) + crash filter | IS | 125.8% | 0.814 | 1.206 | 0.898 | 0.403 | 1.34 | 51.4% | 58.1% | 0.00 | 20.9% | 0 |
| 4x | (d) + crash filter | OOS | 131.8% | 0.812 | 1.278 | 0.972 | 0.472 | 1.32 | 57.5% | 71.8% | 0.00 | 20.9% | 0 |
| 4x | (d) + crash filter | full | 129.5% | 0.825 | 1.252 | 0.934 | 0.436 | 1.34 | 59.2% | 71.8% | 0.00 | 20.9% | 0 |
| 4x | (e) + kill 35%/14d (live) | IS | 55.1% | 0.438 | 0.794 | 0.857 | 0.367 | 0.93 | 60.2% | 65.5% | 1.95 | 26.9% | 0 |
| 4x | (e) + kill 35%/14d (live) | OOS | 104.6% | 0.716 | 1.106 | 0.891 | 0.397 | 1.24 | 61.9% | 79.6% | 1.95 | 26.9% | 0 |
| 4x | (e) + kill 35%/14d (live) | full | 79.2% | 0.583 | 0.955 | 0.873 | 0.381 | 1.09 | 61.9% | 79.6% | 1.95 | 26.9% | 0 |

### B. Kill sweep (no stops, crash filter live, costs/funding on). Cells: IS Calmar_i / OOS Calmar_i (full CAGR; kills per year)

Cooldown 0 = permanent halt after the first kill (engine semantics). Kill 'off' = kill >= 100% (liquidation logic still active).

#### 2x  (off: IS/OOS Calmar_i 1.87/1.77, full CAGR 70%, liq 0 over 3 phases)

| kill \ cooldown | 0d (permanent) | 1d | 7d | 14d | 30d |
|---:|---:|---:|---:|---:|---:|
| 15% | 0.07 / 0.00 (0%; 0.2) | 1.25 / 1.06 (48%; 3.8) | 0.97 / 0.81 (41%; 3.6) | 0.93 / 1.44 (47%; 3.5) | 2.69 / 1.19 (65%; 2.4) |
| 20% | 0.15 / 0.00 (2%; 0.2) | 1.97 / 1.42 (65%; 1.8) | 1.83 / 1.42 (63%; 1.8) | 0.68 / 0.83 (36%; 2.4) | 1.04 / 0.99 (49%; 1.7) |
| 25% | 0.28 / 0.00 (4%; 0.2) | 2.13 / 1.66 (73%; 1.1) | 1.95 / 1.59 (72%; 1.1) | 1.39 / 2.73 (72%; 1.0) | 1.53 / 0.82 (49%; 1.0) |
| 30% | 1.44 / 0.09 (25%; 0.2) | 1.85 / 1.67 (68%; 0.6) | 1.89 / 1.48 (66%; 0.6) | 1.87 / 2.18 (76%; 0.4) | 1.62 / 1.09 (56%; 0.6) |
| 35% | 1.87 / 1.50 (63%; 0.1) | 1.87 / 1.95 (73%; 0.1) | 1.87 / 1.81 (71%; 0.1) | 1.87 / 1.84 (71%; 0.1) | 1.87 / 1.86 (73%; 0.1) |
| 40% | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) |
| 50% | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) |
| 60% | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) |
| 70% | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) | 1.87 / 1.77 (70%; 0.0) |

#### 3x  (off: IS/OOS Calmar_i 2.04/1.87, full CAGR 102%, liq 0 over 3 phases)

| kill \ cooldown | 0d (permanent) | 1d | 7d | 14d | 30d |
|---:|---:|---:|---:|---:|---:|
| 15% | -0.23 / 0.00 (-2%; 0.2) | 1.88 / 2.38 (97%; 7.1) | 0.64 / 0.89 (41%; 6.9) | 1.70 / 0.26 (48%; 5.5) | 2.44 / 0.47 (63%; 4.7) |
| 20% | 0.08 / 0.00 (0%; 0.2) | 2.72 / 2.19 (126%; 3.1) | 2.57 / 1.46 (106%; 3.1) | 1.45 / 1.70 (92%; 3.3) | 2.20 / 0.95 (84%; 3.4) |
| 25% | 0.26 / 0.00 (4%; 0.2) | 1.95 / 2.50 (121%; 2.4) | 1.97 / 1.86 (105%; 2.4) | 2.47 / 1.18 (90%; 1.8) | 2.11 / 0.86 (75%; 2.4) |
| 30% | 0.14 / 0.00 (2%; 0.2) | 1.96 / 1.60 (95%; 1.5) | 1.91 / 1.44 (91%; 1.5) | 2.00 / 2.16 (110%; 1.2) | 1.06 / 0.81 (61%; 1.8) |
| 35% | 0.24 / 0.00 (5%; 0.2) | 1.98 / 1.47 (90%; 1.0) | 1.73 / 1.59 (91%; 1.0) | 1.36 / 1.56 (87%; 1.0) | 1.84 / 1.16 (80%; 1.0) |
| 40% | 0.84 / -0.13 (14%; 0.2) | 2.09 / 1.59 (93%; 0.8) | 2.02 / 1.29 (87%; 0.8) | 1.60 / 1.31 (77%; 0.8) | 1.78 / 1.23 (83%; 0.7) |
| 50% | 2.04 / 1.59 (92%; 0.1) | 2.04 / 2.05 (107%; 0.1) | 2.04 / 1.92 (104%; 0.1) | 2.04 / 1.95 (104%; 0.1) | 2.04 / 2.01 (107%; 0.1) |
| 60% | 2.04 / 1.87 (102%; 0.0) | 2.04 / 1.87 (102%; 0.0) | 2.04 / 1.87 (102%; 0.0) | 2.04 / 1.87 (102%; 0.0) | 2.04 / 1.87 (102%; 0.0) |
| 70% | 2.04 / 1.87 (102%; 0.0) | 2.04 / 1.87 (102%; 0.0) | 2.04 / 1.87 (102%; 0.0) | 2.04 / 1.87 (102%; 0.0) | 2.04 / 1.87 (102%; 0.0) |

#### 4x  (off: IS/OOS Calmar_i 2.18/1.88, full CAGR 129%, liq 0 over 3 phases)

| kill \ cooldown | 0d (permanent) | 1d | 7d | 14d | 30d |
|---:|---:|---:|---:|---:|---:|
| 15% | -0.17 / 0.00 (-2%; 0.2) | 2.43 / 2.55 (146%; 10.7) | 1.08 / 1.67 (86%; 9.0) | 0.28 / 0.40 (24%; 8.7) | 3.58 / 0.56 (93%; 5.7) |
| 20% | -0.24 / 0.00 (-3%; 0.2) | 1.60 / 1.55 (95%; 6.9) | 1.47 / 1.49 (94%; 6.1) | 1.43 / 0.41 (56%; 5.7) | 1.21 / 0.51 (60%; 5.0) |
| 25% | 0.10 / 0.00 (1%; 0.2) | 2.37 / 1.20 (118%; 4.0) | 2.46 / 1.58 (133%; 3.8) | 1.14 / 1.60 (102%; 3.7) | 1.65 / 0.91 (92%; 3.7) |
| 30% | 0.28 / 0.00 (5%; 0.2) | 1.21 / 1.57 (92%; 2.9) | 1.42 / 1.04 (78%; 2.9) | 3.00 / 0.38 (84%; 2.6) | 2.23 / 0.68 (89%; 2.4) |
| 35% | 0.15 / 0.00 (3%; 0.2) | 2.14 / 1.27 (107%; 1.7) | 2.06 / 0.98 (95%; 1.7) | 0.84 / 1.31 (79%; 2.0) | 1.17 / 0.35 (55%; 2.0) |
| 40% | 0.07 / 0.00 (2%; 0.2) | 1.81 / 1.42 (110%; 1.1) | 1.51 / 1.58 (108%; 1.1) | 1.92 / 2.92 (143%; 1.0) | 1.35 / 0.59 (70%; 1.5) |
| 50% | 0.86 / -0.13 (16%; 0.2) | 2.03 / 1.40 (107%; 0.8) | 1.98 / 1.07 (98%; 0.8) | 1.77 / 1.35 (103%; 0.9) | 1.79 / 0.16 (55%; 1.0) |
| 60% | 2.18 / 1.61 (117%; 0.1) | 2.18 / 2.07 (136%; 0.1) | 2.18 / 1.94 (133%; 0.1) | 2.18 / 1.97 (132%; 0.1) | 2.18 / 2.06 (137%; 0.1) |
| 70% | 2.18 / 1.88 (129%; 0.0) | 2.18 / 1.88 (129%; 0.0) | 2.18 / 1.88 (129%; 0.0) | 2.18 / 1.88 (129%; 0.0) | 2.18 / 1.88 (129%; 0.0) |

### B2. IS-selected kill setting per leverage vs live and off (eligible = IS end wealth >= 85% of live IS end wealth)

| lev | setting | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | kills/yr | liq | flat share | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2x | live 35%/14d | 63%/34%/1.87 | 79%/43%/1.84 | 71%/43%/1.65 | 0.07 | 0 | 21% | 26% | 81% | 204% | 84% | 6% |
| 2x | IS-selected 15%/30d | 78%/29%/2.69 | 50%/42%/1.19 | 65%/42%/1.54 | 2.44 | 0 | 36% | 26% | 100% | 203% | 91% | -26% |
| 2x | off | 63%/34%/1.87 | 77%/44%/1.77 | 70%/44%/1.61 | 0.00 | 0 | 21% | 26% | 81% | 204% | 89% | 1% |
| 2x | 2nd-best 25%/1d | 69%/33%/2.13 | 75%/45%/1.66 | 73%/45%/1.61 | 1.12 | 0 | 21% | 22% | 103% | 220% | 75% | -0% |
| 3x | live 35%/14d | 77%/57%/1.36 | 95%/63%/1.56 | 87%/64%/1.37 | 0.98 | 0 | 24% | 27% | 56% | 342% | 92% | 20% |
| 3x | IS-selected 20%/1d | 126%/46%/2.72 | 121%/55%/2.19 | 126%/55%/2.27 | 3.14 | 0 | 22% | 52% | 196% | 341% | 138% | 3% |
| 3x | off | 95%/47%/2.04 | 108%/59%/1.87 | 102%/59%/1.75 | 0.00 | 0 | 21% | 37% | 123% | 342% | 141% | -4% |
| 3x | 2nd-best 20%/7d | 121%/48%/2.57 | 87%/60%/1.46 | 106%/60%/1.77 | 3.14 | 0 | 26% | 51% | 184% | 403% | 68% | -12% |
| 4x | live 35%/14d | 55%/65%/0.84 | 105%/80%/1.31 | 79%/80%/0.99 | 1.95 | 0 | 27% | 46% | 35% | 407% | 135% | -30% |
| 4x | IS-selected 15%/30d | 156%/44%/3.58 | 38%/69%/0.56 | 93%/69%/1.36 | 5.65 | 0 | 58% | 140% | 128% | 169% | 161% | -36% |
| 4x | off | 126%/58%/2.18 | 132%/72%/1.88 | 129%/72%/1.82 | 0.00 | 0 | 21% | 47% | 164% | 495% | 195% | -11% |
| 4x | 2nd-best 30%/14d | 150%/50%/3.00 | 28%/74%/0.38 | 84%/74%/1.13 | 2.58 | 0 | 29% | 61% | 165% | 309% | 95% | -47% |
(per-year columns: calendar-year return, phase mean; 2026 is partial to 10-09)

#### B3. Concentration of the selected-vs-live difference

| lev | selected | full log-wealth gain vs live (phase mean) | top-5 days' share of positive daily log-return differences | top-5 days' dates (phase 0) |
|---|---|---:|---:|---|
| 2x | 15%/30d | -0.17 | 7% | 2024-12-09, 2025-11-07, 2024-12-05, 2022-11-09, 2025-09-08 |
| 3x | 20%/1d | 0.93 | 7% | 2024-12-04, 2023-12-07, 2024-11-30, 2024-04-12, 2024-12-09 |
| 4x | 15%/30d | 0.37 | 6% | 2026-09-28, 2025-11-10, 2024-12-03, 2024-03-19, 2023-01-14 |

### C. Extended stop curves (both sides, reentry, fill mode 1, crash filter live)

#### 2x, kill setting 'live' (35%/14d)

No-stop baseline: IS 63%/34%/1.87, OOS 79%/43%/1.84, full 71%/43%/1.65, kills/yr 0.07, liq 0. († = at/after liquidation-equivalent 50.0%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -60%/90%/-0.67 | -59%/87%/-0.68 | -59%/99%/-0.60 | 848/849 | 2.02 | 0 | hurts |
| 0.5% | -60%/90%/-0.67 | -43%/74%/-0.57 | -52%/97%/-0.54 | 758/735 | 1.75 | 0 | hurts |
| 1% | -56%/88%/-0.64 | -19%/71%/-0.26 | -41%/93%/-0.44 | 673/644 | 1.54 | 0 | hurts |
| 1.5% | -57%/89%/-0.64 | -17%/75%/-0.23 | -42%/95%/-0.44 | 602/577 | 1.95 | 0 | hurts |
| 2% | -49%/84%/-0.58 | 1%/62%/0.02 | -29%/86%/-0.34 | 550/502 | 1.47 | 0 | hurts |
| 3% | -18%/57%/-0.31 | 16%/61%/0.26 | -3%/61%/-0.05 | 449/409 | 0.98 | 0 | hurts |
| 4% | -8%/55%/-0.15 | 22%/56%/0.39 | 6%/57%/0.10 | 367/333 | 0.63 | 0 | hurts |
| 5% | 3%/50%/0.07 | 54%/45%/1.22 | 26%/50%/0.52 | 307/264 | 0.49 | 0 | hurts |
| 6% | 15%/45%/0.32 | 49%/46%/1.09 | 31%/47%/0.66 | 259/222 | 0.63 | 0 | hurts |
| 7% | 1%/54%/0.07 | 49%/46%/1.07 | 22%/55%/0.42 | 221/189 | 0.77 | 0 | hurts |
| 8% | 9%/49%/0.19 | 59%/48%/1.22 | 31%/51%/0.61 | 186/160 | 0.42 | 0 | hurts |
| 9% | 10%/47%/0.23 | 60%/50%/1.21 | 32%/52%/0.62 | 157/136 | 0.63 | 0 | hurts |
| 10% | 13%/53%/0.26 | 80%/37%/2.20 | 42%/53%/0.80 | 134/120 | 0.21 | 0 | hurts |
| 12% | 27%/48%/0.56 | 46%/57%/0.81 | 37%/57%/0.65 | 96/88 | 0.42 | 0 | hurts |
| 14% | 33%/45%/0.74 | 64%/45%/1.48 | 48%/48%/1.02 | 73/66 | 0.42 | 0 | hurts |
| 16% | 42%/40%/1.11 | 59%/48%/1.27 | 51%/50%/1.01 | 55/52 | 0.28 | 0 | hurts |
| 18% | 46%/39%/1.21 | 62%/47%/1.36 | 54%/48%/1.16 | 42/40 | 0.28 | 0 | hurts |
| 20% | 41%/36%/1.16 | 58%/47%/1.23 | 50%/47%/1.06 | 30/34 | 0.35 | 0 | hurts |
| 22.5% | 47%/38%/1.26 | 63%/46%/1.40 | 55%/46%/1.23 | 21/26 | 0.35 | 0 | hurts |
| 25% | 43%/37%/1.21 | 65%/48%/1.38 | 54%/48%/1.15 | 14/20 | 0.28 | 0 | hurts |
| 27.5% | 53%/38%/1.44 | 52%/50%/1.07 | 54%/50%/1.09 | 10/15 | 0.35 | 0 | hurts |
| 30% | 56%/38%/1.50 | 45%/52%/0.87 | 51%/52%/1.00 | 6/12 | 0.42 | 0 | hurts |
| 31% | 55%/38%/1.46 | 56%/49%/1.18 | 56%/49%/1.18 | 6/11 | 0.35 | 0 | hurts |
| 32.5% | 55%/39%/1.45 | 68%/42%/1.65 | 62%/43%/1.49 | 4/8 | 0.21 | 0 | hurts |
| 35% | 60%/36%/1.68 | 71%/40%/1.81 | 66%/40%/1.68 | 3/6 | 0.07 | 0 | hurts |
| 37.5% | 63%/35%/1.82 | 72%/42%/1.76 | 68%/42%/1.66 | 2/5 | 0.07 | 0 | hurts |
| 40% | 63%/34%/1.86 | 72%/40%/1.82 | 68%/40%/1.73 | 1/4 | 0.07 | 0 | hurts |
| 42.5% | 63%/35%/1.84 | 73%/40%/1.86 | 69%/40%/1.74 | 1/3 | 0.07 | 0 | hurts |
| 45% | 63%/35%/1.86 | 71%/40%/1.80 | 68%/40%/1.72 | 1/3 | 0.07 | 0 | hurts |
| 47.5% | 63%/34%/1.84 | 70%/40%/1.77 | 67%/40%/1.69 | 1/3 | 0.07 | 0 | hurts |
| 50%† | 62%/35%/1.83 | 65%/44%/1.59 | 64%/44%/1.55 | 1/2 | 0.14 | 0 | hurts |
| 55%† | 62%/35%/1.80 | 71%/40%/1.79 | 67%/40%/1.68 | 1/1 | 0.07 | 0 | noise |
| 60%† | 57%/38%/1.62 | 74%/40%/1.86 | 66%/43%/1.57 | 0/1 | 0.14 | 0 | noise |
| 65%† | 60%/36%/1.72 | 83%/45%/1.92 | 71%/46%/1.59 | 0/1 | 0.21 | 0 | noise |
| 70%† | 59%/36%/1.69 | 73%/45%/1.69 | 67%/46%/1.47 | 0/1 | 0.21 | 0 | noise |
| 75%† | 59%/37%/1.67 | 74%/46%/1.69 | 67%/47%/1.46 | 0/1 | 0.21 | 0 | noise |
| 80%† | 61%/35%/1.78 | 83%/45%/1.92 | 72%/45%/1.63 | 0/0 | 0.21 | 0 | noise |
| 85%† | 61%/35%/1.77 | 83%/45%/1.91 | 71%/45%/1.62 | 0/0 | 0.21 | 0 | noise |
| 90%† | 61%/35%/1.76 | 81%/45%/1.88 | 71%/45%/1.61 | 0/0 | 0.21 | 0 | noise |
| 95%† | 60%/36%/1.71 | 83%/43%/1.95 | 72%/43%/1.67 | 0/0 | 0.14 | 0 | noise |
| 100%† | 57%/36%/1.67 | 85%/43%/1.99 | 71%/43%/1.66 | 0/0 | 0.21 | 0 | noise |

IS-selected stop: 40.0% -> IS/OOS Calmar_i 1.86/1.82 vs baseline 1.87/1.84; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: none; 'helps' levels: none.

#### 2x, kill setting 'off' (off)

No-stop baseline: IS 63%/34%/1.87, OOS 77%/44%/1.77, full 70%/44%/1.61, kills/yr 0.00, liq 0. († = at/after liquidation-equivalent 50.0%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -62%/91%/-0.68 | -60%/88%/-0.69 | -62%/99%/-0.62 | 910/911 | 0.00 | 0 | hurts |
| 0.5% | -60%/90%/-0.67 | -47%/78%/-0.60 | -55%/98%/-0.56 | 808/790 | 0.00 | 0 | hurts |
| 1% | -60%/90%/-0.66 | -19%/68%/-0.27 | -44%/95%/-0.46 | 718/687 | 0.00 | 0 | hurts |
| 1.5% | -55%/87%/-0.62 | -12%/69%/-0.17 | -38%/93%/-0.41 | 642/611 | 0.00 | 0 | hurts |
| 2% | -51%/85%/-0.60 | 8%/66%/0.12 | -29%/87%/-0.33 | 576/540 | 0.00 | 0 | hurts |
| 3% | -31%/69%/-0.43 | 20%/63%/0.31 | -10%/72%/-0.14 | 466/426 | 0.00 | 0 | hurts |
| 4% | -16%/62%/-0.24 | 34%/57%/0.66 | 5%/63%/0.10 | 385/338 | 0.00 | 0 | hurts |
| 5% | -9%/59%/-0.12 | 43%/52%/0.85 | 13%/60%/0.26 | 321/275 | 0.00 | 0 | hurts |
| 6% | 4%/53%/0.12 | 53%/48%/1.12 | 25%/56%/0.49 | 268/228 | 0.00 | 0 | hurts |
| 7% | 1%/52%/0.05 | 63%/46%/1.37 | 28%/53%/0.55 | 228/192 | 0.00 | 0 | hurts |
| 8% | 4%/50%/0.09 | 65%/46%/1.43 | 31%/51%/0.60 | 193/163 | 0.00 | 0 | hurts |
| 9% | 11%/46%/0.24 | 70%/45%/1.57 | 37%/48%/0.76 | 161/140 | 0.00 | 0 | hurts |
| 10% | 16%/47%/0.35 | 68%/46%/1.55 | 40%/51%/0.78 | 139/120 | 0.00 | 0 | hurts |
| 12% | 27%/43%/0.62 | 60%/48%/1.26 | 43%/49%/0.89 | 100/92 | 0.00 | 0 | hurts |
| 14% | 37%/42%/0.87 | 63%/46%/1.43 | 49%/47%/1.07 | 74/69 | 0.00 | 0 | hurts |
| 16% | 42%/40%/1.11 | 64%/44%/1.48 | 53%/47%/1.15 | 56/53 | 0.00 | 0 | hurts |
| 18% | 46%/38%/1.24 | 60%/45%/1.33 | 54%/46%/1.17 | 42/42 | 0.00 | 0 | hurts |
| 20% | 48%/37%/1.32 | 57%/45%/1.29 | 54%/46%/1.18 | 31/33 | 0.00 | 0 | hurts |
| 22.5% | 47%/38%/1.27 | 56%/46%/1.24 | 52%/47%/1.13 | 22/26 | 0.00 | 0 | hurts |
| 25% | 49%/37%/1.33 | 59%/45%/1.37 | 55%/45%/1.23 | 15/20 | 0.00 | 0 | hurts |
| 27.5% | 55%/36%/1.53 | 62%/43%/1.46 | 59%/43%/1.39 | 10/15 | 0.00 | 0 | hurts |
| 30% | 58%/36%/1.60 | 61%/43%/1.46 | 60%/43%/1.43 | 6/11 | 0.00 | 0 | hurts |
| 31% | 57%/37%/1.56 | 60%/43%/1.40 | 59%/43%/1.38 | 6/11 | 0.00 | 0 | hurts |
| 32.5% | 58%/36%/1.62 | 66%/41%/1.62 | 63%/41%/1.54 | 4/8 | 0.00 | 0 | hurts |
| 35% | 60%/36%/1.68 | 68%/41%/1.71 | 65%/41%/1.62 | 3/6 | 0.00 | 0 | hurts |
| 37.5% | 63%/35%/1.82 | 71%/41%/1.78 | 68%/41%/1.69 | 2/5 | 0.00 | 0 | hurts |
| 40% | 63%/34%/1.86 | 69%/41%/1.74 | 67%/41%/1.67 | 1/4 | 0.00 | 0 | hurts |
| 42.5% | 63%/35%/1.84 | 70%/41%/1.76 | 67%/41%/1.68 | 1/3 | 0.00 | 0 | hurts |
| 45% | 63%/35%/1.86 | 69%/41%/1.72 | 67%/41%/1.66 | 1/3 | 0.00 | 0 | hurts |
| 47.5% | 63%/34%/1.84 | 68%/41%/1.70 | 66%/41%/1.64 | 1/2 | 0.00 | 0 | hurts |
| 50%† | 62%/35%/1.83 | 68%/41%/1.70 | 66%/41%/1.64 | 1/2 | 0.00 | 0 | hurts |
| 55%† | 62%/35%/1.80 | 68%/41%/1.70 | 66%/41%/1.63 | 1/2 | 0.00 | 0 | hurts |
| 60%† | 61%/35%/1.79 | 70%/41%/1.75 | 66%/41%/1.64 | 0/1 | 0.00 | 0 | noise |
| 65%† | 62%/35%/1.81 | 76%/43%/1.79 | 69%/43%/1.63 | 0/1 | 0.00 | 0 | noise |
| 70%† | 61%/35%/1.79 | 76%/43%/1.80 | 69%/43%/1.63 | 0/1 | 0.00 | 0 | noise |
| 75%† | 61%/35%/1.77 | 76%/43%/1.80 | 69%/43%/1.62 | 0/1 | 0.00 | 0 | noise |
| 80%† | 61%/35%/1.77 | 76%/43%/1.79 | 69%/43%/1.61 | 0/0 | 0.00 | 0 | noise |
| 85%† | 60%/35%/1.75 | 76%/43%/1.78 | 68%/43%/1.60 | 0/0 | 0.00 | 0 | noise |
| 90%† | 61%/35%/1.76 | 75%/43%/1.76 | 69%/43%/1.59 | 0/0 | 0.00 | 0 | noise |
| 95%† | 61%/36%/1.75 | 75%/43%/1.75 | 68%/43%/1.58 | 0/0 | 0.00 | 0 | noise |
| 100%† | 61%/36%/1.75 | 75%/44%/1.73 | 68%/44%/1.57 | 0/0 | 0.00 | 0 | hurts |

IS-selected stop: 40.0% -> IS/OOS Calmar_i 1.86/1.74 vs baseline 1.87/1.77; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: none; 'helps' levels: none.

#### 2x, kill setting 'selected' (15%/30d)

No-stop baseline: IS 78%/29%/2.69, OOS 50%/42%/1.19, full 65%/42%/1.54, kills/yr 2.44, liq 0. († = at/after liquidation-equivalent 50.0%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -49%/81%/-0.60 | -46%/75%/-0.61 | -47%/95%/-0.50 | 628/631 | 3.77 | 0 | hurts |
| 0.5% | -42%/74%/-0.56 | -33%/64%/-0.51 | -38%/90%/-0.42 | 567/560 | 3.63 | 0 | hurts |
| 1% | -29%/62%/-0.47 | -30%/68%/-0.44 | -30%/86%/-0.35 | 490/466 | 3.98 | 0 | hurts |
| 1.5% | -35%/69%/-0.51 | -17%/69%/-0.25 | -27%/85%/-0.31 | 416/416 | 4.12 | 0 | hurts |
| 2% | -31%/65%/-0.48 | 57%/40%/1.43 | 2%/65%/0.03 | 392/371 | 3.98 | 0 | noise |
| 3% | -21%/62%/-0.30 | -20%/75%/-0.27 | -21%/81%/-0.26 | 320/289 | 4.19 | 0 | noise |
| 4% | -2%/43%/-0.04 | 62%/52%/1.19 | 25%/52%/0.48 | 265/238 | 3.70 | 0 | noise |
| 5% | -8%/54%/-0.15 | 13%/51%/0.26 | 2%/55%/0.04 | 229/196 | 3.63 | 0 | noise |
| 6% | -2%/42%/-0.05 | 28%/47%/0.60 | 12%/47%/0.25 | 195/172 | 3.07 | 0 | noise |
| 7% | -4%/43%/-0.03 | 59%/41%/1.45 | 23%/46%/0.56 | 158/147 | 3.42 | 0 | hurts |
| 8% | -21%/61%/-0.35 | -19%/67%/-0.28 | -20%/82%/-0.24 | 141/103 | 4.33 | 0 | hurts |
| 9% | 5%/48%/0.15 | 29%/43%/0.68 | 16%/48%/0.37 | 112/110 | 3.35 | 0 | hurts |
| 10% | 9%/48%/0.21 | 43%/53%/0.80 | 24%/53%/0.46 | 100/102 | 3.21 | 0 | hurts |
| 12% | 29%/35%/0.85 | 17%/56%/0.31 | 24%/56%/0.42 | 74/74 | 3.28 | 0 | hurts |
| 14% | 60%/32%/1.91 | 6%/58%/0.10 | 32%/58%/0.56 | 53/58 | 3.42 | 0 | hurts |
| 16% | 26%/44%/0.60 | 58%/45%/1.27 | 41%/45%/0.91 | 47/43 | 3.21 | 0 | hurts |
| 18% | 36%/33%/1.09 | 23%/51%/0.45 | 30%/51%/0.60 | 29/33 | 3.21 | 0 | hurts |
| 20% | 48%/38%/1.28 | 26%/55%/0.46 | 38%/55%/0.68 | 23/29 | 3.21 | 0 | hurts |
| 22.5% | 48%/32%/1.48 | 46%/49%/0.93 | 48%/49%/0.97 | 18/23 | 3.07 | 0 | hurts |
| 25% | 71%/31%/2.46 | 30%/51%/0.63 | 49%/51%/0.97 | 11/17 | 3.07 | 0 | hurts |
| 27.5% | 48%/41%/1.18 | 36%/40%/0.90 | 43%/41%/1.05 | 8/13 | 3.28 | 0 | hurts |
| 30% | 39%/47%/0.82 | 37%/41%/0.91 | 39%/47%/0.82 | 4/9 | 3.28 | 0 | hurts |
| 31% | 36%/47%/0.77 | 18%/53%/0.34 | 28%/53%/0.53 | 4/9 | 3.28 | 0 | hurts |
| 32.5% | 32%/47%/0.68 | 56%/39%/1.45 | 44%/47%/0.93 | 3/6 | 3.28 | 0 | noise |
| 35% | 64%/38%/1.67 | 25%/53%/0.47 | 45%/53%/0.85 | 2/5 | 3.28 | 0 | noise |
| 37.5% | 85%/30%/2.81 | 21%/54%/0.39 | 52%/54%/0.96 | 2/4 | 2.86 | 0 | noise |
| 40% | 46%/42%/1.08 | 20%/55%/0.36 | 34%/55%/0.61 | 1/4 | 3.28 | 0 | hurts |
| 42.5% | 26%/39%/0.66 | 23%/56%/0.42 | 25%/56%/0.45 | 1/3 | 3.28 | 0 | hurts |
| 45% | 26%/39%/0.67 | 22%/57%/0.38 | 25%/57%/0.43 | 1/3 | 3.28 | 0 | hurts |
| 47.5% | 64%/38%/1.68 | 20%/57%/0.35 | 42%/57%/0.74 | 1/2 | 3.07 | 0 | hurts |
| 50%† | 27%/35%/0.76 | 18%/48%/0.36 | 23%/48%/0.48 | 1/2 | 3.49 | 0 | hurts |
| 55%† | 75%/30%/2.54 | 31%/42%/0.72 | 53%/42%/1.26 | 1/1 | 2.44 | 0 | hurts |
| 60%† | 75%/30%/2.51 | 34%/42%/0.80 | 55%/42%/1.29 | 0/1 | 2.44 | 0 | hurts |
| 65%† | 75%/30%/2.52 | 34%/42%/0.81 | 55%/42%/1.30 | 0/0 | 2.44 | 0 | hurts |
| 70%† | 75%/30%/2.49 | 36%/42%/0.85 | 56%/42%/1.32 | 0/0 | 2.44 | 0 | noise |
| 75%† | 77%/29%/2.68 | 53%/42%/1.26 | 66%/42%/1.57 | 0/0 | 2.44 | 0 | noise |
| 80%† | 78%/29%/2.70 | 53%/42%/1.25 | 66%/42%/1.57 | 0/0 | 2.44 | 0 | noise |
| 85%† | 78%/29%/2.69 | 52%/42%/1.24 | 66%/42%/1.57 | 0/0 | 2.44 | 0 | noise |
| 90%† | 78%/29%/2.69 | 52%/42%/1.23 | 66%/42%/1.56 | 0/0 | 2.44 | 0 | noise |
| 95%† | 77%/29%/2.68 | 51%/42%/1.22 | 65%/42%/1.56 | 0/0 | 2.44 | 0 | noise |
| 100%† | 78%/29%/2.69 | 51%/42%/1.21 | 65%/42%/1.56 | 0/0 | 2.44 | 0 | noise |

IS-selected stop: 37.5% -> IS/OOS Calmar_i 2.81/0.39 vs baseline 2.69/1.19; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: ['80.0%']; 'helps' levels: none.

#### 3x, kill setting 'live' (35%/14d)

No-stop baseline: IS 77%/57%/1.36, OOS 95%/63%/1.56, full 87%/64%/1.37, kills/yr 0.98, liq 0. († = at/after liquidation-equivalent 33.3%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -73%/96%/-0.76 | -71%/94%/-0.75 | -72%/100%/-0.72 | 817/819 | 2.72 | 0 | hurts |
| 0.5% | -69%/95%/-0.73 | -55%/85%/-0.65 | -63%/99%/-0.64 | 726/705 | 2.93 | 0 | hurts |
| 1% | -66%/94%/-0.70 | -44%/86%/-0.51 | -57%/99%/-0.58 | 647/630 | 2.79 | 0 | hurts |
| 1.5% | -69%/95%/-0.73 | -26%/86%/-0.29 | -53%/98%/-0.54 | 577/548 | 2.79 | 0 | hurts |
| 2% | -60%/91%/-0.65 | -23%/86%/-0.26 | -45%/96%/-0.47 | 505/495 | 3.00 | 0 | hurts |
| 3% | -50%/88%/-0.57 | -12%/89%/-0.14 | -35%/93%/-0.37 | 428/398 | 2.37 | 0 | hurts |
| 4% | -33%/82%/-0.41 | 34%/68%/0.50 | -6%/82%/-0.08 | 365/325 | 1.88 | 0 | hurts |
| 5% | -1%/65%/-0.01 | 24%/75%/0.32 | 11%/75%/0.15 | 299/260 | 1.75 | 0 | hurts |
| 6% | -15%/73%/-0.20 | 35%/69%/0.51 | 7%/74%/0.10 | 259/216 | 1.75 | 0 | hurts |
| 7% | -5%/69%/-0.06 | 84%/63%/1.43 | 31%/70%/0.47 | 217/181 | 1.26 | 0 | hurts |
| 8% | 9%/63%/0.15 | 84%/63%/1.35 | 41%/63%/0.66 | 184/155 | 1.33 | 0 | hurts |
| 9% | 3%/65%/0.05 | 68%/61%/1.14 | 30%/68%/0.44 | 153/131 | 1.54 | 0 | hurts |
| 10% | 3%/72%/0.10 | 98%/55%/1.79 | 40%/72%/0.61 | 134/114 | 1.33 | 0 | hurts |
| 12% | 24%/69%/0.38 | 44%/68%/0.64 | 34%/72%/0.48 | 97/84 | 1.05 | 0 | hurts |
| 14% | 51%/62%/0.83 | 77%/64%/1.20 | 64%/64%/1.00 | 69/68 | 1.05 | 0 | noise |
| 16% | 41%/68%/0.60 | 64%/63%/1.06 | 52%/68%/0.78 | 53/51 | 1.19 | 0 | hurts |
| 18% | 42%/57%/0.77 | 126%/53%/2.38 | 79%/59%/1.38 | 42/40 | 0.91 | 0 | hurts |
| 20% | 75%/58%/1.31 | 63%/59%/1.06 | 70%/61%/1.16 | 30/32 | 0.70 | 0 | noise |
| 22.5% | 46%/54%/0.89 | 91%/64%/1.45 | 68%/68%/1.00 | 20/26 | 1.19 | 0 | noise |
| 25% | 66%/58%/1.14 | 96%/58%/1.65 | 81%/58%/1.40 | 14/17 | 0.98 | 0 | noise |
| 27.5% | 70%/59%/1.18 | 78%/57%/1.37 | 75%/59%/1.27 | 10/14 | 0.84 | 0 | noise |
| 30% | 64%/52%/1.23 | 97%/57%/1.69 | 80%/57%/1.40 | 6/11 | 0.98 | 0 | noise |
| 31% | 63%/53%/1.20 | 97%/60%/1.62 | 80%/60%/1.33 | 5/11 | 1.12 | 0 | noise |
| 32.5% | 79%/52%/1.55 | 108%/57%/1.90 | 94%/57%/1.64 | 3/8 | 0.98 | 0 | noise |
| 35%† | 67%/52%/1.27 | 87%/61%/1.43 | 78%/61%/1.27 | 2/7 | 0.98 | 0 | noise |
| 37.5%† | 71%/51%/1.39 | 109%/55%/2.01 | 90%/55%/1.63 | 2/5 | 1.05 | 0 | helps |
| 40%† | 73%/50%/1.47 | 119%/51%/2.37 | 95%/55%/1.74 | 1/4 | 0.98 | 0 | noise |
| 42.5%† | 71%/51%/1.42 | 107%/52%/2.06 | 89%/54%/1.67 | 1/3 | 0.98 | 0 | noise |
| 45%† | 76%/58%/1.32 | 95%/54%/1.77 | 86%/58%/1.50 | 1/3 | 0.98 | 0 | noise |
| 47.5%† | 76%/58%/1.32 | 100%/52%/1.96 | 88%/58%/1.54 | 1/3 | 0.98 | 0 | noise |
| 50%† | 77%/58%/1.32 | 92%/57%/1.63 | 85%/58%/1.47 | 1/2 | 1.05 | 0 | noise |
| 55%† | 76%/58%/1.31 | 95%/56%/1.70 | 86%/58%/1.49 | 1/2 | 0.98 | 0 | noise |
| 60%† | 63%/64%/0.99 | 116%/54%/2.13 | 87%/64%/1.38 | 0/1 | 0.98 | 0 | noise |
| 65%† | 68%/62%/1.11 | 124%/52%/2.39 | 94%/62%/1.54 | 0/1 | 0.98 | 0 | noise |
| 70%† | 66%/62%/1.08 | 128%/53%/2.44 | 95%/62%/1.55 | 0/1 | 0.98 | 0 | noise |
| 75%† | 69%/58%/1.19 | 133%/47%/2.82 | 99%/58%/1.70 | 0/1 | 1.12 | 0 | noise |
| 80%† | 69%/58%/1.19 | 133%/47%/2.80 | 99%/58%/1.69 | 0/0 | 1.12 | 0 | noise |
| 85%† | 68%/59%/1.17 | 132%/47%/2.78 | 98%/59%/1.67 | 0/0 | 1.12 | 0 | noise |
| 90%† | 69%/61%/1.13 | 115%/55%/2.14 | 91%/61%/1.49 | 0/0 | 1.12 | 0 | noise |
| 95%† | 68%/62%/1.11 | 114%/55%/2.12 | 90%/62%/1.47 | 0/0 | 1.12 | 0 | noise |
| 100%† | 58%/60%/0.98 | 143%/54%/2.68 | 96%/60%/1.61 | 0/0 | 1.12 | 0 | noise |

IS-selected stop: 32.5% -> IS/OOS Calmar_i 1.55/1.90 vs baseline 1.36/1.56; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: ['32.5%', '37.5%', '40.0%', '42.5%']; 'helps' levels: ['37.5%'].

#### 3x, kill setting 'off' (off)

No-stop baseline: IS 95%/47%/2.04, OOS 108%/59%/1.87, full 102%/59%/1.75, kills/yr 0.00, liq 0. († = at/after liquidation-equivalent 33.3%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -77%/97%/-0.79 | -75%/96%/-0.78 | -76%/100%/-0.76 | 910/911 | 0.00 | 0 | hurts |
| 0.5% | -76%/97%/-0.78 | -62%/90%/-0.69 | -70%/100%/-0.70 | 808/790 | 0.00 | 0 | hurts |
| 1% | -75%/97%/-0.77 | -31%/83%/-0.36 | -60%/99%/-0.60 | 718/687 | 0.00 | 0 | hurts |
| 1.5% | -71%/96%/-0.74 | -23%/85%/-0.27 | -54%/98%/-0.55 | 642/611 | 0.00 | 0 | hurts |
| 2% | -67%/95%/-0.71 | 1%/81%/0.02 | -44%/97%/-0.46 | 576/540 | 0.00 | 0 | hurts |
| 3% | -46%/84%/-0.53 | 15%/79%/0.19 | -23%/86%/-0.26 | 466/426 | 0.00 | 0 | hurts |
| 4% | -28%/79%/-0.34 | 36%/72%/0.56 | -3%/80%/-0.02 | 385/338 | 0.00 | 0 | hurts |
| 5% | -19%/74%/-0.22 | 50%/68%/0.77 | 9%/75%/0.16 | 321/275 | 0.00 | 0 | hurts |
| 6% | -1%/69%/0.02 | 66%/63%/1.07 | 27%/71%/0.41 | 268/228 | 0.00 | 0 | hurts |
| 7% | -5%/69%/-0.05 | 84%/61%/1.37 | 31%/69%/0.47 | 228/192 | 0.00 | 0 | hurts |
| 8% | -1%/68%/-0.01 | 88%/61%/1.45 | 36%/68%/0.53 | 193/163 | 0.00 | 0 | hurts |
| 9% | 9%/63%/0.15 | 95%/61%/1.60 | 45%/65%/0.71 | 161/140 | 0.00 | 0 | hurts |
| 10% | 17%/63%/0.28 | 94%/61%/1.61 | 50%/67%/0.75 | 139/120 | 0.00 | 0 | hurts |
| 12% | 34%/58%/0.57 | 80%/64%/1.28 | 55%/64%/0.87 | 100/92 | 0.00 | 0 | hurts |
| 14% | 49%/56%/0.88 | 85%/60%/1.46 | 67%/62%/1.10 | 74/69 | 0.00 | 0 | hurts |
| 16% | 59%/53%/1.15 | 86%/58%/1.52 | 73%/62%/1.20 | 56/53 | 0.00 | 0 | hurts |
| 18% | 66%/52%/1.28 | 79%/59%/1.35 | 74%/60%/1.23 | 42/42 | 0.00 | 0 | hurts |
| 20% | 70%/51%/1.37 | 75%/59%/1.29 | 74%/60%/1.23 | 31/33 | 0.00 | 0 | hurts |
| 22.5% | 67%/51%/1.33 | 73%/61%/1.22 | 71%/61%/1.18 | 22/26 | 0.00 | 0 | hurts |
| 25% | 70%/51%/1.39 | 79%/59%/1.37 | 76%/60%/1.30 | 15/20 | 0.00 | 0 | hurts |
| 27.5% | 81%/50%/1.64 | 83%/57%/1.47 | 83%/57%/1.47 | 10/15 | 0.00 | 0 | hurts |
| 30% | 86%/50%/1.73 | 82%/57%/1.46 | 86%/57%/1.51 | 6/11 | 0.00 | 0 | hurts |
| 31% | 85%/50%/1.69 | 80%/58%/1.40 | 84%/58%/1.46 | 6/11 | 0.00 | 0 | hurts |
| 32.5% | 87%/50%/1.75 | 89%/56%/1.63 | 90%/56%/1.62 | 4/8 | 0.00 | 0 | hurts |
| 35%† | 90%/49%/1.83 | 94%/56%/1.72 | 93%/56%/1.70 | 3/6 | 0.00 | 0 | hurts |
| 37.5%† | 95%/48%/1.98 | 98%/56%/1.80 | 98%/56%/1.78 | 2/5 | 0.00 | 0 | hurts |
| 40%† | 96%/47%/2.04 | 96%/56%/1.75 | 98%/56%/1.76 | 1/4 | 0.00 | 0 | hurts |
| 42.5%† | 95%/48%/2.01 | 97%/56%/1.78 | 98%/56%/1.77 | 1/3 | 0.00 | 0 | hurts |
| 45%† | 96%/48%/2.03 | 95%/56%/1.73 | 97%/56%/1.75 | 1/3 | 0.00 | 0 | hurts |
| 47.5%† | 94%/48%/2.01 | 93%/56%/1.70 | 95%/56%/1.72 | 1/2 | 0.00 | 0 | hurts |
| 50%† | 94%/48%/1.99 | 93%/56%/1.70 | 95%/56%/1.72 | 1/2 | 0.00 | 0 | hurts |
| 55%† | 93%/48%/1.97 | 94%/56%/1.71 | 95%/56%/1.71 | 1/2 | 0.00 | 0 | hurts |
| 60%† | 92%/48%/1.94 | 97%/56%/1.78 | 96%/56%/1.73 | 0/1 | 0.00 | 0 | noise |
| 65%† | 94%/48%/1.98 | 107%/58%/1.87 | 101%/58%/1.76 | 0/1 | 0.00 | 0 | noise |
| 70%† | 92%/48%/1.95 | 107%/58%/1.89 | 100%/58%/1.75 | 0/1 | 0.00 | 0 | noise |
| 75%† | 91%/48%/1.92 | 108%/58%/1.89 | 100%/58%/1.75 | 0/1 | 0.00 | 0 | noise |
| 80%† | 91%/49%/1.92 | 108%/58%/1.88 | 100%/58%/1.74 | 0/0 | 0.00 | 0 | noise |
| 85%† | 91%/49%/1.90 | 107%/58%/1.86 | 99%/58%/1.72 | 0/0 | 0.00 | 0 | noise |
| 90%† | 92%/49%/1.91 | 106%/58%/1.84 | 99%/58%/1.72 | 0/0 | 0.00 | 0 | hurts |
| 95%† | 91%/49%/1.90 | 105%/59%/1.82 | 99%/59%/1.70 | 0/0 | 0.00 | 0 | hurts |
| 100%† | 91%/49%/1.90 | 104%/59%/1.80 | 99%/59%/1.69 | 0/0 | 0.00 | 0 | hurts |

IS-selected stop: 40.0% -> IS/OOS Calmar_i 2.04/1.75 vs baseline 2.04/1.87; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: none; 'helps' levels: none.

#### 3x, kill setting 'selected' (20%/1d)

No-stop baseline: IS 126%/46%/2.72, OOS 121%/55%/2.19, full 126%/55%/2.27, kills/yr 3.14, liq 0. († = at/after liquidation-equivalent 33.3%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -78%/98%/-0.80 | -77%/97%/-0.80 | -78%/100%/-0.78 | 923/924 | 6.49 | 0 | hurts |
| 0.5% | -80%/98%/-0.81 | -62%/91%/-0.68 | -73%/100%/-0.73 | 822/798 | 7.26 | 0 | hurts |
| 1% | -79%/98%/-0.80 | -13%/67%/-0.19 | -59%/99%/-0.59 | 729/690 | 6.42 | 0 | hurts |
| 1.5% | -74%/97%/-0.76 | -29%/82%/-0.35 | -58%/99%/-0.58 | 641/624 | 7.68 | 0 | hurts |
| 2% | -59%/92%/-0.64 | 23%/74%/0.31 | -31%/92%/-0.33 | 581/544 | 6.35 | 0 | hurts |
| 3% | -49%/88%/-0.56 | -16%/85%/-0.19 | -35%/93%/-0.38 | 486/424 | 7.68 | 0 | hurts |
| 4% | -44%/90%/-0.49 | 35%/64%/0.55 | -14%/90%/-0.16 | 396/338 | 6.49 | 0 | hurts |
| 5% | -41%/87%/-0.46 | 47%/74%/0.64 | -8%/88%/-0.09 | 329/276 | 6.35 | 0 | hurts |
| 6% | -42%/88%/-0.48 | 126%/57%/2.20 | 12%/88%/0.14 | 273/229 | 5.51 | 0 | hurts |
| 7% | -21%/74%/-0.28 | 47%/68%/0.69 | 7%/74%/0.10 | 229/193 | 6.14 | 0 | hurts |
| 8% | -25%/79%/-0.32 | 109%/59%/1.86 | 23%/79%/0.29 | 197/158 | 5.72 | 0 | hurts |
| 9% | -7%/73%/-0.09 | 51%/62%/0.82 | 18%/73%/0.25 | 171/137 | 5.51 | 0 | hurts |
| 10% | -4%/76%/-0.05 | 58%/61%/0.96 | 23%/76%/0.30 | 141/122 | 5.72 | 0 | hurts |
| 12% | 18%/66%/0.27 | 83%/59%/1.41 | 47%/66%/0.71 | 98/89 | 5.31 | 0 | hurts |
| 14% | 2%/71%/0.02 | 143%/48%/2.94 | 55%/72%/0.77 | 73/69 | 5.03 | 0 | hurts |
| 16% | 37%/50%/0.74 | 85%/54%/1.56 | 59%/54%/1.09 | 58/50 | 4.82 | 0 | hurts |
| 18% | 71%/53%/1.35 | 37%/69%/0.53 | 55%/69%/0.80 | 39/37 | 4.33 | 0 | hurts |
| 20% | 43%/62%/0.69 | 37%/71%/0.52 | 41%/71%/0.58 | 29/32 | 4.75 | 0 | hurts |
| 22.5% | 34%/58%/0.59 | 79%/65%/1.22 | 55%/65%/0.85 | 22/24 | 4.40 | 0 | hurts |
| 25% | 37%/60%/0.62 | 112%/52%/2.14 | 71%/60%/1.17 | 13/19 | 4.40 | 0 | hurts |
| 27.5% | 69%/53%/1.30 | 77%/65%/1.19 | 74%/65%/1.15 | 11/13 | 4.40 | 0 | hurts |
| 30% | 75%/47%/1.63 | 49%/67%/0.73 | 64%/67%/0.95 | 8/10 | 4.47 | 0 | hurts |
| 31% | 58%/53%/1.10 | 28%/67%/0.42 | 44%/67%/0.66 | 8/10 | 4.68 | 0 | hurts |
| 32.5% | 88%/47%/1.89 | 69%/61%/1.12 | 80%/61%/1.31 | 5/8 | 4.19 | 0 | hurts |
| 35%† | 103%/48%/2.19 | 90%/55%/1.63 | 98%/55%/1.78 | 2/6 | 4.12 | 0 | hurts |
| 37.5%† | 111%/47%/2.36 | 133%/55%/2.42 | 123%/55%/2.24 | 2/4 | 3.70 | 0 | hurts |
| 40%† | 114%/48%/2.40 | 109%/55%/1.97 | 113%/55%/2.05 | 1/3 | 3.91 | 0 | hurts |
| 42.5%† | 115%/47%/2.45 | 117%/54%/2.17 | 117%/54%/2.18 | 1/3 | 3.70 | 0 | hurts |
| 45%† | 115%/47%/2.45 | 112%/54%/2.09 | 115%/54%/2.14 | 1/2 | 3.70 | 0 | hurts |
| 47.5%† | 116%/47%/2.50 | 102%/51%/2.00 | 111%/51%/2.19 | 1/2 | 3.84 | 0 | hurts |
| 50%† | 116%/47%/2.48 | 87%/54%/1.62 | 103%/54%/1.92 | 1/2 | 3.84 | 0 | hurts |
| 55%† | 96%/48%/2.02 | 89%/54%/1.65 | 94%/54%/1.75 | 1/2 | 4.05 | 0 | hurts |
| 60%† | 106%/47%/2.27 | 100%/51%/1.97 | 105%/51%/2.06 | 0/1 | 3.35 | 0 | noise |
| 65%† | 106%/48%/2.26 | 146%/54%/2.70 | 126%/54%/2.32 | 0/1 | 3.28 | 0 | noise |
| 70%† | 105%/48%/2.25 | 145%/54%/2.70 | 125%/54%/2.32 | 0/0 | 3.28 | 0 | noise |
| 75%† | 125%/46%/2.71 | 147%/56%/2.61 | 137%/56%/2.44 | 0/0 | 3.14 | 0 | noise |
| 80%† | 126%/46%/2.72 | 146%/56%/2.60 | 138%/56%/2.45 | 0/0 | 3.14 | 0 | noise |
| 85%† | 126%/46%/2.71 | 137%/56%/2.44 | 133%/56%/2.37 | 0/0 | 3.35 | 0 | noise |
| 90%† | 126%/47%/2.70 | 137%/56%/2.43 | 133%/56%/2.36 | 0/0 | 3.35 | 0 | noise |
| 95%† | 125%/47%/2.69 | 136%/56%/2.41 | 132%/56%/2.35 | 0/0 | 3.35 | 0 | noise |
| 100%† | 126%/46%/2.72 | 135%/56%/2.40 | 132%/56%/2.35 | 0/0 | 3.35 | 0 | noise |

IS-selected stop: 80.0% -> IS/OOS Calmar_i 2.72/2.60 vs baseline 2.72/2.19; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: ['80.0%']; 'helps' levels: none.

#### 4x, kill setting 'live' (35%/14d)

No-stop baseline: IS 55%/65%/0.84, OOS 105%/80%/1.31, full 79%/80%/0.99, kills/yr 1.95, liq 0. († = at/after liquidation-equivalent 25.0%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -82%/99%/-0.83 | -78%/97%/-0.81 | -80%/100%/-0.80 | 793/795 | 3.77 | 0 | hurts |
| 0.5% | -81%/98%/-0.83 | -70%/94%/-0.74 | -77%/100%/-0.77 | 706/689 | 3.77 | 0 | hurts |
| 1% | -73%/96%/-0.76 | -50%/87%/-0.58 | -65%/99%/-0.65 | 640/597 | 3.49 | 0 | hurts |
| 1.5% | -64%/93%/-0.69 | -49%/94%/-0.52 | -58%/99%/-0.58 | 559/530 | 3.42 | 0 | hurts |
| 2% | -76%/98%/-0.78 | -12%/88%/-0.14 | -55%/99%/-0.56 | 506/460 | 3.98 | 0 | hurts |
| 3% | -55%/93%/-0.59 | -25%/95%/-0.27 | -43%/97%/-0.44 | 420/384 | 3.56 | 0 | hurts |
| 4% | -26%/82%/-0.32 | -2%/92%/-0.02 | -14%/92%/-0.15 | 349/299 | 2.93 | 0 | hurts |
| 5% | -34%/86%/-0.39 | -16%/91%/-0.18 | -25%/92%/-0.27 | 294/248 | 3.00 | 0 | hurts |
| 6% | 19%/71%/0.26 | -4%/92%/-0.05 | 8%/92%/0.08 | 239/209 | 2.72 | 0 | hurts |
| 7% | -14%/86%/-0.16 | 78%/71%/1.10 | 23%/86%/0.27 | 206/178 | 2.37 | 0 | hurts |
| 8% | -10%/80%/-0.10 | 49%/82%/0.60 | 15%/87%/0.18 | 172/154 | 2.51 | 0 | hurts |
| 9% | -22%/86%/-0.26 | 60%/79%/0.76 | 10%/88%/0.11 | 142/134 | 2.65 | 0 | hurts |
| 10% | 16%/73%/0.22 | 60%/75%/0.81 | 37%/75%/0.49 | 127/107 | 2.02 | 0 | hurts |
| 12% | 15%/76%/0.21 | 40%/77%/0.52 | 27%/79%/0.35 | 91/87 | 2.09 | 0 | noise |
| 14% | 68%/72%/0.96 | 52%/79%/0.66 | 62%/79%/0.79 | 68/67 | 1.88 | 0 | noise |
| 16% | 71%/69%/1.08 | 68%/69%/0.99 | 71%/73%/0.98 | 52/50 | 1.54 | 0 | noise |
| 18% | 69%/66%/1.03 | 43%/70%/0.62 | 58%/70%/0.82 | 36/38 | 2.23 | 0 | noise |
| 20% | 109%/62%/1.82 | 36%/66%/0.55 | 72%/69%/1.06 | 28/30 | 1.75 | 0 | noise |
| 22.5% | 110%/62%/1.76 | 14%/77%/0.19 | 59%/77%/0.77 | 19/23 | 2.37 | 0 | noise |
| 25%† | 80%/57%/1.40 | 43%/73%/0.59 | 63%/73%/0.87 | 14/17 | 2.23 | 0 | noise |
| 27.5%† | 44%/62%/0.72 | 49%/76%/0.64 | 48%/76%/0.63 | 10/15 | 2.02 | 0 | noise |
| 30%† | 27%/74%/0.37 | 2%/72%/0.03 | 16%/74%/0.22 | 5/12 | 2.86 | 0 | noise |
| 31%† | 59%/69%/0.85 | 9%/72%/0.12 | 34%/73%/0.47 | 4/10 | 2.65 | 0 | noise |
| 32.5%† | 60%/69%/0.87 | 7%/79%/0.09 | 34%/79%/0.43 | 4/8 | 2.44 | 0 | noise |
| 35%† | 73%/77%/0.95 | 4%/83%/0.04 | 37%/83%/0.44 | 3/5 | 2.44 | 0 | noise |
| 37.5%† | 72%/65%/1.11 | 62%/80%/0.77 | 69%/80%/0.86 | 2/4 | 2.02 | 0 | noise |
| 40%† | 105%/64%/1.65 | 38%/75%/0.51 | 72%/75%/0.96 | 1/3 | 2.02 | 0 | noise |
| 42.5%† | 102%/65%/1.59 | 65%/80%/0.82 | 85%/80%/1.07 | 1/3 | 2.02 | 0 | noise |
| 45%† | 47%/67%/0.70 | 62%/80%/0.77 | 56%/80%/0.70 | 1/2 | 2.16 | 0 | noise |
| 47.5%† | 47%/66%/0.71 | 58%/80%/0.73 | 54%/80%/0.68 | 1/2 | 2.16 | 0 | hurts |
| 50%† | 46%/66%/0.70 | 56%/80%/0.70 | 52%/80%/0.66 | 1/2 | 2.16 | 0 | hurts |
| 55%† | 45%/66%/0.67 | 3%/84%/0.03 | 24%/84%/0.29 | 1/1 | 2.58 | 0 | noise |
| 60%† | 97%/64%/1.54 | 5%/84%/0.06 | 47%/84%/0.56 | 1/1 | 2.44 | 0 | noise |
| 65%† | 84%/64%/1.32 | 96%/80%/1.20 | 92%/80%/1.15 | 0/1 | 1.81 | 0 | noise |
| 70%† | 83%/64%/1.29 | 93%/80%/1.17 | 90%/80%/1.12 | 0/1 | 1.81 | 0 | noise |
| 75%† | 78%/63%/1.25 | 89%/80%/1.11 | 85%/80%/1.07 | 0/1 | 2.02 | 0 | noise |
| 80%† | 55%/65%/0.84 | 100%/80%/1.26 | 77%/80%/0.97 | 0/0 | 1.95 | 0 | noise |
| 85%† | 55%/66%/0.84 | 100%/80%/1.25 | 77%/80%/0.97 | 0/0 | 1.95 | 0 | noise |
| 90%† | 54%/66%/0.83 | 99%/80%/1.24 | 76%/80%/0.96 | 0/0 | 1.95 | 0 | noise |
| 95%† | 54%/66%/0.82 | 82%/80%/1.03 | 69%/80%/0.87 | 0/0 | 2.16 | 0 | noise |
| 100%† | 55%/65%/0.84 | 81%/80%/1.02 | 69%/80%/0.87 | 0/0 | 2.16 | 0 | noise |

IS-selected stop: 20.0% -> IS/OOS Calmar_i 1.82/0.55 vs baseline 0.84/1.31; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: none; 'helps' levels: none.

#### 4x, kill setting 'off' (off)

No-stop baseline: IS 126%/58%/2.18, OOS 132%/72%/1.88, full 129%/72%/1.82, kills/yr 0.00, liq 0. († = at/after liquidation-equivalent 25.0%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -86%/99%/-0.87 | -85%/99%/-0.86 | -85%/100%/-0.85 | 910/911 | 0.00 | 0 | hurts |
| 0.5% | -85%/99%/-0.86 | -74%/96%/-0.77 | -81%/100%/-0.81 | 808/790 | 0.00 | 0 | hurts |
| 1% | -85%/99%/-0.86 | -43%/92%/-0.46 | -72%/100%/-0.72 | 718/687 | 0.00 | 0 | hurts |
| 1.5% | -82%/99%/-0.83 | -35%/93%/-0.38 | -67%/100%/-0.67 | 642/611 | 0.00 | 0 | hurts |
| 2% | -79%/98%/-0.80 | -9%/90%/-0.10 | -58%/99%/-0.59 | 576/540 | 0.00 | 0 | hurts |
| 3% | -59%/93%/-0.63 | 4%/89%/0.05 | -37%/95%/-0.39 | 466/426 | 0.00 | 0 | hurts |
| 4% | -41%/89%/-0.45 | 30%/83%/0.41 | -14%/91%/-0.15 | 385/338 | 0.00 | 0 | hurts |
| 5% | -30%/85%/-0.33 | 48%/79%/0.63 | 1%/85%/0.03 | 321/275 | 0.00 | 0 | hurts |
| 6% | -9%/80%/-0.10 | 70%/75%/0.96 | 23%/82%/0.30 | 268/228 | 0.00 | 0 | hurts |
| 7% | -14%/81%/-0.16 | 96%/73%/1.32 | 28%/81%/0.36 | 228/192 | 0.00 | 0 | hurts |
| 8% | -9%/80%/-0.11 | 101%/72%/1.40 | 34%/80%/0.43 | 193/163 | 0.00 | 0 | hurts |
| 9% | 4%/76%/0.05 | 112%/73%/1.56 | 48%/77%/0.62 | 161/140 | 0.00 | 0 | hurts |
| 10% | 14%/75%/0.18 | 111%/72%/1.60 | 54%/79%/0.69 | 139/120 | 0.00 | 0 | hurts |
| 12% | 35%/71%/0.50 | 92%/75%/1.23 | 61%/77%/0.81 | 100/92 | 0.00 | 0 | hurts |
| 14% | 58%/67%/0.85 | 99%/71%/1.43 | 78%/73%/1.08 | 74/69 | 0.00 | 0 | hurts |
| 16% | 71%/64%/1.15 | 101%/69%/1.49 | 87%/72%/1.21 | 56/53 | 0.00 | 0 | hurts |
| 18% | 82%/64%/1.30 | 90%/70%/1.29 | 88%/72%/1.22 | 42/42 | 0.00 | 0 | hurts |
| 20% | 87%/62%/1.40 | 84%/70%/1.21 | 88%/71%/1.23 | 31/33 | 0.00 | 0 | hurts |
| 22.5% | 83%/63%/1.34 | 81%/72%/1.15 | 84%/72%/1.18 | 22/26 | 0.00 | 0 | hurts |
| 25%† | 88%/62%/1.42 | 91%/71%/1.31 | 91%/71%/1.30 | 15/20 | 0.00 | 0 | hurts |
| 27.5%† | 105%/61%/1.72 | 95%/69%/1.40 | 102%/69%/1.48 | 10/15 | 0.00 | 0 | hurts |
| 30%† | 112%/61%/1.83 | 94%/70%/1.38 | 105%/70%/1.52 | 6/11 | 0.00 | 0 | hurts |
| 31%† | 110%/62%/1.78 | 90%/70%/1.32 | 102%/70%/1.47 | 6/11 | 0.00 | 0 | hurts |
| 32.5%† | 113%/61%/1.86 | 105%/69%/1.58 | 111%/69%/1.65 | 4/8 | 0.00 | 0 | hurts |
| 35%† | 117%/60%/1.94 | 112%/69%/1.67 | 117%/69%/1.73 | 3/6 | 0.00 | 0 | hurts |
| 37.5%† | 125%/59%/2.11 | 118%/69%/1.76 | 124%/69%/1.82 | 2/5 | 0.00 | 0 | hurts |
| 40%† | 127%/59%/2.18 | 114%/69%/1.70 | 123%/69%/1.81 | 1/4 | 0.00 | 0 | hurts |
| 42.5%† | 125%/59%/2.14 | 116%/69%/1.73 | 123%/69%/1.81 | 1/3 | 0.00 | 0 | hurts |
| 45%† | 126%/59%/2.17 | 112%/69%/1.68 | 121%/69%/1.79 | 1/3 | 0.00 | 0 | hurts |
| 47.5%† | 124%/59%/2.14 | 110%/69%/1.64 | 119%/69%/1.75 | 1/2 | 0.00 | 0 | hurts |
| 50%† | 124%/59%/2.12 | 110%/69%/1.64 | 119%/69%/1.74 | 1/2 | 0.00 | 0 | hurts |
| 55%† | 123%/59%/2.10 | 111%/69%/1.65 | 118%/69%/1.74 | 1/2 | 0.00 | 0 | hurts |
| 60%† | 121%/59%/2.06 | 115%/69%/1.72 | 120%/69%/1.76 | 0/1 | 0.00 | 0 | hurts |
| 65%† | 123%/59%/2.11 | 130%/71%/1.88 | 127%/71%/1.82 | 0/1 | 0.00 | 0 | noise |
| 70%† | 121%/59%/2.08 | 130%/71%/1.89 | 127%/71%/1.81 | 0/1 | 0.00 | 0 | noise |
| 75%† | 120%/60%/2.04 | 131%/71%/1.89 | 126%/71%/1.81 | 0/1 | 0.00 | 0 | noise |
| 80%† | 120%/60%/2.04 | 130%/71%/1.88 | 126%/71%/1.80 | 0/0 | 0.00 | 0 | noise |
| 85%† | 119%/60%/2.02 | 129%/71%/1.86 | 125%/71%/1.78 | 0/0 | 0.00 | 0 | noise |
| 90%† | 120%/60%/2.04 | 128%/71%/1.84 | 125%/71%/1.78 | 0/0 | 0.00 | 0 | hurts |
| 95%† | 119%/60%/2.02 | 127%/71%/1.82 | 124%/71%/1.76 | 0/0 | 0.00 | 0 | hurts |
| 100%† | 120%/60%/2.02 | 125%/71%/1.79 | 123%/71%/1.75 | 0/0 | 0.00 | 0 | hurts |

IS-selected stop: 40.0% -> IS/OOS Calmar_i 2.18/1.70 vs baseline 2.18/1.88; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: none; 'helps' levels: none.

#### 4x, kill setting 'selected' (15%/30d)

No-stop baseline: IS 156%/44%/3.58, OOS 38%/69%/0.56, full 93%/69%/1.36, kills/yr 5.65, liq 0. († = at/after liquidation-equivalent 25.0%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -66%/93%/-0.70 | -64%/90%/-0.71 | -65%/99%/-0.65 | 485/484 | 6.07 | 0 | hurts |
| 0.5% | -64%/92%/-0.69 | -37%/66%/-0.56 | -53%/97%/-0.54 | 406/387 | 6.28 | 0 | hurts |
| 1% | -63%/92%/-0.68 | -22%/71%/-0.30 | -47%/96%/-0.49 | 342/308 | 6.70 | 0 | hurts |
| 1.5% | -44%/77%/-0.57 | -2%/80%/-0.03 | -27%/87%/-0.31 | 303/288 | 6.84 | 0 | hurts |
| 2% | -53%/86%/-0.62 | -14%/58%/-0.24 | -38%/92%/-0.41 | 274/245 | 6.70 | 0 | hurts |
| 3% | -25%/80%/-0.32 | -44%/84%/-0.52 | -34%/93%/-0.37 | 213/177 | 7.26 | 0 | hurts |
| 4% | -44%/85%/-0.52 | -32%/75%/-0.43 | -38%/94%/-0.40 | 187/136 | 7.05 | 0 | hurts |
| 5% | -37%/81%/-0.45 | 15%/62%/0.25 | -16%/81%/-0.18 | 150/115 | 7.26 | 0 | hurts |
| 6% | -1%/64%/-0.01 | 38%/62%/0.62 | 17%/68%/0.26 | 135/112 | 6.07 | 0 | noise |
| 7% | -16%/63%/-0.25 | -9%/62%/-0.15 | -12%/76%/-0.16 | 95/95 | 6.91 | 0 | noise |
| 8% | 3%/47%/0.07 | 81%/55%/1.47 | 37%/55%/0.67 | 95/93 | 6.21 | 0 | noise |
| 9% | -2%/65%/-0.02 | 48%/60%/0.81 | 21%/76%/0.28 | 78/80 | 6.28 | 0 | noise |
| 10% | 22%/61%/0.36 | -2%/61%/-0.02 | 11%/66%/0.17 | 64/62 | 6.21 | 0 | noise |
| 12% | 18%/54%/0.33 | -4%/53%/-0.08 | 8%/64%/0.12 | 45/48 | 6.42 | 0 | noise |
| 14% | 48%/47%/1.04 | 8%/67%/0.12 | 29%/77%/0.38 | 36/30 | 6.28 | 0 | hurts |
| 16% | 61%/61%/0.99 | 43%/66%/0.65 | 54%/66%/0.82 | 29/21 | 6.07 | 0 | noise |
| 18% | 7%/63%/0.12 | 8%/52%/0.15 | 9%/70%/0.12 | 19/16 | 6.28 | 0 | noise |
| 20% | 85%/59%/1.45 | 57%/64%/0.89 | 74%/64%/1.15 | 14/15 | 5.58 | 0 | noise |
| 22.5% | -4%/69%/-0.05 | 60%/69%/0.87 | 23%/69%/0.33 | 10/12 | 6.28 | 0 | noise |
| 25%† | -10%/72%/-0.13 | 50%/68%/0.74 | 15%/72%/0.21 | 7/8 | 6.28 | 0 | noise |
| 27.5%† | 15%/55%/0.27 | 31%/63%/0.49 | 22%/63%/0.35 | 5/7 | 6.28 | 0 | noise |
| 30%† | 127%/43%/2.94 | 27%/63%/0.43 | 72%/63%/1.15 | 5/5 | 5.86 | 0 | noise |
| 31%† | 130%/43%/3.02 | 35%/67%/0.52 | 78%/67%/1.17 | 3/5 | 5.86 | 0 | hurts |
| 32.5%† | 124%/43%/2.89 | 40%/67%/0.60 | 79%/67%/1.18 | 3/4 | 5.86 | 0 | hurts |
| 35%† | 119%/49%/2.41 | 32%/67%/0.48 | 74%/67%/1.11 | 2/2 | 5.86 | 0 | hurts |
| 37.5%† | 125%/50%/2.50 | 30%/67%/0.45 | 75%/67%/1.12 | 1/3 | 5.86 | 0 | hurts |
| 40%† | 148%/44%/3.40 | 27%/67%/0.40 | 82%/67%/1.23 | 1/2 | 5.65 | 0 | hurts |
| 42.5%† | 153%/44%/3.50 | 28%/67%/0.41 | 85%/67%/1.27 | 1/2 | 5.65 | 0 | hurts |
| 45%† | 156%/44%/3.57 | 27%/67%/0.41 | 86%/67%/1.28 | 1/1 | 5.65 | 0 | noise |
| 47.5%† | 155%/44%/3.56 | 41%/67%/0.61 | 95%/67%/1.42 | 1/1 | 5.65 | 0 | noise |
| 50%† | 155%/44%/3.54 | 39%/67%/0.58 | 93%/67%/1.39 | 1/1 | 5.65 | 0 | noise |
| 55%† | 155%/44%/3.55 | 21%/67%/0.32 | 81%/67%/1.21 | 1/1 | 5.86 | 0 | noise |
| 60%† | 154%/44%/3.53 | 41%/67%/0.61 | 94%/67%/1.41 | 1/0 | 5.65 | 0 | noise |
| 65%† | 156%/44%/3.58 | 33%/67%/0.50 | 90%/67%/1.35 | 0/0 | 5.65 | 0 | noise |
| 70%† | 156%/44%/3.58 | 34%/67%/0.50 | 90%/67%/1.35 | 0/0 | 5.65 | 0 | noise |
| 75%† | 156%/44%/3.58 | 38%/69%/0.56 | 93%/69%/1.36 | 0/0 | 5.65 | 0 | noise |
| 80%† | 156%/44%/3.58 | 38%/69%/0.56 | 93%/69%/1.36 | 0/0 | 5.65 | 0 | noise |
| 85%† | 156%/44%/3.58 | 38%/69%/0.56 | 93%/69%/1.36 | 0/0 | 5.65 | 0 | noise |
| 90%† | 156%/44%/3.58 | 38%/69%/0.56 | 93%/69%/1.36 | 0/0 | 5.65 | 0 | noise |
| 95%† | 156%/44%/3.58 | 38%/69%/0.56 | 93%/69%/1.36 | 0/0 | 5.65 | 0 | noise |
| 100%† | 156%/44%/3.58 | 38%/69%/0.56 | 93%/69%/1.36 | 0/0 | 5.65 | 0 | noise |

IS-selected stop: 65.0% -> IS/OOS Calmar_i 3.58/0.50 vs baseline 3.58/0.56; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: none; 'helps' levels: none.

### D. Crash filter OFF (BTC filter disabled) stop curves for the three IS-best (lev, kill) pairs

3x 20%/1d: baseline crash-ON IS/OOS Calmar_i 2.72/2.19; crash-OFF 1.08/1.50 (full CAGR 126% vs 76%).

#### crash OFF, 3x, kill 20%/1d

No-stop baseline: IS 57%/53%/1.08, OOS 95%/63%/1.50, full 76%/63%/1.20, kills/yr 4.61, liq 0. († = at/after liquidation-equivalent 33.3%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -80%/98%/-0.82 | -78%/97%/-0.81 | -79%/100%/-0.79 | 989/990 | 6.91 | 0 | hurts |
| 0.5% | -77%/97%/-0.79 | -65%/92%/-0.70 | -72%/100%/-0.72 | 873/834 | 6.91 | 0 | hurts |
| 1% | -76%/98%/-0.78 | -46%/89%/-0.51 | -64%/100%/-0.65 | 761/739 | 7.47 | 0 | hurts |
| 1.5% | -83%/99%/-0.84 | -25%/90%/-0.28 | -66%/100%/-0.66 | 691/667 | 9.42 | 0 | hurts |
| 2% | -80%/99%/-0.81 | -21%/88%/-0.24 | -61%/99%/-0.62 | 619/578 | 8.17 | 0 | hurts |
| 3% | -71%/97%/-0.74 | -8%/80%/-0.09 | -50%/98%/-0.51 | 516/454 | 8.45 | 0 | hurts |
| 4% | -58%/92%/-0.64 | -17%/86%/-0.19 | -42%/96%/-0.44 | 418/371 | 8.80 | 0 | hurts |
| 5% | -64%/94%/-0.68 | 2%/76%/0.02 | -41%/94%/-0.43 | 361/302 | 8.66 | 0 | hurts |
| 6% | -63%/93%/-0.67 | 48%/71%/0.67 | -27%/93%/-0.29 | 306/254 | 7.89 | 0 | hurts |
| 7% | -42%/81%/-0.52 | 76%/69%/1.09 | -1%/81%/-0.01 | 243/209 | 6.77 | 0 | hurts |
| 8% | -43%/79%/-0.54 | 49%/72%/0.68 | -9%/82%/-0.11 | 219/183 | 7.19 | 0 | hurts |
| 9% | -38%/76%/-0.50 | -9%/85%/-0.11 | -25%/88%/-0.29 | 190/162 | 7.61 | 0 | hurts |
| 10% | -35%/75%/-0.46 | 50%/75%/0.67 | -2%/77%/-0.03 | 157/134 | 6.98 | 0 | hurts |
| 12% | -15%/68%/-0.22 | 27%/64%/0.42 | 4%/68%/0.06 | 121/98 | 6.70 | 0 | hurts |
| 14% | -6%/67%/-0.09 | 112%/66%/1.69 | 40%/68%/0.58 | 89/74 | 6.00 | 0 | hurts |
| 16% | 23%/57%/0.40 | 44%/69%/0.63 | 34%/69%/0.49 | 67/57 | 5.79 | 0 | hurts |
| 18% | -10%/66%/-0.15 | 83%/64%/1.29 | 26%/66%/0.39 | 51/48 | 6.35 | 0 | hurts |
| 20% | 30%/58%/0.52 | 26%/69%/0.38 | 30%/69%/0.43 | 39/38 | 5.58 | 0 | hurts |
| 22.5% | 56%/53%/1.07 | 41%/76%/0.54 | 50%/76%/0.66 | 31/26 | 5.51 | 0 | noise |
| 25% | 73%/52%/1.41 | 82%/74%/1.11 | 79%/74%/1.07 | 19/21 | 5.03 | 0 | noise |
| 27.5% | 69%/53%/1.32 | 91%/63%/1.43 | 81%/63%/1.28 | 15/16 | 4.68 | 0 | noise |
| 30% | 74%/51%/1.46 | 69%/76%/0.91 | 74%/76%/0.96 | 10/11 | 5.03 | 0 | noise |
| 31% | 70%/51%/1.37 | 63%/79%/0.80 | 68%/79%/0.87 | 9/11 | 5.24 | 0 | noise |
| 32.5% | 45%/53%/0.85 | 42%/75%/0.56 | 45%/75%/0.60 | 8/10 | 5.58 | 0 | noise |
| 35%† | 78%/51%/1.52 | 39%/68%/0.57 | 60%/68%/0.87 | 5/7 | 4.82 | 0 | noise |
| 37.5%† | 48%/62%/0.77 | 60%/65%/0.93 | 55%/65%/0.85 | 3/5 | 5.31 | 0 | noise |
| 40%† | 32%/56%/0.56 | 80%/65%/1.22 | 54%/65%/0.83 | 2/4 | 5.17 | 0 | noise |
| 42.5%† | 63%/54%/1.15 | 63%/64%/0.99 | 65%/64%/1.01 | 2/3 | 4.75 | 0 | hurts |
| 45%† | 56%/55%/1.03 | 62%/65%/0.95 | 61%/65%/0.93 | 1/3 | 4.82 | 0 | hurts |
| 47.5%† | 52%/55%/0.94 | 41%/66%/0.62 | 48%/66%/0.73 | 1/3 | 5.17 | 0 | noise |
| 50%† | 55%/56%/0.99 | 62%/65%/0.95 | 60%/65%/0.92 | 1/2 | 4.89 | 0 | noise |
| 55%† | 59%/53%/1.12 | 54%/63%/0.85 | 58%/63%/0.92 | 1/1 | 4.89 | 0 | noise |
| 60%† | 60%/53%/1.13 | 65%/64%/1.03 | 64%/64%/1.00 | 1/1 | 4.75 | 0 | noise |
| 65%† | 58%/53%/1.10 | 71%/65%/1.11 | 66%/65%/1.02 | 0/1 | 4.61 | 0 | noise |
| 70%† | 58%/53%/1.09 | 69%/65%/1.07 | 65%/65%/1.00 | 0/1 | 4.61 | 0 | noise |
| 75%† | 56%/53%/1.07 | 72%/66%/1.09 | 65%/66%/0.99 | 0/1 | 4.61 | 0 | noise |
| 80%† | 57%/53%/1.08 | 99%/63%/1.57 | 77%/63%/1.23 | 0/0 | 4.61 | 0 | noise |
| 85%† | 57%/53%/1.07 | 98%/63%/1.56 | 77%/63%/1.22 | 0/0 | 4.61 | 0 | noise |
| 90%† | 57%/53%/1.07 | 98%/63%/1.55 | 77%/63%/1.22 | 0/0 | 4.61 | 0 | noise |
| 95%† | 56%/53%/1.07 | 97%/63%/1.54 | 76%/63%/1.21 | 0/0 | 4.61 | 0 | noise |
| 100%† | 57%/53%/1.08 | 96%/63%/1.53 | 76%/63%/1.21 | 0/0 | 4.61 | 0 | noise |

IS-selected stop: 35.0% -> IS/OOS Calmar_i 1.52/0.57 vs baseline 1.08/1.50; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: ['80.0%']; 'helps' levels: none.
4x 15%/30d: baseline crash-ON IS/OOS Calmar_i 3.58/0.56; crash-OFF 1.20/0.78 (full CAGR 93% vs 68%).

#### crash OFF, 4x, kill 15%/30d

No-stop baseline: IS 82%/68%/1.20, OOS 53%/69%/0.78, full 68%/69%/0.98, kills/yr 6.07, liq 0. († = at/after liquidation-equivalent 25.0%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -67%/94%/-0.71 | -60%/88%/-0.69 | -64%/99%/-0.64 | 510/512 | 6.14 | 0 | hurts |
| 0.5% | -65%/93%/-0.70 | -25%/62%/-0.38 | -50%/97%/-0.52 | 422/396 | 6.49 | 0 | hurts |
| 1% | -64%/93%/-0.68 | -11%/67%/-0.17 | -44%/96%/-0.46 | 326/287 | 7.47 | 0 | hurts |
| 1.5% | -50%/84%/-0.59 | 24%/49%/0.48 | -22%/88%/-0.25 | 298/273 | 7.19 | 0 | hurts |
| 2% | -62%/92%/-0.67 | -42%/83%/-0.51 | -54%/98%/-0.55 | 232/219 | 7.96 | 0 | hurts |
| 3% | -44%/82%/-0.53 | 27%/79%/0.35 | -16%/90%/-0.18 | 212/186 | 7.54 | 0 | hurts |
| 4% | -52%/88%/-0.59 | -20%/71%/-0.28 | -38%/93%/-0.41 | 168/145 | 7.82 | 0 | hurts |
| 5% | -28%/75%/-0.37 | 19%/62%/0.31 | -7%/85%/-0.09 | 150/116 | 7.54 | 0 | hurts |
| 6% | -28%/69%/-0.40 | -21%/65%/-0.33 | -24%/86%/-0.28 | 122/106 | 7.54 | 0 | hurts |
| 7% | -37%/73%/-0.50 | -20%/71%/-0.29 | -29%/83%/-0.35 | 107/90 | 7.33 | 0 | hurts |
| 8% | -31%/71%/-0.43 | 44%/59%/0.75 | -2%/74%/-0.02 | 101/76 | 7.26 | 0 | hurts |
| 9% | -27%/72%/-0.38 | 90%/60%/1.49 | 16%/81%/0.20 | 83/71 | 6.77 | 0 | hurts |
| 10% | -6%/68%/-0.09 | -6%/76%/-0.08 | -6%/76%/-0.07 | 72/60 | 6.77 | 0 | hurts |
| 12% | -10%/66%/-0.15 | -22%/74%/-0.29 | -15%/81%/-0.18 | 49/41 | 6.98 | 0 | hurts |
| 14% | 0%/60%/0.02 | -2%/77%/-0.02 | -1%/83%/-0.01 | 41/33 | 6.98 | 0 | hurts |
| 16% | -2%/67%/-0.03 | 3%/69%/0.04 | 1%/71%/0.02 | 35/24 | 6.91 | 0 | hurts |
| 18% | 26%/48%/0.56 | -21%/69%/-0.30 | 3%/80%/0.03 | 24/17 | 6.91 | 0 | hurts |
| 20% | 33%/49%/0.69 | -12%/69%/-0.17 | 11%/71%/0.15 | 19/14 | 6.63 | 0 | hurts |
| 22.5% | -10%/71%/-0.13 | 32%/67%/0.48 | 8%/71%/0.12 | 14/8 | 6.49 | 0 | hurts |
| 25%† | 10%/72%/0.13 | 38%/66%/0.58 | 22%/72%/0.31 | 12/5 | 6.49 | 0 | hurts |
| 27.5%† | 48%/62%/0.77 | 26%/66%/0.39 | 37%/66%/0.56 | 8/7 | 6.49 | 0 | noise |
| 30%† | 60%/55%/1.08 | 72%/67%/1.07 | 66%/67%/0.98 | 6/5 | 6.07 | 0 | noise |
| 31%† | 68%/63%/1.09 | 69%/67%/1.03 | 69%/67%/1.02 | 6/5 | 6.28 | 0 | noise |
| 32.5%† | 84%/64%/1.31 | 62%/67%/0.93 | 73%/67%/1.10 | 4/3 | 5.86 | 0 | noise |
| 35%† | 84%/65%/1.30 | 45%/67%/0.67 | 64%/67%/0.96 | 3/2 | 5.86 | 0 | noise |
| 37.5%† | 34%/71%/0.48 | 45%/67%/0.67 | 39%/71%/0.55 | 2/2 | 6.49 | 0 | noise |
| 40%† | 36%/66%/0.54 | 44%/67%/0.66 | 40%/67%/0.60 | 1/2 | 6.49 | 0 | hurts |
| 42.5%† | 54%/67%/0.81 | 49%/67%/0.73 | 52%/67%/0.77 | 1/2 | 6.28 | 0 | hurts |
| 45%† | 43%/68%/0.63 | 47%/67%/0.70 | 45%/68%/0.66 | 1/1 | 6.49 | 0 | hurts |
| 47.5%† | 71%/67%/1.06 | 47%/67%/0.70 | 59%/67%/0.88 | 1/1 | 6.42 | 0 | hurts |
| 50%† | 86%/67%/1.29 | 41%/67%/0.61 | 63%/67%/0.94 | 1/0 | 6.28 | 0 | hurts |
| 55%† | 81%/68%/1.18 | 39%/67%/0.58 | 59%/68%/0.87 | 1/0 | 6.28 | 0 | noise |
| 60%† | 81%/68%/1.19 | 41%/67%/0.61 | 61%/68%/0.89 | 1/0 | 6.28 | 0 | noise |
| 65%† | 82%/68%/1.20 | 49%/67%/0.73 | 65%/68%/0.95 | 0/0 | 6.07 | 0 | noise |
| 70%† | 82%/68%/1.20 | 48%/67%/0.72 | 65%/68%/0.95 | 0/0 | 6.07 | 0 | noise |
| 75%† | 82%/68%/1.20 | 53%/69%/0.78 | 68%/69%/0.98 | 0/0 | 6.07 | 0 | noise |
| 80%† | 82%/68%/1.20 | 53%/69%/0.78 | 68%/69%/0.98 | 0/0 | 6.07 | 0 | noise |
| 85%† | 82%/68%/1.20 | 53%/69%/0.78 | 68%/69%/0.98 | 0/0 | 6.07 | 0 | noise |
| 90%† | 82%/68%/1.20 | 53%/69%/0.78 | 68%/69%/0.98 | 0/0 | 6.07 | 0 | noise |
| 95%† | 82%/68%/1.20 | 53%/69%/0.78 | 68%/69%/0.98 | 0/0 | 6.07 | 0 | noise |
| 100%† | 82%/68%/1.20 | 53%/69%/0.78 | 68%/69%/0.98 | 0/0 | 6.07 | 0 | noise |

IS-selected stop: 32.5% -> IS/OOS Calmar_i 1.31/0.93 vs baseline 1.20/0.78; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: ['32.5%']; 'helps' levels: none.
4x 30%/14d: baseline crash-ON IS/OOS Calmar_i 3.00/0.38; crash-OFF 1.83/0.51 (full CAGR 84% vs 76%).

#### crash OFF, 4x, kill 30%/14d

No-stop baseline: IS 110%/60%/1.83, OOS 41%/81%/0.51, full 76%/81%/0.94, kills/yr 3.14, liq 0. († = at/after liquidation-equivalent 25.0%)

| s | IS CAGR/iMDD/Calmar | OOS CAGR/iMDD/Calmar | full CAGR/iMDD/Calmar | stops/yr (L/S) | kills/yr | liq | label |
|---:|---|---|---|---:|---:|---:|---|
| 0% | -83%/99%/-0.84 | -83%/98%/-0.84 | -83%/100%/-0.83 | 817/817 | 4.82 | 0 | hurts |
| 0.5% | -84%/99%/-0.85 | -61%/89%/-0.69 | -76%/100%/-0.76 | 712/696 | 5.03 | 0 | hurts |
| 1% | -81%/98%/-0.82 | -48%/90%/-0.53 | -69%/100%/-0.69 | 637/588 | 5.17 | 0 | hurts |
| 1.5% | -86%/99%/-0.86 | -58%/90%/-0.64 | -76%/100%/-0.76 | 548/522 | 5.51 | 0 | hurts |
| 2% | -86%/99%/-0.86 | -36%/94%/-0.38 | -71%/100%/-0.71 | 498/467 | 5.86 | 0 | hurts |
| 3% | -71%/97%/-0.74 | -29%/95%/-0.30 | -55%/99%/-0.56 | 402/372 | 5.37 | 0 | hurts |
| 4% | -58%/93%/-0.62 | -27%/88%/-0.31 | -46%/97%/-0.47 | 343/302 | 5.44 | 0 | hurts |
| 5% | -44%/91%/-0.48 | 42%/74%/0.56 | -12%/91%/-0.13 | 286/242 | 4.68 | 0 | hurts |
| 6% | -44%/87%/-0.51 | 28%/87%/0.33 | -16%/89%/-0.18 | 235/211 | 4.54 | 0 | noise |
| 7% | -57%/91%/-0.63 | 6%/89%/0.06 | -33%/94%/-0.35 | 221/160 | 5.10 | 0 | noise |
| 8% | -56%/90%/-0.62 | 45%/81%/0.56 | -21%/92%/-0.23 | 177/160 | 5.17 | 0 | noise |
| 9% | -51%/91%/-0.56 | 13%/89%/0.15 | -26%/91%/-0.28 | 154/137 | 4.54 | 0 | noise |
| 10% | -61%/94%/-0.65 | 116%/73%/1.59 | -12%/94%/-0.13 | 126/118 | 4.33 | 0 | noise |
| 12% | -33%/81%/-0.41 | 13%/82%/0.16 | -14%/85%/-0.16 | 101/88 | 4.40 | 0 | hurts |
| 14% | -3%/73%/-0.04 | -5%/88%/-0.05 | -4%/88%/-0.05 | 74/66 | 4.19 | 0 | hurts |
| 16% | 22%/60%/0.37 | 29%/86%/0.34 | 27%/86%/0.31 | 52/55 | 3.77 | 0 | hurts |
| 18% | 71%/61%/1.21 | 4%/84%/0.04 | 35%/84%/0.42 | 43/40 | 3.49 | 0 | hurts |
| 20% | 71%/62%/1.16 | -7%/85%/-0.09 | 29%/85%/0.35 | 31/32 | 3.77 | 0 | hurts |
| 22.5% | 91%/63%/1.45 | 31%/81%/0.39 | 61%/81%/0.76 | 25/26 | 3.14 | 0 | noise |
| 25%† | 36%/62%/0.57 | 41%/75%/0.55 | 40%/77%/0.52 | 19/21 | 3.35 | 0 | noise |
| 27.5%† | 54%/65%/0.82 | 57%/76%/0.75 | 57%/76%/0.75 | 13/16 | 3.21 | 0 | noise |
| 30%† | 43%/69%/0.61 | 35%/80%/0.44 | 40%/80%/0.51 | 9/12 | 3.42 | 0 | noise |
| 31%† | 57%/66%/0.89 | 30%/79%/0.38 | 44%/79%/0.56 | 8/12 | 3.42 | 0 | noise |
| 32.5%† | 22%/64%/0.34 | 87%/78%/1.11 | 51%/78%/0.65 | 6/10 | 3.07 | 0 | noise |
| 35%† | 68%/66%/1.03 | 33%/77%/0.42 | 52%/77%/0.67 | 5/6 | 3.35 | 0 | noise |
| 37.5%† | 39%/69%/0.57 | 84%/78%/1.08 | 56%/78%/0.71 | 3/6 | 3.35 | 0 | noise |
| 40%† | 29%/64%/0.46 | 74%/81%/0.92 | 51%/81%/0.63 | 2/5 | 2.93 | 0 | noise |
| 42.5%† | 21%/64%/0.32 | 67%/81%/0.83 | 43%/81%/0.53 | 2/4 | 3.21 | 0 | noise |
| 45%† | 102%/60%/1.70 | 35%/81%/0.43 | 69%/81%/0.85 | 1/3 | 3.21 | 0 | noise |
| 47.5%† | 115%/60%/1.92 | 42%/81%/0.52 | 78%/81%/0.97 | 1/3 | 2.93 | 0 | noise |
| 50%† | 112%/60%/1.86 | 40%/81%/0.49 | 76%/81%/0.94 | 1/3 | 2.93 | 0 | noise |
| 55%† | 110%/60%/1.84 | 31%/81%/0.39 | 70%/81%/0.87 | 1/2 | 3.14 | 0 | noise |
| 60%† | 108%/60%/1.79 | 31%/81%/0.39 | 69%/81%/0.85 | 1/1 | 3.14 | 0 | noise |
| 65%† | 111%/60%/1.84 | 42%/81%/0.52 | 77%/81%/0.95 | 0/1 | 3.14 | 0 | noise |
| 70%† | 110%/60%/1.84 | 41%/81%/0.50 | 76%/81%/0.94 | 0/0 | 3.14 | 0 | noise |
| 75%† | 110%/60%/1.83 | 34%/81%/0.42 | 71%/81%/0.88 | 0/0 | 3.35 | 0 | noise |
| 80%† | 110%/60%/1.83 | 33%/81%/0.41 | 71%/81%/0.88 | 0/0 | 3.35 | 0 | noise |
| 85%† | 109%/60%/1.82 | 26%/81%/0.33 | 67%/81%/0.82 | 0/0 | 3.35 | 0 | noise |
| 90%† | 110%/60%/1.83 | 26%/81%/0.32 | 66%/81%/0.82 | 0/0 | 3.35 | 0 | noise |
| 95%† | 110%/60%/1.83 | 25%/81%/0.31 | 66%/81%/0.81 | 0/0 | 3.35 | 0 | noise |
| 100%† | 110%/60%/1.83 | 24%/81%/0.30 | 65%/81%/0.81 | 0/0 | 3.35 | 0 | noise |

IS-selected stop: 47.5% -> IS/OOS Calmar_i 1.92/0.52 vs baseline 1.83/0.51; levels improving Calmar_i in BOTH IS and OOS with CAGR>=0.9x base: ['47.5%', '65.0%']; 'helps' levels: none.
