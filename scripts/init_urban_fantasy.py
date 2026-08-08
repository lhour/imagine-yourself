"""初始化都市异能主题剧本 — 生成完整 9+1 文件结构并导入数据库。

主角能力：短暂夺舍他人 5 秒，他人无感知且无其他影响。
时代背景：近未来都市，异能者隐匿于普通人之中。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # d:/Desktop/projecct
sys.path.insert(0, str(ROOT))

# ============ 剧本名称 ============
DRAMA_NAME = "urban_fantasy"

# ============ meta.txt ============
META = {
    "name": "都市隐能录",
    "summary_raw": "在这座看似平静的超级都市中，异能者隐匿于人群。主角陆沉在一次意外中觉醒了短暂夺舍他人5秒的异能——他人无感知，无其他影响。这个能力看似弱小，却在关键时刻能窥探真相、扭转局势。随着调查一起离奇失踪案，陆沉逐渐卷入异能者组织、官方管理机构和神秘势力的多方博弈中，发现自己的觉醒并非偶然，而是与一个百年前的秘密实验紧密相连。",
    "summary_polished": "",
    "era_name": "近未来都市",
    "world_background_raw": "",
    "world_background_polished": "",
    "protagonist_name_default": "陆沉",
    "protagonist_gender_default": "男",
    "protagonist_ability": "短暂夺舍他人5秒",
    "start_game_time": "2024-03-15 22:00",
    "stable_context_version": 1,
}

META["world_background_raw"] = """【时代背景】
故事发生在2024年的东海市——一座拥有三千万人口的超级都市。表面上，这里是科技发达、秩序井然的现代化城市；暗地里，却活跃着数千名隐匿身份的异能者。

【文明形态】
科技：城市拥有完善的监控网络、AI交通系统、生物识别技术。普通人对异能的存在一无所知，政府将其列为最高机密。
社会：异能者分布于社会各阶层，有自己的地下经济和社交网络。官方设立异能管理局负责登记和监管，但登记率不足30%。
文化：异能者文化融合了传统武学、西方神秘学和现代科技。大多数异能者选择隐藏身份，过着双重生活。
经济：城市地下存在以异能者为核心的灰色经济，包括情报交易、异能道具市场、保护服务等。

【主角异能】
陆沉的异能为「短暂夺舍」——可以在5秒内将意识转移到视线内任意一人身上，控制对方的身体。被夺舍者不会有任何感知，事后也不会记得这5秒内发生的事。此能力无冷却时间，但每次只能夺舍一人，距离不超过50米。夺舍期间，陆沉的身体处于无意识状态。

【核心冲突】
陆沉的觉醒并非偶然，而是与一个名为「零号计划」的百年前秘密实验有关。他的存在威胁到多方势力的利益，成为了争夺的核心。"""

META["world_background_polished"] = META["world_background_raw"]
META["summary_polished"] = META["summary_raw"]


# ============ characters.txt (30+ characters) ============
CHARACTERS = [
    # 主角及核心
    {"name": "陆沉", "char_name": "陆沉", "age": 25, "gender": "男", "appearance_raw": "身高182cm，体型偏瘦但肌肉线条明显。黑色短发微乱，额前碎发常遮住右眼。深邃的棕色眼睛，笑起来左脸有一个小酒窝。平时穿着简约的黑色T恤和深灰色夹克，脚踩白色运动鞋。左手腕有一道旧伤疤。", "personality_raw": "表面冷淡疏离，实则内心善良。不擅长表达情感，但会用行动帮助身边的人。对不公之事有本能的愤怒，但习惯压抑。有着远超常人的观察力和同理心，这也是他夺舍能力觉醒的关键。", "ability": "短暂夺舍", "ability_level": "E→D", "importance": 5, "memories": ["童年时父亲离家出走，母亲独自抚养他", "大学时曾因见义勇为受伤，获得一等奖学金", "半年前在地铁事故中意外觉醒夺舍能力", "发现有人在暗中监视自己", "与林晚第一次合作时成功利用夺舍能力破案"]},
    {"name": "林晚", "char_name": "林晚", "age": 24, "gender": "女", "appearance_raw": "身高168cm，长发及肩常扎成马尾。鹅蛋脸，五官精致，眼神锐利。身着便衣时喜欢白色T恤和牛仔裤，配黑色马丁靴。耳后有一颗小痣。", "personality_raw": "干练果决的刑警，说话直接不留情面。对工作极度认真，常常加班到深夜。外表强硬，内心有柔软的一面，对流浪猫格外温柔。因一起特殊案件与陆沉相识。", "ability": "直觉推理", "ability_level": "F", "importance": 5, "memories": ["父亲是警察，在她16岁时因公殉职", "以全省第一的成绩毕业于警官学院", "接手了一起涉及异能者的离奇失踪案", "与陆沉相遇后逐渐发现世界的真相", "养了一只叫「豆豆」的橘猫"]},
    {"name": "苏墨然", "char_name": "苏墨然", "age": 28, "gender": "男", "appearance_raw": "身高185cm，身形修长。黑色长发及腰，用一支玉簪束着。面容俊朗偏中性，皮肤白皙。总是穿着剪裁考究的黑色长风衣，内搭白色衬衫。腰间挂着一柄古朴长剑。", "personality_raw": "表面温文尔雅，实则心思缜密。说话慢条斯理，嘴角常带微笑，但笑容从不达眼底。对陆沉有特殊关注，既像老师又像观察者。身份成谜。", "ability": "剑意操控", "ability_level": "B", "importance": 5, "memories": ["自幼在神秘门派修习剑术", "十年前出现在东海市，身份从无到有", "与天机阁关系密切但不隶属于任何组织", "似乎知道陆沉觉醒的真正原因", "收藏着多件上古灵器"]},
    {"name": "沈清秋", "char_name": "沈清秋", "age": 26, "gender": "女", "appearance_raw": "身高170cm，身材纤细。留着帅气的棕色短发，发梢微翘。面容冷峻，眉骨突出。常穿黑色皮夹克和深紫色唇膏。", "personality_raw": "异能管理局行动组队长，行事雷厉风行。对异能者的存在持保守态度，主张严格监管。内心矛盾，既相信规则又同情觉醒者。与陆沉多次交锋后态度逐渐转变。", "ability": "能量护盾", "ability_level": "A", "importance": 4, "memories": ["18岁觉醒异能，被管理局招募", "曾在行动中误伤无辜平民，留下心理阴影", "与上司在异能政策上存在分歧", "暗中资助过几个无法自处的年轻觉醒者", "知道零号计划的部分真相"]},
    {"name": "周煜", "char_name": "周煜", "age": 32, "gender": "男", "appearance_raw": "身高178cm，微胖。圆脸，戴着金丝眼镜。穿着总是一丝不苟的西装，领带颜色每天不同。中年发福但风度犹存。", "personality_raw": "异能管理局研究组组长，性格温和，善于倾听。是陆沉在管理局内最重要的盟友。对异能研究有狂热的兴趣，但从不越过伦理底线。", "ability": "信息感知", "ability_level": "C", "importance": 4, "memories": ["大学主修神经科学，后被管理局招募", "参与了多项异能研究课题", "发现零号计划的档案并秘密保存", "一直在寻找治愈异能副作用的方法", "有一个同样是觉醒者的女儿"]},

    # 第二梯队重要角色
    {"name": "叶知秋", "char_name": "叶知秋", "age": 27, "gender": "男", "appearance_raw": "身高180cm，身材精壮。短寸头，面容刚毅有棱有角。手臂布满纹身，多为几何图案。穿着黑色背心和战术裤。", "personality_raw": "影渊组织的执行队长，沉默寡言，行动果断。从不质疑命令，也从不透露组织秘密。内心深处渴望摆脱组织束缚，但被家人威胁。", "ability": "影子潜行", "ability_level": "B", "importance": 4, "memories": ["从小被影渊收养训练", "执行过超过50次任务", "家人被组织扣押作为威胁", "与陆沉的多次交手后产生动摇", "最终选择帮助陆沉对抗组织"]},
    {"name": "温诗雨", "char_name": "温诗雨", "age": 22, "gender": "女", "appearance_raw": "身高165cm，娇小。栗色长发，发梢微卷。圆脸大眼睛，笑起来有两个小酒窝。穿洛丽塔风格的裙子或宽松卫衣。", "personality_raw": "表面天真烂漫的大学生，实则是血色议会的私生女。异能是记忆读取，但她不会控制，常常读到他人的痛苦记忆而崩溃。陆沉是第一个保护她的人。", "ability": "记忆读取", "ability_level": "D", "importance": 4, "memories": ["不知道自己的真实身世", "经常在课堂上无意识读取同学的记忆", "被当作异类孤立", "遇到陆沉后获得安全感", "逐渐学会控制异能"]},
    {"name": "韩铁衣", "char_name": "韩铁衣", "age": 45, "gender": "男", "appearance_raw": "身高195cm，虎背熊腰。光头，脸上有刀疤。手臂粗壮如树干，指节布满老茧。穿着无袖黑色T恤，脖子上挂着粗金项链。", "personality_raw": "地下黑市的老大，掌控着东海市异能道具交易。讲义气，对兄弟大方，对敌人残酷。与陆沉惺惺相惜，提供情报支持。", "ability": "金属强化", "ability_level": "A", "importance": 3, "memories": ["曾是军方特种部队成员", "因一次任务中觉醒异能被军队除名", "建立铁衣帮垄断黑市", "与血色议会有利益冲突", "欣赏陆沉的胆识"]},
    {"name": "白少卿", "char_name": "白少卿", "age": 30, "gender": "男", "appearance_raw": "身高183cm，气质儒雅。银灰色头发（天生），面容白净。常穿白色三件套西装，戴银色怀表。手指修长白净。", "personality_raw": "血色议会现任族长之子，腹黑且有野心。视陆沉为必须铲除的威胁。表面上对温诗雨关怀备至，实则视其为棋子。", "ability": "精神压制", "ability_level": "B+", "importance": 4, "memories": ["自幼接受家族精英教育", "20岁觉醒后成为家族重点培养对象", "与温诗雨同父异母但关系恶劣", "一直在寻找零号计划的研究成果", "曾派人刺杀陆沉"]},
    {"name": "秦暮雪", "char_name": "秦暮雪", "age": 29, "gender": "女", "appearance_raw": "身高175cm，身材高挑。黑色长发盘成优雅的髻。凤眸，眼尾微挑。穿着旗袍或深色连衣裙，气质高贵。", "personality_raw": "天机阁首席占卜师，能预知短期未来。性格冷淡，说话时总带有一丝宿命感。对陆沉的命运有特殊关注，多次在预言中看到他的身影。", "ability": "预知之眼", "ability_level": "A", "importance": 4, "memories": ["12岁觉醒后被天机阁收养", "看过无数未来画面，但从未看全自己的命运", "预言中看到陆沉是改变格局的关键", "暗中帮助陆沉但从不解释原因", "最终预言自己会为陆沉而死"]},

    # 第三梯队
    {"name": "林长风", "char_name": "林长风", "age": 48, "gender": "男", "appearance_raw": "身高175cm，普通中年男子长相。黑发夹杂白发，面容和善。穿着朴素的夹克衫，戴着老花镜。", "personality_raw": "林晚的父亲，退休刑警。知道女儿涉及的案件远比表面复杂，暗中提供支持。普通人类，不知道异能存在。", "ability": "无", "ability_level": "-", "importance": 2, "memories": ["妻子早逝，独自抚养林晚", "退休前调查过一起离奇案件未果", "发现女儿最近状态异常", "暗中调查女儿的案件", "最终知道了异能者的存在"]},
    {"name": "方一鸣", "char_name": "方一鸣", "age": 27, "gender": "男", "appearance_raw": "身高176cm，瘦削。戴黑框眼镜，头发乱糟糟。穿着格子衫和牛仔裤，典型程序员打扮。", "personality_raw": "异能管理局技术支持，电脑天才。性格腼腆，不善言辞，但是部门中不可或缺的技术力量。对陆沉的异能数据特别感兴趣。", "ability": "数据入侵", "ability_level": "C", "importance": 3, "memories": ["从小就是电脑天才", "被管理局招募负责技术支持", "偷偷分析陆沉的异能数据", "帮助陆沉获取过机密档案", "发现零号计划的技术日志"]},
    {"name": "赵小虎", "char_name": "赵小虎", "age": 23, "gender": "男", "appearance_raw": "身高172cm，一脸稚气。身材瘦小但眼神机灵。穿着潮流的街头服饰，戴多串手链。", "personality_raw": "街头情报贩子，消息灵通，人脉广泛。虽然年纪小，在道上却是老资格。对陆沉态度友好，是他的重要情报来源。", "ability": "无", "ability_level": "-", "importance": 2, "memories": ["初中辍学混社会", "在旧书市集摆摊起家", "与铁衣帮关系不错", "提供过很多关键情报给陆沉", "被影渊威胁过但没有屈服"]},
    {"name": "楚云裳", "char_name": "楚云裳", "age": 35, "gender": "女", "appearance_raw": "身高178cm，身材傲人。烈焰红唇，波浪卷发。穿着红色紧身连衣裙或黑色职业套装。高跟鞋永远不低于10cm。", "personality_raw": "零号实验室前研究员，因发现项目真相而叛逃。信息女王，掌握大量机密。性格大胆且具攻击性，擅长用魅力达成目的。", "ability": "灵魂侵入", "ability_level": "A-", "importance": 4, "memories": ["曾是生物学研究员", "被零号计划招募参与异能研究", "发现实验的非人道真相", "叛逃时带走大量机密资料", "一直在追杀和被追杀中"]},
    {"name": "许白", "char_name": "许白", "age": 20, "gender": "男", "appearance_raw": "身高170cm，少年感十足。银白色短发（异能副作用），大眼睛。穿着宽松的病号服或运动服。", "personality_raw": "零号实验室的幸存实验体之一，异能失控导致身体停止衰老。性格纯真但害怕与他人接触。被陆沉救出后逐渐恢复。", "ability": "能量爆轰", "ability_level": "S", "importance": 3, "memories": ["从出生就被实验室关押", "多次异能实验导致身体异变", "在实验室中与陆沉相遇", "被陆沉救出后开始新生活", "异能极不稳定，可能危及他人"]},
    {"name": "关如月", "char_name": "关如月", "age": 28, "gender": "女", "appearance_raw": "身高172cm，职业女性气质。齐耳短发，戴着无框眼镜。穿着黑色职业装，拎皮质公文包。", "personality_raw": "中央检察院的特别检察官，负责调查异能相关案件。立场中立，只相信证据。林晚的联络人，多次为案件提供法律支持。", "ability": "无", "ability_level": "-", "importance": 2, "memories": ["司法世家出身", "检察官中的明日之星", "接到第一个异能相关案件", "与林晚合作调查", "逐渐了解异能者世界"]},
    {"name": "姜北", "char_name": "姜北", "age": 38, "gender": "男", "appearance_raw": "身高190cm，粗犷。络腮胡，光头。戴着黑色皮手套，常穿军绿色大衣。", "personality_raw": "影渊组织副总指挥，叶知秋的上级。冷酷无情的执行者，对组织绝对忠诚。唯一的弱点是叶知秋——那是他看着长大的孩子。", "ability": "冰系异能", "ability_level": "A+", "importance": 3, "memories": ["前特种部队成员", "被影渊招募成为骨干", "训练了叶知秋等多位执行者", "执行过多次跨国任务", "最终为保护叶知秋而死"]},
    {"name": "宋星辞", "char_name": "宋星辞", "age": 22, "gender": "女", "appearance_raw": "身高166cm，甜美。栗色卷发，蝴蝶结发饰。穿着粉色系或白色连衣裙。笑容甜美可爱。", "personality_raw": "人气偶像歌手，表面清纯无害，实则是影渊的情报员。利用演出场合收集各方情报。对自己的双重身份感到厌倦。", "ability": "声线操控", "ability_level": "D", "importance": 2, "memories": ["从小被影渊培养为双面间谍", "在娱乐圈打拼五年", "厌倦双重身份想退出", "与陆沉合作提供情报", "最终选择脱离组织"]},
    {"name": "魏行舟", "char_name": "魏行舟", "age": 52, "gender": "男", "appearance_raw": "身高180cm，威严。满头银发整齐后梳，长眉锐目。穿着深色三件套西装，拄银色拐杖。", "personality_raw": "血色议会现任族长，白少卿之父。老谋深算的政治家，将所有人视为棋子。对家族血脉有近乎偏执的重视。", "ability": "血脉觉醒", "ability_level": "A", "importance": 3, "memories": ["25岁继任族长", "将家族从地下势力发展成经济帝国", "对温诗雨的存在感到尴尬", "将陆沉视为最大威胁", "最终被自己儿子背叛"]},
    {"name": "韩星野", "char_name": "韩星野", "age": 26, "gender": "男", "appearance_raw": "身高183cm，俊美。黑色长眉，桃花眼。穿着时尚设计师品牌，金丝边眼镜。", "personality_raw": "天机阁占卜师，秦暮雪的师弟。性格跳脱，爱开玩笑，但占卜准确率极高。对秦暮雪有超越姐弟的感情。", "ability": "吉凶占卜", "ability_level": "B", "importance": 3, "memories": ["天机阁内门弟子", "占卜天赋仅次于秦暮雪", "暗恋师姐秦暮雪", "帮助陆沉分析过多次危机", "最终接任天机阁首席"]},
    {"name": "沈默", "char_name": "沈默", "age": 33, "gender": "男", "appearance_raw": "身高175cm，普通。戴着鸭舌帽，帽檐压得很低。穿着普通的灰色卫衣。", "personality_raw": "都市传说中的「无声行者」，能潜行至任意位置。身份成谜，有人说他是情报贩子，有人说他是幽灵。其实是多年前失踪的觉醒者。", "ability": "无声潜行", "ability_level": "A", "importance": 3, "memories": ["十年前突然消失", "一直以神秘身份活动", "为各方提供情报但不收钱", "暗中保护过多个年轻觉醒者", "真实身份是陆沉父亲的旧友"]},
    {"name": "陆远山", "char_name": "陆远山", "age": 58, "gender": "男", "appearance_raw": "身高178cm，沧桑。满脸皱纹，灰白头发。穿着旧式中山装，眼神深邃。", "personality_raw": "陆沉的父亲，当年「离家出走」实则是为调查零号计划而卧底。性格沉默寡言，将感情深埋心底。知道陆沉会觉醒，一直在暗中引导。", "ability": "感知强化", "ability_level": "B", "importance": 4, "memories": ["零号计划原研究员之一", "30年前选择卧底而非逃亡", "以普通人身份生活多年", "暗中引导陆沉的成长", "最终与陆沉相认并牺牲"]},
    {"name": "顾青山", "char_name": "顾青山", "age": 60, "gender": "男", "appearance_raw": "身高172cm，精瘦。戴着老花镜，皱纹深刻。穿着灰色衬衫和布鞋，手里常拿放大镜。", "personality_raw": "旧书市集的古董商，前天机阁成员。看似普通的老人，实则知晓大量异能界秘辛。是陆沉的重要顾问。", "ability": "鉴定", "ability_level": "F", "importance": 2, "memories": ["天机阁前占卜师", "因预言到自身悲剧而选择隐退", "在旧书市集经营30年", "是陆沉的启蒙者之一", "最终为保护市集中的觉醒者而牺牲"]},
    {"name": "江若溪", "char_name": "江若溪", "age": 25, "gender": "女", "appearance_raw": "身高169cm，温婉。黑色直长发，素面朝天。穿着素色连衣裙，气质安静。", "personality_raw": "陆沉的前邻居兼同学，普通人类。善良温柔，是陆沉与普通人世界的唯一连接。不知道陆沉的异能，只觉得他「偶尔会发呆」。", "ability": "无", "ability_level": "-", "importance": 3, "memories": ["从小和陆沉一起长大", "对陆沉有特殊感情但未表白", "感觉陆沉最近变了", "是陆沉最想保护的人", "最终知道真相并选择接受"]},
    {"name": "郑一鸣", "char_name": "郑一鸣", "age": 42, "gender": "男", "appearance_raw": "身高176cm，精神。短发梳理整齐，黑西装红领带。拿着黑色公文包。", "personality_raw": "异能管理局副局长，沈清秋的上司。政治手腕老道，在各方势力间游走。对陆沉的态度暧昧——既想拉拢又想控制。", "ability": "无", "ability_level": "-", "importance": 3, "memories": ["从基层一路晋升", "政治嗅觉敏锐", "与血色议会有秘密交易", "想利用陆沉达成政治目的", "最终在选举中落马"]},
    {"name": "柳乘风", "char_name": "柳乘风", "age": 34, "gender": "男", "appearance_raw": "身高181cm，潇洒。长发束冠，白色长袍或浅色风衣。手执纸扇。", "personality_raw": "天机阁现任阁主，苏墨然的老友。为人正直但行事神秘。能占卜大事，但代价是自身寿命。", "ability": "天机演算", "ability_level": "S", "importance": 4, "memories": ["天机阁最年轻的阁主", "与苏墨然是多年至交", "一直在关注陆沉", "消耗寿命为陆沉占卜未来", "最终预言自身之死并兑现"]},
    {"name": "白无咎", "char_name": "白无咎", "age": 24, "gender": "女", "appearance_raw": "身高162cm，冷艳。银白色齐腰长发，斜刘海遮住左眼。穿着黑色旗袍，有纹身。", "personality_raw": "白少卿的双胞胎妹妹，异能因性别而不被家族重视。性格冷峻孤傲，只对哥哥有温情。内心渴望自由。", "ability": "冰魄凝形", "ability_level": "A-", "importance": 3, "memories": ["从小被忽视因为是女孩", "与哥哥白少卿感情最好", "被当作联姻工具", "暗中反抗家族安排", "最终背叛家族选择自我"]},
    {"name": "周鹤年", "char_name": "周鹤年", "age": 70, "gender": "男", "appearance_raw": "身高170cm，老态。银发白须，面容慈祥。穿着旧式唐装，手指因长年握笔而变形。", "personality_raw": "零号计划的发起人之一，当年的首席科学家。对自己的研究造成的后果深感愧疚，一直在试图弥补。知道陆沉的一切。", "ability": "无", "ability_level": "-", "importance": 5, "memories": ["100年前参与零号计划", "负责异能觉醒的核心研究", "导致了无数实验体的悲剧", "一直活到现在观察后代", "最终以自我牺牲终结了零号计划"]},
    {"name": "罗飞羽", "char_name": "罗飞羽", "age": 28, "gender": "男", "appearance_raw": "身高179cm，阳光。笑容灿烂，短发微卷。穿着运动休闲装，活力四射。", "personality_raw": "异能管理局行动组副组长，沈清秋的搭档。性格开朗乐观，是队伍中的开心果。有正义感但有时过于冲动。", "ability": "疾风步", "ability_level": "C", "importance": 2, "memories": ["体育大学毕业后加入管理局", "与沈清秋搭档三年", "崇拜沈清秋队长", "在行动中救过队友", "最终接任行动组队长"]},
    {"name": "唐婉", "char_name": "唐婉", "age": 26, "gender": "女", "appearance_raw": "身高168cm，温婉。长发微卷，戴眼镜。穿着米色风衣和连衣裙。气质书卷。", "personality_raw": "异能管理局研究组研究员，周煜的助手。聪明勤奋，对陆沉的异能有独到研究。暗中方一鸣互有好感。", "ability": "分析", "ability_level": "F", "importance": 2, "memories": ["生物学博士毕业", "被周煜招入研究组", "研究陆沉的异能特性", "与方一鸣合作写过论文", "发现了零号计划的遗传密码"]},
    {"name": "苏清寒", "char_name": "苏清寒", "age": 21, "gender": "女", "appearance_raw": "身高163cm，可爱。粉色短发，大眼睛。穿着二次元风格的连衣裙。", "personality_raw": "天才黑客，方一鸣的徒弟。性格活泼跳脱，在网络上无所不能。对陆沉的「夺舍」能力脑洞大开。", "ability": "网络入侵", "ability_level": "D", "importance": 2, "memories": ["14岁成为顶级黑客", "被方一鸣收为徒弟", "协助陆沉多次入侵系统", "崇拜苏墨然", "成为东海市网络安全顾问"]},
    {"name": "姜文轩", "char_name": "姜文轩", "age": 31, "gender": "男", "appearance_raw": "身高184cm，冷峻。轮廓分明的下颌，深邃眼神。穿着黑色高领毛衣和深色大衣。", "personality_raw": "影渊情报组组长，叶知秋的另一位上级。冷静到近乎冷酷，将情报工作视为纯粹的博弈。与陆沉多次在情报战中过招。", "ability": "心灵壁垒", "ability_level": "B+", "importance": 3, "memories": ["大学心理学教授被影渊招募", "负责所有情报分析工作", "与陆沉的情报博弈", "被叶知秋的叛变牵连", "最终选择帮助叶知秋"]},
    {"name": "殷无极", "char_name": "殷无极", "age": 40, "gender": "男", "appearance_raw": "身高192cm，恐怖。全身覆盖黑色鳞片化皮肤，双眼赤红。穿着黑色斗篷遮人眼目。", "personality_raw": "零号计划的成功实验体，S级变异异能者。没有人类情感，只认「强者为尊」的法则。是全剧最强反派。", "ability": "能量吞噬", "ability_level": "S+", "importance": 5, "memories": ["零号计划唯一成功的实验体", "拥有吞噬一切能量的能力", "被各势力追杀又惧怕", "最终对决陆沉", "被陆沉的夺舍能力反噬"]},
    {"name": "陆沉母亲", "char_name": "陆沉母亲", "age": 52, "gender": "女", "appearance_raw": "身高160cm，温柔。黑发中夹杂白丝，面容慈祥。穿着家常的棉质衣物。", "personality_raw": "普通的退休教师，独自抚养陆沉长大。温柔坚强，对儿子的关爱无微不至。不知道丈夫的真实身份。", "ability": "无", "ability_level": "-", "importance": 2, "memories": ["丈夫「离家出走」后独自抚养陆沉", "一直等待丈夫归来", "为陆沉的成长感到骄傲", "不知道儿子的异能", "最终知道真相并选择接受"]},
]

# Filter out special entries and rename keys to match expected schema
def format_char(c):
    return {
        "name": c["char_name"],
        "age": c.get("age", 25),
        "gender": c.get("gender", "男"),
        "appearance_raw": c.get("appearance_raw", ""),
        "personality_raw": c.get("personality_raw", ""),
        "ability": c.get("ability", "无"),
        "ability_level": c.get("ability_level", "-"),
        "importance": c.get("importance", 3),
        "memories": c.get("memories", []),
    }

CHARACTERS_JSONL = [format_char(c) for c in CHARACTERS]


# ============ groups.txt (10+ organizations/groups) ============
GROUPS = [
    {"name": "天机阁", "group_name": "天机阁", "desc_raw": "都市最古老的异能者组织，成员以占卜、预知类异能为主。声称维持异能与普通人世界的平衡，实则在幕后操控各方势力。现任阁主柳乘风。", "leader_name": "柳乘风", "members": [{"char_name": "苏墨然", "role_raw": "核心成员"}, {"char_name": "秦暮雪", "role_raw": "首席占卜师"}, {"char_name": "韩星野", "role_raw": "占卜师"}, {"char_name": "顾青山", "role_raw": "前成员"}], "importance": 5},
    {"name": "影渊", "group_name": "影渊", "desc_raw": "由暗杀者和情报贩子组成的地下组织，只接受委托行事。等级森严，从不背叛雇主。副总指挥姜北，情报组组长姜文轩，执行队长叶知秋。", "leader_name": "姜北", "members": [{"char_name": "叶知秋", "role_raw": "执行队长"}, {"char_name": "宋星辞", "role_raw": "情报员"}, {"char_name": "姜文轩", "role_raw": "情报组组长"}], "importance": 5},
    {"name": "异能管理局", "group_name": "异能管理局", "desc_raw": "官方异能者管理机构，负责登记、监管和调解异能者事务。分行动组和研究组。副局长郑一鸣，行动组队长沈清秋，研究组组长周煜。", "leader_name": "郑一鸣", "members": [{"char_name": "沈清秋", "role_raw": "行动组队长"}, {"char_name": "周煜", "role_raw": "研究组组长"}, {"char_name": "罗飞羽", "role_raw": "行动组副组长"}, {"char_name": "方一鸣", "role_raw": "技术支持"}, {"char_name": "唐婉", "role_raw": "研究员"}], "importance": 5},
    {"name": "血色议会", "group_name": "血色议会", "desc_raw": "由纯血异能家族组成的利益联盟，掌控城市地下经济。以血脉纯度为尊。现任族长魏行舟，核心成员白少卿、白无咎。", "leader_name": "魏行舟", "members": [{"char_name": "白少卿", "role_raw": "继承人"}, {"char_name": "白无咎", "role_raw": "成员"}, {"char_name": "温诗雨", "role_raw": "私生女"}], "importance": 4},
    {"name": "零号实验室", "group_name": "零号实验室", "desc_raw": "百年前由周鹤年发起的秘密研究设施，从事异能觉醒和强化实验。造成无数悲剧，产出殷无极等变异体。已被官方查封但仍有残余势力活动。", "leader_name": "周鹤年", "members": [{"char_name": "殷无极", "role_raw": "成功实验体"}, {"char_name": "许白", "role_raw": "幸存实验体"}, {"char_name": "楚云裳", "role_raw": "前研究员"}], "importance": 5},
    {"name": "铁衣帮", "group_name": "铁衣帮", "desc_raw": "地下黑市帮派，掌控异能道具交易。帮主韩铁衣。与陆沉关系良好，提供情报支持。", "leader_name": "韩铁衣", "members": [], "importance": 3},
    {"name": "暗夜酒吧", "group_name": "暗夜酒吧", "desc_raw": "异能者聚集地，入口在旧书市集中。酒吧内禁止使用异能。老板身份神秘，据说与天机阁有关。", "leader_name": "未知", "members": [], "importance": 3},
    {"name": "监察特组", "group_name": "监察特组", "desc_raw": "中央检察院下属的异能案件特别调查小组。检察官关如月负责。立场中立，只相信证据。", "leader_name": "关如月", "members": [], "importance": 2},
    {"name": "无声行者", "group_name": "无声行者", "desc_raw": "都市传说中的神秘情报团体，成员身份不明。为各方提供情报但从不收钱。可能是当年零号计划的反对派。", "leader_name": "沈默", "members": [], "importance": 3},
    {"name": "血脉议会", "group_name": "血脉议会", "desc_raw": "血色议会的下属机构，由年轻一代纯血异能者组成。主张改革，对白少卿的极端路线不满。", "leader_name": "白无咎", "members": [], "importance": 2},
    {"name": "街头情报网", "group_name": "街头情报网", "desc_raw": "由赵小虎运营的街头情报网络，消息灵通，覆盖城市各个角落。与影渊和铁衣帮都有合作。", "leader_name": "赵小虎", "members": [], "importance": 2},
    {"name": "觉醒者互助会", "group_name": "觉醒者互助会", "desc_raw": "由周煜秘密创立的民间组织，为新晋觉醒者提供心理疏导和生存指导。成员多为F-E级低能力觉醒者。", "leader_name": "周煜", "members": [], "importance": 2},
]

def format_group(g):
    return {
        "name": g["group_name"],
        "desc_raw": g.get("desc_raw", ""),
        "leader_name": g.get("leader_name", ""),
        "members": g.get("members", []),
        "importance": g.get("importance", 3),
    }

GROUPS_JSONL = [format_group(g) for g in GROUPS]


# ============ group_hierarchies.txt ============
GROUP_HIERARCHIES = [
    {"parent_group_name": "血色议会", "child_group_name": "血脉议会"},
    {"parent_group_name": "影渊", "child_group_name": "无声行者"},  # 名义从属
    {"parent_group_name": "异能管理局", "child_group_name": "监察特组"},
    {"parent_group_name": "铁衣帮", "child_group_name": "街头情报网"},
]


# ============ items.txt ============
ITEMS = [
    {"name": "墨渊剑", "item_name": "墨渊剑", "desc_raw": "上古神剑，剑身漆黑如墨，蕴含深渊之力。苏墨然的佩剑。使用者需以心神为引，否则易被剑意反噬。", "category": "武器", "importance": 5},
    {"name": "太虚镜", "item_name": "太虚镜", "desc_raw": "能映照人心最深处的欲望与恐惧，亦能看穿幻术。秦暮雪使用的法器。", "category": "法宝", "importance": 5},
    {"name": "天机罗盘", "item_name": "天机罗盘", "desc_raw": "可感知城市中强大异能者方位的法器，精度有限。天机阁标配。", "category": "辅助", "importance": 4},
    {"name": "追魂锁", "item_name": "追魂锁", "desc_raw": "锁定敌人魂魄的灵器，被锁定者短时间无法使用异能。影渊标配工具。", "category": "封印", "importance": 4},
    {"name": "屏蔽手环", "item_name": "屏蔽手环", "desc_raw": "佩戴后可短时间屏蔽自身异能波动，躲避感知型探测。黑市有售。", "category": "防御", "importance": 4},
    {"name": "能量饮料", "item_name": "能量饮料", "desc_raw": "异能者专用恢复剂，快速补充异能消耗。有轻微依赖性。", "category": "消耗品", "importance": 3},
    {"name": "记忆碎片", "item_name": "记忆碎片", "desc_raw": "能读取他人一段记忆的透明晶体，一次性道具。", "category": "消耗品", "importance": 4},
    {"name": "契约卷轴", "item_name": "契约卷轴", "desc_raw": "上古仪式道具，用于签订具有精神约束力的契约。违反者遭受反噬。", "category": "仪式", "importance": 5},
    {"name": "定位锚", "item_name": "定位锚", "desc_raw": "小型定位装置，植入目标后持续追踪位置，覆盖整座城市。", "category": "侦查", "importance": 3},
    {"name": "无相甲", "item_name": "无相甲", "desc_raw": "看似普通的灰色布衣，能吸收三成物理伤害。血色议会藏品。", "category": "防具", "importance": 4},
    {"name": "刻名刀", "item_name": "刻名刀", "desc_raw": "能在目标物体上留下不可消除的精神印记，用于标记或追踪。叶知秋常用。", "category": "工具", "importance": 3},
    {"name": "灵石", "item_name": "灵石", "desc_raw": "富含灵气的结晶，可作为修炼媒介或应急能量源。旧书市集偶有出售。", "category": "消耗品", "importance": 3},
    {"name": "影渊令牌", "item_name": "影渊令牌", "desc_raw": "影渊内部身份凭证，黑色金属令牌。持令者可调动影渊资源。", "category": "身份", "importance": 4},
    {"name": "血色徽章", "item_name": "血色徽章", "desc_raw": "血色议会成员徽章，红色金底。象征纯血异能家族身份。", "category": "身份", "importance": 3},
    {"name": "天机玉牌", "item_name": "天机玉牌", "desc_raw": "天机阁弟子凭证，温润白玉。持有者可在危急时刻请求天机阁庇护。", "category": "身份", "importance": 4},
]

def format_item(i):
    return {
        "name": i["item_name"],
        "desc_raw": i.get("desc_raw", ""),
        "category": i.get("category", "其他"),
        "importance": i.get("importance", 3),
    }

ITEMS_JSONL = [format_item(i) for i in ITEMS]


# ============ maps.txt (20+ maps/buildings) ============
MAPS = [
    {"name": "东海市", "map_name": "东海市", "desc_raw": "故事发生的超级都市，三千万人口。分为老城区、中央商务区、科技园区、滨江区四大区域。", "importance": 5},
    {"name": "中央商务区", "map_name": "中央商务区", "desc_raw": "城市核心，摩天大楼林立。白天是金融中心，夜晚异能者活动频繁。中央塔是标志性建筑。", "importance": 5},
    {"name": "老城区", "map_name": "老城区", "desc_raw": "百年历史的旧城区，低矮建筑群。旧书市集、暗夜酒吧、地铁终点站均在此。影栖族聚居。", "importance": 5},
    {"name": "滨江区", "map_name": "滨江区", "desc_raw": "沿海新兴开发区，高端住宅区。血色议会主要活动区域。", "importance": 3},
    {"name": "科技园区", "map_name": "科技园区", "desc_raw": "高科技企业集聚区。零号实验室旧址就在此处地下。", "importance": 3},
    {"name": "东海大学", "map_name": "东海大学", "desc_raw": "城市最高学府，陆沉和江若溪的母校。校园内有隐秘的异能者活动圈子。", "importance": 4},
    {"name": "中央塔", "map_name": "中央塔", "desc_raw": "城市最高建筑，88层。顶楼观景台可俯瞰全城，塔顶有神秘能量波动。", "importance": 5},
    {"name": "旧书市集", "map_name": "旧书市集", "desc_raw": "老城区每周六开放的古董市场。顾青山的店铺所在地，异能道具交易的重要场所。", "importance": 5},
    {"name": "暗夜酒吧", "map_name": "暗夜酒吧", "desc_raw": "老城区地下异能者聚集地。入口在一家书店后。禁止使用异能。", "importance": 5},
    {"name": "地铁终点站", "map_name": "地铁终点站", "desc_raw": "废弃地铁线路终点。影栖族临时据点。灵异事件频发。", "importance": 3},
    {"name": "樱花陵园", "map_name": "樱花陵园", "desc_raw": "百年历史的私人陵园，异能家族先祖安葬地。禁忌之地。", "importance": 5},
    {"name": "零号实验室旧址", "map_name": "零号实验室旧址", "desc_raw": "科技园区地下。百年前秘密实验设施。已被官方查封但有残余势力活动。", "importance": 5},
    {"name": "血月会所", "map_name": "血月会所", "desc_raw": "血色议会的秘密据点，伪装成高端会所。地下三层是家族核心区。", "importance": 4},
    {"name": "天机阁旧址", "map_name": "天机阁旧址", "desc_raw": "老城区山顶古刹，天机阁最初所在地。现已废弃但仍有能量残留。", "importance": 3},
    {"name": "铁衣帮据点", "map_name": "铁衣帮据点", "desc_raw": "码头区仓库，韩铁衣的大本营。也是异能道具集散地。", "importance": 3},
    {"name": "影渊安全屋", "map_name": "影渊安全屋", "desc_raw": "散布在城市各处的影渊安全屋。叶知秋的常驻点在老城区。", "importance": 3},
    {"name": "异能管理局总部", "map_name": "异能管理局总部", "desc_raw": "中央商务区地下七层。含档案室、审讯室、训练场等设施。", "importance": 5},
    {"name": "检察院大楼", "map_name": "检察院大楼", "desc_raw": "中央检察院办公楼。关如月的办公地点。", "importance": 2},
    {"name": "滨江公寓", "map_name": "滨江公寓", "desc_raw": "陆沉的住所所在的中档公寓。24楼，能看到海景。", "importance": 4},
    {"name": "东海火车站", "map_name": "东海火车站", "desc_raw": "城市主要交通枢纽。人流量巨大，也是情报交易的场所之一。", "importance": 2},
    {"name": "人民广场", "map_name": "人民广场", "desc_raw": "城市中心广场。经常出现大型活动，也是异能者公开行动的少有的场所。", "importance": 3},
    {"name": "滨江医院", "map_name": "滨江医院", "desc_raw": "城市最好的私立医院。许白的救治地点。", "importance": 3},
]

def format_map(m):
    return {
        "name": m["map_name"],
        "desc_raw": m.get("desc_raw", ""),
        "importance": m.get("importance", 3),
    }

MAPS_JSONL = [format_map(m) for m in MAPS]


# ============ map_features.txt (key buildings within maps) ============
MAP_FEATURES = [
    {"map_name": "中央塔", "name": "塔顶观景台", "desc_raw": "360度海景，夜间可看到城市全部灯光。有神秘能量波动。"},
    {"map_name": "中央塔", "name": "高空走廊", "desc_raw": "连接副楼的高空全透明走廊，恐高者慎入。"},
    {"map_name": "旧书市集", "name": "青山书屋", "desc_raw": "顾青山的古董书店，专卖异能相关道具和古籍。"},
    {"map_name": "旧书市集", "name": "占卜摊", "desc_raw": "市集角落的占卜摊位，韩星野偶尔出没。"},
    {"map_name": "旧书市集", "name": "秘密入口", "desc_raw": "通往暗夜酒吧的隐蔽入口，需知道暗号。"},
    {"map_name": "暗夜酒吧", "name": "主吧台", "desc_raw": "酒吧中央的石质吧台，禁止使用异能的警示牌挂在上方。"},
    {"map_name": "暗夜酒吧", "name": "VIP包间", "desc_raw": "高级异能者密谈的场所，隔音极佳。"},
    {"map_name": "樱花陵园", "name": "家族祠堂", "desc_raw": "血色议会先祖的祠堂，有强大的血脉封印。"},
    {"map_name": "樱花陵园", "name": "暗道", "desc_raw": "通往零号实验室旧址的秘密通道。"},
    {"map_name": "零号实验室旧址", "name": "核心实验室", "desc_raw": "当年异能觉醒研究的核心区域，有变异能量残留。"},
    {"map_name": "零号实验室旧址", "name": "冷藏库", "desc_raw": "保存实验体标本的低温仓库，许白当年被关押处。"},
    {"map_name": "血月会所", "name": "地下三层", "desc_raw": "血色议会核心区，只有族长和继承人可进入。"},
    {"map_name": "血月会所", "name": "宴会厅", "desc_raw": "伪装的高端宴会厅，用来迷惑外界。"},
    {"map_name": "异能管理局总部", "name": "档案室", "desc_raw": "存所有异能者登记信息和案件记录。方一鸣负责维护。"},
    {"map_name": "异能管理局总部", "name": "训练场", "desc_raw": "行动组实战训练区域，有各种模拟场景。"},
    {"map_name": "异能管理局总部", "name": "研究实验室", "desc_raw": "周煜团队的研究场所，有最先进的异能检测设备。"},
    {"map_name": "滨江公寓", "name": "2402室", "desc_raw": "陆沉的住所，简洁现代风格。客厅有一面落地镜。"},
    {"map_name": "滨江公寓", "name": "观景阳台", "desc_raw": "面朝大海的阳台，是陆沉常独处思考的地方。"},
    {"map_name": "东海大学", "name": "图书馆", "desc_raw": "大学图书馆顶层有异能者秘密读书会。"},
    {"map_name": "东海大学", "name": "老教学楼", "desc_raw": "百年历史的老楼，地下室有当年零号计划的早期设施。"},
    {"map_name": "地铁终点站", "name": "废弃站台", "desc_raw": "杂草丛生的废弃站台，影栖族聚集地。"},
    {"map_name": "人民广场", "name": "中心喷泉", "desc_raw": "广场中心大型喷泉，夜间是异能者偶尔公开活动的场所。"},
]

MAP_FEATURES_JSONL = [{"map_name": mf["map_name"], "name": mf["name"], "desc_raw": mf.get("desc_raw", "")} for mf in MAP_FEATURES]


# ============ events.txt (key plot events) ============
EVENTS = [
    {"content_raw": "陆沉在地铁中遭遇意外，短暂失去意识，醒来后发现自己能在5秒内夺舍他人。首次夺舍的是身边一位中年男子，目睹了他的婚外情秘密。", "importance": 5},
    {"content_raw": "东海市发生连环失踪案，警方束手无策。林晚作为刑警负责调查，案件涉及的失踪者都与异能者有关。", "importance": 5},
    {"content_raw": "陆沉在旧书市集偶遇顾青山老人，被其察觉身上的特殊气息。顾青山警告他「你的能力会引来麻烦」。", "importance": 4},
    {"content_raw": "陆沉首次在实战中使用夺舍能力，从一名跟踪者的视角看到了对方的联络暗号——这是影渊的标志。", "importance": 5},
    {"content_raw": "苏墨然出现在陆沉面前，以神秘访客身份警告他「有人在监视你」，并留下一张写有「天机阁」字样的纸条。", "importance": 5},
    {"content_raw": "林晚调查失踪案时发现线索指向零号实验室，她不知道这背后牵扯的能量有多恐怖。", "importance": 4},
    {"content_raw": "影渊派叶知秋追杀陆沉。陆沉利用夺舍能力在叶知秋的手下之间制造混乱，首次利用异能反杀。", "importance": 5},
    {"content_raw": "异能管理局注意到陆沉的异能活动，沈清秋带队前往调查。周煜认为陆沉的异能是前所未见的类型。", "importance": 5},
    {"content_raw": "秦暮雪在预言中看到陆沉的身影，预言内容过于恐怖导致她吐血昏厥。她预言陆沉将决定整个格局的走向。", "importance": 5},
    {"content_raw": "陆沉发现温诗雨在学校因异能失控而崩溃，利用夺舍能力进入她的意识，看到了她被家族抛弃的痛苦记忆。", "importance": 4},
    {"content_raw": "血色议会派人绑架温诗雨，陆沉与白少卿第一次正面交锋。精神压制 vs 夺舍，陆沉虽然处于劣势但成功救出温诗雨。", "importance": 5},
    {"content_raw": "陆沉得知父亲陆远山并非「离家出走」，而是30年前以卧底身份潜伏调查零号计划。父子相认。", "importance": 5},
    {"content_raw": "零号实验室发生大规模越狱事件，许白等实验体逃出。殷无极觉醒，能量等级达到S+，成为最大威胁。", "importance": 5},
    {"content_raw": "楚云裳提供零号计划核心资料，揭示陆沉的觉醒是被刻意设计的——他的基因来自零号计划的成功实验体。", "importance": 5},
    {"content_raw": "白无咎背叛血色议会，带着家族内部情报投奔陆沉阵营。白少卿被迫开始追杀自己的妹妹。", "importance": 4},
    {"content_raw": "秦暮雪为保护陆沉而牺牲，临终预言：「最终之战会在樱花陵园打响」。韩星野接任天机阁首席。", "importance": 5},
    {"content_raw": "沈清秋与郑一鸣公开决裂，沈清秋带着行动组部分成员成为独立力量。罗飞羽接任行动组队长。", "importance": 4},
    {"content_raw": "叶知秋在最后关头背叛影渊，选择保护陆沉。姜北为保护叶知秋而死，临终说「你是我养大的，我相信你」。", "importance": 5},
    {"content_raw": "最终决战在樱花陵园展开：陆沉 vs 殷无极。陆沉利用夺舍5秒的能力，在殷无极吞噬能量的瞬间夺舍他，让他的能量反噬自身。", "importance": 5},
    {"content_raw": "周鹤年为终结零号计划的遗毒，自我牺牲引爆了实验室核心。陆沉成为新的「零号」——但他选择用能力保护他人。", "importance": 5},
    {"content_raw": "所有势力重新洗牌：天机阁由韩星野领导、异能管理局改革、血色议会瓦解、影渊由叶知秋接任并转型。陆沉选择做一个普通人，偶尔用夺舍能力帮助朋友。", "importance": 5},
]

EVENTS_JSONL = [{"content_raw": e["content_raw"], "importance": e.get("importance", 3)} for e in EVENTS]


# ============ settings.txt ============
SETTINGS = [
    {"title": "都市异能等级体系", "content_raw": "异能分为F、E、D、C、B、A、S、SS共8级。F级初学者，S级影响城市范围，SS级视为天灾级。等级通过官方考核评定，但实际战力可能与评级不符。", "importance": 5},
    {"title": "异能觉醒条件", "content_raw": "天生异能基因+特定刺激触发。常见刺激：生死危机、精神重创、接触异能物品。觉醒过程持续数天至数周，多数人在16-25岁之间觉醒。", "importance": 5},
    {"title": "代价等价原则", "content_raw": "都市异能世界的基本法则：获取任何力量都需付出等价代价。代价可以是记忆、寿命、情感、身体部件等。能力越强，代价越大。", "importance": 5},
    {"title": "异能保密法", "content_raw": "官方法律规定异能者必须登记，且不得在普通人面前展示异能。违反者将被逮捕。但实际登记率不足30%。", "importance": 4},
    {"title": "异能组织格局", "content_raw": "三大势力：天机阁（占卜/预知）、影渊（暗杀/情报）、异能管理局（官方监管）。次级势力：血色议会（纯血家族）、零号实验室（已查封但有残余）、铁衣帮（黑市）等。", "importance": 5},
    {"title": "夺舍能力限制", "content_raw": "陆沉的夺舍能力限制：1.持续时间5秒；2.视线内目标；3.距离不超过50米；4.同时只能夺舍一人；5.被夺舍者无感知；6.陆沉本体无意识；7.无冷却时间。", "importance": 5},
    {"title": "记忆封印术", "content_raw": "高阶精神系异能者可封锁目标特定记忆。被封印者不会察觉。解除封印需要对应施术者的精神力或特定道具（如记忆碎片）。", "importance": 4},
    {"title": "空间折叠理论", "content_raw": "城市中存在空间夹层，高阶异能者可感知并短暂穿越。夹层中藏有上古遗迹，但也可能存在危险生物。", "importance": 4},
    {"title": "异能黑市经济", "content_raw": "以铁衣帮为核心的地下经济体系。交易内容包括：异能道具、情报、保护服务、训练指导等。价格通常不菲。", "importance": 3},
    {"title": "零号计划真相", "content_raw": "百年前由周鹤年发起的秘密研究，目的是创造可控的高阶异能者。实验造成无数悲剧，产出殷无极等变异体。核心研究记录被多方势力争夺。", "importance": 5},
]

SETTINGS_JSONL = [{"title": s["title"], "content_raw": s["content_raw"], "importance": s.get("importance", 3)} for s in SETTINGS]


# ============ plot_planning.txt ============
PLOT_PLANNING = [
    {"plot": "第一幕：觉醒", "content_raw": "陆沉在地铁事故中觉醒夺舍能力，被各方势力注意。林晚开始调查连环失踪案。陆沉第一次使用异能反制跟踪者。", "success_condition_raw": "陆沉成功控制新异能，林晚找到第一条重要线索", "importance": 5},
    {"plot": "第二幕：交锋", "content_raw": "陆沉与影渊、血色议会、异能管理局三方交锋。苏墨然、秦暮雪等关键人物登场。顾青山揭示部分真相。陆沉与林晚合作深入调查。", "success_condition_raw": "陆沉与林晚建立信任关系，获得天机阁支持", "importance": 5},
    {"plot": "第三幕：真相", "content_raw": "陆沉得知父亲真实身份和零号计划的存在。楚云裳提供关键资料。温诗雨被绑架事件升级冲突。秦暮雪为保护陆沉牺牲。", "success_condition_raw": "揭露天机阁的秘密，找到零号实验室核心资料", "importance": 5},
    {"plot": "第四幕：决战", "content_raw": "零号实验室越狱事件，殷无极成为最大威胁。各势力重新结盟。叶知秋背叛影渊。最终决战在樱花陵园打响，陆沉利用夺舍5秒的能力击败殷无极。", "success_condition_raw": "击败殷无极，阻止零号计划复活", "importance": 5},
    {"plot": "第五幕：新生", "content_raw": "周鹤年牺牲终结零号计划遗毒。各势力重新洗牌。陆沉选择回归普通人生活，用能力守护身边人。开放式结局，暗示可能的续集。", "success_condition_raw": "各势力达成新平衡，陆沉接受自身命运", "importance": 4},
]

PLOT_PLANNING_JSONL = [{"title": p["plot"], "plot": p["plot"], "content_raw": p["content_raw"], "plot_raw": p["content_raw"], "success_condition_raw": p.get("success_condition_raw", ""), "importance": p.get("importance", 3)} for p in PLOT_PLANNING]


def _write_jsonl(path: Path, data: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  写入 {path.name}: {len(data)} 条")


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  写入 {path.name}: JSON 对象")


def main():
    drama_dir = ROOT / "src" / "backend" / "drama" / DRAMA_NAME
    drama_dir.mkdir(parents=True, exist_ok=True)

    print(f"生成剧本：{DRAMA_NAME}")
    print(f"输出目录：{drama_dir}")
    print()

    _write_json(drama_dir / "meta.txt", META)
    _write_jsonl(drama_dir / "characters.txt", CHARACTERS_JSONL)
    _write_jsonl(drama_dir / "groups.txt", GROUPS_JSONL)
    _write_jsonl(drama_dir / "group_hierarchies.txt", GROUP_HIERARCHIES)
    _write_jsonl(drama_dir / "items.txt", ITEMS_JSONL)
    _write_jsonl(drama_dir / "maps.txt", MAPS_JSONL)
    _write_jsonl(drama_dir / "map_features.txt", MAP_FEATURES_JSONL)
    _write_jsonl(drama_dir / "events.txt", EVENTS_JSONL)
    _write_jsonl(drama_dir / "settings.txt", SETTINGS_JSONL)
    _write_jsonl(drama_dir / "plot_planning.txt", PLOT_PLANNING_JSONL)

    print(f"\n完成！剧本文件已生成：")
    print(f"  角色: {len(CHARACTERS_JSONL)} 个")
    print(f"  组织: {len(GROUPS_JSONL)} 个")
    print(f"  建筑: {len(MAPS_JSONL)} 个地图 + {len(MAP_FEATURES_JSONL)} 个地图要素")
    print(f"  物品: {len(ITEMS_JSONL)} 个")
    print(f"  事件: {len(EVENTS_JSONL)} 个")
    print(f"  设定: {len(SETTINGS_JSONL)} 条")
    print(f"  情节: {len(PLOT_PLANNING_JSONL)} 个章节")

    # 导入数据库
    print("\n尝试导入数据库...")
    try:
        import sys
        sys.path.insert(0, str(ROOT))
        from src.backend.service.drama_service import init_drama
        result = init_drama(DRAMA_NAME, save_name=f"{DRAMA_NAME}_save", overwrite=True)
        print(f"  导入成功: {result}")
    except Exception as e:
        import traceback
        print(f"  导入失败: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
