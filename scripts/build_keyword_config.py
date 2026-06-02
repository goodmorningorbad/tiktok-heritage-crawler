#!/usr/bin/env python3
"""Build versioned UNESCO ICH keyword config from existing project metadata."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = ROOT / "data" / "unesco_tiktok_20260530_233505.csv"
OUT = ROOT / "config" / "unesco_ich_keywords.v1.json"

BASE_TERMS = {
    "春节": ["春节", "新年", "过年", "chinesenewyear", "lunarnewyear", "cny", "springfestival", "gongxifacai", "新年快乐"],
    "中国传统制茶技艺及其相关习俗": ["茶", "茶艺", "中国茶", "gongfutea", "gongfucha", "chinesetea", "teaceremony", "teaculture", "puer", "puerh"],
    "太极拳": ["太极", "太极拳", "taichi", "taijiquan"],
    "送王船": ["送王船", "王船", "ongchun", "wangchuan", "wangkang", "boatburning"],
    "藏医药浴法": ["藏医", "药浴", "sowarigpa", "tibetanmedicine", "tibetanhealing"],
    "二十四节气": ["二十四节气", "节气", "solarterms", "24solarterms", "chinesecalendar"],
    "中国珠算": ["珠算", "算盘", "abacus", "zhusuan"],
    "福建木偶戏": ["木偶", "布袋戏", "puppet", "puppetry", "budaixi", "fujianpuppet"],
    "赫哲族伊玛堪": ["赫哲", "伊玛堪", "hezhe", "yimakan"],
    "中国皮影戏": ["皮影", "皮影戏", "shadowpuppet", "shadowpuppetry", "piying"],
    "麦西热甫": ["麦西热甫", "meshrep", "mäshräp", "uyghur"],
    "中国水密隔舱福船制造技艺": ["水密隔舱", "福船", "watertight", "junk", "fuchuan"],
    "中国木活字印刷术": ["木活字", "活字", "movabletype", "woodentype", "printing"],
    "京剧": ["京剧", "pekingopera", "beijingopera", "chineseopera"],
    "中医针灸": ["针灸", "acupuncture", "tcm", "chinesemedicine"],
    "黎族传统纺染织绣技艺": ["黎族", "织锦", "纺染", "liethnic", "brocade", "textile"],
    "中国木拱桥传统营造技艺": ["木拱桥", "廊桥", "woodenarchbridge", "coveredbridge"],
    "羌年": ["羌年", "羌族", "qiangnewyear", "qiang"],
    "侗族大歌": ["侗族", "侗族大歌", "kamgrandchoir", "dongchorus"],
    "西安鼓乐": ["西安鼓乐", "鼓乐", "xianwind", "drummusic"],
    "中国蚕桑丝织技艺": ["蚕桑", "丝织", "silk", "sericulture", "silkweaving"],
    "南音": ["南音", "nanyin", "nanguan", "quanzhoumusic"],
    "南京云锦织造技艺": ["云锦", "南京云锦", "yunjin", "nanjingbrocade"],
    "宣纸传统制作技艺": ["宣纸", "xuanpaper", "ricepaper", "papermaking"],
    "粤剧": ["粤剧", "cantoneseopera", "yueopera"],
    "格萨(斯)尔史诗传统": ["格萨尔", "格萨", "gesar", "epic"],
    "龙泉青瓷传统烧制技艺": ["龙泉", "青瓷", "longquanceladon", "celadon"],
    "热贡艺术": ["热贡", "唐卡", "regong", "thangka"],
    "藏戏": ["藏戏", "tibetanopera", "lhamo", "achelhamo"],
    "玛纳斯": ["玛纳斯", "manas", "kyrgyz"],
    "蒙古族呼麦": ["呼麦", "khoomei", "throatsinging", "mongolian"],
    "花儿": ["花儿", "huaer", "northwestchinasong"],
    "中国朝鲜族农乐舞": ["农乐舞", "朝鲜族", "nongak", "farmersdance"],
    "中国书法": ["书法", "calligraphy", "shufa", "chineseink"],
    "中国篆刻": ["篆刻", "印章", "sealcarving", "chineseseal"],
    "中国剪纸": ["剪纸", "papercut", "papercutting", "chinesepapercut"],
    "中国传统木结构建筑营造技艺": ["斗拱", "古建", "木结构", "timberframe", "chinesearchitecture"],
    "端午节": ["端午", "端午节", "dragonboat", "duanwu", "zongzi"],
    "妈祖信俗": ["妈祖", "mazu", "seagoddess"],
    "中国雕版印刷技艺": ["雕版", "雕版印刷", "blockprinting", "woodblock"],
    "昆曲": ["昆曲", "kunqu", "kunopera", "kunquopera"],
    "古琴艺术": ["古琴", "guqin", "chinesezither"],
    "新疆维吾尔木卡姆艺术": ["木卡姆", "muqam", "uyghurmuqam"],
    "蒙古族长调民歌": ["长调", "longsong", "urtiinduu", "mongoliansong"],
}

ADJUSTMENTS = {
    "粤剧": {
        "search_terms": ["Cantonese opera", "cantoneseopera", "粤剧"],
        "core_terms": ["Cantonese opera", "cantoneseopera", "粤剧", "广东粤剧", "Hong Kong Cantonese opera"],
        "negative_terms": ["越剧", "Yueju", "Shaoxing opera", "浙江", "越剧红楼梦", "yueopera"],
    },
    "蒙古族呼麦": {
        "search_terms": ["khoomei", "höömii", "throat singing", "呼麦"],
        "core_terms": ["Inner Mongolia", "内蒙古", "Chinese Mongolian", "Mongolian ethnic group in China", "中国 呼麦", "内蒙古 呼麦", "khoomei", "呼麦"],
        "negative_terms": ["Mongolia", "Ulaanbaatar", "Mongolian singer", "Tuvan", "Tuva", "Alash", "Huun-Huur-Tu"],
    },
    "中国蚕桑丝织技艺": {
        "search_terms": ["silk", "丝绸", "sericulture", "silk craftsmanship", "silk weaving", "蚕桑", "缫丝"],
        "core_terms": ["sericulture", "silk craftsmanship", "silk weaving", "silkworm", "silk reeling", "桑蚕", "缫丝", "织造", "蚕桑"],
        "negative_terms": ["silk dress", "silk scarf", "silk pillowcase", "bedsheet", "duvet", "卖货", "factory", "industrial", "satin"],
    },
    "中国传统制茶技艺及其相关习俗": {
        "search_terms": ["Chinese tea", "gongfu tea", "gongfutea", "tea ceremony", "茶艺", "功夫茶", "炒茶", "制茶", "揉捻"],
        "core_terms": ["traditional tea processing", "Chinese tea ceremony", "gongfu tea", "gongfutea", "功夫茶", "茶礼", "炒茶", "制茶工艺", "茶艺"],
        "negative_terms": ["milk tea", "bubble tea", "boba", "matcha latte", "tea shop", "tea pet", "奶茶"],
    },
    "福建木偶戏": {
        "search_terms": ["budaixi", "布袋戏", "掌中戏", "Fujian puppetry", "Chinese puppet", "glove puppetry"],
        "core_terms": ["budaixi", "布袋戏", "掌中戏", "Fujian puppetry", "Chinese puppet", "glove puppetry", "福建木偶"],
        "negative_terms": ["shadow puppetry", "Chinese shadow puppetry", "皮影", "shadow play", "hand shadow"],
    },
    "中国皮影戏": {
        "search_terms": ["Chinese shadow puppetry", "shadow puppetry", "皮影戏", "皮影", "piying"],
        "core_terms": ["Chinese shadow puppetry", "shadow puppetry", "皮影戏", "皮影", "piying"],
        "negative_terms": ["hand shadow", "shadow hand"],
    },
    "黎族传统纺染织绣技艺": {
        "search_terms": ["Li textile", "Li brocade", "黎锦", "黎族织锦", "纺染织绣", "黎族"],
        "core_terms": ["Li textile", "Li brocade", "黎锦", "黎族织锦", "纺染织绣", "spinning dyeing weaving embroidering"],
        "negative_terms": ["Li food", "黎族美食", "restaurant", "ethnic costume challenge", "旅游打卡"],
    },
    "南音": {
        "search_terms": ["Nanyin", "Nanguan music", "南音", "泉州南音", "Fujian Nanyin"],
        "core_terms": ["Nanyin", "Nanguan music", "南音", "泉州南音", "Fujian Nanyin"],
        "negative_terms": ["Nanguan food street", "南关", "兰州南关", "street food", "南关夜市"],
    },
}


def uniq(items):
    seen = set()
    out = []
    for item in items:
        s = str(item).strip()
        key = s.lower()
        if s and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def hashtag_terms(terms):
    out = []
    for term in terms:
        s = str(term).strip().replace("#", "")
        if s and " " not in s and len(s) <= 40:
            out.append(s)
    return uniq(out[:6])


def load_projects():
    projects = {}
    with SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            hid = int(row["heritage_id"])
            projects[hid] = {
                "id": hid,
                "name_cn": row["heritage_name_cn"],
                "name_en": row["heritage_name_en"],
                "year": row.get("heritage_year") or "",
                "category": row.get("heritage_category") or "",
            }
    return [projects[k] for k in sorted(projects)]


def main():
    projects = load_projects()
    config = {
        "version": "v1",
        "description": "UNESCO Chinese ICH TikTok keyword config. negative_terms are labeling-only; never collection exclusions.",
        "source": str(SOURCE_CSV.relative_to(ROOT)),
        "expected_project_count": 45,
        "negative_terms_policy": "label_only_never_exclude",
        "projects": [],
    }
    for p in projects:
        name = p["name_cn"]
        base = BASE_TERMS.get(name, [])
        search_terms = list(base)
        core_terms = list(base)
        negative_terms = []
        adj = ADJUSTMENTS.get(name, {})
        if adj.get("search_terms"):
            search_terms = adj["search_terms"]
        if adj.get("core_terms"):
            core_terms = adj["core_terms"]
        if adj.get("negative_terms"):
            negative_terms = adj["negative_terms"]
        config["projects"].append({
            **p,
            "search_terms": uniq(search_terms),
            "core_terms": uniq(core_terms),
            "negative_terms": uniq(negative_terms),
            "hashtag_terms": hashtag_terms(search_terms),
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} with {len(config['projects'])} projects")
    if len(config["projects"]) != config["expected_project_count"]:
        print(f"WARNING: expected {config['expected_project_count']} projects, found {len(config['projects'])}")


if __name__ == "__main__":
    main()
