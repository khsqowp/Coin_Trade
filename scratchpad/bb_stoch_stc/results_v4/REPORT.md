# V4 real-data research results

## Headline cohort x timeframe x variant

| cohort | timeframe | variant | train_trades | train_return | test_trades | test_return | null_percentile | plateau_verdict | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L2 | 1d | combined | 56 | 19.78276115550858 | 39 | 0.7622176466304207 | 43.5 | FRAGILE | no edge |
| L2 | 1d | long_only | 38 | 36.99835354811303 | 20 | 15.374480470588601 | 8.0 | FRAGILE | no edge |
| L2 | 1d | short_only | 34 | 13.126933395508587 | 20 | -5.1123237616954205 | 33.5 | FRAGILE | no edge |
| L2 | 1d | unconstrained | 38 | 36.99835354811303 | 20 | 15.374480470588601 | 8.0 | FRAGILE | no edge |
| L2 | 1d | with_stop | 56 | 19.78276115550858 | 39 | 0.7622176466304207 | 43.5 | FRAGILE | no edge |
| L2 | 12h | combined | 97 | 50.66183908558223 | 53 | 10.629786347203424 | 87.0 | FRAGILE | no edge |
| L2 | 12h | long_only | 36 | 19.607928016000052 | 32 | 0.7120826682609724 | 0.0 | FRAGILE | no edge |
| L2 | 12h | short_only | 32 | 27.798818106876386 | 16 | -2.3628031099280555 | 36.5 | FRAGILE | no edge |
| L2 | 12h | unconstrained | 97 | 50.66183908558223 | 53 | 10.629786347203424 | 87.0 | FRAGILE | no edge |
| L2 | 12h | with_stop | 97 | 50.66183908558223 | 53 | 10.629786347203424 | 87.0 | FRAGILE | no edge |
| L2 | 8h | combined | 255 | 55.734006209270845 | 115 | 1.921893528130242 | 61.0 | FRAGILE | no edge |
| L2 | 8h | long_only | 62 | 23.042994155357178 | 38 | 2.0477603938306506 | 1.0 | FRAGILE | no edge |
| L2 | 8h | short_only | 44 | 32.790204460981826 | 21 | 5.622503990489973 | 100.0 | FRAGILE | no edge |
| L2 | 8h | unconstrained | 255 | 55.734006209270845 | 115 | 1.921893528130242 | 61.0 | FRAGILE | no edge |
| L2 | 8h | with_stop | 255 | 55.734006209270845 | 115 | 1.921893528130242 | 61.0 | FRAGILE | no edge |
| L5 | 1d | combined | 306 | 68.00191369503747 | 159 | 15.321172713676415 | 56.99999999999999 | FRAGILE | no edge |
| L5 | 1d | long_only | 106 | 86.91881521535828 | 54 | 13.491338544068698 | 6.5 | FRAGILE | no edge |
| L5 | 1d | short_only | 38 | 25.08837351448834 | 16 | 5.201939557852994 | 53.0 | FRAGILE | no edge |
| L5 | 1d | unconstrained | 106 | 86.91881521535828 | 54 | 13.491338544068698 | 6.5 | FRAGILE | no edge |
| L5 | 1d | with_stop | 306 | 68.00191369503747 | 159 | 15.321172713676415 | 56.99999999999999 | FRAGILE | no edge |
| L5 | 12h | combined | 174 | 113.95517590094589 | 78 | 48.7616230770541 | 100.0 | FRAGILE | no edge |
| L5 | 12h | long_only | 103 | 70.95723334250891 | 65 | 49.819735703387835 | 100.0 | FRAGILE | no edge |
| L5 | 12h | short_only | 118 | 44.48322976097168 | 65 | 23.579547778557618 | 100.0 | FRAGILE | no edge |
| L5 | 12h | unconstrained | 174 | 113.95517590094589 | 78 | 48.7616230770541 | 100.0 | FRAGILE | no edge |
| L5 | 12h | with_stop | 174 | 113.95517590094589 | 78 | 48.7616230770541 | 100.0 | FRAGILE | no edge |
| L5 | 8h | combined | 55 | 32.13615308928857 | 29 | 9.812666338865375 | 82.5 | FRAGILE | no edge |
| L5 | 8h | long_only | 435 | 80.278101536165 | 237 | 21.785365081529697 | 1.5 | FRAGILE | no edge |
| L5 | 8h | short_only | 37 | 31.69660422528853 | 16 | 4.236227666234979 | 55.00000000000001 | FRAGILE | no edge |
| L5 | 8h | unconstrained | 435 | 80.278101536165 | 237 | 21.785365081529697 | 1.5 | FRAGILE | no edge |
| L5 | 8h | with_stop | 55 | 32.13615308928857 | 29 | 9.812666338865375 | 82.5 | FRAGILE | no edge |

## E1 frozen pooled full/train/test

| cohort | timeframe | split | trades | total_return | pf | max_dd |
| --- | --- | --- | --- | --- | --- | --- |
| L5 | 1d | full | 221 | -32.4263750512395 | 0.6451925716277318 | -69.11352210857608 |
| L5 | 1d | train | 136 | -12.74793839415709 | 0.7373477415860975 | -44.312168369973904 |
| L5 | 1d | test | 85 | -19.678436657082415 | 0.540824818416393 | -49.67056510495325 |
| L5 | 12h | full | 458 | -19.73416028059063 | 0.8633265350823551 | -95.40577043978166 |
| L5 | 12h | train | 303 | -32.54710409269943 | 0.7127497197510652 | -93.69803248396435 |
| L5 | 12h | test | 155 | 12.812943812108795 | 1.4122120840551837 | -25.100566173328758 |
| L5 | 8h | full | 596 | -23.704938984736327 | 0.8738495258140598 | -86.71469143989013 |
| L5 | 8h | train | 387 | -28.638094790341935 | 0.7873992736482579 | -78.514562745718 |
| L5 | 8h | test | 209 | 4.933155805605607 | 1.092717386907737 | -33.139646362087454 |
| L2 | 1d | full | 89 | -9.809179569249004 | 0.7026782896545042 | -19.173160899566412 |
| L2 | 1d | train | 54 | -11.416945093906158 | 0.5451338126574421 | -18.810881511366958 |
| L2 | 1d | test | 35 | 1.6077655246571543 | 1.2037148499209318 | -11.774123807311813 |
| L2 | 12h | full | 182 | -12.708788136299432 | 0.7935124999951472 | -36.45067882886623 |
| L2 | 12h | train | 113 | -17.126514292750016 | 0.6353065957947576 | -36.45067882886623 |
| L2 | 12h | test | 69 | 4.417726156450582 | 1.3028725452698535 | -7.507302285105226 |
| L2 | 8h | full | 232 | 28.079398644663836 | 1.72645820693456 | -14.845028269823953 |
| L2 | 8h | train | 157 | 18.957984173609113 | 1.7155932074836666 | -14.845028269823953 |
| L2 | 8h | test | 75 | 9.12141447105473 | 1.7501299349522748 | -7.779360950496663 |

## E1 frozen per-symbol full/train/test

| cohort | timeframe | symbol | split | trades | total_return | pf | max_dd | long | short |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L5 | 1d | BTCUSDT | full | 49 | -7.715355209900972 | 0.604270708332427 | -9.071944199968323 | 21 | 28 |
| L5 | 1d | BTCUSDT | train | 27 | -5.523597214558123 | 0.5240048032558153 | -8.71521908515379 | 11 | 16 |
| L5 | 1d | BTCUSDT | test | 22 | -2.1917579953428517 | 0.722289323762255 | -7.849505124399081 | 10 | 12 |
| L5 | 1d | ETHUSDT | full | 40 | -2.093824359348031 | 0.8448473743001307 | -10.101216699598087 | 15 | 25 |
| L5 | 1d | ETHUSDT | train | 27 | -5.893347879348036 | 0.5633022447363645 | -10.095662426213169 | 7 | 20 |
| L5 | 1d | ETHUSDT | test | 13 | 3.799523520000006 | inf | -3.924618682912732 | 8 | 5 |
| L5 | 1d | BNBUSDT | full | 61 | -6.446323932566534 | 0.6988193218219684 | -19.92604535293702 | 23 | 38 |
| L5 | 1d | BNBUSDT | train | 36 | -7.182559389683566 | 0.5419072549164279 | -12.025251117475284 | 14 | 22 |
| L5 | 1d | BNBUSDT | test | 25 | 0.73623545711703 | 1.1286171115172654 | -11.588349692788851 | 9 | 16 |
| L5 | 1d | SOLUSDT | full | 34 | -2.947630466120777 | 0.7605743710003904 | -11.344016987710576 | 18 | 16 |
| L5 | 1d | SOLUSDT | train | 25 | 7.0845800050300545 | inf | -2.109585842142175 | 11 | 14 |
| L5 | 1d | SOLUSDT | test | 9 | -10.032210471150828 | 0.18511891842641173 | -12.502833480205936 | 7 | 2 |
| L5 | 1d | XRPUSDT | full | 37 | -13.223241083303188 | 0.4643187468102142 | -18.670298868362075 | 21 | 16 |
| L5 | 1d | XRPUSDT | train | 21 | -1.2330139155974207 | 0.8410364991866284 | -11.366449898989485 | 9 | 12 |
| L5 | 1d | XRPUSDT | test | 16 | -11.99022716770577 | 0.2917060348617414 | -13.805258124646647 | 12 | 4 |
| L5 | 12h | BTCUSDT | full | 96 | -2.167781053341437 | 0.9210041751172297 | -16.897804828720755 | 32 | 64 |
| L5 | 12h | BTCUSDT | train | 58 | -8.406616339334425 | 0.6410362109692233 | -16.897804828720755 | 19 | 39 |
| L5 | 12h | BTCUSDT | test | 38 | 6.238835285992985 | 2.5509475274432014 | -2.891161452221623 | 13 | 25 |
| L5 | 12h | ETHUSDT | full | 86 | -10.541007082957995 | 0.6909319185936332 | -19.552874000145472 | 30 | 56 |
| L5 | 12h | ETHUSDT | train | 55 | -8.719897953415591 | 0.6296069553317051 | -19.552874000145472 | 21 | 34 |
| L5 | 12h | ETHUSDT | test | 31 | -1.8211091295424027 | 0.8276035227811539 | -4.616140832883603 | 9 | 22 |
| L5 | 12h | BNBUSDT | full | 99 | 0.7543861103606493 | 1.0295087319682807 | -11.091735033893865 | 39 | 60 |
| L5 | 12h | BNBUSDT | train | 63 | 2.2881877861167603 | 1.157502544868828 | -9.383997078076547 | 30 | 33 |
| L5 | 12h | BNBUSDT | test | 36 | -1.533801675756111 | 0.8610296874234832 | -7.931921723795357 | 9 | 27 |
| L5 | 12h | SOLUSDT | full | 85 | -13.637832159389607 | 0.6371007721205652 | -32.0442958932867 | 31 | 54 |
| L5 | 12h | SOLUSDT | train | 64 | -20.667236751389627 | 0.4500501126700727 | -32.0442958932867 | 21 | 43 |
| L5 | 12h | SOLUSDT | test | 21 | 7.02940459200002 | inf | -2.545691226070142 | 10 | 11 |
| L5 | 12h | XRPUSDT | full | 92 | 5.8580739047377595 | 1.2974161379874414 | -15.819060683734874 | 42 | 50 |
| L5 | 12h | XRPUSDT | train | 63 | 2.9584591653234535 | 1.207812842712243 | -15.819060683734874 | 27 | 36 |
| L5 | 12h | XRPUSDT | test | 29 | 2.8996147394143046 | 1.5310274325332072 | -7.115650938358033 | 15 | 14 |
| L5 | 8h | BTCUSDT | full | 115 | 6.475555226462731 | 1.2507552197632752 | -10.06341230519612 | 56 | 59 |
| L5 | 8h | BTCUSDT | train | 78 | 2.1476220826075214 | 1.1133715784459526 | -10.06341230519612 | 35 | 43 |
| L5 | 8h | BTCUSDT | test | 37 | 4.32793314385521 | 1.628969087139886 | -3.9060416708891514 | 21 | 16 |
| L5 | 8h | ETHUSDT | full | 117 | 21.603843418201105 | 2.6840829872380887 | -4.781615964627833 | 44 | 73 |
| L5 | 8h | ETHUSDT | train | 79 | 16.81036209100159 | 3.22669458838913 | -4.781615964627833 | 32 | 47 |
| L5 | 8h | ETHUSDT | test | 38 | 4.793481327199519 | 1.9080653870080095 | -3.8733192796075113 | 12 | 26 |
| L5 | 8h | BNBUSDT | full | 146 | -11.79932665868553 | 0.766649455817096 | -17.187395507844684 | 52 | 94 |
| L5 | 8h | BNBUSDT | train | 99 | -14.166697089819221 | 0.6525381020656761 | -17.187395507844684 | 33 | 66 |
| L5 | 8h | BNBUSDT | test | 47 | 2.367370431133695 | 1.2417443175088139 | -5.112574422921721 | 19 | 28 |
| L5 | 8h | SOLUSDT | full | 118 | -36.55429337852655 | 0.45093072053662814 | -42.018185597175936 | 58 | 60 |
| L5 | 8h | SOLUSDT | train | 73 | -31.203683566402685 | 0.35906824737815074 | -39.01437422242375 | 33 | 40 |
| L5 | 8h | SOLUSDT | test | 45 | -5.3506098121238725 | 0.7009184061030921 | -8.449073508576985 | 25 | 20 |
| L5 | 8h | XRPUSDT | full | 100 | -3.4307175921880826 | 0.8931830947223107 | -12.664082065045559 | 58 | 42 |
| L5 | 8h | XRPUSDT | train | 58 | -2.225698307729139 | 0.8813223582037301 | -7.467764745625613 | 33 | 25 |
| L5 | 8h | XRPUSDT | test | 42 | -1.2050192844589447 | 0.9098281754593366 | -11.798637480092085 | 25 | 17 |
| L2 | 1d | BTCUSDT | full | 49 | -7.715355209900972 | 0.604270708332427 | -9.071944199968323 | 21 | 28 |
| L2 | 1d | BTCUSDT | train | 27 | -5.523597214558123 | 0.5240048032558153 | -8.71521908515379 | 11 | 16 |
| L2 | 1d | BTCUSDT | test | 22 | -2.1917579953428517 | 0.722289323762255 | -7.849505124399081 | 10 | 12 |
| L2 | 1d | ETHUSDT | full | 40 | -2.093824359348031 | 0.8448473743001307 | -10.101216699598087 | 15 | 25 |
| L2 | 1d | ETHUSDT | train | 27 | -5.893347879348036 | 0.5633022447363645 | -10.095662426213169 | 7 | 20 |
| L2 | 1d | ETHUSDT | test | 13 | 3.799523520000006 | inf | -3.924618682912732 | 8 | 5 |
| L2 | 12h | BTCUSDT | full | 96 | -2.167781053341437 | 0.9210041751172297 | -16.897804828720755 | 32 | 64 |
| L2 | 12h | BTCUSDT | train | 58 | -8.406616339334425 | 0.6410362109692233 | -16.897804828720755 | 19 | 39 |
| L2 | 12h | BTCUSDT | test | 38 | 6.238835285992985 | 2.5509475274432014 | -2.891161452221623 | 13 | 25 |
| L2 | 12h | ETHUSDT | full | 86 | -10.541007082957995 | 0.6909319185936332 | -19.552874000145472 | 30 | 56 |
| L2 | 12h | ETHUSDT | train | 55 | -8.719897953415591 | 0.6296069553317051 | -19.552874000145472 | 21 | 34 |
| L2 | 12h | ETHUSDT | test | 31 | -1.8211091295424027 | 0.8276035227811539 | -4.616140832883603 | 9 | 22 |
| L2 | 8h | BTCUSDT | full | 115 | 6.475555226462731 | 1.2507552197632752 | -10.06341230519612 | 56 | 59 |
| L2 | 8h | BTCUSDT | train | 78 | 2.1476220826075214 | 1.1133715784459526 | -10.06341230519612 | 35 | 43 |
| L2 | 8h | BTCUSDT | test | 37 | 4.32793314385521 | 1.628969087139886 | -3.9060416708891514 | 21 | 16 |
| L2 | 8h | ETHUSDT | full | 117 | 21.603843418201105 | 2.6840829872380887 | -4.781615964627833 | 44 | 73 |
| L2 | 8h | ETHUSDT | train | 79 | 16.81036209100159 | 3.22669458838913 | -4.781615964627833 | 32 | 47 |
| L2 | 8h | ETHUSDT | test | 38 | 4.793481327199519 | 1.9080653870080095 | -3.8733192796075113 | 12 | 26 |

## Pooled all-3 signal counts by symbol and split

| cohort | timeframe | symbol | split | all3_events |
| --- | --- | --- | --- | --- |
| L5 | 1d | BTCUSDT | full | 76 |
| L5 | 1d | BTCUSDT | train | 41 |
| L5 | 1d | BTCUSDT | test | 35 |
| L5 | 1d | ETHUSDT | full | 53 |
| L5 | 1d | ETHUSDT | train | 33 |
| L5 | 1d | ETHUSDT | test | 20 |
| L5 | 1d | BNBUSDT | full | 68 |
| L5 | 1d | BNBUSDT | train | 38 |
| L5 | 1d | BNBUSDT | test | 30 |
| L5 | 1d | SOLUSDT | full | 44 |
| L5 | 1d | SOLUSDT | train | 30 |
| L5 | 1d | SOLUSDT | test | 14 |
| L5 | 1d | XRPUSDT | full | 50 |
| L5 | 1d | XRPUSDT | train | 28 |
| L5 | 1d | XRPUSDT | test | 22 |
| L5 | 12h | BTCUSDT | full | 134 |
| L5 | 12h | BTCUSDT | train | 79 |
| L5 | 12h | BTCUSDT | test | 55 |
| L5 | 12h | ETHUSDT | full | 118 |
| L5 | 12h | ETHUSDT | train | 74 |
| L5 | 12h | ETHUSDT | test | 44 |
| L5 | 12h | BNBUSDT | full | 138 |
| L5 | 12h | BNBUSDT | train | 85 |
| L5 | 12h | BNBUSDT | test | 53 |
| L5 | 12h | SOLUSDT | full | 106 |
| L5 | 12h | SOLUSDT | train | 76 |
| L5 | 12h | SOLUSDT | test | 30 |
| L5 | 12h | XRPUSDT | full | 127 |
| L5 | 12h | XRPUSDT | train | 92 |
| L5 | 12h | XRPUSDT | test | 35 |
| L5 | 8h | BTCUSDT | full | 206 |
| L5 | 8h | BTCUSDT | train | 126 |
| L5 | 8h | BTCUSDT | test | 80 |
| L5 | 8h | ETHUSDT | full | 177 |
| L5 | 8h | ETHUSDT | train | 124 |
| L5 | 8h | ETHUSDT | test | 53 |
| L5 | 8h | BNBUSDT | full | 228 |
| L5 | 8h | BNBUSDT | train | 147 |
| L5 | 8h | BNBUSDT | test | 81 |
| L5 | 8h | SOLUSDT | full | 168 |
| L5 | 8h | SOLUSDT | train | 105 |
| L5 | 8h | SOLUSDT | test | 63 |
| L5 | 8h | XRPUSDT | full | 155 |
| L5 | 8h | XRPUSDT | train | 90 |
| L5 | 8h | XRPUSDT | test | 65 |
| L2 | 1d | BTCUSDT | full | 76 |
| L2 | 1d | BTCUSDT | train | 41 |
| L2 | 1d | BTCUSDT | test | 35 |
| L2 | 1d | ETHUSDT | full | 53 |
| L2 | 1d | ETHUSDT | train | 33 |
| L2 | 1d | ETHUSDT | test | 20 |
| L2 | 12h | BTCUSDT | full | 134 |
| L2 | 12h | BTCUSDT | train | 79 |
| L2 | 12h | BTCUSDT | test | 55 |
| L2 | 12h | ETHUSDT | full | 118 |
| L2 | 12h | ETHUSDT | train | 74 |
| L2 | 12h | ETHUSDT | test | 44 |
| L2 | 8h | BTCUSDT | full | 206 |
| L2 | 8h | BTCUSDT | train | 126 |
| L2 | 8h | BTCUSDT | test | 80 |
| L2 | 8h | ETHUSDT | full | 177 |
| L2 | 8h | ETHUSDT | train | 124 |
| L2 | 8h | ETHUSDT | test | 53 |

## Cohort-timeframe pooled all-3 events

| cohort | timeframe | split | all3_events |
| --- | --- | --- | --- |
| L2 | 12h | full | 252 |
| L2 | 12h | test | 99 |
| L2 | 12h | train | 153 |
| L2 | 1d | full | 129 |
| L2 | 1d | test | 55 |
| L2 | 1d | train | 74 |
| L2 | 8h | full | 383 |
| L2 | 8h | test | 133 |
| L2 | 8h | train | 250 |
| L5 | 12h | full | 623 |
| L5 | 12h | test | 217 |
| L5 | 12h | train | 406 |
| L5 | 1d | full | 291 |
| L5 | 1d | test | 121 |
| L5 | 1d | train | 170 |
| L5 | 8h | full | 934 |
| L5 | 8h | test | 342 |
| L5 | 8h | train | 592 |

## E1 random-entry null

| cohort | timeframe | status | null_p50 | null_p90 | null_percentile | test_return | reps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L5 | 1d | OK | -4.727999748455321 | 7.860101656429125 | 10.5 | -19.678436657082415 | 200 |
| L5 | 12h | OK | -0.09372419352403603 | 14.362298672751997 | 87.5 | 12.812943812108795 | 200 |
| L5 | 8h | OK | -0.371759606738998 | 12.912742351116602 | 70.5 | 4.933155805605607 | 200 |
| L2 | 1d | OK | 0.12167332373011032 | 7.3448528655533 | 59.5 | 1.6077655246571543 | 200 |
| L2 | 12h | OK | -0.6513284482808857 | 7.1292236862289196 | 79.0 | 4.417726156450582 | 200 |
| L2 | 8h | OK | 1.8514820985800235 | 8.156398547016478 | 93.5 | 9.12141447105473 | 200 |

## Tuned walk-forward summary

| cohort | timeframe | windows | test_trades | test_return | positive_windows_pct |
| --- | --- | --- | --- | --- | --- |
| L2 | 12h | 14 | 316 | 1.0367401460552919 | 64.28571428571429 |
| L2 | 1d | 6 | 136 | -7.750314732938017 | 66.66666666666666 |
| L2 | 8h | 14 | 259 | -1.1087587296704082 | 50.0 |
| L5 | 12h | 8 | 155 | -10.205627212457825 | 75.0 |
| L5 | 1d | 3 | 110 | 2.441128692301257 | 33.33333333333333 |
| L5 | 8h | 8 | 161 | -23.744572971166107 | 50.0 |

## Plateau

| cohort | timeframe | variant | neighbors | robust_neighbor_pct | verdict |
| --- | --- | --- | --- | --- | --- |
| L2 | 1d | combined | 43 | 11.627906976744185 | FRAGILE |
| L2 | 1d | long_only | 43 | 16.27906976744186 | FRAGILE |
| L2 | 1d | short_only | 34 | 5.882352941176471 | FRAGILE |
| L2 | 1d | unconstrained | 43 | 16.27906976744186 | FRAGILE |
| L2 | 1d | with_stop | 43 | 11.627906976744185 | FRAGILE |
| L2 | 12h | combined | 43 | 13.953488372093023 | FRAGILE |
| L2 | 12h | long_only | 43 | 18.6046511627907 | FRAGILE |
| L2 | 12h | short_only | 29 | 27.586206896551722 | FRAGILE |
| L2 | 12h | unconstrained | 43 | 13.953488372093023 | FRAGILE |
| L2 | 12h | with_stop | 43 | 13.953488372093023 | FRAGILE |
| L2 | 8h | combined | 43 | 16.27906976744186 | FRAGILE |
| L2 | 8h | long_only | 43 | 20.930232558139537 | FRAGILE |
| L2 | 8h | short_only | 46 | 17.391304347826086 | FRAGILE |
| L2 | 8h | unconstrained | 43 | 16.27906976744186 | FRAGILE |
| L2 | 8h | with_stop | 43 | 16.27906976744186 | FRAGILE |
| L5 | 1d | combined | 43 | 11.627906976744185 | FRAGILE |
| L5 | 1d | long_only | 43 | 11.627906976744185 | FRAGILE |
| L5 | 1d | short_only | 46 | 10.869565217391305 | FRAGILE |
| L5 | 1d | unconstrained | 43 | 11.627906976744185 | FRAGILE |
| L5 | 1d | with_stop | 43 | 11.627906976744185 | FRAGILE |
| L5 | 12h | combined | 46 | 19.565217391304348 | FRAGILE |
| L5 | 12h | long_only | 43 | 16.27906976744186 | FRAGILE |
| L5 | 12h | short_only | 46 | 19.565217391304348 | FRAGILE |
| L5 | 12h | unconstrained | 46 | 19.565217391304348 | FRAGILE |
| L5 | 12h | with_stop | 46 | 19.565217391304348 | FRAGILE |
| L5 | 8h | combined | 44 | 6.818181818181818 | FRAGILE |
| L5 | 8h | long_only | 41 | 7.317073170731708 | FRAGILE |
| L5 | 8h | short_only | 41 | 7.317073170731708 | FRAGILE |
| L5 | 8h | unconstrained | 41 | 7.317073170731708 | FRAGILE |
| L5 | 8h | with_stop | 44 | 6.818181818181818 | FRAGILE |

## Data starts and gaps

| symbol | timeframe | first_date | last_date | bars |
| --- | --- | --- | --- | --- |
| BTCUSDT | 1d | 2017-08-17T00:00:00+00:00 | 2026-11-19T00:00:00+00:00 | 3382 |
| BTCUSDT | 12h | 2017-08-17T00:00:00+00:00 | 2026-11-19T12:00:00+00:00 | 6763 |
| BTCUSDT | 8h | 2017-08-17T00:00:00+00:00 | 2026-11-19T16:00:00+00:00 | 10143 |
| ETHUSDT | 1d | 2017-08-17T00:00:00+00:00 | 2026-11-19T00:00:00+00:00 | 3382 |
| ETHUSDT | 12h | 2017-08-17T00:00:00+00:00 | 2026-11-19T12:00:00+00:00 | 6763 |
| ETHUSDT | 8h | 2017-08-17T00:00:00+00:00 | 2026-11-19T16:00:00+00:00 | 10143 |
| BNBUSDT | 1d | 2017-11-06T00:00:00+00:00 | 2026-11-19T00:00:00+00:00 | 3301 |
| BNBUSDT | 12h | 2017-11-06T00:00:00+00:00 | 2026-11-19T12:00:00+00:00 | 6601 |
| BNBUSDT | 8h | 2017-11-06T00:00:00+00:00 | 2026-11-19T16:00:00+00:00 | 9900 |
| SOLUSDT | 1d | 2020-08-11T00:00:00+00:00 | 2026-11-19T00:00:00+00:00 | 2292 |
| SOLUSDT | 12h | 2020-08-11T00:00:00+00:00 | 2026-11-19T12:00:00+00:00 | 4584 |
| SOLUSDT | 8h | 2020-08-11T00:00:00+00:00 | 2026-11-19T16:00:00+00:00 | 6876 |
| XRPUSDT | 1d | 2018-05-04T00:00:00+00:00 | 2026-11-19T00:00:00+00:00 | 3122 |
| XRPUSDT | 12h | 2018-05-04T00:00:00+00:00 | 2026-11-19T12:00:00+00:00 | 6244 |
| XRPUSDT | 8h | 2018-05-04T08:00:00+00:00 | 2026-11-19T16:00:00+00:00 | 9365 |
| symbol | timeframe | bars | gaps | gap_details |
| --- | --- | --- | --- | --- |
| BTCUSDT | 1d | 3382 | 0 | [] |
| BTCUSDT | 12h | 6763 | 1 | [["2018-02-08 00:00:00+00:00", "2018-02-09 00:00:00+00:00", 1]] |
| BTCUSDT | 8h | 10143 | 1 | [["2018-02-08 00:00:00+00:00", "2018-02-09 08:00:00+00:00", 3]] |
| ETHUSDT | 1d | 3382 | 0 | [] |
| ETHUSDT | 12h | 6763 | 1 | [["2018-02-08 00:00:00+00:00", "2018-02-09 00:00:00+00:00", 1]] |
| ETHUSDT | 8h | 10143 | 1 | [["2018-02-08 00:00:00+00:00", "2018-02-09 08:00:00+00:00", 3]] |
| BNBUSDT | 1d | 3301 | 0 | [] |
| BNBUSDT | 12h | 6601 | 1 | [["2018-02-08 00:00:00+00:00", "2018-02-09 00:00:00+00:00", 1]] |
| BNBUSDT | 8h | 9900 | 1 | [["2018-02-08 00:00:00+00:00", "2018-02-09 08:00:00+00:00", 3]] |
| SOLUSDT | 1d | 2292 | 0 | [] |
| SOLUSDT | 12h | 4584 | 0 | [] |
| SOLUSDT | 8h | 6876 | 0 | [] |
| XRPUSDT | 1d | 3122 | 0 | [] |
| XRPUSDT | 12h | 6244 | 0 | [] |
| XRPUSDT | 8h | 9365 | 0 | [] |

## Stage timings

| cohort | timeframe | stage | seconds |
| --- | --- | --- | --- |
| L2 | 1d | tune | 2.8065301249735057 |
| L2 | 12h | tune | 5.163846791954711 |
| L2 | 8h | tune | 7.968588541960344 |
| L5 | 1d | tune | 6.767698000068776 |
| L5 | 12h | tune | 13.769294874975458 |
| L5 | 8h | tune | 18.269958999939263 |
| STAGE | data | data | 0.051 |
| STAGE | e1 | e1 | 13.677 |
| STAGE | tune | tune | 54.75 |
| STAGE | wf | wf | 12.189 |
| STAGE | random_null | random_null | 67.86 |
| STAGE | report | report | 0.011602208018302917 |

## Search design and deviations

- Strict all-3 conjunction is the existing `strategy.signal_frame` BB AND stochastic AND STC logic.
- Per-series chronological 60/40 cut; all candidate selection and plateau scoring use train slices only.
- Signal phase 1 uses 64 deterministic points sampled evenly from the 4^5 five-axis design. The other five signal parameters remain at v3 canonical values. The requested 10-knob full search was reduced to fit runtime.
- Management phase uses 36 deterministic evenly spaced settings from the requested wide Cartesian surface; full Cartesian management enumeration was not run.
- Pool workers: 6 for tune finalist simulations and random-entry null; WF simulation is coordinator-serial.
- Pooled return and PF sum pooled trade outcomes using the v3 aggregation convention. Pooled MDD is the sum of per-series mark-to-market MDDs, not a synchronized multi-asset portfolio equity curve.
- The research process ran in supervised attached execution sessions; detached nohup children could not be retained by the shell environment.
- Random-entry null is valid only when at least 10 unique returns and nonzero variance; otherwise status is NULL_DEGENERATE and percentile is withheld.
- Mechanical verdict is COUNTS only when test return beats null p90, plateau is not FRAGILE, and test trades >=30.
- Reproduce: `.venv/bin/python run_v4.py --stage all --max-minutes 45`; force: append `--force`.
- E1 management and signal were loaded from `results_v3/tune_winners.csv`, L5/4h/combined.
