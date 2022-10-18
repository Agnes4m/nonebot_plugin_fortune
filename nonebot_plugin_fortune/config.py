from nonebot import get_driver
from nonebot.log import logger
from pydantic import BaseModel, Extra
from typing import List, Dict, Union
from pathlib import Path
try:
    import ujson as json
except ModuleNotFoundError:
    import json
    
from .download import DownloadError, download_url

'''
    抽签主题对应表，第一键值为“抽签设置”或“主题列表”展示的主题名称
    Key-Value: 主题资源文件夹名-设置主题别名
'''
FortuneThemesDict: Dict[str, List[str]] = {
    "random": ["随机"],
    "pcr": ["PCR", "公主链接", "公主连结", "Pcr", "pcr"],
    "genshin": ["原神", "Genshin Impact", "genshin", "Genshin", "op", "原批"],
    "hololive": ["Hololive", "hololive", "Vtb", "vtb", "管人", "Holo", "holo", "猴楼"],
    "touhou": ["东方", "touhou", "Touhou", "车万"],
    "touhou_lostword": ["东方归言录", "东方lostword", "touhou lostword", "Touhou dlc"],
    "touhou_old": ["旧东方", "旧版东方", "老东方", "老版东方", "经典东方"],
    "onmyoji": ["阴阳师", "yys", "Yys", "痒痒鼠"],
    "azure": ["碧蓝航线", "碧蓝", "azure", "Azure"],
    "asoul": ["Asoul", "asoul", "a手", "A手", "as", "As"],
    "arknights": ["明日方舟", "方舟", "arknights", "鹰角", "Arknights", "舟游"],
    "granblue_fantasy": ["碧蓝幻想", "Granblue Fantasy", "granblue fantasy", "幻想", "fantasy", "Fantasy"],
    "punishing":["战双", "战双帕弥什"],
    "pretty_derby": ["赛马娘", "马", "马娘", "赛马"],
    "dc4": ["dc4", "DC4", "Dc4", "初音岛", "初音岛4"],
    "einstein": ["爱因斯坦携爱敬上", "爱因斯坦", "einstein", "Einstein"],
    "sweet_illusion": ["灵感满溢的甜蜜创想", "甜蜜一家人", "富婆妹"],
    "liqingge": ["李清歌", "清歌"],
    "hoshizora": ["星空列车与白的旅行", "星空列车"],
    "sakura": ["樱色之云绯色之恋", "樱云之恋", "樱云绯恋", "樱云"],
    "summer_pockets": ["夏日口袋", "夏兜", "sp", "SP"],
    "amazing_grace": ["奇异恩典"]
}

class ResourceError(Exception):
    def __init__(self, msg):
        self.msg = msg
        
    def __str__(self):
        return self.msg

class PluginConfig(BaseModel, extra=Extra.ignore):
    fortune_path: Path = Path(__file__).parent / "resource"

class ThemesFlagConfig(BaseModel, extra=Extra.ignore):
    '''
        各主题抽签开关，仅在random抽签中生效
        请确保不全是False
    '''
    amazing_grace_flag: bool = True
    arknights_flag: bool = True
    asoul_flag: bool = True
    azure_flag: bool = True
    genshin_flag:  bool = True
    onmyoji_flag: bool = True
    pcr_flag: bool = True
    touhou_flag: bool = True
    touhou_lostword_flag: bool = True
    touhou_old_flag: bool = True
    hololive_flag: bool = True
    granblue_fantasy_flag: bool = True
    punishing_flag: bool = True
    pretty_derby_flag: bool = True
    dc4_flag: bool = True
    einstein_flag: bool = True
    sweet_illusion_flag: bool = True
    liqingge_flag: bool = True
    hoshizora_flag: bool = True
    sakura_flag: bool = True 
    summer_pockets_flag: bool = True

driver = get_driver()
fortune_config: PluginConfig = PluginConfig.parse_obj(driver.config.dict())
themes_flag_config: ThemesFlagConfig = ThemesFlagConfig.parse_obj(driver.config.dict())

@driver.on_startup
async def fortune_check() -> None:
    if not fortune_config.fortune_path.exists():
        fortune_config.fortune_path.mkdir(parents=True, exist_ok=True)
    
    '''
        Check whether all themes disable
    '''
    content = themes_flag_config.dict()
    _flag: bool = False
    for theme in content:
        if content.get(theme, False):
            _flag = True
            break
    
    if not _flag:
        logger.warning("Fortune themes ALL disabled! Please check!")
        raise ResourceError("Fortune themes ALL disabled! Please check!")
    
    flags_config_path: Path = fortune_config.fortune_path / "fortune_config.json"            
    with flags_config_path.open("w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=4)
    
    '''
        Try to get the latest copywriting from repo
    '''
    copywriting_path: Path = fortune_config.fortune_path / "fortune" / "copywriting.json"
    url: str = "https://raw.fastgit.org/MinatoAquaCrews/nonebot_plugin_fortune/beta/nonebot_plugin_fortune/resource/fortune/copywriting.json"
    response = await download_url(url)
    if response is None:
        if not copywriting_path.exists():
           raise DownloadError("Copywriting resource missing! Please check!")
    else:
        docs = response.json()
        version = docs.get("version")

        with copywriting_path.open("w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=4)
        
        logger.info(f"Got the latest copywriting docs from repo, version: {version}")
    
    fortune_data_path: Path = fortune_config.fortune_path / "fortune_data.json"
    fortune_setting_path: Path = fortune_config.fortune_path / "fortune_setting.json"
    group_rules_path: Path = fortune_config.fortune_path / "group_rules.json"
    specific_rules_path: Path = fortune_config.fortune_path / "specific_rules.json"
    
    if not fortune_data_path.exists():
        logger.warning("fortune_data.json is missing, initialized one...")
        
        with fortune_data_path.open("w", encoding="utf-8") as f:
            json.dump(dict(), f, ensure_ascii=False, indent=4)
    
    _flag = False
    if not group_rules_path.exists():        
        # In version 0.4.x, compatible job will be done automatically if group_rules.json doesn't exist
        if fortune_setting_path.exists():
            # Try to transfer from the old setting json
            ret: bool = group_rules_transfer(fortune_setting_path, group_rules_path)
            if ret:
                logger.info("旧版 fortune_setting.json 文件中群聊抽签主题设置已更新至 group_rules.json")
                _flag = True
        
        if not _flag:
            # If failed or fortune_setting_path doesn't exist, initialize group_rules.json
            with group_rules_path.open("w", encoding="utf-8") as f:
                json.dump(dict(), f, ensure_ascii=False, indent=4)
            
            logger.info("旧版 fortune_setting.json 文件中群聊抽签主题设置不存在，初始化 group_rules.json")

    _flag = False
    if not specific_rules_path.exists():
        # In version 0.4.x, data transfering will be done automatically if specific_rules.json doesn't exist
        if fortune_setting_path.exists():
            # Try to transfer from the old setting json
            ret: bool = specific_rules_transfer(fortune_setting_path, specific_rules_path)
            if ret:
                logger.info("旧版 fortune_setting.json 文件中签底指定规则已更新至 specific_rules.json")
                _flag = True
        
        if not _flag:
            # Try to download it from repo
            url = "https://raw.fastgit.org/MinatoAquaCrews/nonebot_plugin_fortune/beta/nonebot_plugin_fortune/resource/specific_rules.json"
            response = await download_url(url)
            if response is None:
                # If failed, initialize specific_rules.json
                with specific_rules_path.open("w", encoding="utf-8") as f:
                    json.dump(dict(), f, ensure_ascii=False, indent=4)
                
                logger.info("旧版 fortune_setting.json 文件中签底指定规则不存在，初始化 specific_rules.json")
            else:
                setting = response.json()

                with specific_rules_path.open("w", encoding="utf-8") as f:
                    json.dump(setting, f, ensure_ascii=False, indent=4)
                
                logger.info(f"Downloaded specific_rules.json from repo")

def group_rules_transfer(fortune_setting_dir: Path, group_rules_dir: Path) -> bool:
    '''
        Transfer the group_rule in fortune_setting.json to group_rules.json
    '''
    with open(fortune_setting_dir, 'r', encoding='utf-8') as fs:
        _setting: Dict[str, Dict[str, Union[str, List[str]]]] = json.load(fs)
        group_rules = _setting.get("group_rule", None)  # Old key is group_rule
    
        with open(group_rules_dir, 'w', encoding='utf-8') as fr:
            if not group_rules:
                json.dump(dict(), fr, ensure_ascii=False, indent=4)
                return False
            else:
                json.dump(group_rules, fr, ensure_ascii=False, indent=4)
                return True

def specific_rules_transfer(fortune_setting_dir: Path, specific_rules_dir: Path) -> bool:
    '''
        Transfer the specific_rule in fortune_setting.json to specific_rules.json
    '''
    with open(fortune_setting_dir, 'r', encoding='utf-8') as fs:
        _setting: Dict[str, Dict[str, Union[str, List[str]]]] = json.load(fs)
        specific_rules = _setting.get("specific_rule", None)  # Old key is specific_rule
        
        with open(specific_rules_dir, 'w', encoding='utf-8') as fr:
            if not specific_rules:
                json.dump(dict(), fr, ensure_ascii=False, indent=4)
                return False
            else:
                json.dump(specific_rules, fr, ensure_ascii=False, indent=4)
                return True