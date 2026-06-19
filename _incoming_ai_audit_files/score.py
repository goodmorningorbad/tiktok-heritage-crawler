# -*- coding: utf-8 -*-
"""
判分脚本:对比AI判断 vs 人工标准答案
用法:python3 score.py ai_results.jsonl
ai_results.jsonl 是你那条渠道输出的,每行一个 {"id":..,"verdict":..,...}
"""
import json, sys
from collections import Counter, defaultdict

answer_key=json.load(open('/home/claude/ai_relevance/answer_key_298.json',encoding='utf-8'))

ai={}
with open(sys.argv[1] if len(sys.argv)>1 else 'ai_results.jsonl',encoding='utf-8') as f:
    for line in f:
        line=line.strip()
        if not line: continue
        try:
            d=json.loads(line)
            ai[str(d['id'])]=d.get('verdict','').strip()
        except:
            print("解析失败行:",line[:80])

# 对齐
matched=0; total=0
confusion=defaultdict(lambda:Counter())  # 人工 -> AI
missing=0
for vid,human_v in answer_key.items():
    if vid not in ai:
        missing+=1; continue
    total+=1
    ai_v=ai[vid]
    confusion[human_v][ai_v]+=1
    if ai_v==human_v: matched+=1

print(f"=== 总体 ===")
print(f"AI覆盖: {total}/{len(answer_key)} (缺{missing})")
print(f"总一致率: {matched}/{total} = {matched/total*100:.1f}%")
print(f"⚠️ 注意:人工答案87%是'不相关',总一致率会虚高,重点看下面分类")

print(f"\n=== 分类混淆矩阵(人工 → AI) ===")
for human_v in ['相关','不相关','拿不准']:
    row=confusion[human_v]
    rtot=sum(row.values())
    if rtot==0: continue
    print(f"\n人工判[{human_v}] 共{rtot}条, AI判成:")
    for ai_v,c in row.most_common():
        flag=" ✓" if ai_v==human_v else " ✗"
        print(f"    {ai_v}: {c} ({c/rtot*100:.0f}%){flag}")

print(f"\n=== 关键指标 ===")
# 相关的召回:人工判相关的,AI也判相关的比例
rel=confusion['相关']
rel_recall=rel.get('相关',0)/max(sum(rel.values()),1)
print(f"相关召回率(人工相关→AI也判相关): {rel_recall*100:.0f}%  ← 这个低说明AI漏判相关、在随大流")
# 不相关的准确:AI判不相关的里,人工也判不相关的比例
ai_irrel_total=sum(confusion[h].get('不相关',0) for h in confusion)
ai_irrel_correct=confusion['不相关'].get('不相关',0)
print(f"AI判'不相关'的精确率: {ai_irrel_correct/max(ai_irrel_total,1)*100:.0f}%  ← 这个低说明AI误杀了相关的")

print(f"\n=== 判定 ===")
if rel_recall>=0.6 and matched/total>=0.8:
    print("✅ AI靠谱(相关召回够、总一致高),可以用到YouTube")
elif rel_recall<0.4:
    print("❌ AI在随大流(相关召回太低),没真的学会判断,需调prompt重验")
else:
    print("⚠️ AI中等,看具体混淆矩阵决定是否调prompt")
