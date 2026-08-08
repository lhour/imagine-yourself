"""初始化知识库示例数据 — 为 10 个分类各添加若干条目。"""

import json
import sys
from pathlib import Path

# 添加项目根到路径
ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

# 延迟导入避免循环依赖
def _get_store():
    import importlib.util
    spec = importlib.util.spec_from_file_location("store", str(Path(__file__).parent / "store.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.KnowledgeStore


SAMPLE_DATA = [
    # ===== 武器法宝 =====
    {"title": "墨渊剑", "content": "上古神剑，剑身漆黑如墨，蕴含深渊之力。使用者需以心神为引，否则易被剑意反噬。剑身铭文记载着上古铸剑师的名字。", "category_name": "武器法宝", "keywords": ["神剑", "上古", "墨"], "tags": ["武器", "剑"], "source": "init", "importance": 5},
    {"title": "太虚镜", "content": "能映照人心最深处的欲望与恐惧，亦能看穿幻术与伪装。使用过度会让使用者精神疲惫。", "category_name": "武器法宝", "keywords": ["法宝", "镜", "幻术"], "tags": ["法宝", "辅助"], "source": "init", "importance": 5},
    {"title": "追魂锁", "content": "可以锁定敌人魂魄的灵器，被锁定者短时间内无法使用任何异能。对精神力消耗极大。", "category_name": "武器法宝", "keywords": ["灵器", "锁魂", "克制"], "tags": ["灵器", "封印"], "source": "init", "importance": 4},
    {"title": "无相甲", "content": "外表普通的灰色布衣，实则能吸收三成物理伤害。每次吸收都会在布衣上浮现红色纹路。", "category_name": "武器法宝", "keywords": ["防具", "布衣", "防护"], "tags": ["防具"], "source": "init", "importance": 3},
    {"title": "天机罗盘", "content": "可在城市中感知强大异能者的方位，但精度有限。对同一目标连续使用会引起对方注意。", "category_name": "武器法宝", "keywords": ["罗盘", "感知", "定位"], "tags": ["辅助", "侦查"], "source": "init", "importance": 4},

    # ===== 武功武学 =====
    {"title": "夺魂十三式", "content": "一种以精神力为核心的近战技法，共十三式。最后一式需在生死边缘才能领悟，能短暂夺取敌人意识。", "category_name": "武功武学", "keywords": ["精神力", "十三式", "夺魂"], "tags": ["近战", "精神"], "source": "init", "importance": 5},
    {"title": "御风诀", "content": "都市中的轻身功法，可让人短时间内踏空而行。需要消耗体力，不适合长时间战斗。", "category_name": "武功武学", "keywords": ["轻功", "御风", "都市"], "tags": ["轻功"], "source": "init", "importance": 3},
    {"title": "铁壁桩", "content": "防御型功法，可使身体短时间内变硬如铁。缺点是移动速度大幅降低。", "category_name": "武功武学", "keywords": ["防御", "铁壁", "硬功"], "tags": ["防御"], "source": "init", "importance": 3},
    {"title": "碎影步", "content": "高速身法，移动时会留下残影。对视力好的对手无效，且体力消耗极大。", "category_name": "武功武学", "keywords": ["身法", "残影", "高速"], "tags": ["身法"], "source": "init", "importance": 4},
    {"title": "心魔经", "content": "以精神攻击为核心的功法，可在对方意识中制造幻象。修习者容易走火入魔。", "category_name": "武功武学", "keywords": ["精神攻击", "幻象", "心魔"], "tags": ["精神", "攻击"], "source": "init", "importance": 5},

    # ===== 人物外貌 =====
    {"title": "清冷剑修外貌", "content": "身形颀长，面容冷峻，眉宇间有淡淡的书卷气。身着黑色长风衣，领口微竖。持剑时气场凌厉，不笑时显得疏离。", "category_name": "人物外貌", "keywords": ["清冷", "剑修", "疏离"], "tags": ["外貌", "气质"], "source": "init", "importance": 4},
    {"title": "豪门千金外貌", "content": "身着裁剪考究的米白色西装套裙，长发及腰用珍珠发簪固定。气质优雅疏离，眼神中带着与生俱来的优越感。", "category_name": "人物外貌", "keywords": ["豪门", "优雅", "珍珠"], "tags": ["外貌", "气质"], "source": "init", "importance": 4},
    {"title": "街头少年外貌", "content": "穿着宽大的黑色卫衣和破洞牛仔裤，脖子上挂着耳机。眉眼间带着不羁笑意，左耳有银色耳钉。身上总带着滑板或涂鸦工具。", "category_name": "人物外貌", "keywords": ["街头", "少年", "不羁"], "tags": ["外貌", "穿着"], "source": "init", "importance": 3},
    {"title": "神秘老者外貌", "content": "满头银发却精神矍铄，身着深灰色中山装或唐装。双目深邃如古井，说话时语速缓慢但不容置疑。", "category_name": "人物外貌", "keywords": ["老者", "银发", "深邃"], "tags": ["外貌", "气质"], "source": "init", "importance": 4},
    {"title": "干练女警外貌", "content": "棕色短发及耳，身着黑色制服。腰配手枪和对讲机，走路带风。眼神锐利如鹰，不轻易表露情绪。", "category_name": "人物外貌", "keywords": ["女警", "干练", "短发"], "tags": ["外貌", "职业"], "source": "init", "importance": 3},

    # ===== 人物性格 =====
    {"title": "冷面心热型", "content": "外表冷漠无情，说话直接甚至刻薄，但内心善良。会暗中帮助他人却从不承认。对亲近的人保护欲极强。", "category_name": "人物性格", "keywords": ["冷面", "心热", "保护"], "tags": ["性格"], "source": "init", "importance": 5},
    {"title": "腹黑绅士型", "content": "表面温文尔雅、乐于助人，实则心思缜密、掌控欲强。善于利用他人达成目的，但有自己的底线。", "category_name": "人物性格", "keywords": ["腹黑", "绅士", "掌控"], "tags": ["性格"], "source": "init", "importance": 5},
    {"title": "热血正义型", "content": "正义感爆棚，见不得任何不公。冲动莽撞但关键时刻靠得住。对朋友忠诚，愿意为正义付出代价。", "category_name": "人物性格", "keywords": ["热血", "正义", "冲动"], "tags": ["性格"], "source": "init", "importance": 3},
    {"title": "慵懒智者型", "content": "表面懒散随意，实则洞察一切。说话慢条斯理但总能一针见血。喜欢用玩笑化解严肃场合。", "category_name": "人物性格", "keywords": ["慵懒", "智者", "洞察"], "tags": ["性格"], "source": "init", "importance": 4},
    {"title": "隐忍复仇者型", "content": "表面温顺有礼，内心背负深重仇恨。行事步步为营，绝不轻易暴露真实想法。最终目标明确且不可动摇。", "category_name": "人物性格", "keywords": ["隐忍", "复仇", "深沉"], "tags": ["性格"], "source": "init", "importance": 5},

    # ===== 种族生物 =====
    {"title": "影栖族", "content": "生活在城市阴影中的异能者种族，能与影子融为一体。人数稀少，聚居在老城区地下。对阳光敏感。", "category_name": "种族生物", "keywords": ["异能族", "影子", "都市"], "tags": ["种族"], "source": "init", "importance": 5},
    {"title": "血脉觉醒者", "content": "天生携带异能基因的人类后裔，需经特定事件或仪式才能觉醒。觉醒后能力因人而异，从预知未来到操纵元素不等。", "category_name": "种族生物", "keywords": ["觉醒", "血脉", "基因"], "tags": ["种族", "异能"], "source": "init", "importance": 5},
    {"title": "机械改造体", "content": "通过手术植入机械部件的人类，改造程度从假肢到全身体。拥有超人的力量但失去部分人类情感。", "category_name": "种族生物", "keywords": ["改造", "机械", "赛博"], "tags": ["种族", "改造"], "source": "init", "importance": 4},
    {"title": "灵兽", "content": "被异能者驯化或自然诞生的特殊生物，拥有微弱的意识和特定能力。可作为战斗伙伴或情报来源。", "category_name": "种族生物", "keywords": ["灵兽", "驯化", "伙伴"], "tags": ["生物"], "source": "init", "importance": 3},
    {"title": "虚空行者", "content": "能在不同空间夹层中穿行的存在，极少现身。据说掌握着异能起源的秘密。", "category_name": "种族生物", "keywords": ["虚空", "空间", "神秘"], "tags": ["种族", "神秘"], "source": "init", "importance": 5},

    # ===== 势力组织 =====
    {"title": "天机阁", "content": "都市中最古老的异能者组织，负责维护异能世界与普通人世界的平衡。成员以占卜、预知类异能为主。", "category_name": "势力组织", "keywords": ["组织", "平衡", "古老"], "tags": ["组织", "中立"], "source": "init", "importance": 5},
    {"title": "影渊", "content": "由暗杀者和情报贩子组成的地下组织，只接受委托行事。组织内部等级森严，从不背叛雇主。", "category_name": "势力组织", "keywords": ["暗杀", "情报", "地下"], "tags": ["组织", "黑暗"], "source": "init", "importance": 5},
    {"title": "异能管理局", "content": "官方异能者管理机构，负责登记、监管和调解异能者事务。分为行动组和研究组两大体系。", "category_name": "势力组织", "keywords": ["官方", "管理", "登记"], "tags": ["组织", "官方"], "source": "init", "importance": 5},
    {"title": "血色议会", "content": "由纯血异能家族组成的利益联盟，掌控着城市地下经济。以血脉纯度为尊，歧视平民觉醒者。", "category_name": "势力组织", "keywords": ["家族", "血脉", "利益"], "tags": ["组织", "家族"], "source": "init", "importance": 4},
    {"title": "零号实验室", "content": "不明机构下属的异能研究设施，进行异能觉醒实验和强化研究。失踪者案件频繁的区域。", "category_name": "势力组织", "keywords": ["实验室", "研究", "失踪"], "tags": ["组织", "阴谋"], "source": "init", "importance": 5},

    # ===== 场景地点 =====
    {"title": "暗夜酒吧", "content": "隐藏在老城区地下的异能者聚集地，入口在一家书店后。酒吧内禁止使用异能，违者会被永久拉黑。", "category_name": "场景地点", "keywords": ["酒吧", "地下", "禁忌"], "tags": ["场所", "聚会"], "source": "init", "importance": 5},
    {"title": "中央塔顶层", "content": "城市最高建筑的观景台，夜晚可以俯瞰整座城市。传闻塔顶有神秘能量波动。", "category_name": "场景地点", "keywords": ["高塔", "观景", "能量"], "tags": ["场所", "地标"], "source": "init", "importance": 4},
    {"title": "旧书市集", "content": "每周六清晨开放的古董市场，据说能淘到与异能相关的古籍和道具。吸引各路异能者前来。", "category_name": "场景地点", "keywords": ["市集", "古董", "古籍"], "tags": ["场所", "交易"], "source": "init", "importance": 4},
    {"title": "地铁终点站", "content": "一条废弃的地铁线路终点站，传闻常有灵异事件。被影栖族当作临时据点。", "category_name": "场景地点", "keywords": ["地铁", "废弃", "灵异"], "tags": ["场所", "据点"], "source": "init", "importance": 3},
    {"title": "樱花陵园", "content": "一座百年历史的私人陵园，安葬着多位异能家族先祖。禁忌之地，进入者需有血脉指引。", "category_name": "场景地点", "keywords": ["陵园", "家族", "禁忌"], "tags": ["场所", "禁忌"], "source": "init", "importance": 5},

    # ===== 物品道具 =====
    {"title": "记忆碎片", "content": "能读取他人一段记忆的透明晶体，但只能使用一次。使用时需与目标身体接触。", "category_name": "物品道具", "keywords": ["记忆", "晶体", "一次性"], "tags": ["道具", "消耗品"], "source": "init", "importance": 4},
    {"title": "屏蔽手环", "content": "佩戴后可在短时间内屏蔽自身的异能波动，躲避感知型异能者的探测。持续时间约1小时。", "category_name": "物品道具", "keywords": ["屏蔽", "手环", "探测"], "tags": ["道具", "防御"], "source": "init", "importance": 4},
    {"title": "能量饮料", "content": "异能者专用恢复剂，能快速补充异能消耗。黑市价格昂贵，且有轻微依赖性。", "category_name": "物品道具", "keywords": ["恢复", "饮料", "黑市"], "tags": ["道具", "消耗品"], "source": "init", "importance": 3},
    {"title": "契约卷轴", "content": "上古遗留的仪式道具，用于签订具有精神约束力的契约。违反契约者将遭受精神反噬。", "category_name": "物品道具", "keywords": ["契约", "仪式", "反噬"], "tags": ["道具", "仪式"], "source": "init", "importance": 5},
    {"title": "定位锚", "content": "小型定位装置，植入目标物体后可持续追踪其位置。信号范围覆盖整座城市。", "category_name": "物品道具", "keywords": ["定位", "追踪", "植入"], "tags": ["道具", "侦查"], "source": "init", "importance": 3},

    # ===== 剧情套路 =====
    {"title": "身份反转套路", "content": "在关键战斗中揭露反派是主角的旧友/亲人，增加内心冲突。反转后给予双方一段反思对话时间。", "category_name": "剧情套路", "keywords": ["反转", "身份", "冲突"], "tags": ["套路"], "source": "init", "importance": 5},
    {"title": "极限反杀套路", "content": "主角陷入绝境，通过回忆过去/获得临时buff/利用环境等方式完成反杀。反杀后主角状态应有明显变化。", "category_name": "剧情套路", "keywords": ["反杀", "绝境", "buff"], "tags": ["套路"], "source": "init", "importance": 4},
    {"title": "势力混战套路", "content": "多个组织为争夺同一件宝物/目标展开混战。主角被迫选边或保持中立。混战中展现各组织特色。", "category_name": "剧情套路", "keywords": ["混战", "势力", "争夺"], "tags": ["套路"], "source": "init", "importance": 4},
    {"title": "信任崩塌套路", "content": "主角的核心盟友背叛或被控制，迫使主角重新评估身边所有人。后续剧情增加信任主题的探讨。", "category_name": "剧情套路", "keywords": ["背叛", "信任", "崩塌"], "tags": ["套路"], "source": "init", "importance": 5},
    {"title": "代价觉醒套路", "content": "主角为获得更强能力付出惨痛代价（失去记忆/寿命/亲人）。觉醒后能力应与代价相关联。", "category_name": "剧情套路", "keywords": ["觉醒", "代价", "能力"], "tags": ["套路"], "source": "init", "importance": 5},

    # ===== 其他设定 =====
    {"title": "异能等级体系", "content": "F、E、D、C、B、A、S、SS 共8级。F级为初学者，S级可影响城市范围，SS级被视为天灾级。等级通过官方考核评定。", "category_name": "其他设定", "keywords": ["等级", "体系", "考核"], "tags": ["设定"], "source": "init", "importance": 5},
    {"title": "异能觉醒条件", "content": "天生基因+特定刺激。常见刺激包括：生死危机、精神重创、接触异能物品。觉醒过程因人而异，可能持续数天。", "category_name": "其他设定", "keywords": ["觉醒", "条件", "刺激"], "tags": ["设定"], "source": "init", "importance": 5},
    {"title": "记忆封印术", "content": "用精神力封锁特定记忆，被封印者不会察觉。解除封印需要对应施术者的精神力或特定道具。", "category_name": "其他设定", "keywords": ["记忆", "封印", "精神"], "tags": ["设定"], "source": "init", "importance": 4},
    {"title": "空间折叠理论", "content": "认为城市中存在空间夹层，部分高阶异能者可以感知并穿越。夹层中可能藏有上古遗迹。", "category_name": "其他设定", "keywords": ["空间", "夹层", "理论"], "tags": ["设定", "理论"], "source": "init", "importance": 4},
    {"title": "代价等价原则", "content": "都市异能世界的基本法则：获取任何力量都需付出等价代价。代价可以是记忆、寿命、情感或身体部件。", "category_name": "其他设定", "keywords": ["代价", "等价", "法则"], "tags": ["设定", "法则"], "source": "init", "importance": 5},
]


def main():
    KnowledgeStore = _get_store()
    store = KnowledgeStore()

    # 构建 category name → id 映射
    cats = store.list_categories()
    cat_map = {c["name"]: c["id"] for c in cats}

    added = 0
    for item in SAMPLE_DATA:
        cat_name = item.pop("category_name")
        cat_id = cat_map.get(cat_name)
        if cat_id is None:
            print(f"WARNING: 分类不存在 {cat_name}，跳过")
            continue
        result = store.add_item(
            title=item["title"],
            content=item["content"],
            category_id=cat_id,
            keywords=item.get("keywords", []),
            tags=item.get("tags", []),
            source=item.get("source", "init"),
            importance=item.get("importance", 3),
        )
        added += 1
        print(f"  + {item['title']} (分类: {cat_name}, ID: {result.get('id')})")

    stats = store.get_stats()
    print(f"\n完成！共添加 {added} 条，当前知识库总计 {stats['total_items']} 条，{stats['total_categories']} 个分类。")


if __name__ == "__main__":
    main()
