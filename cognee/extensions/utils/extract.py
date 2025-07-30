import re
from typing import Dict, Optional


def extract_experience_years(text: str) -> Optional[Dict[str, Optional[int]]]:
    number_dict = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
        'ten': 10
    }
    for k, v in number_dict.items():
        text = text.lower().replace(k, f'{v}')
    patterns = [
        (r'minimum (\d+)\s+months?', lambda m: {"low": int(m.group(1)) / 12, "high": None, "is_plus": True,}),
        (r'at least (\d+) months?', lambda m: {"low": int(m.group(1)), "high": None, "is_plus": True}),
        (r'(\d+)\s+to\s+(\d+)\s+months?', lambda m: {"low": int(m.group(1)) / 12, "high": int(m.group(2)) / 12, "is_plus": False, }),
        # 匹配 "X+ years" 模式
        (r'(\d+)\+ years?', lambda m: {"low": int(m.group(1)), "high": None, "is_plus": True}),
        # 匹配 "Minimum of X years" 模式（新增）
        (r'minimum of (\d+) years?', lambda m: {"low": int(m.group(1)), "high": None, "is_plus": True}),
        # 匹配 "X or more years" 模式
        (r'(\d+)\s+or more years?', lambda m: {"low": int(m.group(1)), "high": None, "is_plus": True}),
        (r'at least (\d+) years?', lambda m: {"low": int(m.group(1)), "high": None, "is_plus": True}),
        (r'over (\d+) years?', lambda m: {"low": int(m.group(1)), "high": None, "is_plus": True}),
        # 匹配 "X-Y+ years" 模式
        (r'(\d+)\s*-\s*(\d+)\+\s+years?', lambda m: {"low": int(m.group(1)), "high": int(m.group(2)), "is_plus": True}),

        # 匹配 "X to Y years" 或 "X-Y years" 模式
        (r'(\d+)\s*(?:to|-)\s*(\d+)\s+years?',
         lambda m: {"low": int(m.group(1)), "high": int(m.group(2)), "is_plus": False}),
        # 匹配 "X years" 模式
        (r'(\d+)\s+years?', lambda m: {"low": int(m.group(1)), "high": int(m.group(1)), "is_plus": False}),
        # 匹配 "minimum X years" 模式
        (r'minimum\s+(\d+)\s+years?', lambda m: {"low": int(m.group(1)), "high": None, "is_plus": False}),
        # 匹配 "between X and Y years" 模式
        (r'between\s+(\d+)\s+and\s+(\d+)\s+years?',
         lambda m: {"low": int(m.group(1)), "high": int(m.group(2)), "is_plus": False}),
    ]
    for pattern, handler in patterns:
        match = re.search(pattern, text.lower(), re.IGNORECASE)
        if match:
            return handler(match)
    return None
