# core/keyword_utils.py
import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger("Keyword-Utils")

@dataclass
class KeywordMatch:
    keyword: str
    code: int
    start_pos: int
    end_pos: int
    confidence: float

# 指令关键字配置 - 重新整理
COMMAND_KEYWORDS = {
    # 系统指令
    "关机": 1001, "重启": 1002,
    
    # 呼叫联系人
    "呼叫联系人1": 1101, "呼叫联系人2": 1102, "呼叫联系人3": 1103,
}

# 关机相关的所有表达方式
SHUTDOWN_EXPRESSIONS = {
    # 精确匹配
    "关机", "关闭系统", "系统关机", "关电脑", "计算机关机", "设备关机",
    
    # 模糊表达
    "关上", "关掉", "关了", "关了吧", "关上吧", "关掉吧", "关",
    "关闭", "关设备", "关系统", "关掉系统", "关上系统",
    
    # 口语化表达
    "给我关机", "请关机", "帮我关机", "现在关机", "立即关机", "马上关机",
    "关机吧", "关机了", "关机一下", "关一下机", "把机关了", "把电脑关了",
    
    # 英文表达
    "shutdown", "turn off", "power off",
}

# 重启相关的所有表达方式
RESTART_EXPRESSIONS = {
    "重启", "重新启动", "重启系统", "重启电脑", "重启设备",
    "系统重启", "设备重启", "电脑重启", "重新启动系统",
    "重新启动电脑", "重新启动设备", "reboot", "restart",
}

# 呼叫联系人表达方式
CALL_CONTACT_EXPRESSIONS = {
    "呼叫联系人1", "打电话给联系人1", "拨打联系人1", "联系联系人1",
    "呼叫联系人2", "打电话给联系人2", "拨打联系人2", "联系联系人2", 
    "呼叫联系人3", "打电话给联系人3", "拨打联系人3", "联系联系人3",
}

# 正则表达式模式
COMMAND_PATTERNS = {
    # 关机模式
    r"关[闭掉上]": 1001,
    r"关[闭掉上]吧": 1001,
    r"关[闭掉上]了": 1001,
    r"关[闭掉上]系统": 1001,
    r"关[闭掉上]电脑": 1001,
    r"关[闭掉上]设备": 1001,
    r"现在关[闭掉上]": 1001,
    r"立即关[闭掉上]": 1001,
    r"马上关[闭掉上]": 1001,
    r"帮我关[闭掉上]": 1001,
    r"请关[闭掉上]": 1001,
    r"给我关[闭掉上]": 1001,
    r"把.关[闭掉上]": 1001,
    
    # 重启模式
    r"重启系统": 1002,
    r"重启电脑": 1002,
    r"重启设备": 1002,
    r"重新启动": 1002,
    r"重新启动系统": 1002,
    r"重新启动电脑": 1002,
    r"重新启动设备": 1002,
    
    # 联系人模式 - 支持多种数字表达
    r"联系人1": 1101,
    r"联系人2": 1102,
    r"联系人3": 1103,
    r"联系人一": 1101,
    r"联系人二": 1102,
    r"联系人两": 1102,
    r"联系人三": 1103,
    r"联系人壹": 1101,
    r"联系人贰": 1102,
    r"联系人叁": 1103,
}

class KeywordAnalyzer:
    def __init__(self):
        self._build_keyword_patterns()
    
    def _build_keyword_patterns(self):
        """构建中文友好的关键词匹配模式"""
        self.keyword_patterns = {}
        # 合并所有表达式到关键词字典
        all_expressions = {}
        
        # 添加关机表达式
        for expr in SHUTDOWN_EXPRESSIONS:
            all_expressions[expr] = 1001
            
        # 添加重启表达式  
        for expr in RESTART_EXPRESSIONS:
            all_expressions[expr] = 1002
            
        # 添加呼叫联系人表达式
        for expr in CALL_CONTACT_EXPRESSIONS:
            all_expressions[expr] = 1101 if "1" in expr else (1102 if "2" in expr else 1103)
        
        # 添加基础关键词
        all_expressions.update(COMMAND_KEYWORDS)
        
        self.all_keywords = all_expressions
        
        # 构建关键词模式
        for keyword in self.all_keywords.keys():
            pattern = re.escape(keyword)
            self.keyword_patterns[keyword] = re.compile(pattern)
    
    def normalize_text(self, text: str) -> str:
        """中文文本预处理 - 简化版本"""
        # 去除标点符号和多余空格，保留中文文本结构
        text = re.sub(r'[^\w\u4e00-\u9fff]', ' ', text.lower().strip())
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def expand_synonyms(self, text: str) -> str:
        """扩展同义词"""
        synonym_mapping = {
            "开启": "打开",
            "启动": "打开", 
            "增大": "调高",
            "减小": "调低",
            "关闭": "关机",
            "停止": "关闭",
        }
        
        for synonym, main_word in synonym_mapping.items():
            text = text.replace(synonym, main_word)
        return text
    
    def calculate_confidence(self, matches: List[KeywordMatch], text: str) -> float:
        """计算置信度 - 简化版本"""
        if not matches:
            return 0.0
        
        # 基础置信度基于匹配数量
        base_confidence = min(len(matches) * 0.5, 1.0)
        
        # 文本长度考虑（短文本更可能是命令）
        word_count = len(text)
        if word_count <= 6:  # 短文本奖励
            base_confidence += 0.3
        elif word_count > 15:  # 长文本惩罚
            base_confidence -= 0.4
            
        return max(0.1, min(1.0, base_confidence))
    
    def find_keyword_matches(self, text: str) -> List[KeywordMatch]:
        """查找关键词匹配 - 修复版本"""
        matches = []
        
        # 简单关键词匹配 - 直接搜索包含关系
        for keyword, code in self.all_keywords.items():
            if keyword in text:
                # 找到所有出现位置
                start = 0
                while True:
                    pos = text.find(keyword, start)
                    if pos == -1:
                        break
                    matches.append(KeywordMatch(
                        keyword=keyword,
                        code=code,
                        start_pos=pos,
                        end_pos=pos + len(keyword),
                        confidence=1.0
                    ))
                    start = pos + 1
        
        # 正则表达式模式匹配
        for pattern_str, code in COMMAND_PATTERNS.items():
            try:
                pattern = re.compile(pattern_str)
                for match in pattern.finditer(text):
                    matches.append(KeywordMatch(
                        keyword=pattern_str,
                        code=code,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        confidence=1.0
                    ))
            except Exception as e:
                logger.warning(f"正则表达式匹配失败 {pattern_str}: {e}")
        
        # 按位置排序
        matches.sort(key=lambda x: x.start_pos)
        return matches

# 全局分析器实例
_analyzer = KeywordAnalyzer()

def analyze_keywords(text: str) -> Dict:
    """分析文本中的指令关键字 - 修复版本"""
    if not text or not text.strip():
        return {
            "is_command": False,
            "confidence": 0.0,
            "matched_keywords": [],
            "status_codes": [],
            "primary_status": 0,
            "normalized_text": "",
            "original_text": text
        }
    
    try:
        # 文本预处理（简化）
        normalized_text = _analyzer.normalize_text(text)
        expanded_text = _analyzer.expand_synonyms(normalized_text)
        
        # 查找匹配
        matches = _analyzer.find_keyword_matches(expanded_text)
        
        # 计算置信度
        confidence = _analyzer.calculate_confidence(matches, expanded_text)
        is_command = confidence > 0.3  # 降低阈值
        
        # 获取状态码
        status_codes = [match.code for match in matches]
        primary_status = status_codes[0] if status_codes else 0
        
        # 转换为可序列化的格式
        matched_keywords_info = [
            {
                "keyword": match.keyword,
                "code": match.code,
                "position": f"{match.start_pos}-{match.end_pos}",
                "confidence": match.confidence
            }
            for match in matches
        ]
        
        return {
            "is_command": is_command,
            "confidence": round(confidence, 2),
            "matched_keywords": matched_keywords_info,
            "status_codes": status_codes,
            "primary_status": primary_status,
            "normalized_text": normalized_text,
            "original_text": text,
            "word_count": len(expanded_text)
        }
        
    except Exception as e:
        logger.error(f"关键词分析失败: {e}")
        return {
            "is_command": False,
            "confidence": 0.0,
            "matched_keywords": [],
            "status_codes": [],
            "primary_status": 0,
            "normalized_text": text,
            "original_text": text,
            "error": str(e)
        }

def get_keyword_statistics() -> Dict:
    """获取关键词统计信息"""
    return {
        "total_keywords": len(COMMAND_KEYWORDS),
        "total_patterns": len(COMMAND_PATTERNS),
        "keywords_list": list(COMMAND_KEYWORDS.keys()),
        "patterns_list": list(COMMAND_PATTERNS.keys()),
    }