# A鑲¤瀵熸睜 路 A-Share Watchpool

> 鍩轰簬鍏紑琛屾儏鏁版嵁鐨?A 鑲￠噺鍖栬瀵熶笌绾搁潰楠岃瘉绯荤粺
>
> 浠呬緵涓汉瀛︿範涓庣瓥鐣ョ爺绌讹紝涓嶆瀯鎴愭姇璧勫缓璁紝涓嶄骇鐢熺湡瀹炰拱鍗栨寚浠ゃ€?
---

## 馃搶 椤圭洰绠€浠?
**A鑲¤瀵熸睜** 鏄竴濂楅潰鍚?A 鑲″競鍦虹殑杞婚噺绾ч噺鍖栬瀵熸鏋讹紝甯姪涓汉鎶曡祫鑰?閲忓寲鐖卞ソ鑰咃細

- 馃搳 姣忔棩鑷姩閲囬泦鍏ㄥ競鍦鸿鎯呭揩鐓э紙娌繁浜?A 鑲★紝5500+ 鏍囩殑锛?- 馃攳 澶氱淮搴︾瓫閫夊€欓€夎偂绁紙鍔ㄩ噺銆佹澘鍧椼€佹墽琛岃川閲忋€佸叕鍛婇闄╋級
- 馃摪 鎶撳彇鏀跨瓥/琛屼笟/涓偂鏂伴椈鍌寲鍓傦紝浣滀负閫夎偂杈呭姪淇″彿
- 馃搱 鐢熸垚鐩樺墠閫夎偂鏃ユ姤銆佺洏鍚庡鐩樻姤鍛婏紙HTML 鍙鍖栵級
- 馃梽锔?SQLite 澶嶇洏鏁版嵁搴?+ 绛栫暐瀹¤浠〃鐩?- 馃幆 鍐呯疆绾搁潰妯℃嫙鐩橈紙Paper Simulator锛夛紝T+1/T+2/T+3 璺熻釜楠岃瘉

### 鏍稿績鐞嗗康

> "鍏堥獙璇侊紝鍐嶆墽琛屻€? 鎵€鏈夐€夎偂閫昏緫鍦ㄧ湡瀹炶祫閲戜粙鍏ュ墠锛屽厛缁忚繃鑷冲皯 20 涓湁鏁堟牱鏈殑绾搁潰楠岃瘉銆?
---

## 馃彈锔?绯荤粺鏋舵瀯

```mermaid
graph TD
    A[鍏紑琛屾儏鏁版嵁<br/>AKShare / 涓滄柟璐㈠瘜] -->|08:40 鐩樺墠| B[collect_public_data.py<br/>鍏ㄥ競鍦哄揩鐓?+ 鍊欓€夌瀛怾
    B --> C[check_execution_quality.py<br/>娑ㄥ仠/娴佸姩鎬?鎸箙妫€鏌
    B --> D[check_risk_events.py<br/>鍑忔寔/瑙ｇ/鐩戠椋庨櫓]
    B --> E[collect_policy_news.py<br/>鏀跨瓥/琛屼笟/鍏徃鏂伴椈]
    B --> F[monitor_data_health.py<br/>鏁版嵁鍋ュ悍妫€鏌

    C & D & E & F --> G[render_watchpool_light.py<br/>涓诲叆鍙ｏ細鏋勯€?JSON + 娓叉煋 HTML]

    G --> H[鐩樺墠鏃ユ姤<br/>pre_market_light.html]
    G --> I[鐩樺悗澶嶇洏<br/>post_close_review_light.html]
    G --> J[鍛ㄥ鐩?br/>weekly_review_light.html]

    G --> K[watchpool_db.py<br/>鍐欏叆 SQLite]
    K --> L[绛栫暐浠〃鐩?br/>watchpool_dashboard.html]
    K --> M[瀹¤鎶ュ憡<br/>strategy_audit.html]

    G --> N[paper_sim_portfolio.py<br/>绾搁潰妯℃嫙鐩?14:45 鍐崇瓥]
```

---

## 馃搮 姣忔棩 Pipeline 鏃跺簭

| 鏃堕棿 | Stage | 涓昏浜у嚭 |
|------|-------|---------|
| 08:40 | `pre_market` | 鍏ㄥ競鍦哄揩鐓?+ 鍊欓€夌瀛?+ 鍋ュ悍妫€鏌?|
| 鐩樺墠 | `pre_market` HTML | `pre_market_light.html`锛堢洏鍓嶉€夎偂鏃ユ姤锛?|
| 14:45 | `late_confirm` | 绾搁潰妯℃嫙鐩樺喅绛栵紙浠呰瀵燂紝涓嶅疄鐩橈級 |
| 15:06 | `post_close` | 鏀剁洏蹇収 + 鏁版嵁鍋ュ悍 |
| 16:30 | `review_fill` | T+1/T+2/T+3 鍥為【 + Dashboard 鏇存柊 |
| 鐩樺悗 | `post_close` HTML | `post_close_review_light.html`锛堢洏鍚庡鐩橈級 |
| 姣忓懆浜?| `weekly` HTML | `weekly_review_light.html`锛堝懆澶嶇洏锛?|

---

## 馃敘 閫夎偂妯″瀷鎽樿

褰撳墠绛栫暐鐗堟湰锛歚a-share-watchpool-v0.9.0` 路 妯″瀷锛歚sector-first-driver-risk-execution-v4`

### 涓绘鍏ュ洿纭€ф潯浠讹紙鍏ㄩ儴婊¤冻锛?
| 缁村害 | 闃堝€?|
|------|------|
| 甯傚満鎯呯华鍒?| 鈮?50 |
| 鏉垮潡鏂瑰悜 | 蹇呴』涓轰紭鍏堟柟鍚?|
| `driver_score`锛堥┍鍔ㄥ姏锛墊 鈮?72 |
| `risk_penalty`锛堥闄╂墸鍒嗭級| 鈮?8 |
| `execution_score`锛堟墽琛岃川閲忥級| 鈮?70 |
| `execution_action` | 蹇呴』涓?`clear` |

### 涓夋。鏃堕棿缁村害

| 鍒嗙被 | 鎸佷粨鍛ㄦ湡 | 璇存槑 |
|------|---------|------|
| 鐭嚎娉㈡鍊欓€?| 1鈥?0 浜ゆ槗鏃?| 涓ユ牸涓绘锛岄渶鍏ㄩ儴纭€ф潯浠堕€氳繃 |
| 涓嚎瓒嬪娍鍊欓€?| 20鈥?0 鏃?| 澶囬€?鎺ㄦ紨锛屾潯浠舵湭鍏ㄦ弧瓒虫椂闄嶇骇 |
| 闀跨嚎浠峰€肩嚎绱?| 60鈥?40 鏃?| 鐮旂┒绾跨储锛屼笉杩涚煭绾夸富姒?|

> 璇︾粏妯″瀷璇存槑瑙?[docs/selection-model.md](docs/selection-model.md)

---

## 馃殌 蹇€熶笂鎵?
### 1. 瀹夎渚濊禆

```bash
pip install -r requirements.txt
```

### 2. 鍏嬮殕骞跺垵濮嬪寲宸ヤ綔绌洪棿

```bash
git clone https://github.com/hasesc/a-share-watchpool.git
cd a-share-watchpool

# 鍒涘缓杩愯鏃剁洰褰曪紙鏁版嵁鐩綍涓嶇撼鍏ョ増鏈帶鍒讹級
mkdir -p workspace/data/watchpool workspace/reports/daily workspace/logs
```

### 3. 杩愯鐩樺墠 Pipeline

```powershell
# 淇敼 ROOT 涓轰綘鐨勬湰鍦拌矾寰勶紝DATE 涓虹洰鏍囨棩鏈?$ROOT = "D:\your-path\a-share-watchpool\workspace"
$DATE = "20260624"

powershell -File "scripts\run_daily_pipeline.ps1" -Stage pre_market -Root $ROOT -Date $DATE
```

### 4. 鏌ョ湅鎶ュ憡

鎶ュ憡杈撳嚭鍒?`workspace/reports/daily/<yyyymmdd>/pre_market_light.html`锛岀敤娴忚鍣ㄧ洿鎺ユ墦寮€銆?
> 馃摉 璇︾粏瀹夎涓庨厤缃鏄庤 [docs/quick-start.md](docs/quick-start.md)

---

## 馃搧 鐩綍缁撴瀯

```
a-share-watchpool/
鈹?鈹溾攢鈹€ scripts/                   鈫?鏍稿績鑴氭湰锛堟暟鎹噰闆嗐€佹覆鏌撱€佸璁★級
鈹?  鈹溾攢鈹€ run_daily_pipeline.ps1 鈫?Pipeline 鎬昏皟搴?鈹?  鈹溾攢鈹€ collect_public_data.py 鈫?琛屾儏鏁版嵁閲囬泦
鈹?  鈹溾攢鈹€ render_watchpool_report.py 鈫?HTML 娓叉煋寮曟搸
鈹?  鈹溾攢鈹€ watchpool_db.py        鈫?SQLite + Dashboard
鈹?  鈹溾攢鈹€ audit_strategy.py      鈫?绛栫暐瀹¤
鈹?  鈹斺攢鈹€ ...锛堝叡 14 涓剼鏈級
鈹?鈹溾攢鈹€ workspace/                 鈫?鏈湴杩愯鏃讹紙鍏嬮殕鍚庡湪姝よ繍琛岋級
鈹?  鈹溾攢鈹€ scripts/
鈹?  鈹?  鈹溾攢鈹€ render_watchpool_light.py  鈫?涓绘棩鎶ュ叆鍙?鈹?  鈹?  鈹斺攢鈹€ collect_policy_news.py     鈫?鏂伴椈閲囬泦
鈹?  鈹溾攢鈹€ config/
鈹?  鈹?  鈹斺攢鈹€ industry_theme_map.json    鈫?琛屼笟涓婚鏄犲皠
鈹?  鈹斺攢鈹€ paper-sim/             鈫?绾搁潰妯℃嫙鐩?鈹?      鈹溾攢鈹€ config.json
鈹?      鈹斺攢鈹€ scripts/
鈹?          鈹溾攢鈹€ paper_sim_portfolio.py
鈹?          鈹斺攢鈹€ paper_sim_strategy_lab.py
鈹?鈹溾攢鈹€ tools/                     鈫?鐙珛宸ュ叿锛堟棤闇€ pipeline 涓婁笅鏂囷級
鈹?  鈹溾攢鈹€ screen_a_funds.py      鈫?鍩洪噾绛涢€夛紙鏀剁泭 + 鏈€澶у洖鎾わ級
鈹?  鈹斺攢鈹€ inspect_fund_holdings.py 鈫?鍩洪噾鎸佷粨鏌ヨ
鈹?鈹溾攢鈹€ docs/                      鈫?鏂囨。
鈹?  鈹溾攢鈹€ quick-start.md
鈹?  鈹溾攢鈹€ selection-model.md
鈹?  鈹斺攢鈹€ data-sources.md
鈹?鈹溾攢鈹€ requirements.txt
鈹溾攢鈹€ LICENSE
鈹斺攢鈹€ DISCLAIMER.md
```

---

## 馃洜锔?涓昏鑴氭湰璇存槑

| 鑴氭湰 | 鍔熻兘 |
|------|------|
| `scripts/collect_public_data.py` | 閲囬泦鍏ㄥ競鍦哄揩鐓с€佷氦鏄撴棩鍘嗐€並绾垮巻鍙?|
| `scripts/check_execution_quality.py` | 娑ㄥ仠鏉?娴佸姩鎬?鎸箙/杩介珮椋庨櫓妫€鏌?|
| `scripts/check_risk_events.py` | 鍏憡椋庨櫓鎵弿锛堝噺鎸併€佽В绂併€佺洃绠＄瓑锛?|
| `scripts/check_concentration.py` | 鍊欓€夐泦琛屼笟闆嗕腑搴︽鏌?|
| `scripts/monitor_data_health.py` | 鏁版嵁璐ㄩ噺鍋ュ悍鎶ュ憡 |
| `scripts/render_watchpool_report.py` | 娓叉煋 HTML 鏃ユ姤锛堢函娓叉煋灞傦級 |
| `scripts/watchpool_db.py` | SQLite 绠＄悊 + 绛栫暐浠〃鐩?|
| `scripts/audit_strategy.py` | 绛栫暐璇佹嵁璐ㄩ噺瀹¤锛堥渶 鈮?0 鏍锋湰锛?|
| `scripts/fill_review_outcomes.py` | T+1/T+2/T+3 缁撴灉鑷姩濉厖 |
| `workspace/scripts/render_watchpool_light.py` | 涓绘棩鎶ュ叆鍙ｏ紙杞婚噺鐗堬紝鍚暟鎹鍙?娓叉煋锛?|
| `workspace/scripts/collect_policy_news.py` | 鏀跨瓥/琛屼笟/涓偂鏂伴椈鍌寲鍓傞噰闆?|
| `workspace/paper-sim/scripts/paper_sim_portfolio.py` | 绾搁潰妯℃嫙鐩橈紙鎸佷粨绠＄悊 + 鍐崇瓥锛?|

---

## 馃О 鐙珛宸ュ叿

### 鍩洪噾绛涢€?
```bash
python tools/screen_a_funds.py
```

绛涢€夋潯浠讹細杩?1 骞存鏀剁泭銆佹渶澶у洖鎾?鈮?20%銆佹帓闄ゅ€哄熀/璐у竵/QDII锛岃緭鍑哄墠 40 鍚嶃€?
### 鍩洪噾鎸佷粨鏌ヨ

```bash
python tools/inspect_fund_holdings.py
```

鏌ヨ鎸囧畾鍩洪噾浠ｇ爜鐨勫墠鍗佸ぇ鎸佷粨鍜岃涓氶厤缃€?
---

## 鈿狅笍 鏁版嵁鏉ユ簮

鏈郴缁熶娇鐢ㄤ互涓嬪叕寮€鏁版嵁鎺ュ彛锛?
- **[AKShare](https://github.com/akfamily/akshare)**锛氬叏甯傚満琛屾儏蹇収銆並绾垮巻鍙层€佷氦鏄撴棩鍘?- **涓滄柟璐㈠瘜**锛氳鎯呭鐢ㄦ簮
- **鑵捐琛屾儏**锛氬崟鑲′环鏍间氦鍙夐獙璇?
> 鎵€鏈夋暟鎹潎涓哄叕寮€淇℃伅锛屼笉浣跨敤浠讳綍浠樿垂鎴栫壒鏉冩暟鎹帴鍙ｃ€?
---

## 馃 璐＄尞

娆㈣繋鎻愪氦 Issue 鍜?Pull Request锛?
- **Bug 鍙嶉**锛氫娇鐢?Issue 妯℃澘 鈫?Bug Report
- **鍔熻兘寤鸿**锛氫娇鐢?Issue 妯℃澘 鈫?Feature Request
- **浠ｇ爜璐＄尞**锛欶ork 鈫?鏂板缓鍒嗘敮 鈫?PR锛岃闄勪笂绠€瑕佽鏄?
---

## 馃搫 璁稿彲璇?
MIT License 路 瑙?[LICENSE](LICENSE)

---

## 鈿栵笍 鍏嶈矗澹版槑

鏈」鐩粎渚涗釜浜哄涔犱笌鐮旂┒锛屼笉鏋勬垚鎶曡祫寤鸿锛屼笉浜х敓鐪熷疄涔板崠鎸囦护銆傝瑙?[DISCLAIMER.md](DISCLAIMER.md)銆?
**甯傚満鏈夐闄╋紝浜ゆ槗闇€璋ㄦ厧銆?*

