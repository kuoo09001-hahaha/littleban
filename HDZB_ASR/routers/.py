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
    # 核心系统指令
    "关机": 1001, "重启": 1002, "开机": 1003, "关闭": 1004,
    
    # 音量控制
    "音量": 1005, "静音": 1006, "取消静音": 1007,
    "增大": 1008, "减小": 1009, "调高": 1010, "调低": 1011,
    
    # 应用控制
    "打开": 1012, "启动": 1013, "关闭应用": 1014, "退出": 1015,
    
    # 通讯指令
    "呼叫": 1016, "拨打": 1017, "打电话": 1018,
    
    # 设置指令
    "设置": 1019, "切换": 1020,
    
    # 其他指令
    "停止": 1021, "暂停": 1022, "继续": 1023,
}

# 简化并优化正则表达式模式
COMMAND_PATTERNS = {
    # 音量控制
    r"音量.*(增大|调高|增加|加大)": 1031,
    r"音量.*(减小|调低|降低|缩小)": 1032,
    r"(静音|关闭音量|音量静音)": 1033,
    r"(取消静音|打开音量)": 1034,
    
    # 通讯指令
    r"(拨打|呼叫).*电话": 1035,
    r"打电话给\S+": 1036,
    
    # 应用控制
    r"(打开|启动).*(应用|程序|软件)": 1037,
    r"(关闭|退出).*(应用|程序|软件)": 1038,
    
    # 系统控制
    r"(重启|重新启动).*(系统|设备|电脑)": 1039,
    r"(关机|关闭).*(系统|设备|电脑)": 1040,
    
    # 模式设置
    r"设置.*模式": 1041,
    r"切换.*模式": 1042,
}

class KeywordAnalyzer:
    def __init__(self):
        self._build_keyword_patterns()
    
    def _build_keyword_patterns(self):
        """构建中文友好的关键词匹配模式"""
        self.keyword_patterns = {}
        for keyword in COMMAND_KEYWORDS.keys():
            # 中文不需要单词边界，直接匹配包含关系
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
            base_confidence += 0.2
        elif word_count > 15:  # 长文本惩罚
            base_confidence -= 0.2
            
        return max(0.1, min(1.0, base_confidence))
    
    def find_keyword_matches(self, text: str) -> List[KeywordMatch]:
        """查找关键词匹配 - 修复版本"""
        matches = []
        
        # 简单关键词匹配 - 直接搜索包含关系
        for keyword, code in COMMAND_KEYWORDS.items():
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

if __name__ == "__main__":
    test_keyword_analysis()